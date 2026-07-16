"""题目汇总：终身画像 (problem_stats) + 每日快照 (problem_daily_stats)。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

ACCEPTED = "Accepted"


def _local_day(dt_str: str) -> str:
    return str(dt_str)[:10]


def _parse_ts(dt_str: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str[:19], fmt)
        except ValueError:
            continue
    return None


def _solve_time_seconds(first_attempt_at: Optional[str], first_accepted_at: Optional[str]) -> Optional[int]:
    if not first_attempt_at or not first_accepted_at:
        return None
    start = _parse_ts(first_attempt_at)
    end = _parse_ts(first_accepted_at)
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds()))


def _tags_json(tags: Any) -> Optional[str]:
    if tags is None:
        return None
    if isinstance(tags, str):
        return tags
    if isinstance(tags, (list, tuple)):
        return json.dumps(list(tags), ensure_ascii=False)
    return str(tags)


def _tags_list(tags_json: Optional[str]) -> list[str]:
    if not tags_json:
        return []
    try:
        value = json.loads(tags_json)
        if isinstance(value, list):
            return [str(x) for x in value]
    except json.JSONDecodeError:
        pass
    return []


def breakdown_from_json(raw: Optional[str]) -> dict[str, int]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): int(v) for k, v in data.items()}


def breakdown_to_json(counts: dict[str, int]) -> str:
    ordered = dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    return json.dumps(ordered, ensure_ascii=False)


def _inc_breakdown(counts: dict[str, int], status: str) -> None:
    counts[status] = int(counts.get(status, 0)) + 1


def _rates(total: int, accepted: int, wrong: int) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    return (
        round(accepted / total, 4),
        round(wrong / total, 4),
    )


@dataclass
class _DailyBucket:
    attempts: int = 0
    accepted_today: int = 0
    wrong_today: int = 0
    breakdown: dict[str, int] = field(default_factory=dict)
    had_ac: bool = False
    had_wrong: bool = False


@dataclass
class _LifetimeAcc:
    problem_id: int
    title: str
    title_slug: str
    difficulty: Optional[str]
    topic_tags: Optional[str]
    total_attempts: int = 0
    accepted_count: int = 0
    wrong_count: int = 0
    breakdown: dict[str, int] = field(default_factory=dict)
    first_attempt_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    first_accepted_at: Optional[str] = None
    attempts_at_last_ac: int = 0
    avg_attempts_to_ac: Optional[float] = None
    last_status: Optional[str] = None
    last_submitted_at: Optional[str] = None


def _status_change(
    *,
    day: str,
    bucket: _DailyBucket,
    prev_bucket: Optional[_DailyBucket],
    first_accepted_at: Optional[str],
    had_ac_before_day: bool,
) -> Optional[str]:
    if bucket.had_ac:
        if first_accepted_at and _local_day(first_accepted_at) == day:
            return "first_ac"
        return "improved"
    if bucket.had_wrong:
        if prev_bucket and prev_bucket.had_wrong:
            return "stuck"
        if had_ac_before_day:
            return "declined"
    return None


def _consecutive_days(day_rows: dict[str, _DailyBucket], day: str) -> int:
    current = date.fromisoformat(day)
    streak = 0
    while True:
        key = current.isoformat()
        bucket = day_rows.get(key)
        if not bucket or bucket.attempts <= 0:
            break
        streak += 1
        current -= timedelta(days=1)
    return streak


def _apply_submission_to_lifetime(state: _LifetimeAcc, status: str, submitted_at: str) -> None:
    state.total_attempts += 1
    _inc_breakdown(state.breakdown, status)
    if state.first_attempt_at is None:
        state.first_attempt_at = submitted_at
    state.last_attempt_at = submitted_at
    state.last_submitted_at = submitted_at
    state.last_status = status

    if status == ACCEPTED:
        state.accepted_count += 1
        if state.first_accepted_at is None:
            state.first_accepted_at = submitted_at
        state.avg_attempts_to_ac = float(state.total_attempts - state.attempts_at_last_ac)
        state.attempts_at_last_ac = state.total_attempts
    else:
        state.wrong_count += 1


def _apply_submission_to_daily(bucket: _DailyBucket, status: str) -> None:
    bucket.attempts += 1
    _inc_breakdown(bucket.breakdown, status)
    if status == ACCEPTED:
        bucket.accepted_today += 1
        bucket.had_ac = True
    else:
        bucket.wrong_today += 1
        bucket.had_wrong = True


def _write_lifetime_row(conn: sqlite3.Connection, state: _LifetimeAcc) -> None:
    acceptance_rate, struggle_score = _rates(
        state.total_attempts, state.accepted_count, state.wrong_count
    )
    conn.execute(
        """
        INSERT INTO problem_stats (
            problem_id, title, title_slug, difficulty, topic_tags,
            total_attempts, accepted_count, wrong_count, status_breakdown,
            first_attempt_at, last_attempt_at, first_accepted_at,
            acceptance_rate, struggle_score, solve_time_seconds,
            avg_attempts_to_ac, attempts_at_last_ac,
            last_status, last_submitted_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title = excluded.title,
            title_slug = excluded.title_slug,
            difficulty = COALESCE(excluded.difficulty, problem_stats.difficulty),
            topic_tags = COALESCE(excluded.topic_tags, problem_stats.topic_tags),
            total_attempts = excluded.total_attempts,
            accepted_count = excluded.accepted_count,
            wrong_count = excluded.wrong_count,
            status_breakdown = excluded.status_breakdown,
            first_attempt_at = excluded.first_attempt_at,
            last_attempt_at = excluded.last_attempt_at,
            first_accepted_at = excluded.first_accepted_at,
            acceptance_rate = excluded.acceptance_rate,
            struggle_score = excluded.struggle_score,
            solve_time_seconds = excluded.solve_time_seconds,
            avg_attempts_to_ac = excluded.avg_attempts_to_ac,
            attempts_at_last_ac = excluded.attempts_at_last_ac,
            last_status = excluded.last_status,
            last_submitted_at = excluded.last_submitted_at,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            state.problem_id,
            state.title,
            state.title_slug,
            state.difficulty,
            state.topic_tags,
            state.total_attempts,
            state.accepted_count,
            state.wrong_count,
            breakdown_to_json(state.breakdown),
            state.first_attempt_at,
            state.last_attempt_at,
            state.first_accepted_at,
            acceptance_rate,
            struggle_score,
            _solve_time_seconds(state.first_attempt_at, state.first_accepted_at),
            state.avg_attempts_to_ac,
            state.attempts_at_last_ac,
            state.last_status,
            state.last_submitted_at,
        ),
    )


