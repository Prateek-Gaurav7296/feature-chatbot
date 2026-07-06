"""Slack ChatPlatform implementation."""

from __future__ import annotations

from typing import Any

from app.adapters.interfaces import ChatPlatform, OutgoingMessage
from app.adapters.slack.client import SlackClient
from app.adapters.slack.formatter import SlackMessageFormatter


class SlackPlatform(ChatPlatform):
    def __init__(self, client: SlackClient | None = None):
        self._client = client or SlackClient()
        self._formatter = SlackMessageFormatter()

    def send(self, message: OutgoingMessage) -> dict[str, Any]:
        payload = self._formatter.to_api_payload(message)
        return self._client.post_message(
            channel=payload["channel"],
            text=payload["text"],
            thread_ts=payload.get("thread_ts"),
            blocks=payload.get("blocks"),
        )

    def reply(self, message: OutgoingMessage) -> dict[str, Any]:
        return self.send(message)

    def notify(self, message: OutgoingMessage) -> dict[str, Any]:
        return self.reply(message)
