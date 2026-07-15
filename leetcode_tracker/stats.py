"""统计查询（供 stats、report、仪表盘复用）。"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional


@dataclass
class OverviewStats:
    total_submissions: int
    accepted_count: int
    acceptance_rate: float
    easy_solved: int
    medium_solved: int
    hard_solved: int
    today_submissions: int
    today_accepted: int
    today_acceptance_rate: float
    streak_days: int
    recent: list[dict[str, Any]]
    today_items: list[dict[str, Any]]
    today_wrong: list[dict[str, Any]] = field(default_factory=list)
    last7: list[dict[str, Any]] = field(default_factory=list)


def _rate(accepted: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * accepted / total, 1)


def _local_today() -> date:
    return datetime.now().astimezone().date()


def compute_streak(conn: sqlite3.Connection, today: Optional[date] = None) -> int:
    today = today or _local_today()
    rows = conn.execute(
        "SELECT DISTINCT date(submitted_at, 'localtime') AS d FROM submissions ORDER BY d DESC"
    ).fetchall()
    days = {date.fromisoformat(row["d"]) for row in rows if row["d"]}
    if not days:
        return 0

    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0

    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "submission_id": row["submission_id"],
        "problem_id": row["problem_id"],
        "title": row["title"],
        "slug": row["slug"],
        "difficulty": row["difficulty"],
        "status": row["status"],
        "runtime_ms": row["runtime_ms"],
        "memory_mb": row["memory_mb"],
        "language": row["language"],
        "submitted_at": row["submitted_at"],
    }


def get_today_wrong(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict[str, Any]]:
    today = today or _local_today()
    rows = conn.execute(
        """
        SELECT s.submission_id, s.problem_id, p.title, p.slug, p.difficulty,
               s.status, s.runtime_ms, s.memory_mb, s.language, s.submitted_at
        FROM submissions s
        JOIN problems p ON p.problem_id = s.problem_id
        WHERE date(s.submitted_at, 'localtime') = ?
          AND s.status != 'Accepted'
        ORDER BY s.submitted_at DESC, s.id DESC
        """,
        (today.isoformat(),),
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def get_last7_days(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict[str, Any]]:
    today = today or _local_today()
    result: list[dict[str, Any]] = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        total = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM submissions
                WHERE date(submitted_at, 'localtime') = ?
                """,
                (day_str,),
            ).fetchone()["c"]
        )
        accepted = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM submissions
                WHERE date(submitted_at, 'localtime') = ? AND status = 'Accepted'
                """,
                (day_str,),
            ).fetchone()["c"]
        )
        result.append(
            {
                "date": day_str,
                "submissions": total,
                "accepted": accepted,
            }
        )
    return result


def get_overview(conn: sqlite3.Connection, *, recent_limit: int = 20) -> OverviewStats:
    today = _local_today()
    today_str = today.isoformat()

    total = int(conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"])
    accepted = int(
        conn.execute(
            "SELECT COUNT(*) AS c FROM submissions WHERE status = 'Accepted'"
        ).fetchone()["c"]
    )

    def solved(diff: str) -> int:
        return int(
            conn.execute(
                """
                SELECT COUNT(DISTINCT s.problem_id) AS c
                FROM submissions s
                JOIN problems p ON p.problem_id = s.problem_id
                WHERE s.status = 'Accepted' AND p.difficulty = ?
                """,
                (diff,),
            ).fetchone()["c"]
        )

    today_total = int(
        conn.execute(
            """
            SELECT COUNT(*) AS c FROM submissions
            WHERE date(submitted_at, 'localtime') = ?
            """,
            (today_str,),
        ).fetchone()["c"]
    )
    today_accepted = int(
        conn.execute(
            """
            SELECT COUNT(*) AS c FROM submissions
            WHERE date(submitted_at, 'localtime') = ? AND status = 'Accepted'
            """,
            (today_str,),
        ).fetchone()["c"]
    )

    recent_rows = conn.execute(
        """
        SELECT s.submission_id, s.problem_id, p.title, p.slug, p.difficulty,
               s.status, s.runtime_ms, s.memory_mb, s.language, s.submitted_at
        FROM submissions s
        JOIN problems p ON p.problem_id = s.problem_id
        ORDER BY s.submitted_at DESC, s.id DESC
        LIMIT ?
        """,
        (recent_limit,),
    ).fetchall()

    today_rows = conn.execute(
        """
        SELECT s.submission_id, s.problem_id, p.title, p.slug, p.difficulty,
               s.status, s.runtime_ms, s.memory_mb, s.language, s.submitted_at
        FROM submissions s
        JOIN problems p ON p.problem_id = s.problem_id
        WHERE date(s.submitted_at, 'localtime') = ?
        ORDER BY s.submitted_at DESC, s.id DESC
        """,
        (today_str,),
    ).fetchall()

    return OverviewStats(
        total_submissions=total,
        accepted_count=accepted,
        acceptance_rate=_rate(accepted, total),
        easy_solved=solved("Easy"),
        medium_solved=solved("Medium"),
        hard_solved=solved("Hard"),
        today_submissions=today_total,
        today_accepted=today_accepted,
        today_acceptance_rate=_rate(today_accepted, today_total),
        streak_days=compute_streak(conn, today),
        recent=[_row_to_item(r) for r in recent_rows],
        today_items=[_row_to_item(r) for r in today_rows],
        today_wrong=get_today_wrong(conn, today),
        last7=get_last7_days(conn, today),
    )


def overview_to_dict(stats: OverviewStats) -> dict[str, Any]:
    return asdict(stats)


def format_stats_text(stats: OverviewStats) -> str:
    lines = [
        "力扣刷题统计",
        "============",
        f"今日提交: {stats.today_submissions}",
        f"今日通过: {stats.today_accepted} ({stats.today_acceptance_rate}%)",
        f"今日错题: {len(stats.today_wrong)}",
        f"累计提交: {stats.total_submissions}",
        f"累计通过: {stats.accepted_count} ({stats.acceptance_rate}%)",
        f"难度通过(去重): Easy {stats.easy_solved} / Medium {stats.medium_solved} / Hard {stats.hard_solved}",
        f"连续打卡: {stats.streak_days} 天",
        "",
        "近 7 日:",
    ]
    for day in stats.last7:
        lines.append(
            f"  {day['date']}: 提交 {day['submissions']} / 通过 {day['accepted']}"
        )
    if stats.today_wrong:
        lines.append("")
        lines.append("今日错题:")
        for item in stats.today_wrong:
            lines.append(
                f"  {item['problem_id']}. {item['title']} | {item['status']}"
            )
    lines.append("")
    lines.append(f"最近 {len(stats.recent)} 条提交:")
    for item in stats.recent:
        runtime = f"{item['runtime_ms']}ms" if item["runtime_ms"] is not None else "-"
        lines.append(
            f"  [{item['submitted_at']}] {item['problem_id']}. {item['title']} "
            f"| {item['difficulty'] or '-'} | {item['status']} | {runtime}"
        )
    return "\n".join(lines) + "\n"
