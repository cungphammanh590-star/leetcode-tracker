"""陪练会话元数据（与 LangGraph checkpoint 同库）。"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def ensure_coach_session_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coach_sessions (
            session_id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            problem_id INTEGER NOT NULL,
            opening TEXT NOT NULL,
            context_markdown TEXT,
            thread_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_coach_sessions_submission ON coach_sessions(submission_id)"
    )
    conn.commit()


def create_session(
    conn: sqlite3.Connection,
    *,
    submission_id: str,
    problem_id: int,
    opening: str,
    context_markdown: str,
) -> dict[str, Any]:
    ensure_coach_session_schema(conn)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO coach_sessions (
            session_id, submission_id, problem_id, opening,
            context_markdown, thread_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            submission_id,
            problem_id,
            opening,
            context_markdown,
            session_id,
            now,
            now,
        ),
    )
    conn.commit()
    return {
        "session_id": session_id,
        "submission_id": submission_id,
        "problem_id": problem_id,
        "opening": opening,
        "thread_id": session_id,
        "created_at": now,
    }


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict[str, Any]]:
    ensure_coach_session_schema(conn)
    row = conn.execute(
        "SELECT * FROM coach_sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return dict(row) if row else None


def touch_session(conn: sqlite3.Connection, session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE coach_sessions SET updated_at = ? WHERE session_id = ?",
        (now, session_id),
    )
    conn.commit()
