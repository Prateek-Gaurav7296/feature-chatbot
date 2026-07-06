"""
The graph is re-invoked many times over an issue's life, each time with a
different `event_type` in state. Instead of one long linear chain, we use a
router at the entry point that dispatches to the right node based on what
just happened. This is the pattern to internalize: LangGraph graphs for
event-driven systems are usually "hub and spoke", not a straight line.
"""
from langgraph.graph import StateGraph, END

from app.config import settings
from app.graph.state import IssueState
from app.graph.nodes import (
    parse_request_node,
    create_issue_node,
    notify_chat_created_node,
    ask_assignee_email_node,
    send_assignment_email_node,
    sync_comments_node,
    issue_closed_node,
)


def route_event(state: IssueState) -> str:
    event = state.get("event_type")
    if event == "chat_message":
        return "parse_request"
    if event == "github_assigned":
        return "ask_assignee_email"
    if event == "chat_email_reply":
        return "send_assignment_email"
    if event == "github_comment":
        return "sync_comments"
    if event == "github_closed":
        return "issue_closed"
    return "noop"


def _build_checkpointer():
    url = settings.DATABASE_URL
    if url.startswith(("postgres://", "postgresql://")):
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver

        pool = ConnectionPool(
            conninfo=url,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
        return checkpointer

    from langgraph.checkpoint.sqlite import SqliteSaver

    memory = SqliteSaver.from_conn_string("featurebot_graph.db")
    return memory


def build_graph():
    graph = StateGraph(IssueState)

    graph.add_node("parse_request", parse_request_node)
    graph.add_node("create_issue", create_issue_node)
    graph.add_node("notify_chat_created", notify_chat_created_node)
    graph.add_node("ask_assignee_email", ask_assignee_email_node)
    graph.add_node("send_assignment_email", send_assignment_email_node)
    graph.add_node("sync_comments", sync_comments_node)
    graph.add_node("issue_closed", issue_closed_node)
    graph.add_node("noop", lambda state: state)

    graph.set_conditional_entry_point(
        route_event,
        {
            "parse_request": "parse_request",
            "ask_assignee_email": "ask_assignee_email",
            "send_assignment_email": "send_assignment_email",
            "sync_comments": "sync_comments",
            "issue_closed": "issue_closed",
            "noop": "noop",
        },
    )

    graph.add_edge("parse_request", "create_issue")
    graph.add_edge("create_issue", "notify_chat_created")
    graph.add_edge("notify_chat_created", END)

    graph.add_edge("ask_assignee_email", END)
    graph.add_edge("send_assignment_email", END)
    graph.add_edge("sync_comments", END)
    graph.add_edge("issue_closed", END)
    graph.add_edge("noop", END)

    return graph.compile(checkpointer=_build_checkpointer())


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
