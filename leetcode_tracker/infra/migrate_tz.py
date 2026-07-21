"""将历史 UTC 时间戳一次性迁移为中国墙钟，并重建按日统计。"""

from __future__ import annotations

import sqlite3

from leetcode_tracker.infra.timeutil import (
    TZ_META_KEY,
    TZ_META_VALUE,
    china_now_iso,
    to_china_iso,
)

# SQLite CURRENT_TIMESTAMP 风格（无时区后缀）→ +8 小时
_SQL_UTC_NAIVE_TABLES: list[tuple[str, tuple[str, ...]]] = [
    ("problems", ("created_at",)),
    (
        "submissions",
        ("submitted_at",),
    ),
    (
        "problem_stats",
        (
            "first_attempt_at",
            "last_attempt_at",
            "first_accepted_at",
            "last_submitted_at",
            "updated_at",
        ),
    ),
]

# ISO 带偏移（旧陪练会话等）
_ISO_TABLES: list[tuple[str, str, tuple[str, ...]]] = [
    ("coach_sessions", "session_id", ("created_at", "updated_at")),
]


def _ensure_app_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _already_migrated(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (TZ_META_KEY,),
    ).fetchone()
    return bool(row and str(row["value"]) == TZ_META_VALUE)


def _shift_sql_naive_utc(conn: sqlite3.Connection) -> None:
    for table, cols in _SQL_UTC_NAIVE_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            continue
        for col in cols:
            conn.execute(
                f"""
                UPDATE {table}
                SET {col} = datetime({col}, '+8 hours')
                WHERE {col} IS NOT NULL
                  AND instr({col}, '+') = 0
                  AND instr({col}, 'Z') = 0
                """
            )


def _shift_iso_columns(conn: sqlite3.Connection) -> None:
    for table, pk, cols in _ISO_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            continue
        col_list = ", ".join(cols)
        rows = conn.execute(f"SELECT {pk}, {col_list} FROM {table}").fetchall()
        for row in rows:
            updates: dict[str, str] = {}
            for col in cols:
                value = row[col]
                if not value:
                    continue
                text = str(value)
                # 已是中国时区则跳过
                if text.endswith("+08:00"):
                    continue
                updates[col] = to_china_iso(text)
            if not updates:
                continue
            sets = ", ".join(f"{c} = ?" for c in updates)
            conn.execute(
                f"UPDATE {table} SET {sets} WHERE {pk} = ?",
                (*updates.values(), row[pk]),
            )


def ensure_china_timestamps(conn: sqlite3.Connection) -> bool:
    """
    若尚未迁移：把旧 UTC naive / UTC ISO 转为中国时间，并重建每日统计。
    返回是否执行了迁移。
    """
    _ensure_app_meta(conn)
    if _already_migrated(conn):
        return False

    _shift_sql_naive_utc(conn)
    _shift_iso_columns(conn)

    # 日切边界可能变化，按新墙钟重建汇总
    from leetcode_tracker.core.problem_stats import rebuild_stats

    submissions = int(
        conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"]
    )
    if submissions > 0:
        rebuild_stats(conn, from_scratch=True)

    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        (TZ_META_KEY, TZ_META_VALUE),
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        ("timestamps_migrated_at", china_now_iso()),
    )
    conn.commit()
    return True
