"""Slack Events API webhook handler."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from app.adapters.slack.auth import verify_slack_signature
from app.adapters.slack.normalizer import SlackEventNormalizer
from app.config import settings
from app.services.message_handler import handle_incoming_message

router = APIRouter(tags=["slack"])

_normalizer = SlackEventNormalizer()


@router.post("/slack/events")
async def slack_events(request: Request):
    body = await request.body()
    verify_slack_signature(
        settings.SLACK_SIGNING_SECRET,
        body,
        request.headers.get("X-Slack-Request-Timestamp"),
        request.headers.get("X-Slack-Signature"),
    )

    payload = json.loads(body)

    # URL verification handshake (Slack app setup)
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if payload.get("type") != "event_callback":
        return {"ok": True}

    incoming = _normalizer.normalize(payload)
    if incoming is None:
        return {"ok": True}

    # Slack requires a fast 200; processing is synchronous for now (Cloud Run scales).
    try:
        handle_incoming_message(incoming)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ok": True}
