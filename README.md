# Pollinations API

[![Deploy](https://img.shields.io/badge/deploy-vercel-black)](https://vercel.com)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A clean, key-guarded HTTP API for [pollinations.ai](https://pollinations.ai) —
**AI chat and image generation** through a single deployable service. No
upstream account or token required.

Built with Flask and deployed as a Vercel serverless function.

---

## Features

- 💬 **Chat** — conversational AI with history support (OpenAI-compatible upstream)
- 🎨 **Image generation** — text-to-image via the `flux` model (more models supported)
- 🔑 **API key guard** — `x-api-key` header + per-key rate limiting
- ⚡ **Serverless-ready** — one-click deploy to Vercel

## Endpoints

| Method    | Path      | Description                                        |
|-----------|-----------|----------------------------------------------------|
| `GET`     | `/`       | Service info and endpoint list                     |
| `GET/POST`| `/chat`   | Chat completion                                    |
| `GET/POST`| `/image`  | Image generation (bytes or JSON URL)               |
| `GET`     | `/models` | Available text models                              |

All endpoints except `/` require the `x-api-key` header.

### Chat

**POST** `/chat` — JSON body:

```json
{
  "message": "Hello!",
  "model": "openai",
  "history": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello!"}
  ]
}
```

**GET** `/chat?message=Hello!&model=openai` also works
(`history` as a JSON-encoded query param).

Response:

```json
{
  "response": "Hi there! How can I help?",
  "model": "gpt-oss-20b",
  "history": [...]
}
```

### Image

**POST** `/image` — JSON body (or **GET** with query params):

```json
{
  "prompt": "a cat astronaut",
  "width": 1024,
  "height": 1024,
  "model": "flux",
  "seed": 42,
  "nologo": true
}
```

Returns raw image bytes by default. Add `"format": "url"` (or
`?format=url`) to get JSON instead:

```json
{
  "image_url": "https://image.pollinations.ai/prompt/...",
  "content_type": "image/jpeg"
}
```

## Quick start

```bash
# Chat (POST)
curl -s -X POST https://<your-project>.vercel.app/chat \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"message": "Write a haiku about the ocean"}'

# Chat (GET)
curl -s 'https://<your-project>.vercel.app/chat?message=Hello' \
  -H 'x-api-key: <redacted>

# Image (POST → saves JPEG)
curl -s -X POST https://<your-project>.vercel.app/image \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"prompt": "a cat astronaut", "width": 512, "height": 512}' \
  -o cat.png

# Image (GET)
curl -s 'https://<your-project>.vercel.app/image?prompt=a%20cat&width=512' \
  -H 'x-api-key: <redacted> -o cat.png

# Models
curl -s https://<your-project>.vercel.app/models \
  -H 'x-api-key: <redacted>
```

## Deployment

### Option A — Vercel CLI

```bash
cd pollinations-api
vercel          # link / create project
vercel --prod   # deploy
```

### Option B — GitHub

1. Push this folder to a GitHub repo
2. Vercel → **Add New** → **Project** → **Import** the repo
3. Deploy — no build configuration needed

### Environment variables

| Variable                  | Required | Default | Description                          |
|---------------------------|----------|---------|--------------------------------------|
| `API_KEY`                 | No       | —       | Your own guard key (added to allowed keys) |
| `POLL_RATE_LIMIT`         | No       | `30`    | Max requests per key per window      |
| `POLL_RATE_WINDOW_SECONDS`| No       | `60`    | Rate-limit window in seconds         |

Set them in Vercel → Project → Settings → Environment Variables, then redeploy.

## Project structure

```
pollinations-api/
├── api/
│   └── index.py              # Flask app: routes, key guard, rate limiting
├── core/
│   └── core/
│       ├── __init__.py
│       └── pollinations.py   # Upstream client (chat + image)
├── vercel.json               # Serverless function config
├── requirements.txt
└── README.md
```

The `core/` client works standalone — no Flask needed:

```python
from core.core.pollinations import PollinationsClient

client = PollinationsClient()
print(client.ask("Hello!")["response"])
img = client.image("a sunset over mountains")
open("sunset.jpg", "wb").write(img["content"])
```

## Notes

- The upstream service is free and anonymous. The default **30 req / 60s**
  per-key limit keeps usage fair.
- Pollinations rate-limits anonymous IPs under heavy bursts (HTTP 402,
  recovers in ~60s). This API maps that to **HTTP 429** so clients can
  back off gracefully.
- Default text model: `openai`. Default image model: `flux`.
- If pollinations.ai changes its endpoints, update
  `core/core/pollinations.py` from the live site.

## License

MIT
