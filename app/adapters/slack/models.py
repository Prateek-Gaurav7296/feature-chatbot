"""Slack-specific constants and type aliases."""

SUPPORTED_EVENT_TYPES = frozenset(
    {
        "message",
        "app_mention",
    }
)

IGNORED_MESSAGE_SUBTYPES = frozenset(
    {
        "bot_message",
        "message_changed",
        "message_deleted",
        "channel_join",
        "channel_leave",
    }
)

OAUTH_SCOPES = ",".join(
    [
        "app_mentions:read",
        "chat:write",
        "channels:history",
        "groups:history",
        "im:history",
        "mpim:history",
    ]
)
