# Slack app setup checklist

Platform Slack app (one app, many workspaces via install store). Laptop-as-VPS + tunnel.

Related: `docs/tunnel-plan.md`

## 1. Create the app

1. Open [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → From scratch.
2. Name e.g. `Client Slack AI Agents` → pick any workspace for development.
3. Copy credentials into root `.env`:
   - **Client ID** → `SLACK_CLIENT_ID`
   - **Client Secret** → `SLACK_CLIENT_SECRET`
   - **Signing Secret** (Basic Information) → `SLACK_SIGNING_SECRET`

## 2. Public base URL (tunnel)

```bash
# API on :8000
cloudflared tunnel --url http://localhost:8000
# or: ngrok http 8000
```

Set in `.env`:

```
PUBLIC_BASE_URL=https://<your-tunnel-host>
```

Restart uvicorn after changing env (or avoid cached settings in long-lived process).

## 3. Event Subscriptions

| Setting | Value |
| ------- | ----- |
| Enable Events | On |
| Request URL | `{PUBLIC_BASE_URL}/slack/events` |

Slack sends a `url_verification` challenge; the API must respond with the `challenge` string (Task 4.2).

### Subscribe to bot events

| Event | Why |
| ----- | --- |
| `app_mention` | @mention in channels (mentions-only) |
| `message.im` | Direct messages to the bot |

Optional later (history sync / private channels): `message.channels`, `message.groups`, `member_joined_channel`.

## 4. OAuth & Permissions

### Redirect URL

```
{PUBLIC_BASE_URL}/slack/oauth/callback
```

### Bot Token Scopes (echo + live history sync)

| Scope | Why |
| ----- | --- |
| `app_mentions:read` | Receive @mentions |
| `chat:write` | Post grounded agent replies |
| `im:history` | Read DM context |
| `im:read` | DM events |
| `im:write` | Open/reply in DMs |
| `team:read` | Workspace metadata on install |
| `channels:read` | List public channels (`conversations.list`) |
| `channels:history` | Pull public channel messages |
| `groups:read` | List private channels the bot is in |
| `groups:history` | Pull private channel messages |
| `files:read` | Download Slack attachments (Sprint 23 file actions) |
| `files:write` | Upload PDF deliverables / `files.edit` title (Sprint 23 rename) |
| `users:read` | Resolve user display names (optional later) |

If the app was installed before these scopes were added, **reinstall** via `/slack/install?tenant_id=…` so the bot token picks them up. Update the same scopes in the Slack app **OAuth & Permissions** UI.

Sprint 23 detail: `docs/slack-file-actions.md`.

### Install entry (our API)

Org portal: sign in → **Slack** → **Connect Slack** (`/app/slack`), which opens:

```
{PUBLIC_BASE_URL}/slack/install?tenant_id=<session-tenant-uuid>
```

CLI/demo can open the same link directly while API + tunnel are running. OAuth `state` carries `tenant_id` → install row maps `team_id` → `client_id` (`tenants.id`). After success, the browser returns to `{WEB_APP_URL}/app/slack?connected=1`.

Status API: `GET /slack/connection` (JWT) returns connected flag, team, and `install_url`.

## 5. App Home / Display (optional)

- Display name + icon for teammate feel.
- **Socket Mode: Off** (we use HTTP Events).

## 6. Private channels (client ops)

The bot **cannot** see or reply in a private channel until a member invites it:

```
/invite @YourBotName
```

Then @mention the bot for a grounded reply (Sprint 14). Public channels still need the bot present (invite or apps in channel). DMs work after install without a channel invite.

Not automated in MVP — org admins / teammates must invite the bot per private channel.

## 7. Verify (grounded replies — Sprint 14)

1. `docker compose up -d` + `uv run uvicorn api.app.main:app --port 8000`
2. Tunnel → `PUBLIC_BASE_URL`
3. Paste Events URL → Slack shows **Verified**
4. Install via `/slack/install?tenant_id=…` → row in `slack_installs`
5. Ensure the tenant has an **active** plan (`billing_customers.plan_status=active` with `agent` entitlement) — Stripe Checkout webhook, or local activate via billing helpers
6. Sync/upload knowledge for that tenant (Qdrant + TEI)
7. @mention in a channel (or DM the bot) → grounded answer (+ `*Sources:*` when evidence exists)
8. Try coordination asks (“status on…”, “who said…”, “summarize this thread”) → attribution/summary-style replies (still RAG-grounded)
9. Inactive plan / over token budget → clear denial message (no agent invent)

## Needs human

Operator must create the Slack app and paste secrets into `.env` (never commit). Free tunnel URLs change on restart — update Slack Request URL + Redirect URL + `PUBLIC_BASE_URL`. Live mention/DM Q&A also needs an active billing plan for the mapped tenant.
