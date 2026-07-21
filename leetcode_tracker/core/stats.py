"""统计查询（供 stats、仪表盘复用）。"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from leetcode_tracker.core.problem_stats import ensure_stats_materialized, get_today_wrong_summary
from leetcode_tracker.infra.timeutil import china_today


@dataclass
class OverviewStats:
    date: str
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


def compute_streak(conn: sqlite3.Connection, today: Optional[date] = None) -> int:
    today = today or china_today()
    rows = conn.execute(
        "SELECT DISTINCT date(submitted_at) AS d FROM submissions ORDER BY d DESC"
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
    today = today or china_today()
    rows = conn.execute(
        """
        SELECT s.submission_id, s.problem_id, p.title, p.slug, p.difficulty,
               s.status, s.runtime_ms, s.memory_mb, s.language, s.submitted_at
        FROM submissions s
        JOIN problems p ON p.problem_id = s.problem_id
        WHERE date(s.submitted_at) = ?
          AND s.status != 'Accepted'
        ORDER BY s.submitted_at DESC, s.id DESC
        """,
        (today.isoformat(),),
    ).fetchall()
    return [_row_to_item(r) for r in rows]


def summarize_today_wrong(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按题目汇总今日错题，每种错误类型统计次数。"""
    grouped: dict[int, dict[str, Any]] = {}
    for item in items:
        pid = int(item["problem_id"])
        bucket = grouped.get(pid)
        if bucket is None:
            bucket = {
                "problem_id": pid,
                "title": item["title"],
                "slug": item["slug"],
                "difficulty": item["difficulty"],
                "total": 0,
                "status_counts": {},
            }
            grouped[pid] = bucket
        if item["difficulty"] and not bucket["difficulty"]:
            bucket["difficulty"] = item["difficulty"]
        status = str(item["status"])
        counts = bucket["status_counts"]
        counts[status] = int(counts.get(status, 0)) + 1
        bucket["total"] += 1

    result = list(grouped.values())
    for bucket in result:
        counts = bucket["status_counts"]
        bucket["status_counts"] = dict(
            sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        )
    result.sort(key=lambda row: (-int(row["total"]), int(row["problem_id"])))
    return result


def format_status_counts(status_counts: dict[str, int]) -> str:
    if not status_counts:
        return "-"
    return ", ".join(f"{status}×{count}" for status, count in status_counts.items())


def get_last7_days(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict[str, Any]]:
    today = today or china_today()
    result: list[dict[str, Any]] = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        total = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM submissions
                WHERE date(submitted_at) = ?
                """,
                (day_str,),
            ).fetchone()["c"]
        )
        accepted = int(
            conn.execute(
                """
                SELECT COUNT(*) AS c FROM submissions
                WHERE date(submitted_at) = ? AND status = 'Accepted'
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


def get_overview(
    conn: sqlite3.Connection,
    *,
    day: Optional[date] = None,
    recent_limit: int = 20,
) -> OverviewStats:
    """概览。day 为中国时区日历日；缺省为今天。today_* 字段表示所选日切片。"""
    ensure_stats_materialized(conn)
    selected = day or china_today()
    day_str = selected.isoformat()

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

    day_total = int(
        conn.execute(
            """
            SELECT COUNT(*) AS c FROM submissions
            WHERE date(submitted_at) = ?
            """,
            (day_str,),
        ).fetchone()["c"]
    )
    day_accepted = int(
        conn.execute(
            """
            SELECT COUNT(*) AS c FROM submissions
            WHERE date(submitted_at) = ? AND status = 'Accepted'
            """,
            (day_str,),
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

    day_rows = conn.execute(
        """
        SELECT s.submission_id, s.problem_id, p.title, p.slug, p.difficulty,
               s.status, s.runtime_ms, s.memory_mb, s.language, s.submitted_at
        FROM submissions s
        JOIN problems p ON p.problem_id = s.problem_id
        WHERE date(s.submitted_at) = ?
        ORDER BY s.submitted_at DESC, s.id DESC
        """,
        (day_str,),
    ).fetchall()

    day_wrong = get_today_wrong_summary(conn, selected)

    return OverviewStats(
        date=day_str,
        total_submissions=total,
        accepted_count=accepted,
        acceptance_rate=_rate(accepted, total),
        easy_solved=solved("Easy"),
        medium_solved=solved("Medium"),
        hard_solved=solved("Hard"),
        today_submissions=day_total,
        today_accepted=day_accepted,
        today_acceptance_rate=_rate(day_accepted, day_total),
        streak_days=compute_streak(conn, selected),
        recent=[_row_to_item(r) for r in recent_rows],
        today_items=[_row_to_item(r) for r in day_rows],
        today_wrong=day_wrong,
        last7=get_last7_days(conn, selected),
    )


def overview_to_dict(stats: OverviewStats) -> dict[str, Any]:
    return asdict(stats)


def format_stats_text(stats: OverviewStats) -> str:
    lines = [
        "力扣刷题统计",
        "============",
        f"今日提交: {stats.today_submissions}",
        f"今日通过: {stats.today_accepted} ({stats.today_acceptance_rate}%)",
        f"今日错题: {sum(item['total'] for item in stats.today_wrong)}",
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
            summary = format_status_counts(item["status_counts"])
            lines.append(
                f"  {item['problem_id']}. {item['title']} | "
                f"{item['difficulty'] or '-'} | {summary}"
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
