"""Handle normalized incoming messages — repo binding, email replies, feature requests."""

from __future__ import annotations

import re

from app.adapters.interfaces import IncomingMessage, OutgoingMessage
from app.adapters.registry import get_chat_platform
from app.config import settings
from app.db import get_thread_repo, save_mapping, set_thread_repo
from app.services.graph_runner import invoke_graph, state_from_message

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

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


def _reply(msg: IncomingMessage, text: str) -> None:
    platform = get_chat_platform()
    platform.reply(
        OutgoingMessage(
            channel_id=msg.channel_id,
            thread_ts=msg.thread_ts,
            text=text,
        )
    )


def handle_incoming_message(msg: IncomingMessage) -> None:
    thread_id = msg.thread_id

    repo_cmd = _extract_repo_command(msg.text)
    if repo_cmd:
        set_thread_repo(thread_id, repo_cmd)
        _reply(
            msg,
            f"Got it — this thread is now linked to `{repo_cmd}`. "
            f"Feature requests here will create issues there.",
        )
        return

    email_match = EMAIL_RE.search(msg.text)
    if email_match:
        invoke_graph(
            thread_id,
            {
                "event_type": "chat_email_reply",
                "assignee_email": email_match.group(0),
            },
        )
        _reply(msg, "Got it, notifying them now.")
        return

    repo = get_thread_repo(thread_id) or settings.GITHUB_REPO
    if not repo:
        _reply(
            msg,
            "This thread isn't linked to a repo yet. Reply with "
            "`repo: owner/repo` (or paste the GitHub URL) first.",
        )
        return

    result = invoke_graph(
        thread_id,
        state_from_message(
            msg,
            repo=repo,
            event_type="chat_message",
        ),
    )

    if result.get("issue_number"):
        save_mapping(result["issue_number"], thread_id, repo)

    _reply(msg, "Working on it...")
