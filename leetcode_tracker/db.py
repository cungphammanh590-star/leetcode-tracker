"""SQLite 连接与 schema。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from leetcode_tracker.paths import db_path, ensure_parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    difficulty TEXT CHECK(difficulty IN ('Easy', 'Medium', 'Hard')),
    tags TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT NOT NULL UNIQUE,
    problem_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    code TEXT,
    runtime_ms INTEGER,
    memory_mb REAL,
    language TEXT,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (problem_id) REFERENCES problems(problem_id)
);

CREATE INDEX IF NOT EXISTS idx_submissions_problem_id ON submissions(problem_id);
CREATE INDEX IF NOT EXISTS idx_submissions_submitted_at ON submissions(submitted_at);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);

CREATE TABLE IF NOT EXISTS problem_stats (
    problem_id INTEGER PRIMARY KEY REFERENCES problems(problem_id),
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
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS problem_daily_stats (
    problem_id INTEGER NOT NULL REFERENCES problems(problem_id),
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

CREATE INDEX IF NOT EXISTS idx_problem_daily_day ON problem_daily_stats(day);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    ensure_parent(target)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    own = conn is None
    if own:
        conn = connect()
    assert conn is not None
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
