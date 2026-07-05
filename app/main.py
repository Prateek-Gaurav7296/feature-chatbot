import hashlib
import hmac
import re

from fastapi import FastAPI, Request, HTTPException

from app.config import settings
from app.db import init_db, save_mapping, get_thread_id
from app.graph.build_graph import compiled_graph

app = FastAPI()
init_db()

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _invoke(thread_id: str, partial_state: dict):
    """Resume (or start) the graph for this thread_id."""
    config = {"configurable": {"thread_id": thread_id}}
    return compiled_graph.invoke(partial_state, config=config)


@app.post("/chat-webhook")
async def chat_webhook(request: Request):
    payload = await request.json()

    # Google Chat's event shape: payload["message"]["text"], payload["space"]["name"]
    message = payload.get("message", {})
    space_name = payload.get("space", {}).get("name")
    text = message.get("text", "")
    thread_name = message.get("thread", {}).get("name", space_name)

    if not space_name:
        return {"text": "Couldn't identify the space this came from."}

    # thread_id used for graph checkpointing = the Chat thread name itself
    thread_id = thread_name

    # Heuristic: if this thread is already awaiting an email reply, treat
    # this message as the email answer rather than a new feature request.
    # (In production, check saved state's `status` field instead of guessing.)
    email_match = EMAIL_RE.search(text)
    if email_match:
        _invoke(
            thread_id,
            {"event_type": "chat_email_reply", "assignee_email": email_match.group(0)},
        )
        return {"text": "Got it, notifying them now."}

    # Otherwise: treat as a new feature request
    result = _invoke(
        thread_id,
        {
            "thread_id": space_name,
            "repo": settings.GITHUB_REPO,
            "raw_request": text,
            "event_type": "chat_message",
        },
    )

    if result.get("issue_number"):
        save_mapping(result["issue_number"], space_name, settings.GITHUB_REPO)

    # Chat expects a synchronous JSON response to acknowledge the message.
    # The actual "issue created" message is sent proactively via chat_client
    # inside notify_chat_created_node, so this ack can be minimal.
    return {"text": "Working on it..."}


def _verify_github_signature(secret: str, payload_body: bytes, signature_header: str):
    if not secret:
        return  # skip verification if not configured (dev only - configure in prod!)
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
        return {"ok": True}  # not an issue-related event, ignore

    issue_number = issue["number"]
    thread_id = get_thread_id(issue_number)
    if not thread_id:
        return {"ok": True}  # not an issue we created/track

    action = payload.get("action")

    if event_name == "issues" and action == "assigned":
        assignee = payload.get("assignee", {}).get("login")
        _invoke(
            thread_id,
            {"event_type": "github_assigned", "assignee": assignee, "issue_number": issue_number},
        )

    elif event_name == "issues" and action == "closed":
        _invoke(thread_id, {"event_type": "github_closed", "issue_number": issue_number})

    elif event_name == "issue_comment" and action == "created":
        _invoke(thread_id, {"event_type": "github_comment", "issue_number": issue_number})

    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