def _write_daily_rows(
    conn: sqlite3.Connection,
    problem_id: int,
    *,
    first_attempt_at: Optional[str],
    first_accepted_at: Optional[str],
    day_rows: dict[str, _DailyBucket],
) -> None:
    first_day = _local_day(first_attempt_at) if first_attempt_at else None
    first_ac_day = _local_day(first_accepted_at) if first_accepted_at else None
    ordered_days = sorted(day_rows.keys())
    had_ac_before: dict[str, bool] = {}
    seen_ac = False
    for day in ordered_days:
        had_ac_before[day] = seen_ac
        if day_rows[day].had_ac:
            seen_ac = True

    for idx, day in enumerate(ordered_days):
        bucket = day_rows[day]
        prev = day_rows[ordered_days[idx - 1]] if idx > 0 else None
        conn.execute(
            """
            INSERT INTO problem_daily_stats (
                problem_id, day, attempts, accepted_today, wrong_today,
                status_breakdown, consecutive_days, is_new_today, is_review_today,
                status_change
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(problem_id, day) DO UPDATE SET
                attempts = excluded.attempts,
                accepted_today = excluded.accepted_today,
                wrong_today = excluded.wrong_today,
                status_breakdown = excluded.status_breakdown,
                consecutive_days = excluded.consecutive_days,
                is_new_today = excluded.is_new_today,
                is_review_today = excluded.is_review_today,
                status_change = excluded.status_change
            """,
            (
                problem_id,
                day,
                bucket.attempts,
                bucket.accepted_today,
                bucket.wrong_today,
                breakdown_to_json(bucket.breakdown),
                _consecutive_days(day_rows, day),
                1 if first_day == day else 0,
                1 if first_ac_day and first_ac_day < day and bucket.attempts > 0 else 0,
                _status_change(
                    day=day,
                    bucket=bucket,
                    prev_bucket=prev,
                    first_accepted_at=first_accepted_at,
                    had_ac_before_day=had_ac_before[day],
                ),
            ),
        )


