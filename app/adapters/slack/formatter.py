"""Convert platform-neutral messages to Slack Block Kit payloads."""

from __future__ import annotations

import re

from app.adapters.interfaces import OutgoingMessage

_BOLD_RE = re.compile(r"\*([^*]+)\*")


class SlackMessageFormatter:
    @staticmethod
    def to_api_payload(message: OutgoingMessage) -> dict:
        text = _BOLD_RE.sub(r"*\1*", message.text)
        payload: dict = {
            "channel": message.channel_id,
            "text": text,
            "thread_ts": message.thread_ts,
        }
        if message.blocks:
            payload["blocks"] = message.blocks
        return payload

    @staticmethod
    def strip_bot_mention(text: str, bot_user_id: str | None = None) -> str:
        if bot_user_id:
            text = text.replace(f"<@{bot_user_id}>", "")
        return text.strip()
