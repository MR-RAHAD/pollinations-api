import os
import sys
import time
import json

from flask import Flask, Response, jsonify, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))
from core import PollinationsClient, PollinationsError  # noqa: E402

app = Flask(__name__)
app.json.ensure_ascii = False

API_KEYS = {"rahad", "rahad1", "rahad2"}

RATE_LIMIT = int(os.getenv("POLL_RATE_LIMIT", "30"))
RATE_WINDOW = int(os.getenv("POLL_RATE_WINDOW_SECONDS", "60"))
_hits: dict = {}


def _load_system_prompt():
    path = os.path.join(os.path.dirname(__file__), "..", "system prompt.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


DEFAULT_SYSTEM_PROMPT = (
    "তুমি একজন সহনশীল ও প্রাণবন্ত নারী এআই সহকারী। "
    "ব্যবহারকারীকে একজন পুরুষ হিসেবে বিবেচনা করে সেভাবে ব্যাকরণ ও সম্বোধন প্রয়োগ করবে।\n"
    "ভাষাগত নিয়ম: ব্যবহারকারী যে ভাষাতেই লিখুক না কেন, "
    "তোমার প্রতিটি উত্তর হতে হবে শুধুমাত্র বাংলায়।\n"
    "ইমোজির ব্যবহার: কথার ভাবাবেগ ও প্রসঙ্গের সাথে মিল রেখে "
    "প্রতিটি বার্তার শেষে বা মাঝে উপযুক্ত ইমোজি যোগ করবে। 😊💬"
)

SYSTEM_PROMPT = (
    os.getenv("SYSTEM_PROMPT", "").strip()
    or _load_system_prompt()
    or DEFAULT_SYSTEM_PROMPT
)


def _check_api_key():
    allowed = set(API_KEYS)
    extra = os.environ.get("API_KEY", "").strip()
    if extra:
        allowed.add(extra)
    key = request.headers.get("x-api-key", "")
    if key not in allowed:
        return jsonify({"error": "unauthorized"}), 401
    now = time.time()
    bucket = _hits.setdefault(key, [])
    while bucket and bucket[0] <= now - RATE_WINDOW:
        bucket.pop(0)
    if len(bucket) >= RATE_LIMIT:
        return jsonify({"error": "rate limited, try again later"}), 429
    bucket.append(now)
    return None


@app.get("/")
def index():
    return jsonify({
        "service": "pollinations-api",
        "status": "ok",
        "upstream": "pollinations.ai",
        "endpoints": {
            "/chat": "GET/POST {message, model?, history?, system_prompt?}",
            "/image": "GET/POST {prompt, width?, height?, model?, seed?, nologo?, format?}",
            "/models": "GET",
        },
    })


@app.post("/chat")
def chat_post():
    denied = _check_api_key()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    return _do_chat(
        message=(data.get("message") or "").strip(),
        history=data.get("history") or [],
        model=(data.get("model") or "openai").strip() or "openai",
        system_prompt=(data.get("system_prompt") or "").strip() or None,
    )


@app.get("/chat")
def chat_get():
    denied = _check_api_key()
    if denied:
        return denied
    q = request.args
    history = []
    raw_history = (q.get("history") or "").strip()
    if raw_history:
        try:
            history = json.loads(raw_history)
        except (ValueError, TypeError):
            return jsonify({"error": "'history' must be a JSON array string"}), 400
    return _do_chat(
        message=(q.get("message") or "").strip(),
        history=history,
        model=(q.get("model") or "openai").strip() or "openai",
        system_prompt=(q.get("system_prompt") or "").strip() or None,
    )


def _do_chat(message, history, model, system_prompt=None):
    if not message:
        return jsonify({"error": "missing 'message'"}), 400

    if not isinstance(history, list):
        return jsonify({"error": "'history' must be a list of {role, content}"}), 400

    client = PollinationsClient()
    try:
        result = client.ask(message, model=model, history=history,
                            system_prompt=system_prompt or SYSTEM_PROMPT)
    except PollinationsError as e:
        status = 429 if "402" in str(e) else 502
        return jsonify({"error": str(e)}), status

    return jsonify({
        "response": result["response"],
        "model": result["model"],
        "history": [
            *[{"role": h.get("role"), "content": h.get("content")}
              for h in history[-9:]
              if isinstance(h, dict) and h.get("role") and h.get("content")],
            {"role": "user", "content": message},
            {"role": "assistant", "content": result["response"]},
        ],
    })


@app.post("/image")
def image():
    denied = _check_api_key()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    q = request.args
    prompt = (data.get("prompt") or q.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "missing 'prompt'"}), 400

    def _param(name, default):
        return data.get(name, q.get(name, default))

    client = PollinationsClient()
    try:
        result = client.image(
            prompt,
            width=int(_param("width", 1024)),
            height=int(_param("height", 1024)),
            model=str(_param("model", "flux")),
            seed=int(_param("seed")) if _param("seed", None) is not None else None,
            nologo=str(_param("nologo", "true")).lower() != "false",
        )
    except (PollinationsError, ValueError) as e:
        status = 429 if "402" in str(e) else 502
        return jsonify({"error": str(e)}), status

    if (data.get("format") or q.get("format") or "") == "url":
        return jsonify({"image_url": result["url"],
                        "content_type": result["content_type"]})
    return Response(result["content"], mimetype=result["content_type"])


@app.get("/image")
def image_get():
    return image()


@app.get("/models")
def models():
    denied = _check_api_key()
    if denied:
        return denied
    try:
        return jsonify({"models": PollinationsClient().models()})
    except PollinationsError as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 3000)))
