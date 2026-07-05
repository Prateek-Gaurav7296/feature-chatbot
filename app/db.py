"""Database layer: SQLite (local dev) or Postgres/Supabase (production)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import settings

SQLITE_PATH = "featurebot_map.db"

_ISSUE_THREAD_MAP_DDL = """
CREATE TABLE IF NOT EXISTS issue_thread_map (
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    thread_id TEXT NOT NULL,
    PRIMARY KEY (repo, issue_number)
)
"""

_THREAD_REPO_MAP_DDL = """
CREATE TABLE IF NOT EXISTS thread_repo_map (
    thread_id TEXT PRIMARY KEY,
    repo TEXT NOT NULL
)
"""


def _uses_postgres() -> bool:
    return settings.DATABASE_URL.startswith(("postgres://", "postgresql://"))


@contextmanager
def _sqlite_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _postgres_conn():
    from psycopg import connect

    with connect(settings.DATABASE_URL, autocommit=True) as conn:
        yield conn


@contextmanager
def _conn():
    if _uses_postgres():
        with _postgres_conn() as conn:
            yield conn
    else:
        with _sqlite_conn() as conn:
            yield conn


def init_db():
    with _conn() as conn:
        if _uses_postgres():
            conn.execute(_ISSUE_THREAD_MAP_DDL)
            conn.execute(_THREAD_REPO_MAP_DDL)
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_issue_thread_map_thread_id
                ON issue_thread_map (thread_id)
                """
            )
        else:
            conn.execute(_ISSUE_THREAD_MAP_DDL)
            conn.execute(_THREAD_REPO_MAP_DDL)


def save_mapping(issue_number: int, thread_id: str, repo: str):
    with _conn() as conn:
        if _uses_postgres():
            conn.execute(
                """
                INSERT INTO issue_thread_map (repo, issue_number, thread_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (repo, issue_number) DO UPDATE SET thread_id = EXCLUDED.thread_id
                """,
                (repo, issue_number, thread_id),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO issue_thread_map (repo, issue_number, thread_id) VALUES (?, ?, ?)",
                (repo, issue_number, thread_id),
            )


def get_thread_id(repo: str, issue_number: int) -> str | None:
    with _conn() as conn:
        if _uses_postgres():
            row = conn.execute(
                "SELECT thread_id FROM issue_thread_map WHERE repo = %s AND issue_number = %s",
                (repo, issue_number),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT thread_id FROM issue_thread_map WHERE repo = ? AND issue_number = ?",
                (repo, issue_number),
            ).fetchone()
        return row[0] if row else None


def set_thread_repo(thread_id: str, repo: str):
    with _conn() as conn:
        if _uses_postgres():
            conn.execute(
                """
                INSERT INTO thread_repo_map (thread_id, repo)
                VALUES (%s, %s)
                ON CONFLICT (thread_id) DO UPDATE SET repo = EXCLUDED.repo
                """,
                (thread_id, repo),
            )
        else:
            conn.execute(
                """
                INSERT INTO thread_repo_map (thread_id, repo) VALUES (?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET repo=excluded.repo
                """,
                (thread_id, repo),
            )


def get_thread_repo(thread_id: str) -> str | None:
    with _conn() as conn:
        if _uses_postgres():
            row = conn.execute(
                "SELECT repo FROM thread_repo_map WHERE thread_id = %s",
                (thread_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT repo FROM thread_repo_map WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
        return row[0] if row else None
