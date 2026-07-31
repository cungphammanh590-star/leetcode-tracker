"""智能教练会话消息持久化（与 LangGraph checkpoint 分离）。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from leetcode_tracker.infra.timeutil import china_now_iso


def ensure_smart_history_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS smart_coach_history (
            session_id TEXT PRIMARY KEY,
            messages_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def load_history(conn: sqlite3.Connection, session_id: str) -> list[dict[str, str]]:
    ensure_smart_history_schema(conn)
    row = conn.execute(
        "SELECT messages_json FROM smart_coach_history WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        return []
    try:
        data = json.loads(str(row["messages_json"] or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "")
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out


def save_history(
    conn: sqlite3.Connection, session_id: str, messages: list[dict[str, str]]
) -> None:
    ensure_smart_history_schema(conn)
    # 保留最近约 20 轮
    trimmed = messages[-40:]
    conn.execute(
        """
        INSERT INTO smart_coach_history (session_id, messages_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            messages_json = excluded.messages_json,
            updated_at = excluded.updated_at
        """,
        (session_id, json.dumps(trimmed, ensure_ascii=False), china_now_iso()),
    )
    conn.commit()
