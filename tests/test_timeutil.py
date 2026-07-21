"""中国时区与历史 UTC 迁移测试。"""

from __future__ import annotations

from pathlib import Path

from leetcode_tracker.db import connect, init_db
from leetcode_tracker.migrate_tz import ensure_china_timestamps
from leetcode_tracker.stats import get_overview
from leetcode_tracker.store import save_submission
from leetcode_tracker.timeutil import (
    TZ_META_KEY,
    TZ_META_VALUE,
    calendar_day,
    china_today,
    to_china_iso,
)


def test_to_china_iso_shifts_utc_naive() -> None:
    # UTC 06:00 → 中国 14:00 同日
    assert to_china_iso("2026-07-21 06:00:00").startswith("2026-07-21T14:00:00")
    assert to_china_iso("2026-07-21T06:00:00+00:00").startswith("2026-07-21T14:00:00")


def test_calendar_day() -> None:
    assert calendar_day("2026-07-21 15:22:30") == "2026-07-21"
    assert calendar_day("2026-07-21T15:22:30.1+08:00") == "2026-07-21"


def test_migrate_utc_submissions_to_china_day(tmp_path: Path) -> None:
    path = tmp_path / "tz.sqlite"
    conn = connect(path)
    conn.executescript(
        """
        CREATE TABLE problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL UNIQUE,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            difficulty TEXT,
            tags TEXT,
            created_at DATETIME
        );
        CREATE TABLE submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id TEXT NOT NULL UNIQUE,
            problem_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            code TEXT,
            runtime_ms INTEGER,
            memory_mb REAL,
            language TEXT,
            submitted_at DATETIME
        );
        CREATE TABLE problem_stats (
            problem_id INTEGER PRIMARY KEY,
            title TEXT,
            title_slug TEXT,
            difficulty TEXT,
            topic_tags TEXT,
            total_attempts INTEGER DEFAULT 0,
            accepted_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            status_breakdown TEXT,
            first_attempt_at DATETIME,
            last_attempt_at DATETIME,
            first_accepted_at DATETIME,
            acceptance_rate REAL DEFAULT 0.0,
            struggle_score REAL DEFAULT 0.0,
            solve_time_seconds INTEGER,
            avg_attempts_to_ac REAL,
            attempts_at_last_ac INTEGER DEFAULT 0,
            last_status TEXT,
            last_submitted_at DATETIME,
            llm_summary TEXT,
            common_pitfall TEXT,
            updated_at DATETIME
        );
        CREATE TABLE problem_daily_stats (
            problem_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            accepted_today INTEGER DEFAULT 0,
            wrong_today INTEGER DEFAULT 0,
            status_breakdown TEXT,
            consecutive_days INTEGER DEFAULT 0,
            is_new_today INTEGER DEFAULT 0,
            is_review_today INTEGER DEFAULT 0,
            status_change TEXT,
            PRIMARY KEY (problem_id, day)
        );
        """
    )
    conn.execute(
        "INSERT INTO problems (problem_id, title, slug, created_at) VALUES (1, 'Two Sum', 'two-sum', '2026-07-20 16:00:00')"
    )
    # UTC 16:00 = 中国次日 00:00，切日后应算 7-21
    conn.execute(
        """
        INSERT INTO submissions (submission_id, problem_id, status, submitted_at)
        VALUES ('s1', 1, 'Accepted', '2026-07-20 16:00:00')
        """
    )
    conn.commit()

    assert ensure_china_timestamps(conn) is True
    assert ensure_china_timestamps(conn) is False  # 幂等

    row = conn.execute(
        "SELECT submitted_at FROM submissions WHERE submission_id = 's1'"
    ).fetchone()
    assert str(row["submitted_at"]) == "2026-07-21 00:00:00"

    meta = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?", (TZ_META_KEY,)
    ).fetchone()
    assert meta["value"] == TZ_META_VALUE

    daily = conn.execute(
        "SELECT day, attempts FROM problem_daily_stats WHERE problem_id = 1"
    ).fetchone()
    assert daily["day"] == "2026-07-21"
    assert int(daily["attempts"]) == 1
    conn.close()


def test_new_submission_uses_china_wall_clock(tmp_path: Path) -> None:
    path = tmp_path / "new.sqlite"
    conn = init_db(connect(path))
    try:
        save_submission(
            conn,
            {
                "submission_id": "s-new",
                "problem_id": 2,
                "title": "Add Two",
                "slug": "add-two",
                "status": "Wrong Answer",
                "language": "java",
            },
        )
        row = conn.execute(
            "SELECT submitted_at FROM submissions WHERE submission_id = 's-new'"
        ).fetchone()
        submitted_at = str(row["submitted_at"])
        assert "+" not in submitted_at
        assert calendar_day(submitted_at) == china_today().isoformat()
        overview = get_overview(conn)
        assert overview.today_submissions >= 1
    finally:
        conn.close()
