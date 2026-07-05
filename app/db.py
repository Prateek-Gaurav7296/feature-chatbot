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
                issue_number INTEGER PRIMARY KEY,
                thread_id TEXT NOT NULL,
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
            "INSERT OR REPLACE INTO issue_thread_map (issue_number, thread_id, repo) VALUES (?, ?, ?)",
            (issue_number, thread_id, repo),
        )


def get_thread_id(issue_number: int) -> str | None:
    with _conn() as c:
        row = c.execute(
            "SELECT thread_id FROM issue_thread_map WHERE issue_number = ?",
            (issue_number,),
        ).fetchone()
        return row[0] if row else None
