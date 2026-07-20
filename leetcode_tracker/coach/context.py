"""陪练上下文组装。"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from leetcode_tracker.kg.queries import format_kg_context_markdown
from leetcode_tracker.submissions import (
    count_today_attempts_for_problem,
    get_latest_submission_for_problem,
    get_submission_by_id,
)


def _recent_attempts_markdown(
    conn: sqlite3.Connection, problem_id: int, *, limit: int = 5
) -> str:
    rows = conn.execute(
        """
        SELECT status, submitted_at
        FROM submissions
        WHERE problem_id = ?
        ORDER BY submitted_at DESC, id DESC
        LIMIT ?
        """,
        (problem_id, limit),
    ).fetchall()
    if not rows:
        return ""
    items = [f"- {row['submitted_at']}: {row['status']}" for row in rows]
    return "## 该题最近尝试\n" + "\n".join(items)


def build_coach_context(
    conn: sqlite3.Connection,
    submission_id: str = "",
    *,
    problem_id: Optional[int] = None,
) -> dict[str, Any]:
    """构建上下文；精确提交缺失时可显式按题回退到最近提交。"""
    requested_submission_id = str(submission_id or "").strip()
    sub = (
        get_submission_by_id(conn, requested_submission_id)
        if requested_submission_id
        else None
    )
    fallback_used = False
    if sub is None:
        if problem_id is None:
            if requested_submission_id:
                raise ValueError(f"未找到提交: {requested_submission_id}")
            raise ValueError("需要 submission_id 或 problem_id")
        sub = get_latest_submission_for_problem(conn, int(problem_id))
        if sub is None:
            raise ValueError(
                f"未找到提交: {requested_submission_id or '—'}；"
                f"题目 {problem_id} 也没有可回退的历史提交"
            )
        fallback_used = True

    resolved_problem_id = int(sub["problem_id"])
    today_count = count_today_attempts_for_problem(conn, resolved_problem_id)
    kg_md, placement = format_kg_context_markdown(conn, resolved_problem_id)

    runtime = (
        f"{sub['runtime_ms']}ms" if sub.get("runtime_ms") is not None else "—"
    )
    title = sub.get("title") or f"Problem {resolved_problem_id}"
    difficulty = sub.get("difficulty") or "—"

    submission_md = f"""## 本次提交
- 题目：{resolved_problem_id}. {title}（{difficulty}）
- 状态：{sub['status']}
- 语言：{sub.get('language') or '—'}
- 用时：{runtime}
- 今日该题第 {today_count} 次提交
"""
    recent_md = _recent_attempts_markdown(conn, resolved_problem_id)
    markdown = "\n".join(part for part in (submission_md, recent_md, kg_md) if part)
    resolved_submission_id = str(sub["submission_id"])
    return {
        "submission_id": resolved_submission_id,
        "requested_submission_id": requested_submission_id or resolved_submission_id,
        "resolved_submission_id": resolved_submission_id,
        "fallback_used": fallback_used,
        "problem_id": resolved_problem_id,
        "status": sub["status"],
        "title": title,
        "difficulty": difficulty,
        "markdown": markdown,
        "placement": placement,
        "today_count": today_count,
    }
