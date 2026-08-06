"""智能教练只读/绑题工具（禁止注入历史 AC 源码）。"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Optional

from leetcode_tracker.coach.strip_comments import strip_code_comments
from leetcode_tracker.core.problem_stats import get_problem_stats_row
from leetcode_tracker.core.submissions import (
    get_latest_submission_for_problem,
    get_submission_by_id,
)
from leetcode_tracker.infra.timeutil import china_now_iso, china_today

MAX_TOOL_ROUNDS = 3


def load_current_code(conn: sqlite3.Connection, session: dict[str, Any]) -> dict[str, Any]:
    """读取当前会话绑定题目的最新提交代码（去注释）。不含历史 AC。"""
    problem_id = int(session.get("problem_id") or 0)
    sid = str(session.get("submission_id") or "")
    if problem_id <= 0:
        if sid.startswith("mode:"):
            return {
                "ok": False,
                "note": "尚未绑定题目。请先调用 bind_problem，或请用户给出题号/标题。",
            }
        return {"ok": False, "note": "无题目上下文"}

    sub = get_latest_submission_for_problem(conn, problem_id)
    if sub is None and sid and not sid.startswith("mode:") and not sid.startswith("bound:"):
        sub = get_submission_by_id(conn, sid)
    if not sub:
        return {
            "ok": True,
            "code": "",
            "language": "",
            "status": str(session.get("submission_status") or ""),
            "problem_id": problem_id,
            "note": "已绑定题目，但库中尚无该题提交；可先聊思路，用户提交后再读码。",
        }
    lang = str(sub.get("language") or "")
    raw = str(sub.get("code") or "")
    code = strip_code_comments(raw, lang) if raw else ""
    lines = code.splitlines()
    if len(lines) > 120:
        code = "\n".join(lines[:120]) + "\n…（已截断）"
    return {
        "ok": True,
        "code": code,
        "language": lang,
        "status": str(sub.get("status") or ""),
        "submission_id": str(sub.get("submission_id") or sub.get("id") or ""),
        "problem_id": problem_id,
        "note": "仅当前最新提交；不含任何历史 Accepted 源码",
    }


def load_error_summary(conn: sqlite3.Connection, session: dict[str, Any]) -> dict[str, Any]:
    """错因/挣扎要点：来自 problem_stats，不读 AC 源码。"""
    problem_id = int(session.get("problem_id") or 0)
    if problem_id <= 0:
        return {"ok": False, "note": "尚未绑定题目"}
    stats = get_problem_stats_row(conn, problem_id)
    if not stats:
        return {
            "ok": True,
            "problem_id": problem_id,
            "note": "库中暂无该题统计（可能尚未提交过）",
        }
    breakdown = stats.get("status_breakdown") or {}
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except json.JSONDecodeError:
            breakdown = {}
    return {
        "ok": True,
        "problem_id": problem_id,
        "title": stats.get("title"),
        "difficulty": stats.get("difficulty"),
        "total_attempts": stats.get("total_attempts"),
        "accepted_count": stats.get("accepted_count"),
        "struggle_score": round(float(stats.get("struggle_score") or 0), 3),
        "status_breakdown": breakdown,
        "topic_tags": stats.get("topic_tags") or [],
        "current_status": str(session.get("submission_status") or ""),
        "note": "仅统计与标签；无历史 AC 源码",
    }


def last_advice_from_history(history: list[dict[str, str]]) -> str:
    """从会话历史取最近一条助手建议摘要。"""
    for item in reversed(history or []):
        if str(item.get("role") or "") != "assistant":
            continue
        text = str(item.get("content") or "").strip()
        if text:
            return text[:1200]
    return ""


def _problem_row(conn: sqlite3.Connection, problem_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT problem_id, title, slug, difficulty
        FROM problems WHERE problem_id = ?
        """,
        (problem_id,),
    ).fetchone()
    if row:
        return dict(row)
    stats = get_problem_stats_row(conn, problem_id)
    if not stats:
        return None
    return {
        "problem_id": problem_id,
        "title": stats.get("title") or f"Problem {problem_id}",
        "slug": stats.get("title_slug") or "",
        "difficulty": stats.get("difficulty") or "",
    }


