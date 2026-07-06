#!/usr/bin/env python3
"""Validate FeatureBot credentials and setup prerequisites."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

REQUIRED = {
    "GROQ_API_KEY": "Groq LLM — https://console.groq.com",
    "GITHUB_TOKEN": "GitHub PAT (repo scope) — https://github.com/settings/tokens",
    "SLACK_BOT_TOKEN": "Slack bot token (xoxb-…) — from OAuth install or app settings",
    "SLACK_SIGNING_SECRET": "Slack signing secret — Basic Information → App Credentials",
    "RESEND_API_KEY": "Resend email — https://resend.com",
    "EMAIL_FROM": "Sender address on a verified Resend domain",
}

PROD_RECOMMENDED = {
    "GITHUB_WEBHOOK_SECRET": "GitHub webhook HMAC secret (required in production)",
}

OPTIONAL = {
    "GITHUB_REPO": "Fallback repo — in Slack, send `repo: owner/repo` in a thread instead",
    "SLACK_CLIENT_ID": "Slack OAuth — only needed for /slack/oauth/install flow",
    "SLACK_CLIENT_SECRET": "Slack OAuth client secret",
    "SLACK_REDIRECT_URI": "OAuth callback URL, e.g. https://<host>/slack/oauth/callback",
    "DATABASE_URL": "Postgres/Supabase URL for production (default: SQLite)",
}


def _is_set(name: str) -> bool:
    value = os.getenv(name, "").strip()
    if not value:
        return False
    placeholders = {"bot@yourdomain.com", "bot@example.com"}
    return value not in placeholders


def main() -> int:
    print("FeatureBot credential check\n" + "=" * 40)

    missing_required: list[str] = []
    for name, hint in REQUIRED.items():
        ok = _is_set(name)
        status = "OK" if ok else "MISSING"
        print(f"  [{status}] {name}")
        if not ok:
            print(f"           → {hint}")
            missing_required.append(name)

    print()
    for name, hint in PROD_RECOMMENDED.items():
        ok = _is_set(name)
        status = "OK" if ok else "WARN (dev OK)"
        print(f"  [{status}] {name}")
        if not ok:
            print(f"           → {hint}")

    print()
    for name, hint in OPTIONAL.items():
        ok = _is_set(name)
        status = "OK" if ok else "unset (optional)"
        print(f"  [{status}] {name}")
        if not ok:
            print(f"           → {hint}")

    print("\n" + "=" * 40)
    if missing_required:
        print(f"Missing {len(missing_required)} required item(s). See SETUP.md.")
        return 1

    print("All required credentials are configured.")
    print("\nNext steps:")
    print("  1. Slack app → Event Subscriptions → https://<public-url>/slack/events")
    print("  2. GitHub webhook → https://<public-url>/github-webhook")
    print("  3. uvicorn app.main:app --reload --port 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