def rebuild_stats(conn: sqlite3.Connection, *, from_scratch: bool = True) -> int:
    """从 submissions 全量重建汇总表。返回处理的题目数。"""
    if from_scratch:
        conn.execute("DELETE FROM problem_daily_stats")
        conn.execute("DELETE FROM problem_stats")

    rows = conn.execute(
        """
        SELECT s.problem_id, s.status, s.submitted_at,
               p.title, p.slug, p.difficulty, p.tags
        FROM submissions s
        JOIN problems p ON p.problem_id = s.problem_id
        ORDER BY s.problem_id ASC, s.submitted_at ASC, s.id ASC
        """
    ).fetchall()

    if not rows:
        conn.commit()
        return 0

    current_pid: Optional[int] = None
    lifetime: Optional[_LifetimeAcc] = None
    day_rows: dict[str, _DailyBucket] = {}
    processed = 0

    def flush_problem() -> None:
        nonlocal lifetime, day_rows, processed
        if lifetime is None:
            return
        _write_lifetime_row(conn, lifetime)
        _write_daily_rows(
            conn,
            lifetime.problem_id,
            first_attempt_at=lifetime.first_attempt_at,
            first_accepted_at=lifetime.first_accepted_at,
            day_rows=day_rows,
        )
        processed += 1
        day_rows = {}

    for row in rows:
        pid = int(row["problem_id"])
        if current_pid is not None and pid != current_pid:
            flush_problem()
        if current_pid != pid:
            current_pid = pid
            lifetime = _LifetimeAcc(
                problem_id=pid,
                title=row["title"],
                title_slug=row["slug"],
                difficulty=row["difficulty"],
                topic_tags=row["tags"],
            )
        assert lifetime is not None
        status = str(row["status"])
        submitted_at = str(row["submitted_at"])
        _apply_submission_to_lifetime(lifetime, status, submitted_at)
        day = _local_day(submitted_at)
        bucket = day_rows.setdefault(day, _DailyBucket())
        _apply_submission_to_daily(bucket, status)

    flush_problem()
    conn.commit()
    return processed


def sync_problem_meta(
    conn: sqlite3.Connection,
    *,
    problem_id: int,
    title: str,
    slug: str,
    difficulty: Optional[str],
    tags: Any,
) -> None:
    """upsert_problem 后同步冗余元数据到 problem_stats。"""
    conn.execute(
        """
        INSERT INTO problem_stats (
            problem_id, title, title_slug, difficulty, topic_tags, updated_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(problem_id) DO UPDATE SET
            title = excluded.title,
            title_slug = excluded.title_slug,
            difficulty = COALESCE(excluded.difficulty, problem_stats.difficulty),
            topic_tags = COALESCE(excluded.topic_tags, problem_stats.topic_tags),
            updated_at = CURRENT_TIMESTAMP
        """,
        (problem_id, title, slug, difficulty, _tags_json(tags)),
    )


