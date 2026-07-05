"""
Sends proactive messages into a Google Chat space/thread using a service
account. This is separate from *receiving* messages - incoming messages
arrive via the webhook in main.py because Google Chat calls your app's URL
directly when a user @-mentions the bot.

Setup required (see README):
1. Create a GCP project, enable the Google Chat API.
2. Create a service account, download its JSON key -> service_account.json
3. Configure the Chat app in the GCP console to point its HTTP endpoint
   at your deployed /chat-webhook URL.
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/chat.bot"]

_creds = None
_service = None


def _get_service():
    global _creds, _service
    if _service is None:
        _creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        _service = build("chat", "v1", credentials=_creds)
    return _service


def post_message(space_name: str, text: str, thread_key: str | None = None):
    """
    space_name: e.g. "spaces/AAAAxxxxxx" (from the incoming event payload)
    thread_key: pass the same thread name back to keep replies in one thread
    """
    service = _get_service()
    body = {"text": text}
    if thread_key:
        body["thread"] = {"name": thread_key}
    return (
        service.spaces()
        .messages()
        .create(parent=space_name, body=body)
        .execute()
    )
