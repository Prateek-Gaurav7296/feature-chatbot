from github import Github
from app.config import settings

_gh = Github(settings.GITHUB_TOKEN) if settings.GITHUB_TOKEN else None


def _repo():
    if not _gh:
        raise RuntimeError("GITHUB_TOKEN not configured")
    return _gh.get_repo(settings.GITHUB_REPO)


def create_issue(title: str, body: str, labels: list[str] | None = None) -> dict:
    repo = _repo()
    issue = repo.create_issue(title=title, body=body, labels=labels or [])
    return {"number": issue.number, "url": issue.html_url}


def get_issue(issue_number: int):
    return _repo().get_issue(issue_number)


def get_new_comments(issue_number: int, since_comment_id: int | None):
    """Return comments newer than since_comment_id, oldest first."""
    issue = _repo().get_issue(issue_number)
    comments = list(issue.get_comments())
    if since_comment_id is None:
        return comments
    return [c for c in comments if c.id > since_comment_id]


def get_assignee_login(issue_number: int) -> str | None:
    issue = get_issue(issue_number)
    if issue.assignee:
        return issue.assignee.login
    return None