def apply_submission_stats(
    conn: sqlite3.Connection,
    *,
    problem_id: int,
    status: str,
    submitted_at: str,
) -> None:
    """新提交写入后增量更新汇总表。"""
    problem = conn.execute(
        "SELECT title, slug, difficulty, tags FROM problems WHERE problem_id = ?",
        (problem_id,),
    ).fetchone()
    if problem is None:
        return

    row = conn.execute(
        "SELECT * FROM problem_stats WHERE problem_id = ?",
        (problem_id,),
    ).fetchone()
    if row is None:
        rebuild_stats(conn, from_scratch=True)
        return

    day = _local_day(submitted_at)
    had_ac_before_day = bool(
        row["first_accepted_at"] and _local_day(str(row["first_accepted_at"])) < day
    )

    state = _LifetimeAcc(
        problem_id=problem_id,
        title=problem["title"],
        title_slug=problem["slug"],
        difficulty=problem["difficulty"],
        topic_tags=problem["tags"],
        total_attempts=int(row["total_attempts"]),
        accepted_count=int(row["accepted_count"]),
        wrong_count=int(row["wrong_count"]),
        breakdown=breakdown_from_json(row["status_breakdown"]),
        first_attempt_at=row["first_attempt_at"],
        last_attempt_at=row["last_attempt_at"],
        first_accepted_at=row["first_accepted_at"],
        attempts_at_last_ac=int(row["attempts_at_last_ac"] or 0),
        avg_attempts_to_ac=row["avg_attempts_to_ac"],
        last_status=row["last_status"],
        last_submitted_at=row["last_submitted_at"],
    )
    _apply_submission_to_lifetime(state, status, submitted_at)
    _write_lifetime_row(conn, state)

    daily = conn.execute(
        "SELECT * FROM problem_daily_stats WHERE problem_id = ? AND day = ?",
        (problem_id, day),
    ).fetchone()
    bucket = _DailyBucket(
        attempts=int(daily["attempts"]) if daily else 0,
        accepted_today=int(daily["accepted_today"]) if daily else 0,
        wrong_today=int(daily["wrong_today"]) if daily else 0,
        breakdown=breakdown_from_json(daily["status_breakdown"]) if daily else {},
        had_ac=bool(daily and int(daily["accepted_today"]) > 0),
        had_wrong=bool(daily and int(daily["wrong_today"]) > 0),
    )
    _apply_submission_to_daily(bucket, status)

    prev_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    prev = conn.execute(
        "SELECT accepted_today, wrong_today FROM problem_daily_stats WHERE problem_id = ? AND day = ?",
        (problem_id, prev_day),
    ).fetchone()
    prev_bucket = None
    if prev:
        prev_bucket = _DailyBucket(
            had_ac=int(prev["accepted_today"]) > 0,
            had_wrong=int(prev["wrong_today"]) > 0,
        )

    first_day = _local_day(state.first_attempt_at) if state.first_attempt_at else day
    first_ac_day = (
        _local_day(state.first_accepted_at) if state.first_accepted_at else None
    )

    conn.execute(
        """
        INSERT INTO problem_daily_stats (
            problem_id, day, attempts, accepted_today, wrong_today,
            status_breakdown, consecutive_days, is_new_today, is_review_today,
            status_change
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(problem_id, day) DO UPDATE SET
            attempts = excluded.attempts,
            accepted_today = excluded.accepted_today,
            wrong_today = excluded.wrong_today,
            status_breakdown = excluded.status_breakdown,
            consecutive_days = excluded.consecutive_days,
            is_new_today = excluded.is_new_today,
            is_review_today = excluded.is_review_today,
            status_change = excluded.status_change
        """,
        (
            problem_id,
            day,
            bucket.attempts,
            bucket.accepted_today,
            bucket.wrong_today,
            breakdown_to_json(bucket.breakdown),
            _consecutive_days_for_problem(conn, problem_id, date.fromisoformat(day)),
            1 if first_day == day else 0,
            1 if first_ac_day and first_ac_day < day and bucket.attempts > 0 else 0,
            _status_change(
                day=day,
                bucket=bucket,
                prev_bucket=prev_bucket,
                first_accepted_at=state.first_accepted_at,
                had_ac_before_day=had_ac_before_day,
            ),
        ),
    )


