import json
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.clients import github_client, chat_client, email_client
from app.graph.state import IssueState

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.GROQ_API_KEY, temperature=0)

PARSE_PROMPT = """You turn a short, informal feature request into a structured \
GitHub issue. Respond with ONLY valid JSON, no markdown fences, no preamble. \
Schema: {{"title": str, "body": str, "labels": [str]}}. \
The body should have "## Description" and "## Acceptance Criteria" sections \
(acceptance criteria as a markdown checklist). Labels should be chosen from: \
feature, bug, chore, ui, backend, urgent - pick 1-2 that fit."""


def parse_request_node(state: IssueState) -> IssueState:
    raw = state["raw_request"]
    resp = llm.invoke(
        [SystemMessage(content=PARSE_PROMPT), HumanMessage(content=raw)]
    )
    try:
        parsed = json.loads(resp.content)
    except json.JSONDecodeError:
        # fallback: don't let a bad LLM response break the pipeline
        parsed = {
            "title": raw[:60],
            "body": f"## Description\n{raw}\n\n## Acceptance Criteria\n- [ ] TBD",
            "labels": ["feature"],
        }
    state["title"] = parsed["title"]
    state["body"] = parsed["body"]
    state["labels"] = parsed.get("labels", ["feature"])
    state["status"] = "drafted"
    return state


def create_issue_node(state: IssueState) -> IssueState:
    result = github_client.create_issue(
        title=state["title"], body=state["body"], labels=state.get("labels")
    )
    state["issue_number"] = result["number"]
    state["issue_url"] = result["url"]
    state["status"] = "created"
    return state


def notify_chat_created_node(state: IssueState) -> IssueState:
    chat_client.post_message(
        space_name=state["thread_id"],
        text=(
            f"✅ Created issue #{state['issue_number']}: *{state['title']}*\n"
            f"{state['issue_url']}\n"
            f"Waiting for it to be assigned on GitHub."
        ),
    )
    state["status"] = "awaiting_assignment"
    return state


def ask_assignee_email_node(state: IssueState) -> IssueState:
    assignee = state.get("assignee", "someone")
    chat_client.post_message(
        space_name=state["thread_id"],
        text=(
            f"🎯 Issue #{state['issue_number']} was just assigned to {assignee}. "
            f"Could you reply with their email so I can notify them?"
        ),
    )
    state["status"] = "awaiting_email"
    return state


def send_assignment_email_node(state: IssueState) -> IssueState:
    email = state.get("assignee_email")
    if email:
        email_client.send_assignment_email(
            to_email=email,
            issue_title=state["title"],
            issue_url=state["issue_url"],
        )
        chat_client.post_message(
            space_name=state["thread_id"],
            text=f"📧 Notified {email} about issue #{state['issue_number']}.",
        )
    state["status"] = "in_progress"
    return state


def sync_comments_node(state: IssueState) -> IssueState:
    new_comments = github_client.get_new_comments(
        state["issue_number"], state.get("last_comment_id")
    )
    for c in new_comments:
        chat_client.post_message(
            space_name=state["thread_id"],
            text=f"💬 {c.user.login} commented on #{state['issue_number']}: {c.body}",
        )
        state["last_comment_id"] = c.id
    return state


def issue_closed_node(state: IssueState) -> IssueState:
    chat_client.post_message(
        space_name=state["thread_id"],
        text=f"🎉 Issue #{state['issue_number']} closed: *{state['title']}*",
    )
    state["status"] = "closed"
    return state
