# FeatureBot

A Google Chat bot that turns an @-mentioned feature request into a GitHub issue, tracks its assignment, emails the assignee, and relays GitHub comment activity back into the chat thread — built with **FastAPI**, **LangGraph**, and **LangChain**.

> **First time setup?** See **[SETUP.md](SETUP.md)** for a complete guide to every API key, credential, and external console configuration.

## Overview

FeatureBot sits between three external systems:

| System | Role |
|--------|------|
| **Google Chat** | Users @-mention the bot with informal feature requests; the bot posts status updates back into the same thread |
| **GitHub** | Issues are created, assigned, commented on, and closed; webhooks drive downstream automation |
| **Resend** | Sends assignment notification emails once the team provides the assignee's address |

An **LLM (Groq / Llama 3.3 70B)** parses informal chat text into structured GitHub issue JSON (title, body with acceptance criteria, labels). The rest of the pipeline is deterministic graph nodes that call GitHub, Chat, and email APIs.

---

## System architecture

```mermaid
flowchart TB
    subgraph External["External services"]
        GC[Google Chat]
        GH[GitHub]
        GROQ[Groq LLM API]
        RESEND[Resend Email]
    end

    subgraph FeatureBot["FeatureBot (FastAPI)"]
        CW["/chat-webhook"]
        GW["/github-webhook"]
        HC["/health"]

        subgraph Graph["LangGraph agent"]
            ROUTER{route_event}
            NODES[Graph nodes]
        end

        subgraph Clients["Clients"]
            CC[chat_client]
            GHC[github_client]
            EC[email_client]
        end

        subgraph Storage["Persistence"]
            CP[(featurebot_graph.db<br/>LangGraph checkpointer)]
            MAP[(featurebot_map.db<br/>issue ↔ thread map)]
        end
    end

    GC -->|"user @-mentions bot"| CW
    GH -->|"issues / comments webhooks"| GW

    CW --> Graph
    GW --> Graph

    ROUTER --> NODES
    NODES --> CC
    NODES --> GHC
    NODES --> EC
    NODES --> GROQ

    CC -->|"post_message"| GC
    GHC -->|"create_issue, get_comments"| GH
    EC -->|"send_assignment_email"| RESEND

    Graph --> CP
    CW --> MAP
    GW --> MAP
```

### Request flow (high level)

1. **Chat message** → `POST /chat-webhook` → graph invoked with `event_type: chat_message` → LLM parses request → GitHub issue created → bot posts confirmation in Chat → issue↔thread mapping saved.
2. **GitHub assignment** → `POST /github-webhook` → lookup thread by issue number → graph invoked with `event_type: github_assigned` → bot asks Chat for assignee email.
3. **Email reply in Chat** → `POST /chat-webhook` → graph invoked with `event_type: chat_email_reply` → Resend sends email → bot confirms in Chat.
4. **New GitHub comment** → `POST /github-webhook` → graph invoked with `event_type: github_comment` → new comments synced to Chat thread.
5. **Issue closed** → `POST /github-webhook` → graph invoked with `event_type: github_closed` → closure announced in Chat.

---

## Agent architecture (LangGraph)

The agent is an **event-driven hub-and-spoke graph**, not a single linear pipeline. Each webhook re-invokes the same compiled graph with a fresh `event_type`; the **conditional entry router** dispatches to the correct node. LangGraph's **SqliteSaver checkpointer** (keyed by Chat `thread_id`) merges new input with prior state so the graph resumes instead of starting over.

```mermaid
flowchart TD
    START([Graph invoked]) --> ROUTER{route_event<br/>by event_type}

    ROUTER -->|chat_message| PARSE[parse_request]
    PARSE --> CREATE[create_issue]
    CREATE --> NOTIFY[notify_chat_created]
    NOTIFY --> END1([END])

    ROUTER -->|github_assigned| ASK[ask_assignee_email]
    ASK --> END2([END])

    ROUTER -->|chat_email_reply| SEND[send_assignment_email]
    SEND --> END3([END])

    ROUTER -->|github_comment| SYNC[sync_comments]
    SYNC --> END4([END])

    ROUTER -->|github_closed| CLOSE[issue_closed]
    CLOSE --> END5([END])

    ROUTER -->|unknown| NOOP[noop]
    NOOP --> END6([END])

    PARSE -.->|Groq LLM| LLM["llama-3.3-70b-versatile<br/>JSON: title, body, labels"]
    CREATE -.-> GHC[github_client]
    NOTIFY -.-> CHAT[chat_client]
    ASK -.-> CHAT
    SEND -.-> EMAIL[email_client + chat_client]
    SYNC -.-> GHC
    SYNC -.-> CHAT
    CLOSE -.-> CHAT
```

