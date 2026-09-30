from urllib.parse import quote

from curl_cffi import requests

TEXT_BASE = "https://text.pollinations.ai"
IMAGE_BASE = "https://image.pollinations.ai"

OPENAI_PATH = "/openai"
MODELS_PATH = "/models"

DEFAULT_TEXT_MODEL = "openai"
DEFAULT_IMAGE_MODEL = "flux"

TIMEOUT = (10, 30)
IMAGE_TIMEOUT = (10, 60)

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
    def __init__(self, timeout=TIMEOUT) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)

    def ask(self, message: str, model: str = DEFAULT_TEXT_MODEL,
            history: list | None = None, stream: bool = False,
            system_prompt: str | None = None) -> dict:
        message = (message or "").strip()
        if not message:
            raise PollinationsError("empty message")

        messages = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system",
                             "content": system_prompt.strip()})
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
        try:
            resp = self.session.get(TEXT_BASE + MODELS_PATH,
                                    impersonate="chrome136",
                                    timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise PollinationsError(f"models request failed: {e}") from e

    def image(self, prompt: str, width: int = 1024, height: int = 1024,
              model: str = DEFAULT_IMAGE_MODEL, seed: int | None = None,
              nologo: bool = True) -> dict:
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
