"""题目与提交的写入逻辑。"""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from leetcode_tracker.core.problem_stats import apply_submission_stats, sync_problem_meta


class StoreError(Exception):
    """可映射为 HTTP 4xx 的业务错误。"""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class SaveResult:
    created: bool
    submission_id: str


_DIFFICULTY_MAP = {
    "easy": "Easy",
    "medium": "Medium",
    "hard": "Hard",
    "1": "Easy",
    "2": "Medium",
    "3": "Hard",
    "简单": "Easy",
    "中等": "Medium",
    "困难": "Hard",
}


def normalize_difficulty(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return {1: "Easy", 2: "Medium", 3: "Hard"}.get(value)
    text = str(value).strip()
    mapped = _DIFFICULTY_MAP.get(text) or _DIFFICULTY_MAP.get(text.lower())
    return mapped if mapped else (text if text in ("Easy", "Medium", "Hard") else None)


_STATUS_MAP = {
    "通过": "Accepted",
    "Accepted": "Accepted",
    "解答错误": "Wrong Answer",
    "Wrong Answer": "Wrong Answer",
    "超时": "Time Limit Exceeded",
    "Time Limit Exceeded": "Time Limit Exceeded",
    "内存超出": "Memory Limit Exceeded",
    "Memory Limit Exceeded": "Memory Limit Exceeded",
    "执行出错": "Runtime Error",
    "Runtime Error": "Runtime Error",
    "编译错误": "Compile Error",
    "Compile Error": "Compile Error",
}


def normalize_status(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _STATUS_MAP.get(text, text)


def _looks_like_real_slug(slug: str) -> bool:
    slug = slug.strip()
    return bool(slug) and not slug.startswith("problem-")


def fetch_difficulty_from_leetcode(slug: str) -> Optional[str]:
    """扩展未采到难度时，用题目 slug 向 leetcode.cn GraphQL 补全。"""
    if not _looks_like_real_slug(slug):
        return None
    query = (
        "query questionData($titleSlug: String!) {"
        " question(titleSlug: $titleSlug) { difficulty } }"
    )
    body = json.dumps(
        {"query": query, "variables": {"titleSlug": slug}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://leetcode.cn/graphql/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    diff = data.get("data", {}).get("question", {}).get("difficulty")
    return normalize_difficulty(diff)


def resolve_difficulty(payload: dict[str, Any]) -> Optional[str]:
    diff = normalize_difficulty(payload.get("difficulty"))
    if diff:
        return diff
    slug = str(payload.get("slug") or "").strip()
    return fetch_difficulty_from_leetcode(slug)


def upsert_problem(
    conn: sqlite3.Connection,
    *,
    problem_id: int,
    title: str,
    slug: str,
    difficulty: Any = None,
    tags: Any = None,
) -> None:
    from leetcode_tracker.infra.timeutil import china_now_sql

    diff = normalize_difficulty(difficulty)
    if isinstance(tags, (list, tuple)):
        tags_json = json.dumps(list(tags), ensure_ascii=False)
    elif tags is None:
        tags_json = None
    else:
        tags_json = str(tags)

    conn.execute(
        """
        INSERT INTO problems (problem_id, title, slug, difficulty, tags, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(problem_id) DO UPDATE SET
            title = excluded.title,
            slug = excluded.slug,
            difficulty = COALESCE(excluded.difficulty, problems.difficulty),
            tags = COALESCE(excluded.tags, problems.tags)
        """,
        (problem_id, title, slug, diff, tags_json, china_now_sql()),
    )
    sync_problem_meta(
        conn,
        problem_id=problem_id,
        title=title,
        slug=slug,
        difficulty=diff,
        tags=tags_json,
    )


def save_submission(conn: sqlite3.Connection, payload: dict[str, Any]) -> SaveResult:
    submission_id = payload.get("submission_id")
    if submission_id is None or str(submission_id).strip() == "":
        raise StoreError("submission_id is required", status_code=400)
    submission_id = str(submission_id).strip()

    try:
        problem_id = int(payload["problem_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise StoreError("problem_id is required and must be an integer", status_code=400) from exc

    title = str(payload.get("title") or "").strip() or f"Problem {problem_id}"
    slug = str(payload.get("slug") or "").strip() or f"problem-{problem_id}"
    status = normalize_status(payload.get("status"))
    if not status:
        raise StoreError("status is required", status_code=400)

    code = payload.get("code")
    if code is not None:
        code = str(code)

    runtime_ms = payload.get("runtime_ms")
    if runtime_ms is not None and runtime_ms != "":
        try:
            runtime_ms = int(runtime_ms)
        except (TypeError, ValueError) as exc:
            raise StoreError("runtime_ms must be an integer", status_code=400) from exc
    else:
        runtime_ms = None

    memory_mb = payload.get("memory_mb")
    if memory_mb is not None and memory_mb != "":
        try:
            memory_mb = float(memory_mb)
        except (TypeError, ValueError) as exc:
            raise StoreError("memory_mb must be a number", status_code=400) from exc
    else:
        memory_mb = None

    language = payload.get("language")
    if language is not None:
        language = str(language)

    upsert_problem(
        conn,
        problem_id=problem_id,
        title=title,
        slug=slug,
        difficulty=resolve_difficulty(payload),
        tags=payload.get("tags"),
    )

    existing = conn.execute(
        "SELECT 1 FROM submissions WHERE submission_id = ?",
        (submission_id,),
    ).fetchone()
    if existing:
        conn.commit()
        return SaveResult(created=False, submission_id=submission_id)

    try:
        from leetcode_tracker.infra.timeutil import china_now_sql

        submitted_at = china_now_sql()
        conn.execute(
            """
            INSERT INTO submissions (
                submission_id, problem_id, status, code, runtime_ms, memory_mb,
                language, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission_id,
                problem_id,
                status,
                code,
                runtime_ms,
                memory_mb,
                language,
                submitted_at,
            ),
        )
        apply_submission_stats(
            conn,
            problem_id=problem_id,
            status=status,
            submitted_at=submitted_at,
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        # 并发重复投递：扩展/轮询可能几乎同时 POST 同一 submission_id
        return SaveResult(created=False, submission_id=submission_id)
    return SaveResult(created=True, submission_id=submission_id)


def count_submissions(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()
    return int(row["c"] if row else 0)
