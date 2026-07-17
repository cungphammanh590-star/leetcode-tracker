"""提交记录查询。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Any, Optional


def get_submission_by_id(
    conn: sqlite3.Connection, submission_id: str
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT s.submission_id, s.problem_id, s.status, s.code, s.runtime_ms,
               s.memory_mb, s.language, s.submitted_at,
               p.title, p.slug, p.difficulty, p.tags
        FROM submissions s
        LEFT JOIN problems p ON p.problem_id = s.problem_id
        WHERE s.submission_id = ?
        """,
        (submission_id,),
    ).fetchone()
    return dict(row) if row else None


def get_latest_submission_for_problem(
    conn: sqlite3.Connection, problem_id: int
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT s.submission_id, s.problem_id, s.status, s.runtime_ms,
               s.memory_mb, s.language, s.submitted_at,
               p.title, p.slug, p.difficulty
        FROM submissions s
        LEFT JOIN problems p ON p.problem_id = s.problem_id
        WHERE s.problem_id = ?
        ORDER BY s.submitted_at DESC, s.id DESC
        LIMIT 1
        """,
        (problem_id,),
    ).fetchone()
    return dict(row) if row else None


def get_problem_id_by_slug(
    conn: sqlite3.Connection, slug: str
) -> Optional[int]:
    row = conn.execute(
        "SELECT problem_id FROM problems WHERE slug = ? LIMIT 1",
        (slug,),
    ).fetchone()
    if row:
        return int(row["problem_id"])
    return None


def count_today_attempts_for_problem(
    conn: sqlite3.Connection, problem_id: int, *, day: date | None = None
) -> int:
    day = day or datetime.now().astimezone().date()
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM submissions
        WHERE problem_id = ? AND date(submitted_at, 'localtime') = ?
        """,
        (problem_id, day.isoformat()),
    ).fetchone()
    return int(row["c"] if row else 0)
