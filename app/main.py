import hashlib
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException

from app.adapters.registry import set_chat_platform
from app.adapters.slack.oauth import router as slack_oauth_router
from app.adapters.slack.platform import SlackPlatform
from app.adapters.slack.webhook import router as slack_events_router
from app.config import settings
from app.db import get_thread_id, init_db
from app.services.graph_runner import invoke_graph
from app.services.notifier import notify_by_thread_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_chat_platform(SlackPlatform())
    init_db()
    yield


app = FastAPI(title="FeatureBot", lifespan=lifespan)

app.include_router(slack_events_router)
app.include_router(slack_oauth_router)


def _verify_github_signature(secret: str, payload_body: bytes, signature_header: str):
    if not secret:
        return  # skip verification if not configured (dev only)
    expected = "sha256=" + hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header or ""):
        raise HTTPException(status_code=401, detail="Invalid GitHub signature")


@app.post("/github-webhook")
async def github_webhook(request: Request):
    body = await request.body()
    _verify_github_signature(
        settings.GITHUB_WEBHOOK_SECRET, body, request.headers.get("X-Hub-Signature-256")
    )

    event_name = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    issue = payload.get("issue")
    if not issue:
        return {"ok": True}

    issue_number = issue["number"]
    repo = payload.get("repository", {}).get("full_name")
    thread_id = get_thread_id(repo, issue_number) if repo else None
    if not thread_id:
        return {"ok": True}

    action = payload.get("action")

    if event_name == "issues" and action == "assigned":
        assignee = payload.get("assignee", {}).get("login")
        invoke_graph(
            thread_id,
            {
                "event_type": "github_assigned",
                "assignee": assignee,
                "issue_number": issue_number,
                "repo": repo,
            },
        )

    elif event_name == "issues" and action == "closed":
        invoke_graph(
            thread_id,
            {"event_type": "github_closed", "issue_number": issue_number, "repo": repo},
        )

    elif event_name == "issues" and action == "labeled":
        label = payload.get("label", {}).get("name", "unknown")
        notify_by_thread_id(
            thread_id,
            f"🏷️ Label `{label}` added to issue #{issue_number}.",
        )

    elif event_name == "issue_comment" and action == "created":
        invoke_graph(
            thread_id,
            {"event_type": "github_comment", "issue_number": issue_number, "repo": repo},
        )

    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
