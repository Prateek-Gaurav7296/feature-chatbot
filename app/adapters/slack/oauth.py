"""Slack OAuth v2 install flow."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.adapters.slack.models import OAUTH_SCOPES
from app.config import settings

router = APIRouter(prefix="/slack/oauth", tags=["slack-oauth"])


@router.get("/install")
async def slack_oauth_install():
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_REDIRECT_URI:
        raise HTTPException(
            status_code=500,
            detail="SLACK_CLIENT_ID and SLACK_REDIRECT_URI must be configured for OAuth",
        )
    params = urlencode(
        {
            "client_id": settings.SLACK_CLIENT_ID,
            "scope": OAUTH_SCOPES,
            "redirect_uri": settings.SLACK_REDIRECT_URI,
        }
    )
    return RedirectResponse(f"https://slack.com/oauth/v2/authorize?{params}")


@router.get("/callback")
async def slack_oauth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    if not all(
        [
            settings.SLACK_CLIENT_ID,
            settings.SLACK_CLIENT_SECRET,
            settings.SLACK_REDIRECT_URI,
        ]
    ):
        raise HTTPException(status_code=500, detail="Slack OAuth env vars not configured")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.SLACK_CLIENT_ID,
                "client_secret": settings.SLACK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.SLACK_REDIRECT_URI,
            },
        )
    data = response.json()
    if not data.get("ok"):
        raise HTTPException(status_code=400, detail=data.get("error", "OAuth failed"))

    # For single-workspace installs, copy access_token into SLACK_BOT_TOKEN.
    return {
        "ok": True,
        "team": data.get("team", {}).get("name"),
        "bot_user_id": data.get("bot_user_id"),
        "message": "Copy the access_token below into SLACK_BOT_TOKEN in your environment.",
        "access_token": data.get("access_token"),
    }
