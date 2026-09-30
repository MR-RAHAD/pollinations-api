# pollinations-api

Free, no-login HTTP API for [pollinations.ai](https://pollinations.ai) —
**text/chat and image generation** behind one key-guarded wrapper.

Upstream needs no token or login. This project adds an `x-api-key` guard,
per-key rate limiting, and a clean JSON interface, deployed as a Vercel
Python serverless function.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | service info |
| POST | `/chat` | chat — `{"message": str, "model"?: "openai", "history"?: [{role, content}]}` |
| POST/GET | `/image` | image gen — `{"prompt": str, "width"?: 1024, "height"?: 1024, "model"?: "flux", "seed"?: int, "nologo"?: true}` → image bytes (or `format: "url"` for JSON) |
| GET | `/models` | upstream text model list |

All endpoints (except `/`) require the `x-api-key` header.

## Examples

```bash
# chat
curl -s -X POST https://<your-project>.vercel.app/chat \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"message": "Reply with exactly: ok"}'
# → {"response": "ok", "model": "gpt-oss-20b", "history": [...]}

# continue a conversation (pass back history)
curl -s -X POST https://<your-project>.vercel.app/chat \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"message": "And in French?", "history": [{"role":"user","content":"hi"},{"role":"assistant","content":"hello!"}]}'

# image generation (returns JPEG bytes)
curl -s -X POST https://<your-project>.vercel.app/image \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"prompt": "a cat astronaut", "width": 512, "height": 512}' \
  -o cat.png

# image as URL (no bytes proxied)
curl -s -X POST https://<your-project>.vercel.app/image \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"prompt": "a cat astronaut", "format": "url"}'
# → {"image_url": "https://image.pollinations.ai/prompt/...", "content_type": "image/jpeg"}

# GET also works for images
curl -s 'https://<your-project>.vercel.app/image?prompt=a%20cat' \
  -H 'x-api-key: <redacted> -o cat.png
```

## Deploy

Option A — Vercel CLI:

```bash
cd pollinations-api
vercel          # link / create project
vercel --prod   # deploy
```

Option B — GitHub: push this folder as a **private** repo, then Vercel →
Add New → Project → Import the repo.

Then in the Vercel dashboard: Project → Settings → Environment Variables →
set `API_KEY` (your own guard key; the built-ins `rahad`, `rahad1`, `rahad2`
also work) → Redeploy. Optional: `POLL_RATE_LIMIT` (default 30),
`POLL_RATE_WINDOW_SECONDS` (default 60).

## Project layout

```
api/index.py          # thin Flask app: /chat, /image, /models, key guard, rate limit
core/core/pollinations.py  # the client: OpenAI-compatible chat + image gen
vercel.json           # maxDuration 60
requirements.txt
```

## Notes

- Text model default is `openai` (alias for the current default model).
  Image model default is `flux`.
- Upstream is free and anonymous; be a good citizen — the default
  30 req / 60s per-key limit keeps abuse in check.
- **Anonymous quota:** pollinations rate-limits anonymous IPs (HTTP 402 after
  a burst of requests, recovers in ~60s). The API maps this to HTTP 429 so
  callers know to back off. Heavy/production use needs a pollinations paid
  tier key (set as upstream key in `core/` if you get one).
- If pollinations changes its endpoints, update `core/core/pollinations.py`
  from the live site — never guess URLs.
