# Migration: Google Chat → Slack

This document describes the adapter pivot performed on FeatureBot. **No LangGraph business logic was rewritten.**

## What changed

| Area | Before | After |
|------|--------|-------|
| Chat platform | Google Chat + service account JSON | Slack Events API + bot token |
| Inbound webhook | `POST /chat-webhook` | `POST /slack/events` |
| Outbound messages | `chat_client.py` (Google API) | `SlackPlatform` via `notifier.py` |
| Event shape | Raw Google JSON in `main.py` | `IncomingMessage` dataclass |
| Auth | Google verification token | Slack HMAC signature + timestamp |
| Credentials | `GOOGLE_*`, `service_account.json` | `SLACK_*` env vars |

## What did NOT change

- LangGraph graph, nodes, edges, router
- `IssueState` lifecycle (extended with `channel_id`, `thread_ts`, `platform`)
- GitHub client and webhook handling
- Email (Resend) integration
- Database layer (SQLite local / Supabase prod)
- Groq LLM prompts and parsing logic

## New adapter layout

```
app/adapters/interfaces.py   ← ChatPlatform contract
app/adapters/slack/          ← Slack-only code lives here
app/services/notifier.py     ← Nodes call this (platform-agnostic)
app/services/message_handler.py
```

## thread_id format

LangGraph checkpoint keys changed from Google Chat thread names to:

```
slack:{workspace_id}:{channel_id}:{thread_ts}
```

Existing SQLite checkpoints from Google Chat will not migrate automatically. Start fresh or re-link threads.

## Environment migration

Remove from `.env`:

```
GOOGLE_SERVICE_ACCOUNT_FILE
GOOGLE_CHAT_VERIFICATION_TOKEN
```

Add:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_CLIENT_ID=...          # optional OAuth
SLACK_CLIENT_SECRET=...
SLACK_REDIRECT_URI=https://<host>/slack/oauth/callback
```

## Slack console migration checklist

1. Create Slack app at api.slack.com
2. Configure Event Subscriptions → `/slack/events`
3. Add bot scopes (see README)
4. Install to workspace → copy bot token
5. Update GitHub webhook URL if host changed
6. Remove Google Chat app configuration (no longer needed)

## Adding Google Chat or Teams later

1. Create `app/adapters/google_chat/` or `app/adapters/teams/`
2. Implement `ChatPlatform` + normalizer for that platform's webhook
3. Register routes in `main.py`
4. Call `set_chat_platform()` for the active deployment

LangGraph and nodes require **zero changes**.
