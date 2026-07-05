import hashlib
import hmac
import re

from fastapi import FastAPI, Request, HTTPException

from app.config import settings
from app.db import (
    init_db,
    save_mapping,
    get_thread_id,
    get_thread_repo,
    set_thread_repo,
)
from app.graph.build_graph import compiled_graph

app = FastAPI()
init_db()

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Lets a thread be pointed at a repo without touching .env, e.g.:
#   "repo: owner/repo", "set repo https://github.com/owner/repo", or just
#   pasting a bare github.com URL as the entire message.
REPO_CMD_RE = re.compile(
    r"^(?:(?:set|use|link)\s+)?repo\s*[:=]?\s*(?:https?://github\.com/)?"
    r"([\w.-]+/[\w.-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
BARE_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?$"
)


def _extract_repo_command(text: str) -> str | None:
    stripped = text.strip()
    for pattern in (REPO_CMD_RE, BARE_GITHUB_URL_RE):
        match = pattern.match(stripped)
        if match:
            return match.group(1)
    return None


def _invoke(thread_id: str, partial_state: dict):
    """Resume (or start) the graph for this thread_id."""
    config = {"configurable": {"thread_id": thread_id}}
    return compiled_graph.invoke(partial_state, config=config)


def _verify_chat_token(authorization_header: str | None):
    secret = settings.GOOGLE_CHAT_VERIFICATION_TOKEN
    if not secret:
        return  # skip verification if not configured (dev only - configure in prod!)
    token = (authorization_header or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Invalid Google Chat verification token")


@app.post("/chat-webhook")
async def chat_webhook(request: Request):
    _verify_chat_token(request.headers.get("Authorization"))
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

    # Explicit repo binding for this thread — no .env edit needed per repo.
    repo_cmd = _extract_repo_command(text)
    if repo_cmd:
        set_thread_repo(thread_id, repo_cmd)
        return {
            "text": f"Got it — this thread is now linked to `{repo_cmd}`. "
            f"Feature requests here will create issues there."
        }

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

    # Otherwise: treat as a new feature request. Per-thread repo takes
    # priority; GITHUB_REPO is only a fallback default for un-configured threads.
    repo = get_thread_repo(thread_id) or settings.GITHUB_REPO
    if not repo:
        return {
            "text": "This thread isn't linked to a repo yet. Reply with "
            "`repo: owner/repo` (or paste the GitHub URL) first."
        }

    result = _invoke(
        thread_id,
        {
            "thread_id": space_name,
            "repo": repo,
            "raw_request": text,
            "event_type": "chat_message",
        },
    )

    if result.get("issue_number"):
        save_mapping(result["issue_number"], space_name, repo)

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
    repo = payload.get("repository", {}).get("full_name")
    thread_id = get_thread_id(repo, issue_number) if repo else None
    if not thread_id:
        return {"ok": True}  # not an issue we created/track

    action = payload.get("action")

    if event_name == "issues" and action == "assigned":
        assignee = payload.get("assignee", {}).get("login")
        _invoke(
            thread_id,
            {
                "event_type": "github_assigned",
                "assignee": assignee,
                "issue_number": issue_number,
                "repo": repo,
            },
        )

    elif event_name == "issues" and action == "closed":
        _invoke(
            thread_id,
            {"event_type": "github_closed", "issue_number": issue_number, "repo": repo},
        )

    elif event_name == "issue_comment" and action == "created":
        _invoke(
            thread_id,
            {"event_type": "github_comment", "issue_number": issue_number, "repo": repo},
        )

    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
