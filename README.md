# FeatureBot

A Google Chat bot that turns a mentioned feature request into a GitHub issue,
tracks its assignment, emails the assignee, and relays GitHub comment
activity back into the chat thread — built with LangGraph + LangChain.

## How it works

See the graph in `app/graph/build_graph.py`. One state machine, re-invoked
every time something happens (a chat message, a GitHub assignment, a new
comment). LangGraph's checkpointer remembers where each issue's "thread" of
state is, so the graph resumes instead of starting over.

## 1. Local setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `GROQ_API_KEY` — from console.groq.com (free, no card)
- `GITHUB_TOKEN` — a classic PAT with `repo` scope (github.com/settings/tokens)
- `GITHUB_REPO` — `yourorg/yourrepo`
- `RESEND_API_KEY` — from resend.com (free tier, 100 emails/day)

## 2. Google Chat app setup (do this before running)

1. Go to console.cloud.google.com, create a new project (free).
2. Enable the **Google Chat API**.
3. Under "Configuration" for the Chat API, register a Chat app:
   - App name: FeatureBot
   - Interaction: choose "App URL" (not Apps Script)
   - App URL: you'll fill this in once deployed — for now, use an ngrok URL
     for local testing (see below)
4. Under "Credentials", create a **Service Account**, then create a JSON key
   for it. Download it as `service_account.json` in the project root.
5. In the Chat API configuration, grant the service account permission to
   post messages (the `chat.bot` scope is requested automatically by
   `app/clients/chat_client.py`).

## 3. GitHub webhook setup

In your repo → Settings → Webhooks → Add webhook:
- Payload URL: `https://<your-deployed-url>/github-webhook`
- Content type: `application/json`
- Secret: same value as `GITHUB_WEBHOOK_SECRET` in `.env`
- Events: select "Issues" and "Issue comments"

## 4. Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

For Google Chat and GitHub to reach your local server, tunnel it (e.g. with
`ngrok http 8000`) and use the ngrok URL as your App URL / webhook URL while
testing. This is temporary — once deployed to Cloud Run you get a stable
HTTPS URL and can drop ngrok entirely.

Try it: in the Chat space where you added the bot, type
`@FeatureBot add a dark mode toggle to settings`. Watch the terminal logs —
you should see the graph run through `parse_request → create_issue →
notify_chat_created`, and a message should land back in the chat with the
issue link.

## 5. Deploy to Cloud Run (free tier)

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

gcloud run deploy featurebot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GROQ_API_KEY=...,GITHUB_TOKEN=...,GITHUB_REPO=...,GITHUB_WEBHOOK_SECRET=...,RESEND_API_KEY=...,EMAIL_FROM=...
```

You'll need a `Dockerfile` (below) for `--source .` to build correctly.

After deploy, `gcloud run services describe featurebot` gives you the
public URL. Update:
- The Chat app's App URL to `<that-url>/chat-webhook`
- The GitHub webhook Payload URL to `<that-url>/github-webhook`

### Important: swap SQLite for Postgres before deploying

Cloud Run containers are ephemeral — anything written to local disk
(including `featurebot_graph.db` and `featurebot_map.db`) disappears on
cold start. Before deploying:

1. Create a free Postgres DB on Neon or Supabase.
2. In `app/graph/build_graph.py`, replace:
   ```python
   from langgraph.checkpoint.sqlite import SqliteSaver
   memory = SqliteSaver.from_conn_string("featurebot_graph.db")
   ```
   with:
   ```python
   from langgraph.checkpoint.postgres import PostgresSaver
   memory = PostgresSaver.from_conn_string(settings.DATABASE_URL)
   memory.setup()  # creates tables on first run
   ```
3. Move `app/db.py`'s thread/issue mapping table to the same Postgres
   instance too (swap `sqlite3` for `psycopg2`, same get/save interface).
4. Set `DATABASE_URL` as an env var on Cloud Run pointing to your Neon/Supabase
   connection string.

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Extending it

The nodes in `app/graph/nodes.py` and the router in `build_graph.py` are the
whole system. To add a feature (e.g. duplicate detection, PM approval gate),
you're adding: one new node function, one new entry in `route_event`, and
wiring its edges. Everything else (webhooks, DB mapping, clients) stays
untouched.
