from github import Github
from app.config import settings

_gh = Github(settings.GITHUB_TOKEN) if settings.GITHUB_TOKEN else None


def _get_repo(repo_name: str):
    if not _gh:
        raise RuntimeError("GITHUB_TOKEN not configured")
    if not repo_name:
        raise RuntimeError("No repo configured for this thread")
    return _gh.get_repo(repo_name)


def create_issue(repo: str, title: str, body: str, labels: list[str] | None = None) -> dict:
    r = _get_repo(repo)
    issue = r.create_issue(title=title, body=body, labels=labels or [])
    return {"number": issue.number, "url": issue.html_url}


def get_issue(repo: str, issue_number: int):
    return _get_repo(repo).get_issue(issue_number)


def get_new_comments(repo: str, issue_number: int, since_comment_id: int | None):
    """Return comments newer than since_comment_id, oldest first."""
    issue = get_issue(repo, issue_number)
    comments = list(issue.get_comments())
    if since_comment_id is None:
        return comments
    return [c for c in comments if c.id > since_comment_id]


def get_assignee_login(repo: str, issue_number: int) -> str | None:
    issue = get_issue(repo, issue_number)
    if issue.assignee:
        return issue.assignee.login
    return None
