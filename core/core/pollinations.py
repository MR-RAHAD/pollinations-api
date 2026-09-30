"""Unofficial pollinations.ai API client.

Pollinations exposes OPEN endpoints - no login, no token, no PoW, no signing:

  Text (OpenAI-compatible, SSE streaming supported):
    POST https://text.pollinations.ai/openai
    {"model": "openai", "messages": [{"role": "user", "content": "..."}],
     "stream": false}

  Text (simple GET):
    GET https://text.pollinations.ai/<url-encoded prompt>?model=openai

  Image:
    GET https://image.pollinations.ai/prompt/<url-encoded prompt>
        ?width=1024&height=1024&model=flux&nologo=true&seed=42

This client uses the OpenAI-compatible POST for chat (supports history and
model selection) and the GET image endpoint for generation.
"""

from urllib.parse import quote

from curl_cffi import requests

TEXT_BASE = "https://text.pollinations.ai"
IMAGE_BASE = "https://image.pollinations.ai"

OPENAI_PATH = "/openai"
MODELS_PATH = "/models"

DEFAULT_TEXT_MODEL = "openai"   # alias for the default reasoning model
DEFAULT_IMAGE_MODEL = "flux"

# (connect, read) - never hang: a stalled upstream must fail fast.
TIMEOUT = (10, 30)
IMAGE_TIMEOUT = (10, 60)  # image gen can take longer than text

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://pollinations.ai",
    "Referer": "https://pollinations.ai/",
}


class PollinationsError(Exception):
    pass


class PollinationsClient:
    """Minimal client for pollinations.ai text + image endpoints."""

    def __init__(self, timeout=TIMEOUT) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)

    # ---- text / chat ----

    def ask(self, message: str, model: str = DEFAULT_TEXT_MODEL,
            history: list | None = None, stream: bool = False) -> dict:
        """Send a chat message.

        history: optional [{"role": "user"|"assistant", "content": str}]
        stream: if True, returns {"chunks": generator}; else {"response": str}

        Returns {"response": str, "model": str} (non-streaming).
        """
        message = (message or "").strip()
        if not message:
            raise PollinationsError("empty message")

        messages = []
        for h in (history or [])[-10:]:
            if isinstance(h, dict) and h.get("role") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        payload = {"model": model or DEFAULT_TEXT_MODEL,
                   "messages": messages, "stream": stream}
        try:
            resp = self.session.post(
                TEXT_BASE + OPENAI_PATH, json=payload,
                impersonate="chrome136", timeout=self.timeout,
                stream=stream,
            )
        except Exception as e:
            raise PollinationsError(f"text request failed: {e}") from e

        if resp.status_code != 200:
            if resp.status_code == 402:
                raise PollinationsError(
                    "pollinations anonymous quota exceeded (HTTP 402) - "
                    "back off ~60s or use a paid tier key")
            raise PollinationsError(
                f"text API HTTP {resp.status_code}: {resp.text[:200]}")

        if stream:
            return {"chunks": self._iter_chunks(resp), "model": model}

        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
        except Exception as e:
            raise PollinationsError(f"bad text response: {e}") from e
        if not text or not text.strip():
            raise PollinationsError("empty text response from pollinations")
        return {"response": text.strip(), "model": data.get("model", model)}

    def _iter_chunks(self, resp):
        """Yield content deltas from an SSE stream."""
        for line in resp.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", "replace")
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                import json
                delta = json.loads(payload)["choices"][0]["delta"]
                content = delta.get("content")
            except Exception:
                continue
            if content:
                yield content

    def ask_simple(self, prompt: str, model: str = DEFAULT_TEXT_MODEL) -> dict:
        """One-shot GET text endpoint (no history)."""
        prompt = (prompt or "").strip()
        if not prompt:
            raise PollinationsError("empty prompt")
        url = f"{TEXT_BASE}/{quote(prompt)}?model={quote(model)}"
        try:
            resp = self.session.get(url, impersonate="chrome136",
                                    timeout=self.timeout)
        except Exception as e:
            raise PollinationsError(f"text GET failed: {e}") from e
        if resp.status_code != 200:
            if resp.status_code == 402:
                raise PollinationsError(
                    "pollinations anonymous quota exceeded (HTTP 402) - "
                    "back off ~60s or use a paid tier key")
            raise PollinationsError(
                f"text GET HTTP {resp.status_code}: {resp.text[:200]}")
        text = resp.text.strip()
        if not text:
            raise PollinationsError("empty text response from pollinations")
        return {"response": text, "model": model}

    def models(self) -> list:
        """List available text models."""
        try:
            resp = self.session.get(TEXT_BASE + MODELS_PATH,
                                    impersonate="chrome136",
                                    timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise PollinationsError(f"models request failed: {e}") from e

    # ---- image ----

    def image(self, prompt: str, width: int = 1024, height: int = 1024,
              model: str = DEFAULT_IMAGE_MODEL, seed: int | None = None,
              nologo: bool = True) -> dict:
        """Generate an image.

        Returns {"content": bytes, "content_type": str, "url": str}.
        Raises PollinationsError on failure or non-image response.
        """
        prompt = (prompt or "").strip()
        if not prompt:
            raise PollinationsError("empty image prompt")
        width = max(64, min(int(width or 1024), 2048))
        height = max(64, min(int(height or 1024), 2048))

        params = [f"width={width}", f"height={height}",
                  f"model={quote(model or DEFAULT_IMAGE_MODEL)}",
                  f"nologo={'true' if nologo else 'false'}"]
        if seed is not None:
            params.append(f"seed={int(seed)}")
        url = f"{IMAGE_BASE}/prompt/{quote(prompt)}?{'&'.join(params)}"

        try:
            resp = self.session.get(url, impersonate="chrome136",
                                    timeout=IMAGE_TIMEOUT)
        except Exception as e:
            raise PollinationsError(f"image request failed: {e}") from e
        if resp.status_code != 200:
            if resp.status_code == 402:
                raise PollinationsError(
                    "pollinations anonymous quota exceeded (HTTP 402) - "
                    "back off ~60s or use a paid tier key")
            raise PollinationsError(
                f"image API HTTP {resp.status_code}: {resp.text[:200]}")
        ctype = resp.headers.get("content-type", "")
        if not ctype.startswith("image/"):
            raise PollinationsError(
                f"expected image, got {ctype}: {resp.text[:200]}")
        if len(resp.content) < 1024:
            raise PollinationsError("image response too small, likely an error")
        return {"content": resp.content, "content_type": ctype, "url": url}
