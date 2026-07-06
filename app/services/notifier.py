"""Platform-agnostic outbound messaging for LangGraph nodes."""

from __future__ import annotations

from app.adapters.interfaces import OutgoingMessage
from app.adapters.registry import get_chat_platform
from app.graph.state import IssueState


def notify_thread(state: IssueState, text: str, blocks: list[dict] | None = None) -> None:
    """Send a message to the originating chat thread. Nodes call this — never Slack directly."""
    channel_id = state.get("channel_id")
    thread_ts = state.get("thread_ts")
    if not channel_id or not thread_ts:
        raise RuntimeError("Missing channel_id/thread_ts in graph state for notification")

    platform = get_chat_platform()
    platform.notify(
        OutgoingMessage(
            channel_id=channel_id,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks,
        )
    )


def notify_by_thread_id(thread_id: str, text: str) -> None:
    """Send a thread reply when only the composite thread_id is known (e.g. GitHub webhooks)."""
    parts = thread_id.split(":", 3)
    if len(parts) != 4:
        return
    channel_id, thread_ts = parts[2], parts[3]
    platform = get_chat_platform()
    platform.notify(
        OutgoingMessage(channel_id=channel_id, thread_ts=thread_ts, text=text)
    )
