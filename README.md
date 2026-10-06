# Mayfly

Ephemeral one-page websites. People describe what they want in a chat,
pick how long the site lives, and get a link. When time runs out, the site
evaporates.

Live at **https://trymayfly.com** — start an order at **/start**.

## How it works

- **Chat intake** (`/start`) — conversational order flow (Nova persona) on
  Cloudflare Workers AI. Collects each theme's required facts deterministically,
  asks for photos every time, and closes with duration + email.
- **Worker** (`worker/mayfly-router.js`) — serves the landing page, the chat
  page, and the intake API; publishes subdomains from KV; runs moderation
  (Llama Guard + house-policy classifier + vision screening on uploads).
- **Themes** (`site/themes/`) — eight one-page themes: celebrate, invite,
  announce, sell, remember, rally, inform, play. Shared interactive widget
  block injected by `scripts/inject-widgets.py`.
- **Orders** land in KV (`order:<sessionId>`, `orders:pending`) for human
  review and build. Nothing publishes without a human building it.

## Pricing

Free 24h · $1 / 2 days · $1.50 / 7 days (most popular) · $5 / month · $50 / year.

## Layout

- `worker/` — the Cloudflare Worker (router, intake API, moderation)
- `site/` — landing page, chat page, themes
- `scripts/` — site publisher (`build-site.py`), widget injector, example pinner
- `examples/` — the eight permanent demo sites' vars + photos
- `demos/` — archived demo builds
- `hidden_files/` — ops playbook (internal)

## Secrets

`hidden_files/mayfly.env` holds the admin token and is **never committed**.
Copy it locally from secure storage; it is git-ignored.