### Event types → nodes

| `event_type` | Trigger | Node(s) run | Outcome |
|--------------|---------|-------------|---------|
| `chat_message` | User @-mentions bot with a feature request | `parse_request` → `create_issue` → `notify_chat_created` | GitHub issue created; Chat notified with link |
| `github_assigned` | GitHub `issues.assigned` webhook | `ask_assignee_email` | Bot asks Chat thread for assignee's email |
| `chat_email_reply` | User replies in Chat with an email address | `send_assignment_email` | Resend email sent; Chat confirmation posted |
| `github_comment` | GitHub `issue_comment.created` webhook | `sync_comments` | New comments posted to Chat (deduped via `last_comment_id`) |
| `github_closed` | GitHub `issues.closed` webhook | `issue_closed` | Closure message posted to Chat |

### Issue state lifecycle

State is defined in `app/graph/state.py` as `IssueState` and persisted by the checkpointer:

```
drafted → created → awaiting_assignment → awaiting_email → in_progress → closed
```

Key fields: `thread_id`, `repo`, `raw_request`, `title`, `body`, `labels`, `issue_number`, `issue_url`, `assignee`, `assignee_email`, `last_comment_id`, `status`, `event_type`.

---

## Project structure

```
featurebot/
├── app/
│   ├── main.py                 # FastAPI app, webhook handlers, graph invocation
│   ├── config.py               # Settings loaded from .env
│   ├── db.py                   # SQLite issue_number ↔ thread_id mapping
│   ├── clients/
│   │   ├── chat_client.py      # Google Chat API (service account, chat.bot scope)
│   │   ├── github_client.py    # PyGithub: create issues, fetch comments
│   │   └── email_client.py     # Resend: assignment notification emails
│   └── graph/
│       ├── state.py            # IssueState TypedDict
│       ├── nodes.py            # All graph node implementations + LLM prompt
│       └── build_graph.py      # StateGraph wiring, router, SqliteSaver checkpointer
├── .env.example
├── requirements.txt
└── README.md
```

