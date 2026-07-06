"""Normalize Slack Events API payloads into IncomingMessage."""

from __future__ import annotations

from app.adapters.interfaces import IncomingMessage
from app.adapters.slack.formatter import SlackMessageFormatter
from app.adapters.slack.models import IGNORED_MESSAGE_SUBTYPES, SUPPORTED_EVENT_TYPES


class SlackEventNormalizer:
    def __init__(self, bot_user_id: str | None = None):
        self._bot_user_id = bot_user_id

    def should_ignore(self, payload: dict) -> bool:
        if payload.get("type") != "event_callback":
            return True

        event = payload.get("event", {})
        event_type = event.get("type")

        if event_type not in SUPPORTED_EVENT_TYPES:
            return True

        if event.get("bot_id") or event.get("subtype") in IGNORED_MESSAGE_SUBTYPES:
            return True

        if event.get("user") and self._bot_user_id and event.get("user") == self._bot_user_id:
            return True

        return False

    def normalize(self, payload: dict) -> IncomingMessage | None:
        if self.should_ignore(payload):
            return None

        event = payload.get("event", {})
        team_id = payload.get("team_id") or event.get("team", "")

        channel_id = event.get("channel", "")
        message_ts = event.get("ts", "")
        thread_ts = event.get("thread_ts") or message_ts
        text = event.get("text", "")

        if event.get("type") == "app_mention":
            text = SlackMessageFormatter.strip_bot_mention(text, self._bot_user_id)

        if not text.strip():
            return None

        return IncomingMessage(
            platform="slack",
            workspace_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            message_ts=message_ts,
            sender_id=event.get("user", ""),
            sender_name=event.get("username", event.get("user", "unknown")),
            text=text.strip(),
            raw_event=payload,
        )
