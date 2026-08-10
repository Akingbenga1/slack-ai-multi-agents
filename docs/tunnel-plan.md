# Tunnel plan (Slack Events + public webhooks)

Used from **Sprint 4+** when Slack HTTP Events and Stripe webhooks need a public HTTPS URL pointing at this laptop-as-VPS.

## Why

Slack Events API and Stripe webhooks cannot reach `localhost`. Expose the FastAPI (and optionally Next.js) origin via a tunnel and set `PUBLIC_BASE_URL` to that HTTPS host.

## Options

| Tool | Notes |
| ---- | ----- |
| **cloudflared** (Cloudflare Tunnel) | Preferred for longer-lived demo; free quick tunnels or named tunnel with Cloudflare account |
| **ngrok** | Fastest for one-off demos; free tier rotates URLs unless reserved |

## Recommended flow (cloudflared quick tunnel)

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/).
2. With API listening on `:8000`:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
3. Copy the printed `https://*.trycloudflare.com` URL into `.env`:
   ```
   PUBLIC_BASE_URL=https://<your-tunnel-host>
   ```
4. Slack Request URL: `{PUBLIC_BASE_URL}/slack/events`
5. Slack OAuth redirect: `{PUBLIC_BASE_URL}/slack/oauth/callback`
6. Stripe webhook URL: `{PUBLIC_BASE_URL}/billing/webhooks/stripe` (Sprint 11.4)

Full Slack app checklist: `docs/slack-app-setup.md`.

## ngrok alternative

```bash
ngrok http 8000
```

Use the HTTPS forwarding URL the same way for `PUBLIC_BASE_URL`.

## Next.js

Org portal / admin can stay on `localhost:3000` for local demo. If Slack OAuth redirect or Auth.js callbacks must be public, either:

- Tunnel Next.js separately (`cloudflared tunnel --url http://localhost:3000`), or
- Put both behind one reverse proxy and tunnel that front door.

For MVP laptop demo, tunneling **API only** is enough for Events + Stripe; Auth.js can use `NEXTAUTH_URL=http://localhost:3000` until OAuth redirects require HTTPS.

## Checklist before Sprint 4

- [ ] Tunnel tool installed
- [ ] `PUBLIC_BASE_URL` set to current tunnel URL
- [ ] Slack app Event Subscriptions URL verified against tunnel
- [ ] Remember: free quick-tunnel URLs change when restarted — update Slack/Stripe and `.env`
