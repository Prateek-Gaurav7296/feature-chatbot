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
    "RESEND_API_KEY": "Resend email — https://resend.com",
    "EMAIL_FROM": "Sender address on a verified Resend domain",
}

PROD_RECOMMENDED = {
    "GITHUB_WEBHOOK_SECRET": "GitHub webhook HMAC secret (required in production)",
    "GOOGLE_CHAT_VERIFICATION_TOKEN": "Google Chat verification token from GCP console",
}

OPTIONAL = {
    "GITHUB_REPO": "Fallback repo (owner/repo) for threads that haven't linked one — "
    "in Chat, send '@FeatureBot repo: owner/repo' instead of setting this",
}

FILE_CHECKS = {
    "GOOGLE_SERVICE_ACCOUNT_FILE": "Google Chat service account JSON key",
}


def _is_set(name: str) -> bool:
    value = os.getenv(name, "").strip()
    if not value:
        return False
    placeholders = {"yourorg/yourrepo", "bot@yourdomain.com", "bot@example.com"}
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

    print()
    for env_var, hint in FILE_CHECKS.items():
        path = os.getenv(env_var, "./service_account.json").strip()
        file_path = ROOT / path if not Path(path).is_absolute() else Path(path)
        ok = file_path.is_file()
        status = "OK" if ok else "MISSING"
        print(f"  [{status}] {env_var} → {file_path}")
        if not ok:
            print(f"           → {hint}")
            missing_required.append(env_var)

    print("\n" + "=" * 40)
    if missing_required:
        print(f"Missing {len(missing_required)} required item(s). See SETUP.md for step-by-step instructions.")
        return 1

    print("All required credentials are configured.")
    print("\nNext steps (external console setup):")
    print("  1. Register GitHub webhook → https://<public-url>/github-webhook")
    print("  2. Configure Google Chat app URL → https://<public-url>/chat-webhook")
    print("  3. Run: uvicorn app.main:app --reload --port 8000")
    print("  4. Tunnel with ngrok for local testing: ngrok http 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
