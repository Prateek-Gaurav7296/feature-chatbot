"""Low-level Slack Web API client."""

from __future__ import annotations

from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.config import settings


class SlackClient:
    def __init__(self, token: str | None = None):
        self._token = token or settings.SLACK_BOT_TOKEN or ""
        self._client: WebClient | None = None

    def _get_client(self) -> WebClient:
        if not self._token:
            raise RuntimeError("SLACK_BOT_TOKEN not configured")
        if self._client is None:
            self._client = WebClient(token=self._token)
        return self._client

    def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        if blocks:
            kwargs["blocks"] = blocks
        try:
            response = self._get_client().chat_postMessage(**kwargs)
            return response.data
        except SlackApiError as exc:
            raise RuntimeError(f"Slack API error: {exc.response['error']}") from exc
