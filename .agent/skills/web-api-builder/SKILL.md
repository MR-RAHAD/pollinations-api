---
name: "web-api-builder"
description: "Build an unofficial HTTP API project from an AI chat website: reverse-engineer the web client, handle auth/challenges, wrap in a serverless Flask app, deploy to Vercel. Use when the user asks to make an API from a website like grok.com, kimi, phind, deepseek, duck.ai."
---

# Web API Builder

Methodology distilled from five shipped projects: `worm-ai` (Grok), `kimi-api`,
`phind-api`, `deepseek-api`, `ddg-ai-api`. Each follows the same architecture
and the same four-phase workflow.

## Standard Project Layout

```
<name>-api/
  api/index.py        # Flask app, serverless entry (Vercel routes /api/* here)
  core/core/<svc>.py  # the web client: auth, chat, streaming, retries
  core/core/__init__.py
  vercel.json         # {"functions":{"api/index.py":{"maxDuration":60}}}
  requirements.txt    # flask, curl_cffi, beautifulsoup4, ... (no browser deps)
  README.md           # English, curl examples, deploy steps
  tests/              # optional: live smoke tests (never commit secrets)
```

**Rules:**
- `api/index.py` is thin: parse request → call `core` client → return JSON.
  Never put site-specific logic here.
- `core/` holds 100% of the reverse-engineered protocol. It must work as a
  standalone CLI first (`python -m core.client "hi"`) before the Flask
  wrapper exists.
- Auth secrets come from **environment variables only** (`os.environ`), never
  from files — the serverless filesystem is ephemeral. Exception: a token file
  may be *read* as a fallback for local dev, but Vercel uses env vars.
- Never commit real tokens/keys to the repo. The GitHub repos for these
  projects are private for exactly this reason.

## Phase 1 — Recon (browser devtools)

1. Open the site in the real browser (`browser.spawn_task`), open DevTools →
   Network, send one chat message.
2. Capture: the chat POST URL, method, request headers (auth headers, cookies,
   device-signature headers), request JSON shape, and the streaming response
   format (SSE `data:` lines? custom framing? plain JSON?).
3. Identify the auth model:
   - **None** (phind) → simplest, go straight to prototype.
   - **Bearer token / cookies from login** (kimi, deepseek) → extract once
     from the browser session; plan a refresh flow.
   - **Proof-of-work** (deepseek: WASM PoW) → find the WASM file, plan a
     local solver (wasmtime).
   - **JS challenge** (duck.ai: `X-Vqd-Hash-1`) → find the challenge JS,
     re-implement the solver in Node/Python.
   - **Request signer from JS bundle** (grok: signer byte positions in a
     Turbopack chunk) → locate the module, extract positions, verify against
     a live request before trusting them.
   - **Device fingerprint SDK** (qwen: Alibaba Baxia `x5secdata`) →
     **STOP.** If the signature requires a proprietary, obfuscated,
     browser-only SDK with server-side risk scoring, the site is not
     feasible as a bare-HTTP API. Document and skip.
4. Note the failure modes: what does a bad/expired auth look like (401? 403?
   captcha redirect? punish flow?). You need these to distinguish "auth
   died" from "site changed" later.

## Phase 2 — Prototype the core client

Use `curl_cffi` with `impersonate="chrome136"` (or current) — plain
`requests` gets TLS-fingerprinted and blocked by most of these sites.

```python
from curl_cffi import requests
r = requests.post(url, json=payload, headers=headers,
                  impersonate="chrome136", timeout=(10, 30))
```

- Reproduce the exact header set from DevTools first, then trim
  headers one by one to find the minimal required set.
- Parse the stream incrementally; accumulate `response_text`.
- Timeouts: **never** use a huge/connect-only timeout. Use
  `timeout=(connect, read)` e.g. `(10, 30)` so a stalled stream fails
  fast instead of hanging until the platform kills the function.
  (Lesson from worm-ai: `timeout=9999` caused silent hangs.)
- Prove it with a real prompt: `ask("Reply with exactly: ok")` must return
  `"ok"`. An HTTP 200 alone proves nothing — require a genuine non-empty
  model answer.

## Phase 3 — Harden

Apply as needed, per site:

- **Handshake caching** (grok): the site handshake (challenge keys, bundle
  parse) is expensive; cache it module-level ~5 min, but re-run the
  per-conversation challenge fresh every time.
- **Signer discovery with committed fallback** (grok): sites rotate JS
  bundles often. Discover positions live, but commit the last-known-good
  positions as fallback — cold-start discovery (~35s) is too slow for
  serverless timeouts.
- **Retry with fresh state** (grok): on *any* exception, clear cached
  handshake/parser state, build a fresh client, retry once. Intermittent
  upstream bot-checks/partial pages cause fast 502s; the retry absorbs
  them. Never silently hang — raise a clear error after retries exhaust.
- **Token refresh** (kimi): access token auto-refreshes per request from
  the env refresh token; rotated pairs are lost on cold start by design —
  the next request just refreshes again.
- **Keep-alive cron** (kimi): some tokens die if idle; a 30-min cron
  hitting a cheap endpoint keeps them alive. Warn (don't silently fail)
  on `EXPIRING`/`FAIL`, stay silent on `OK`.
- **PoW solver** (deepseek): ship the WASM + a local solver; note platform
  limits (e.g. Termux/Android lacks the wasmtime native lib).
- **Challenge solver** (duck.ai): re-implement in Node (jsdom+vm if the
  challenge needs DOM); pin the frontend version constants and expect to
  update them when the site changes.
- **Rate limiting**: enforce per-API-key server-side (`X req / Y sec`);
  default conservatively (2/60s for paid buyer keys).

## Phase 4 — Ship

1. `vercel.json` with `maxDuration` (60s default; 300s only if the site
   genuinely needs it and the plan allows).
2. Push to a **private** GitHub repo (`main` branch) via
   `~/workspace/skills/github/bin/github_file.py`. Vercel auto-deploys
   from there. (Note: that helper had a 404 bug — contents API URLs need
   `/contents/` in the path; fixed 2026-09-29. If pushes 404, check
   that first.)
3. Set env vars (tokens, API keys) in the Vercel dashboard, redeploy.
4. Verify the **deployed** URL with a genuine-answer test, not just
   HTTP 200. Test 5–8 sequential requests; report success rate and
   timing honestly — one clean batch does not prove reliability.
5. README: English, badges, curl examples with the real endpoint shape,
   deploy steps. (User boundary: when editing their README, only add
   the newly added items — never redesign.)

## Feasibility Quick-Rank (from experience)

- **Easy:** no-auth sites (phind, pollinations.ai), simple header/challenge
  sites (duck.ai).
- **Medium:** login-token sites with refresh (kimi), PoW sites (deepseek),
  bundle-signer sites (grok) — workable but need ongoing maintenance when
  the site changes its JS.
- **Skip:** device-fingerprint SDK sites (qwen/Baxia) — no reliable
  bare-HTTP path; datacenter IPs are risk-denied.

## Operating Rules

1. `core/` must work standalone before any Flask/Vercel code exists.
2. HTTP 200 ≠ success. Require a genuine non-empty model answer in
   every verification.
3. Never expose tokens, keys, cookies, or signatures in chat, logs,
   or committed files.
4. When the upstream site changes its JS/bundle, re-derive from the live
   bundle — never guess positions, versions, or signatures.
5. `curl_cffi` + `impersonate` is mandatory; plain `requests` will be
   fingerprinted.
6. Keep `api/index.py` thin; all protocol knowledge lives in `core/`.
