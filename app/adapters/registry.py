"""Dependency injection for the active chat platform adapter."""

from __future__ import annotations

from app.adapters.interfaces import ChatPlatform

_platform: ChatPlatform | None = None


def set_chat_platform(platform: ChatPlatform) -> None:
    global _platform
    _platform = platform


def get_chat_platform() -> ChatPlatform:
    if _platform is None:
        raise RuntimeError("Chat platform not initialized")
    return _platform
