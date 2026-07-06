"""Platform-agnostic chat contracts. LangGraph never imports Slack."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IncomingMessage:
    platform: str
    workspace_id: str
    channel_id: str
    thread_ts: str
    message_ts: str
    sender_id: str
    sender_name: str
    text: str
    raw_event: dict = field(default_factory=dict)

    @property
    def thread_id(self) -> str:
        """Stable LangGraph checkpoint key for this conversation thread."""
        return f"{self.platform}:{self.workspace_id}:{self.channel_id}:{self.thread_ts}"


@dataclass
class OutgoingMessage:
    channel_id: str
    thread_ts: str
    text: str
    blocks: Optional[list[dict]] = None


class ChatPlatform(ABC):
    """Interface for any chat platform adapter (Slack, Teams, Google Chat, …)."""

    @abstractmethod
    def send(self, message: OutgoingMessage) -> dict[str, Any]:
        """Post a message (optionally in-thread)."""

    def reply(self, message: OutgoingMessage) -> dict[str, Any]:
        """Reply in an existing thread (default: same as send)."""
        return self.send(message)

    def notify(self, message: OutgoingMessage) -> dict[str, Any]:
        """Push a lifecycle update to a thread (default: same as reply)."""
        return self.reply(message)
