"""陪练上下文组装。"""

from __future__ import annotations

import sqlite3
from typing import Any

from leetcode_tracker.kg.queries import format_kg_context_markdown
from leetcode_tracker.submissions import count_today_attempts_for_problem, get_submission_by_id


def build_coach_context(conn: sqlite3.Connection, submission_id: str) -> dict[str, Any]:
    sub = get_submission_by_id(conn, submission_id)
    if sub is None:
        raise ValueError(f"未找到提交: {submission_id}")

    problem_id = int(sub["problem_id"])
    today_count = count_today_attempts_for_problem(conn, problem_id)
    kg_md, placement = format_kg_context_markdown(conn, problem_id)

    runtime = (
        f"{sub['runtime_ms']}ms" if sub.get("runtime_ms") is not None else "—"
    )
    title = sub.get("title") or f"Problem {problem_id}"
    difficulty = sub.get("difficulty") or "—"

    submission_md = f"""## 本次提交
- 题目：{problem_id}. {title}（{difficulty}）
- 状态：{sub['status']}
- 语言：{sub.get('language') or '—'}
- 用时：{runtime}
- 今日该题第 {today_count} 次提交
"""

    markdown = f"{submission_md}\n{kg_md}"
    return {
        "submission_id": submission_id,
        "problem_id": problem_id,
        "status": sub["status"],
        "title": title,
        "difficulty": difficulty,
        "markdown": markdown,
        "placement": placement,
        "today_count": today_count,
    }
