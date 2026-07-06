"""Slack request signature verification and replay protection."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException

MAX_TIMESTAMP_AGE_SECONDS = 60 * 5


def verify_slack_signature(
    signing_secret: str,
    body: bytes,
    timestamp_header: str | None,
    signature_header: str | None,
) -> None:
    if not signing_secret:
        return  # dev only — configure SLACK_SIGNING_SECRET in production

    if not timestamp_header or not signature_header:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    try:
        timestamp = int(timestamp_header)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Slack timestamp") from exc

    if abs(time.time() - timestamp) > MAX_TIMESTAMP_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Slack request timestamp too old")

    base = f"v0:{timestamp_header}:{body.decode('utf-8')}"
    expected = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            base.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
