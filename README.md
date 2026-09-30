<div align="center">

# 🎨 Pollinations API

**Free AI chat & image generation — one clean HTTP API.**

[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-000000?style=for-the-badge&logo=vercel)](https://vercel.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-00C853?style=for-the-badge)](LICENSE)

*Powered by [pollinations.ai](https://pollinations.ai) — no account, no token, no sign-up needed upstream.*

[Features](#-features) • [Quick Start](#-quick-start) • [API Reference](#-api-reference) • [Deployment](#-deployment) • [License](#-license)

</div>

---

## ✨ Features

| | |
|---|---|
| 💬 **AI Chat** | Conversational AI with full history support |
| 🎨 **Image Generation** | Text-to-image via `flux` and more models |
| 🔑 **Key Guard** | `x-api-key` header + per-key rate limiting |
| ⚡ **Serverless** | One-click deploy to Vercel — zero config |
| 🐍 **Standalone Client** | Use `core/` directly, no Flask required |

---

## 🚀 Quick Start

```bash
# 💬 Chat
curl -X POST https://<your-project>.vercel.app/chat \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"message": "Write a haiku about the ocean"}'

# 🎨 Image
curl -X POST https://<your-project>.vercel.app/image \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"prompt": "a cat astronaut", "width": 512, "height": 512}' \
  -o cat.png
```

> Replace `<your-project>` with your Vercel deployment URL and `<redacted> with your API key.

---

## 📖 API Reference

All endpoints except `/` require the `x-api-key` header.

### Endpoints

| Method | Path | Description |
|:------:|------|-------------|
| `GET` | `/` | Service info & endpoint list |
| `GET` `POST` | `/chat` | Chat completion |
| `GET` `POST` | `/image` | Image generation |
| `GET` | `/models` | Available text models |

### 💬 Chat — `POST /chat`

```jsonc
{
  "message": "Hello!",          // required
  "model": "openai",            // optional, default "openai"
  "history": [                  // optional, for multi-turn conversations
    { "role": "user", "content": "Hi" },
    { "role": "assistant", "content": "Hello!" }
  ]
}
```

<details>
<summary><b>GET alternative</b></summary>

```
/chat?message=Hello!&model=openai
```

Pass `history` as a JSON-encoded query parameter for multi-turn chats.

</details>

**Response**

```jsonc
{
  "response": "Hi there! How can I help?",
  "model": "gpt-oss-20b",
  "history": [ /* updated conversation */ ]
}
```

### 🎨 Image — `POST /image`

```jsonc
{
  "prompt": "a cat astronaut",  // required
  "width": 1024,               // optional, 64–2048, default 1024
  "height": 1024,              // optional, 64–2048, default 1024
  "model": "flux",             // optional, default "flux"
  "seed": 42,                  // optional, for reproducible results
  "nologo": true,              // optional, default true
  "format": "url"              // optional — return JSON instead of bytes
}
```

**Response (default):** raw image bytes (`image/jpeg`).

**Response (`format: "url"`):**

```jsonc
{
  "image_url": "https://image.pollinations.ai/prompt/...",
  "content_type": "image/jpeg"
}
```

<details>
<summary><b>More examples</b></summary>

```bash
# GET image
curl 'https://<your-project>.vercel.app/image?prompt=a%20sunset&width=512' \
  -H 'x-api-key: <redacted> -o sunset.png

# Image as URL (no bytes proxied)
curl -X POST https://<your-project>.vercel.app/image \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: <redacted> \
  -d '{"prompt": "a cat astronaut", "format": "url"}'

# Available models
curl https://<your-project>.vercel.app/models \
  -H 'x-api-key: <redacted>
```

</details>

### ⚠️ Rate limits

| Limit | Value |
|-------|-------|
| Per-key | 30 requests / 60 seconds |
| Upstream burst | HTTP `429` if pollinations throttles anonymous traffic |

---

## 🛠️ Deployment

### Vercel CLI

```bash
git clone https://github.com/MR-RAHAD/pollinations-api.git
cd pollinations-api
vercel          # link / create project
vercel --prod   # deploy
```

### GitHub Import

1. Fork or push this repo to GitHub
2. Vercel → **Add New** → **Project** → **Import** the repo
3. Deploy — no build settings needed ✨

### 🔧 Environment variables

| Variable | Required | Default | Description |
|----------|:--------:|:-------:|-------------|
| `API_KEY` | No | — | Your own guard key (added to the allowed list) |
| `POLL_RATE_LIMIT` | No | `30` | Max requests per key per window |
| `POLL_RATE_WINDOW_SECONDS` | No | `60` | Rate-limit window in seconds |

Set them in **Vercel → Project → Settings → Environment Variables**, then redeploy.

---

## 📁 Project structure

```
pollinations-api/
├── api/
│   └── index.py                 # Flask app — routes, key guard, rate limiting
├── core/
│   └── core/
│       ├── __init__.py
│       └── pollinations.py      # Upstream client — chat + image
├── vercel.json                  # Serverless function config
├── requirements.txt
├── LICENSE
└── README.md
```

### 🐍 Standalone usage

The `core/` client works without Flask:

```python
from core.core.pollinations import PollinationsClient

client = PollinationsClient()

# Chat
print(client.ask("Tell me a joke")["response"])

# Image
img = client.image("a sunset over mountains", width=1024, height=1024)
open("sunset.jpg", "wb").write(img["content"])
```

---

## 📝 Notes

- Upstream ([pollinations.ai](https://pollinations.ai)) is **free and anonymous** — no account needed.
- Default text model: `openai` · Default image model: `flux`.
- If pollinations.ai changes its endpoints, update `core/core/pollinations.py` from the live site.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

<div align="center">

**Built with ❤️ by [Mohammad Rahad](https://github.com/MR-RAHAD)**

</div>
