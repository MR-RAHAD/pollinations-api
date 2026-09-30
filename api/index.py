"""pollinations-api — HTTP wrapper around pollinations.ai (free, no auth upstream).

Deployed on Vercel as a Python serverless function (Flask auto-detected).
Stateless: the caller passes conversation history with each request.

Endpoints:
  POST /chat   {"message": str, "model": "openai", "history": [...]}
  POST /image  {"prompt": str, "width": 1024, "height": 1024,
                "model": "flux", "seed": 42, "nologo": true}
               → returns the image bytes directly (or ?format=url for JSON)
  GET  /models → upstream text model list
"""

import os
import sys
import time

from flask import Flask, Response, jsonify, request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))
from core import PollinationsClient, PollinationsError  # noqa: E402

app = Flask(__name__)

# Built-in API keys (also accepts the API_KEY env var if set).
API_KEYS = {"rahad", "rahad1", "rahad2"}

# Simple per-key rate limit: 30 requests / 60s (in-memory, best-effort).
RATE_LIMIT = int(os.getenv("POLL_RATE_LIMIT", "30"))
RATE_WINDOW = int(os.getenv("POLL_RATE_WINDOW_SECONDS", "60"))
_hits: dict = {}


def _check_api_key():
    """Guard: the x-api-key header must match a built-in key or API_KEY env."""
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
        "upstream": "pollinations.ai (free, no key)",
        "endpoints": {
            "/chat": "POST {message, model?, history?}",
            "/image": "POST {prompt, width?, height?, model?, seed?, nologo?}",
            "/models": "GET",
        },
    })


@app.post("/chat")
def chat():
    denied = _check_api_key()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "missing 'message' in JSON body"}), 400

    history = data.get("history") or []
    if not isinstance(history, list):
        return jsonify({"error": "'history' must be a list of {role, content}"}), 400
    model = (data.get("model") or "openai").strip() or "openai"

    client = PollinationsClient()
    try:
        result = client.ask(message, model=model, history=history)
    except PollinationsError as e:
        # Upstream anonymous quota hit -> tell the caller to back off.
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
    # Also accept GET query params for convenience.
    q = request.args
    prompt = (data.get("prompt") or q.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "missing 'prompt'"}), 400

    def _param(name, default):
        v = data.get(name, q.get(name, default))
        return v

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


# Vercel exposes `app`; local dev can run this file directly.
if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 3000)))