def _consecutive_days_for_problem(
    conn: sqlite3.Connection, problem_id: int, day: date
) -> int:
    streak = 0
    cursor = day
    while True:
        row = conn.execute(
            """
            SELECT attempts FROM problem_daily_stats
            WHERE problem_id = ? AND day = ?
            """,
            (problem_id, cursor.isoformat()),
        ).fetchone()
        if not row or int(row["attempts"]) <= 0:
            break
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def ensure_stats_materialized(conn: sqlite3.Connection) -> None:
    """升级后若汇总表为空但已有提交，自动全量重建。"""
    submissions = int(conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"])
    stats_rows = int(conn.execute("SELECT COUNT(*) AS c FROM problem_stats").fetchone()["c"])
    if submissions > 0 and stats_rows == 0:
        rebuild_stats(conn, from_scratch=True)


def get_today_wrong_summary(
    conn: sqlite3.Connection, today: Optional[date] = None
) -> list[dict[str, Any]]:
    today = today or datetime.now().astimezone().date()
    day = today.isoformat()
    rows = conn.execute(
        """
        SELECT
            ps.problem_id,
            ps.title,
            ps.title_slug AS slug,
            ps.difficulty,
            pds.wrong_today AS total,
            pds.status_breakdown
        FROM problem_daily_stats pds
        JOIN problem_stats ps ON ps.problem_id = pds.problem_id
        WHERE pds.day = ? AND pds.wrong_today > 0
        ORDER BY pds.wrong_today DESC, ps.problem_id ASC
        """,
        (day,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        breakdown = breakdown_from_json(row["status_breakdown"])
        wrong_only = {k: v for k, v in breakdown.items() if k != ACCEPTED}
        result.append(
            {
                "problem_id": int(row["problem_id"]),
                "title": row["title"],
                "slug": row["slug"],
                "difficulty": row["difficulty"],
                "total": int(row["total"]),
                "status_counts": wrong_only,
            }
        )
    return result


def list_problem_stats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT problem_id, title, title_slug, difficulty, total_attempts,
               accepted_count, struggle_score, last_submitted_at
        FROM problem_stats
        ORDER BY last_submitted_at DESC, problem_id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_problem_stats_row(
    conn: sqlite3.Connection, problem_id: int
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM problem_stats WHERE problem_id = ?",
        (problem_id,),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["status_breakdown"] = breakdown_from_json(data.get("status_breakdown"))
    data["topic_tags"] = _tags_list(data.get("topic_tags"))
    return data


def get_daily_stats_rows(
    conn: sqlite3.Connection, problem_id: int, *, limit: int = 30
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM problem_daily_stats
        WHERE problem_id = ?
        ORDER BY day DESC
        LIMIT ?
        """,
        (problem_id, limit),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["status_breakdown"] = breakdown_from_json(item.get("status_breakdown"))
        result.append(item)
    return result


def get_problem_submissions(
    conn: sqlite3.Connection, problem_id: int, *, limit: int = 50
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT submission_id, problem_id, status, runtime_ms, memory_mb,
               language, submitted_at
        FROM submissions
        WHERE problem_id = ?
        ORDER BY submitted_at DESC, id DESC
        LIMIT ?
        """,
        (problem_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def format_daily_rows_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "| （无近期记录） | - | - | - |"
    lines: list[str] = []
    for row in reversed(rows):
        breakdown = row.get("status_breakdown") or {}
        summary = ", ".join(f"{k}×{v}" for k, v in breakdown.items()) or "-"
        lines.append(
            f"| {row['day']} | {row['attempts']} | {row['accepted_today']} | "
            f"{row.get('status_change') or '-'} | {summary} |"
        )
    return "\n".join(lines)


def get_llm_context(conn: sqlite3.Connection, problem_id: int, *, daily_limit: int = 7) -> str:
    stats = get_problem_stats_row(conn, problem_id)
    if stats is None:
        return f"未找到题目 {problem_id} 的汇总数据。请先刷题或运行 leetcode-tracker rebuild-stats。"

    daily = get_daily_stats_rows(conn, problem_id, limit=daily_limit)
    breakdown = stats.get("status_breakdown") or {}
    breakdown_text = ", ".join(f"{k}×{v}" for k, v in breakdown.items()) or "（无）"
    tags = stats.get("topic_tags") or []
    tags_text = ", ".join(tags) if tags else "（无）"
    solve_time = stats.get("solve_time_seconds")
    solve_text = f"{solve_time} 秒" if solve_time is not None else "尚未 AC"

    return f"""## 题目信息
- 标题：{stats.get('title')}（{stats.get('difficulty') or '未知'}）
- 标签：{tags_text}

## 终身表现
- 总尝试：{stats.get('total_attempts')} 次，AC {stats.get('accepted_count')} 次
- 错误分布：{breakdown_text}
- 首次 AC 耗时：{solve_text}
- 最近一次 AC 间隔尝试次数：{stats.get('avg_attempts_to_ac') if stats.get('avg_attempts_to_ac') is not None else '—'}
- 挣扎指数：{float(stats.get('struggle_score') or 0):.2f}

## 最近 {daily_limit} 天趋势
| 日期 | 尝试 | AC | 状态变化 | 当日错误分布 |
{format_daily_rows_markdown(daily)}

请基于以上数据，分析我的解题模式，指出薄弱点并给出复习建议。
"""
