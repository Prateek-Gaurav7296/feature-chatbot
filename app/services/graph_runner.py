"""LangGraph invocation helpers — no platform imports."""

from __future__ import annotations

from app.adapters.interfaces import IncomingMessage
from app.graph.build_graph import get_compiled_graph
from app.graph.state import IssueState


def invoke_graph(thread_id: str, partial_state: dict) -> IssueState:
    config = {"configurable": {"thread_id": thread_id}}
    return get_compiled_graph().invoke(partial_state, config=config)


def state_from_message(msg: IncomingMessage, **extra) -> dict:
    """Build graph input from a normalized IncomingMessage."""
    return {
        "thread_id": msg.thread_id,
        "channel_id": msg.channel_id,
        "thread_ts": msg.thread_ts,
        "workspace_id": msg.workspace_id,
        "platform": msg.platform,
        "raw_request": msg.text,
        **extra,
    }
