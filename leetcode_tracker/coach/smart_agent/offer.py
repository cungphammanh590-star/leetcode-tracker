"""空闲节点刷题提议：未通过续刷 / 否则新荐。"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional


def problem_url(slug: str, problem_id: int) -> str:
    slug = (slug or "").strip()
    if slug:
        return f"https://leetcode.cn/problems/{slug}/"
    return f"/problems/{problem_id}"


def list_unpassed_problems(
    conn: sqlite3.Connection, *, limit: int = 5
) -> list[dict[str, Any]]:
    """近期有尝试但未 AC（或 accepted_count=0）的题。"""
    rows = conn.execute(
        """
        SELECT ps.problem_id AS problem_id,
               COALESCE(p.title, ps.title, '') AS title,
               COALESCE(p.slug, ps.title_slug, '') AS slug,
               COALESCE(p.difficulty, ps.difficulty, '') AS difficulty,
               ps.last_status AS last_status,
               ps.struggle_score AS struggle_score,
               ps.last_submitted_at AS last_submitted_at
        FROM problem_stats ps
        LEFT JOIN problems p ON p.problem_id = ps.problem_id
        WHERE COALESCE(ps.total_attempts, 0) > 0
          AND (
            COALESCE(ps.accepted_count, 0) = 0
            OR COALESCE(ps.last_status, '') != 'Accepted'
          )
        ORDER BY ps.last_submitted_at DESC, ps.struggle_score DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        pid = int(r["problem_id"])
        slug = str(r["slug"] or "")
        out.append(
            {
                "problem_id": pid,
                "title": str(r["title"] or pid),
                "slug": slug,
                "difficulty": str(r["difficulty"] or ""),
                "last_status": str(r["last_status"] or ""),
                "struggle_score": float(r["struggle_score"] or 0),
                "url": problem_url(slug, pid),
            }
        )
    return out


def build_offer_payload(
    conn: sqlite3.Connection,
    *,
    weak_tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """空闲提议：有未通过 → continue；否则 recommend。"""
    unpassed = list_unpassed_problems(conn, limit=3)
    if unpassed:
        top = unpassed[0]
        return {
            "kind": "continue",
            "problem": top,
            "alternatives": unpassed[1:],
            "cta": (
                f"你还有未通过的题：{top['problem_id']}. {top['title']} "
                f"（{top.get('last_status') or '未 AC'}）。\n"
                f"题页：{top['url']}\n"
                "要继续讨论这题，还是先自己去网页交一版？"
            ),
        }

    from leetcode_tracker.coach.recommend import recommend_problems

    cands = recommend_problems(
        conn,
        weak_tags=list(weak_tags or []),
        limit=3,
    )
    slim = []
    for c in cands:
        pid = int(c.get("id") or c.get("problem_id") or 0)
        if pid <= 0:
            continue
        slim.append(
            {
                "problem_id": pid,
                "title": c.get("title") or str(pid),
                "url": c.get("url") or problem_url(str(c.get("slug") or ""), pid),
                "reason": c.get("reason") or c.get("why") or "",
                "difficulty": c.get("difficulty") or "",
            }
        )
    if not slim:
        return {
            "kind": "none",
            "cta": "题库里暂时没有清晰的下一题候选。你可以报题号，我们直接开聊。",
        }
    lines = ["最近没有未通过的题可续，按薄弱点给你几道新题："]
    for i, c in enumerate(slim, 1):
        reason = f"（{c['reason']}）" if c.get("reason") else ""
        lines.append(
            f"{i}. {c['problem_id']}. {c['title']} {reason}\n   {c['url']}"
        )
    lines.append("想刷哪一题？回题号即可，我帮你绑定后继续。")
    return {"kind": "recommend", "candidates": slim, "cta": "\n".join(lines)}


def status_one_liner(profile: dict[str, Any] | None) -> str:
    p = profile or {}
    today = p.get("today") or {}
    submitted = int(today.get("submissions") or today.get("submit_count") or 0)
    due = int(p.get("review_due_count") or 0)
    weak = list(p.get("weak_tags") or [])[:2]
    bits = []
    if submitted <= 0:
        bits.append("你今天还没提交")
    else:
        bits.append(f"你今天已提交 {submitted} 次")
    if due:
        bits.append(f"有 {due} 题到期复习")
    if weak:
        bits.append("薄弱方向：" + "、".join(str(x) for x in weak))
    return "；".join(bits) + "。" if bits else "可以先从一题简单的开刷。"
