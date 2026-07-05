from typing import TypedDict, Optional, List


class IssueState(TypedDict, total=False):
    # identity
    thread_id: str
    repo: str
    issue_number: Optional[int]
    issue_url: Optional[str]

    # content
    raw_request: str
    title: str
    body: str
    labels: List[str]

    # lifecycle
    status: str  # drafted -> created -> awaiting_assignment -> assigned -> in_progress -> closed
    assignee: Optional[str]
    assignee_email: Optional[str]

    # comment sync bookkeeping
    last_comment_id: Optional[int]

    # event-driven input (set fresh each time we re-invoke the graph)
    event_type: Optional[str]  # "chat_message" | "github_assigned" | "github_comment" | "chat_email_reply"
    event_payload: Optional[dict]
