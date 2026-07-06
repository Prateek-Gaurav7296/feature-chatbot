# FeatureBot Setup Guide (Slack)

## Credentials checklist

Run anytime:

```bash
python scripts/check_env.py
```

| Variable | Where to get it |
|----------|-----------------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → PAT (classic, `repo` scope) |
| `SLACK_BOT_TOKEN` | Slack app → OAuth & Permissions → Bot User OAuth Token (`xoxb-…`) |
| `SLACK_SIGNING_SECRET` | Slack app → Basic Information → Signing Secret |
| `RESEND_API_KEY` | [resend.com](https://resend.com) |
| `EMAIL_FROM` | Verified domain in Resend |
| `DATABASE_URL` | Supabase → Project Settings → Database → URI (production) |

---

## 1. Slack app

1. [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → From scratch.
2. **OAuth & Permissions** → Bot Token Scopes:
   - `app_mentions:read`
   - `chat:write`
   - `channels:history`, `groups:history`, `im:history`, `mpim:history`
3. **Event Subscriptions** → Enable
   - Request URL: `https://<public-url>/slack/events`
   - Bot events: `app_mention`, `message.channels`, `message.groups`, `message.im`, `message.mpim`
4. **Install App** to workspace → copy bot token → `SLACK_BOT_TOKEN`
5. Copy Signing Secret → `SLACK_SIGNING_SECRET`

### OAuth (optional)

Set `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_REDIRECT_URI` and visit:

```
https://<public-url>/slack/oauth/install
```

---

## 2. GitHub webhook

- URL: `https://<public-url>/github-webhook`
- Secret: `GITHUB_WEBHOOK_SECRET`
- Events: Issues, Issue comments

---

## 3. Supabase (production)

Run [`supabase/schema.sql`](supabase/schema.sql) in SQL Editor, then:

```env
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

---

## 4. Local dev

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
ngrok http 8000
```

Point Slack Event Subscriptions to `https://<ngrok-url>/slack/events`.

---

## 5. Test in Slack

```
/invite @FeatureBot
@FeatureBot repo: your-org/your-repo
@FeatureBot add export to CSV for the dashboard
```

---

## Security

- Slack signatures verified on every `/slack/events` request
- Requests older than 5 minutes rejected (replay protection)
- GitHub webhooks verified via HMAC-SHA256
- Never commit `.env`
