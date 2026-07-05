"""
Lightweight mapping table: thread_id <-> issue_number.

This is deliberately separate from the LangGraph checkpointer (which stores
full graph state). This table's only job is fast lookup: "a GitHub webhook
just fired for issue #42 - which Chat thread does that belong to?"

Uses plain sqlite3 for simplicity. Swap for a real Postgres table if you
outgrow this - the interface (get/set) stays the same.
"""
import sqlite3
from contextlib import contextmanager

DB_PATH = "featurebot_map.db"


def init_db():
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_thread_map (
                repo TEXT NOT NULL,
                issue_number INTEGER NOT NULL,
                thread_id TEXT NOT NULL,
                PRIMARY KEY (repo, issue_number)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS thread_repo_map (
                thread_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL
            )
            """
        )


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_mapping(issue_number: int, thread_id: str, repo: str):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO issue_thread_map (repo, issue_number, thread_id) VALUES (?, ?, ?)",
            (repo, issue_number, thread_id),
        )


def get_thread_id(repo: str, issue_number: int) -> str | None:
    """Look up the Chat thread for an issue.

    Keyed by (repo, issue_number) rather than issue_number alone: issue
    numbers are only unique within a single repo, and with multiple repos
    now in play, two repos' "#5" would otherwise collide.
    """
    with _conn() as c:
        row = c.execute(
            "SELECT thread_id FROM issue_thread_map WHERE repo = ? AND issue_number = ?",
            (repo, issue_number),
        ).fetchone()
        return row[0] if row else None


def set_thread_repo(thread_id: str, repo: str):
    with _conn() as c:
        c.execute(
            """
            INSERT INTO thread_repo_map (thread_id, repo) VALUES (?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET repo=excluded.repo
            """,
            (thread_id, repo),
        )


def get_thread_repo(thread_id: str) -> str | None:
    with _conn() as c:
        row = c.execute(
            "SELECT repo FROM thread_repo_map WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        return row[0] if row else None