def _search_problems(conn: sqlite3.Connection, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []
    # 纯数字 → 题号
    if re.fullmatch(r"\d{1,5}", q):
        row = _problem_row(conn, int(q))
        return [row] if row else []

    like = f"%{q}%"
    rows = conn.execute(
        """
        SELECT problem_id, title, slug, difficulty
        FROM problems
        WHERE title LIKE ? OR slug LIKE ?
        ORDER BY
          CASE WHEN title = ? OR slug = ? THEN 0
               WHEN title LIKE ? OR slug LIKE ? THEN 1
               ELSE 2 END,
          problem_id
        LIMIT ?
        """,
        (like, like, q, q, f"{q}%", f"{q}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def bind_problem(
    conn: sqlite3.Connection,
    session: dict[str, Any],
    *,
    problem_id: Optional[int] = None,
    query: str = "",
) -> dict[str, Any]:
    """将当前会话绑定到题目；就地更新 session 与 DB。"""
    candidates: list[dict[str, Any]] = []
    if problem_id is not None and int(problem_id) > 0:
        row = _problem_row(conn, int(problem_id))
        if row:
            candidates = [row]
    elif query:
        # 尝试从 query 抽出题号
        m = re.search(r"\b(\d{1,5})\b", query)
        if m and re.fullmatch(r".*\b\d{1,5}\b.*", query.strip()) and len(query.strip()) <= 8:
            row = _problem_row(conn, int(m.group(1)))
            if row:
                candidates = [row]
        if not candidates:
            candidates = _search_problems(conn, query)

    if not candidates:
        return {
            "ok": False,
            "note": "未找到题目。请用户给出题号（如 215）或更完整的标题。",
        }
    if len(candidates) > 1:
        return {
            "ok": False,
            "note": "匹配到多题，请让用户确认题号后再绑定。",
            "candidates": [
                {
                    "problem_id": c["problem_id"],
                    "title": c.get("title"),
                    "difficulty": c.get("difficulty"),
                }
                for c in candidates
            ],
        }

    chosen = candidates[0]
    pid = int(chosen["problem_id"])
    sub = get_latest_submission_for_problem(conn, pid)
    day = china_today().isoformat()
    if sub:
        new_sid = str(sub.get("submission_id") or sub.get("id") or "")
        status = str(sub.get("status") or "")
    else:
        new_sid = f"bound:{pid}:{day}"
        status = "Bound"
    title = str(chosen.get("title") or pid)
    context = (
        f"## 已绑定题目\n- {pid}. {title}\n"
        f"- 难度：{chosen.get('difficulty') or '—'}\n"
        f"- 提交状态：{status or '尚无提交'}\n"
    )
    now = china_now_iso()
    session_id = str(session["session_id"])
    conn.execute(
        """
        UPDATE coach_sessions
        SET problem_id = ?, submission_id = ?, submission_status = ?,
            context_markdown = ?, updated_at = ?
        WHERE session_id = ?
        """,
        (pid, new_sid, status, context, now, session_id),
    )
    conn.commit()
    session["problem_id"] = pid
    session["submission_id"] = new_sid
    session["submission_status"] = status
    session["context_markdown"] = context
    session["updated_at"] = now
    return {
        "ok": True,
        "problem_id": pid,
        "title": title,
        "difficulty": chosen.get("difficulty"),
        "submission_status": status,
        "has_submission": bool(sub),
        "note": f"已绑定 {pid}. {title}"
        + ("；可读取当前提交代码" if sub else "；库中尚无提交，可先聊思路"),
    }


def session_binding(session: dict[str, Any]) -> dict[str, Any]:
    pid = int(session.get("problem_id") or 0)
    return {
        "ok": True,
        "bound": pid > 0,
        "problem_id": pid if pid > 0 else None,
        "submission_id": session.get("submission_id"),
        "submission_status": session.get("submission_status") or "",
    }


def get_latest_submission_global(conn: sqlite3.Connection) -> dict[str, Any]:
    """库内全局最近一条提交（含题页链接）。"""
    from leetcode_tracker.coach.smart_agent.offer import problem_url

    row = conn.execute(
        """
        SELECT s.problem_id, s.status, s.submitted_at, s.language,
               COALESCE(p.title, '') AS title,
               COALESCE(p.slug, '') AS slug,
               COALESCE(p.difficulty, '') AS difficulty
        FROM submissions s
        LEFT JOIN problems p ON p.problem_id = s.problem_id
        ORDER BY s.submitted_at DESC, s.id DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        return {"ok": False, "note": "库中尚无提交记录"}
    pid = int(row["problem_id"])
    slug = str(row["slug"] or "")
    return {
        "ok": True,
        "problem_id": pid,
        "title": str(row["title"] or pid),
        "status": str(row["status"] or ""),
        "submitted_at": str(row["submitted_at"] or ""),
        "language": str(row["language"] or ""),
        "difficulty": str(row["difficulty"] or ""),
        "url": problem_url(slug, pid),
        "note": "全局最近一条提交；不含源码",
    }


def get_user_profile_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    from leetcode_tracker.coach.profile import build_user_profile

    profile = build_user_profile(conn)
    return {
        "ok": True,
        "total_solved": profile.get("total_solved"),
        "weak_tags": profile.get("weak_tags") or [],
        "review_due_count": profile.get("review_due_count"),
        "today": profile.get("today") or {},
        "hot100_progress": profile.get("hot100_progress") or {},
        "recent_attempts": profile.get("recent_attempts") or [],
        "summary_text": profile.get("summary_text") or "",
        "note": "只读画像聚合；无 AC 源码",
    }


def get_topic_mastery(conn: sqlite3.Connection, topic: str) -> dict[str, Any]:
    topic = str(topic or "").strip()
    if not topic:
        return {"ok": False, "note": "请提供标签/知识点名称"}
    like = f"%{topic}%"
    rows = conn.execute(
        """
        SELECT problem_id, title, difficulty, struggle_score,
               accepted_count, total_attempts, topic_tags, last_status
        FROM problem_stats
        WHERE topic_tags LIKE ? AND COALESCE(total_attempts, 0) > 0
        ORDER BY struggle_score DESC
        LIMIT 30
        """,
        (like,),
    ).fetchall()
    attempted = len(rows)
    ac = sum(1 for r in rows if int(r["accepted_count"] or 0) > 0)
    avg_struggle = (
        round(sum(float(r["struggle_score"] or 0) for r in rows) / attempted, 3)
        if attempted
        else 0.0
    )
    hard = [
        {
            "problem_id": int(r["problem_id"]),
            "title": r["title"],
            "struggle_score": round(float(r["struggle_score"] or 0), 3),
            "last_status": r["last_status"],
        }
        for r in rows[:5]
    ]
    return {
        "ok": True,
        "topic": topic,
        "attempted": attempted,
        "accepted": ac,
        "avg_struggle": avg_struggle,
        "top_struggle_problems": hard,
        "note": "按 topic_tags 模糊匹配的聚合；非考试分数",
    }


def get_problem_mastery(conn: sqlite3.Connection, problem_id: int) -> dict[str, Any]:
    from leetcode_tracker.coach.mastered import is_mastered

    pid = int(problem_id or 0)
    if pid <= 0:
        return {"ok": False, "note": "需要有效题号"}
    stats = get_problem_stats_row(conn, pid) or {}
    row = _problem_row(conn, pid)
    return {
        "ok": True,
        "problem_id": pid,
        "title": (row or {}).get("title") or stats.get("title") or pid,
        "mastered": is_mastered(conn, pid),
        "accepted_count": stats.get("accepted_count"),
        "total_attempts": stats.get("total_attempts"),
        "struggle_score": round(float(stats.get("struggle_score") or 0), 3),
        "last_status": stats.get("last_status"),
        "topic_tags": stats.get("topic_tags") or [],
        "note": "单题掌握/挣扎；无源码",
    }


def suggest_next_problems_tool(
    conn: sqlite3.Connection, *, limit: int = 3
) -> dict[str, Any]:
    from leetcode_tracker.coach.profile import build_user_profile
    from leetcode_tracker.coach.recommend import recommend_problems
    from leetcode_tracker.coach.smart_agent.offer import list_unpassed_problems, problem_url

    unpassed = list_unpassed_problems(conn, limit=limit)
    if unpassed:
        return {
            "ok": True,
            "mode": "continue_unpassed",
            "candidates": unpassed,
            "note": "优先未通过续刷；题号仅来自本列表",
        }
    profile = build_user_profile(conn)
    cands = recommend_problems(
        conn, weak_tags=list(profile.get("weak_tags") or []), limit=limit
    )
    slim = []
    for c in cands:
        pid = int(c.get("id") or c.get("problem_id") or 0)
        if pid <= 0:
            continue
        slim.append(
            {
                "problem_id": pid,
                "title": c.get("title"),
                "url": c.get("url") or problem_url(str(c.get("slug") or ""), pid),
                "reason": c.get("reason") or c.get("why") or "",
                "difficulty": c.get("difficulty"),
            }
        )
    return {
        "ok": True,
        "mode": "recommend_new",
        "candidates": slim,
        "note": "规则引擎候选；禁止推荐列表外题号",
    }


def run_tool(
    name: str,
    *,
    conn: sqlite3.Connection,
    session: dict[str, Any],
    history: list[dict[str, str]],
    args: Optional[dict[str, Any]] = None,
) -> str:
    args = args if isinstance(args, dict) else {}
    if name == "get_current_code":
        return json.dumps(load_current_code(conn, session), ensure_ascii=False)
    if name == "get_error_summary":
        return json.dumps(load_error_summary(conn, session), ensure_ascii=False)
    if name == "get_last_advice":
        advice = last_advice_from_history(history)
        return json.dumps(
            {
                "ok": bool(advice),
                "advice": advice or "",
                "note": "无历史建议" if not advice else "来自本会话上一轮助手回复",
            },
            ensure_ascii=False,
        )
    if name == "get_session_binding":
        return json.dumps(session_binding(session), ensure_ascii=False)
    if name == "bind_problem":
        raw_pid = args.get("problem_id")
        pid: Optional[int] = None
        if raw_pid not in (None, ""):
            try:
                pid = int(raw_pid)
            except (TypeError, ValueError):
                pid = None
        return json.dumps(
            bind_problem(
                conn,
                session,
                problem_id=pid,
                query=str(args.get("query") or ""),
            ),
            ensure_ascii=False,
        )
    if name == "get_latest_submission":
        return json.dumps(get_latest_submission_global(conn), ensure_ascii=False)
    if name == "get_user_profile_summary":
        return json.dumps(get_user_profile_summary(conn), ensure_ascii=False)
    if name == "get_topic_mastery":
        return json.dumps(
            get_topic_mastery(conn, str(args.get("topic") or "")),
            ensure_ascii=False,
        )
    if name == "get_problem_mastery":
        raw_pid = args.get("problem_id") or session.get("problem_id") or 0
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            pid = 0
        return json.dumps(get_problem_mastery(conn, pid), ensure_ascii=False)
    if name == "suggest_next_problems":
        lim = args.get("limit") or 3
        try:
            lim_i = max(1, min(5, int(lim)))
        except (TypeError, ValueError):
            lim_i = 3
        return json.dumps(
            suggest_next_problems_tool(conn, limit=lim_i), ensure_ascii=False
        )
    if name == "list_unpassed_problems":
        from leetcode_tracker.coach.smart_agent.offer import list_unpassed_problems

        return json.dumps(
            {"ok": True, "items": list_unpassed_problems(conn, limit=5)},
            ensure_ascii=False,
        )
    return json.dumps({"ok": False, "note": f"未知工具: {name}"}, ensure_ascii=False)


TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "get_session_binding",
            "description": "查看当前会话是否已绑定题目。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bind_problem",
            "description": (
                "将本会话绑定到一道题。用户给出题号或标题时调用。"
                "多候选时不要猜测，把 candidates 转述给用户确认。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_id": {
                        "type": "integer",
                        "description": "力扣题号，如 215",
                    },
                    "query": {
                        "type": "string",
                        "description": "标题或 slug 关键词；无题号时使用",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_code",
            "description": "读取当前绑定题目最新提交的代码与状态（已去注释）。禁止也不提供历史 Accepted 源码。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_error_summary",
            "description": "读取已绑定题目的错因分布、挣扎指数与标签等统计要点。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_advice",
            "description": "获取本会话上一轮助手建议摘要，用于对照验收用户是否按建议改码。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_submission",
            "description": "读取库内全局最近一条提交的题号/状态/题页链接（不含源码）。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_unpassed_problems",
            "description": "列出近期未通过（非 AC）的题目，用于续刷提议。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile_summary",
            "description": "读取用户整体画像：薄弱标签、今日进度、到期复习、题单进度等。",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_topic_mastery",
            "description": "按标签/知识点聚合掌握与挣扎情况。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "标签名，如 动态规划"},
                },
                "required": ["topic"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_problem_mastery",
            "description": "单题掌握/挣扎统计；可省略 problem_id 则用当前绑定题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_id": {"type": "integer"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_next_problems",
            "description": (
                "选题：有未通过则返回续刷候选，否则返回规则引擎新题候选。"
                "禁止推荐返回列表之外的题号。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "候选数量 1～5"},
                },
                "additionalProperties": False,
            },
        },
    },
]