---

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat-webhook` | Receives Google Chat events (feature requests, email replies) |
| `POST` | `/github-webhook` | Receives GitHub issue/comment webhooks (HMAC-SHA256 verified) |
| `GET` | `/health` | Health check (`{"status": "ok"}`) |

### Webhook details

**`/chat-webhook`** extracts `space.name`, `message.text`, and `message.thread.name` from the payload. The Chat thread name is used as the LangGraph `thread_id` for checkpointing. If the message is just a repo reference (`repo: owner/repo`, a bare `github.com` URL, etc.), it links that repo to the thread (`set_thread_repo`) instead of creating an issue. Otherwise, if the message contains an email address it's treated as an assignee email reply; otherwise it's a new feature request, filed against the thread's linked repo (or `GITHUB_REPO` as a fallback).

**`/github-webhook`** verifies the `X-Hub-Signature-256` header against `GITHUB_WEBHOOK_SECRET`, looks up the Chat thread via `get_thread_id(repo, issue_number)` — using the repo GitHub includes in the payload (`repository.full_name`) plus the issue number — and dispatches based on `X-GitHub-Event` and `action` (`assigned`, `closed`, `issue_comment.created`).

---

## Persistence

Two separate SQLite databases (local dev):

| File | Purpose |
|------|---------|
| `featurebot_graph.db` | LangGraph **checkpointer** — full graph state per Chat thread |
| `featurebot_map.db` | **Issue ↔ thread mapping** (`issue_thread_map`, keyed by `(repo, issue_number)`) and **thread ↔ repo links** (`thread_repo_map`, keyed by `thread_id`) |

The issue↔thread mapping is written in `main.py` after issue creation (`save_mapping`) and read on every GitHub webhook (`get_thread_id`). It's keyed by `(repo, issue_number)` rather than issue number alone, since issue numbers repeat across repos. The thread↔repo table is written whenever a thread links a repo (`set_thread_repo`) and read on every chat message (`get_thread_repo`). This separation keeps webhook routing O(1) without loading full graph state.

---

## Environment variables

Copy `.env.example` to `.env` and fill in every required value. For step-by-step instructions on obtaining each API key and configuring external consoles (GitHub webhooks, Google Chat, Resend), see **[SETUP.md](SETUP.md)**.

Validate your configuration anytime:

```bash
python scripts/check_env.py
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key ([console.groq.com](https://console.groq.com)) |
| `OPENAI_API_KEY` | No | Optional fallback LLM (not wired in current nodes) |
| `GITHUB_TOKEN` | Yes | Classic PAT with `repo` scope |
| `GITHUB_REPO` | No | Fallback default repo, e.g. `yourorg/yourrepo`, used only for threads that haven't linked their own repo (see [Linking a Chat thread to a repo](#linking-a-chat-thread-to-a-repo)) |
| `GITHUB_WEBHOOK_SECRET` | Prod | Shared secret for webhook signature verification |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Yes | Path to GCP service account JSON (default: `./service_account.json`) |
| `GOOGLE_CHAT_VERIFICATION_TOKEN` | Prod | Chat app verification token (validated on `/chat-webhook`) |
| `RESEND_API_KEY` | Yes | Resend API key ([resend.com](https://resend.com)) |
| `EMAIL_FROM` | Yes | Sender address for assignment emails |
| `DATABASE_URL` | Optional | Default `sqlite:///./featurebot.db`; use Postgres in production |

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Web framework | FastAPI + Uvicorn |
| Agent orchestration | LangGraph 0.2 (`StateGraph`, conditional entry, checkpointer) |
| LLM | LangChain + Groq (`llama-3.3-70b-versatile`, temperature 0) |
| GitHub | PyGithub |
| Google Chat | `google-auth` + `google-api-python-client` (Chat API v1) |
| Email | Resend |
| Config | `python-dotenv` |
| Persistence (dev) | SQLite (`langgraph.checkpoint.sqlite`, plain `sqlite3`) |

---

## 1. Local setup

**Requires Python 3.11** (3.12 also works). Python 3.14 is not supported — `langchain` depends on `numpy<2`, which has no wheels for 3.14 yet.

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` (see table above). Minimum: `GROQ_API_KEY`, `GITHUB_TOKEN`, `RESEND_API_KEY`, `EMAIL_FROM`, and `GOOGLE_SERVICE_ACCOUNT_FILE`. `GITHUB_REPO` is optional — link repos per Chat thread instead (see below).

---

## 2. Google Chat app setup (do this before running)

1. Go to [console.cloud.google.com](https://console.cloud.google.com), create a new project (free).
2. Enable the **Google Chat API**.
3. Under "Configuration" for the Chat API, register a Chat app:
   - App name: FeatureBot
   - Interaction: choose **App URL** (not Apps Script)
   - App URL: you'll fill this in once deployed — for local testing, use an ngrok URL (see below)
4. Under "Credentials", create a **Service Account**, then create a JSON key for it. Download it as `service_account.json` in the project root.
5. In the Chat API configuration, grant the service account permission to post messages (the `chat.bot` scope is requested automatically by `app/clients/chat_client.py`).

---

## 3. GitHub webhook setup

In **each repo you plan to link to a thread** → **Settings → Webhooks → Add webhook**:

- **Payload URL:** `https://<your-deployed-url>/github-webhook`
- **Content type:** `application/json`
- **Secret:** same value as `GITHUB_WEBHOOK_SECRET` in `.env` (use the same secret for every repo — one bot instance verifies all incoming webhooks with this one value)
- **Events:** select **Issues** and **Issue comments**

---

## Linking a Chat thread to a repo

`GITHUB_REPO` in `.env` is only a fallback default. Instead of editing `.env` every time you want the bot to work against a new repo, link a repo to a Chat thread at runtime by messaging the bot with just the repo (no other text):

```
@FeatureBot repo: owner/repo
@FeatureBot set repo https://github.com/owner/repo
@FeatureBot https://github.com/owner/repo
```

The bot confirms the link and saves `thread_id → repo` in `featurebot_map.db` (`app/db.py`, `thread_repo_map` table). Every feature request sent afterward in that thread creates issues in that repo. Replies to GitHub events (assignment, comments, close) are routed using the repo GitHub includes in the webhook payload itself, keyed together with the issue number (`issue_thread_map`, keyed by `(repo, issue_number)` — issue numbers repeat across repos, so the repo is part of the lookup key). This means a single deployed bot can serve multiple repos across different Chat threads at once, as long as `GITHUB_TOKEN` has access to all of them and each repo's webhook uses the same `GITHUB_WEBHOOK_SECRET`.

If a thread hasn't linked a repo and `GITHUB_REPO` isn't set, the bot asks the user to link one before creating an issue.

---

## 4. Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

For Google Chat and GitHub to reach your local server, tunnel it (e.g. with `ngrok http 8000`) and use the ngrok URL as your App URL / webhook URL while testing. Once deployed to Cloud Run you get a stable HTTPS URL and can drop ngrok.

**Try it:** in the Chat space where you added the bot, type:

```
@FeatureBot add a dark mode toggle to settings
```

Watch the terminal logs — you should see the graph run through `parse_request → create_issue → notify_chat_created`, and a message should land back in the chat with the issue link.

---

## 5. Deploy to Cloud Run (free tier)

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

gcloud run deploy featurebot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GROQ_API_KEY=...,GITHUB_TOKEN=...,GITHUB_WEBHOOK_SECRET=...,RESEND_API_KEY=...,EMAIL_FROM=...
  # GITHUB_REPO=owner/repo is optional here — add it only if you want a default
  # repo for threads that haven't linked one via "@FeatureBot repo: owner/repo"
```

You'll need a `Dockerfile` (below) for `--source .` to build correctly.

After deploy, `gcloud run services describe featurebot` gives you the public URL. Update:

- The Chat app's App URL to `<that-url>/chat-webhook`
- The GitHub webhook Payload URL to `<that-url>/github-webhook`

### Important: use Supabase/Postgres before deploying

Cloud Run containers are ephemeral — anything written to local disk (including `featurebot_graph.db` and `featurebot_map.db`) disappears on cold start.

The app **automatically uses Postgres** when `DATABASE_URL` starts with `postgres://` or `postgresql://`. Otherwise it falls back to SQLite for local dev.

#### Supabase setup

1. Create a project at [supabase.com](https://supabase.com).
2. Open **Project Settings → Database → Connection string → URI** and copy the Postgres URL.
3. Run the app tables SQL in **SQL Editor** (or let `init_db()` create them on first start):

```sql
-- See supabase/schema.sql for the full script
CREATE TABLE IF NOT EXISTS issue_thread_map (
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    thread_id TEXT NOT NULL,
    PRIMARY KEY (repo, issue_number)
);

CREATE TABLE IF NOT EXISTS thread_repo_map (
    thread_id TEXT PRIMARY KEY,
    repo TEXT NOT NULL
);
```

4. Set in `.env`:
   ```
   DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
   Use the **Session pooler** (port 6543) or **Direct connection** (port 5432) URL from Supabase.

5. Start the app — LangGraph checkpoint tables are created automatically via `PostgresSaver.setup()` on first run.

6. Set `DATABASE_URL` on Cloud Run alongside your other env vars.

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## Extending the agent

The nodes in `app/graph/nodes.py` and the router in `build_graph.py` are the whole system. To add a feature (e.g. duplicate detection, PM approval gate):

1. Add a new node function in `nodes.py`.
2. Register it in `build_graph.py` with `graph.add_node(...)`.
3. Add a branch in `route_event` and wire edges (hub-and-spoke or linear chain as needed).

Everything else (webhooks, DB mapping, clients) stays untouched.

### LLM parsing behavior

`parse_request_node` sends the raw chat text to Groq with a system prompt that requests JSON: `{title, body, labels}`. The body must include `## Description` and `## Acceptance Criteria` (markdown checklist). Labels are chosen from: `feature`, `bug`, `chore`, `ui`, `backend`, `urgent`. On JSON parse failure, the node falls back to a truncated title and a minimal body so the pipeline never breaks.
