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


def get_or_create_session(
    conn: sqlite3.Connection,
    *,
    submission_id: str,
    problem_id: int,
    opening: str,
    context_markdown: str,
) -> tuple[dict[str, Any], bool]:
    """原子获取或创建提交级会话；返回 (session, created)。"""
    ensure_coach_session_schema(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM coach_sessions
            WHERE submission_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (submission_id,),
        ).fetchone()
        if row:
            conn.commit()
            return dict(row), False

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
            "context_markdown": context_markdown,
            "thread_id": session_id,
            "created_at": now,
            "updated_at": now,
        }, True
    except Exception:
        conn.rollback()
        raise


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict[str, Any]]:
    ensure_coach_session_schema(conn)
    row = conn.execute(
        "SELECT * FROM coach_sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return dict(row) if row else None


def get_latest_session_for_submission(
    conn: sqlite3.Connection, submission_id: str
) -> Optional[dict[str, Any]]:
    ensure_coach_session_schema(conn)
    row = conn.execute(
        """
        SELECT * FROM coach_sessions
        WHERE submission_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (submission_id,),
    ).fetchone()
    return dict(row) if row else None


def get_latest_session_for_problem(
    conn: sqlite3.Connection, problem_id: int
) -> Optional[dict[str, Any]]:
    ensure_coach_session_schema(conn)
    row = conn.execute(
        """
        SELECT * FROM coach_sessions
        WHERE problem_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (problem_id,),
    ).fetchone()
    return dict(row) if row else None


def touch_session(conn: sqlite3.Connection, session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE coach_sessions SET updated_at = ? WHERE session_id = ?",
        (now, session_id),
    )
    conn.commit()
