import resend
from app.config import settings

resend.api_key = settings.RESEND_API_KEY


def send_assignment_email(to_email: str, issue_title: str, issue_url: str):
    resend.Emails.send(
        {
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": f"You've been assigned: {issue_title}",
            "html": (
                f"<p>Hi,</p>"
                f"<p>You've been assigned a new issue: <b>{issue_title}</b></p>"
                f"<p><a href='{issue_url}'>{issue_url}</a></p>"
                f"<p>- FeatureBot</p>"
            ),
        }
    )
