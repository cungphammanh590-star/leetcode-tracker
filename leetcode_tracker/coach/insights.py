"""智能教练洞察：本机聚合 + API 润色 + 日指纹缓存。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from leetcode_tracker.coach.profile import build_user_profile
from leetcode_tracker.coach.side_skills import (
    _get_cache,
    _put_cache,
    ensure_side_cache_schema,
)
from leetcode_tracker.infra.timeutil import china_today
from leetcode_tracker.llm.provider import get_llm_settings

CACHE_KIND = "smart_insights"


def aggregate_insight_facts(conn: sqlite3.Connection) -> dict[str, Any]:
    profile = build_user_profile(conn)
    today = profile.get("today") or {}
    weak = list(profile.get("weak_tags") or [])[:5]
    review_due = int(profile.get("review_due_count") or 0)
    hot100 = profile.get("hot100_progress") or {}

    struggling: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT problem_id, title, difficulty, struggle_score, accepted_count, total_attempts
        FROM problem_stats
        WHERE total_attempts > 0 AND struggle_score >= 0.35
        ORDER BY struggle_score DESC, total_attempts DESC
        LIMIT 5
        """
    ).fetchall():
        struggling.append(
            {
                "problem_id": int(row["problem_id"]),
                "title": row["title"],
                "difficulty": row["difficulty"],
                "struggle_score": round(float(row["struggle_score"] or 0), 3),
                "accepted_count": int(row["accepted_count"] or 0),
                "total_attempts": int(row["total_attempts"] or 0),
            }
        )

    # 轻量错因：近题错误分布汇总
    status_bits: dict[str, int] = {}
    for row in conn.execute(
        """
        SELECT status_breakdown FROM problem_stats
        WHERE total_attempts > 0
        ORDER BY last_submitted_at DESC
        LIMIT 40
        """
    ).fetchall():
        raw = row["status_breakdown"]
        data = raw
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}
        if isinstance(data, dict):
            for k, v in data.items():
                if str(k).lower() in {"accepted", "ac"}:
                    continue
                try:
                    status_bits[str(k)] = status_bits.get(str(k), 0) + int(v or 0)
                except (TypeError, ValueError):
                    pass
    top_errors = sorted(status_bits.items(), key=lambda x: -x[1])[:5]

    return {
        "day": china_today().isoformat(),
        "review_due_count": review_due,
        "weak_tags": weak,
        "today_attempts": int(today.get("attempts") or 0),
        "today_accepted": int(today.get("accepted") or 0),
        "today_wrong": int(today.get("wrong") or 0),
        "hot100_done": int(hot100.get("done") or 0),
        "hot100_total": int(hot100.get("total") or 0),
        "struggling": struggling,
        "top_errors": [{"status": k, "count": v} for k, v in top_errors],
        "summary_text": str(profile.get("summary_text") or ""),
    }


def _fingerprint(facts: dict[str, Any]) -> str:
    payload = {
        "day": facts.get("day"),
        "review_due_count": facts.get("review_due_count"),
        "weak_tags": facts.get("weak_tags"),
        "today_attempts": facts.get("today_attempts"),
        "today_accepted": facts.get("today_accepted"),
        "today_wrong": facts.get("today_wrong"),
        "hot100_done": facts.get("hot100_done"),
        "struggling_ids": [x.get("problem_id") for x in (facts.get("struggling") or [])],
        "top_errors": facts.get("top_errors"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def format_rule_insights(facts: dict[str, Any]) -> dict[str, Any]:
    insights: list[str] = []
    due = int(facts.get("review_due_count") or 0)
    if due > 0:
        insights.append(f"今天有 {due} 道到期复习题，建议先清积压再刷新题。")
    attempts = int(facts.get("today_attempts") or 0)
    wrong = int(facts.get("today_wrong") or 0)
    ac = int(facts.get("today_accepted") or 0)
    if attempts > 0:
        insights.append(f"今日已尝试 {attempts} 次（AC {ac}，未过 {wrong}）。")
    elif due == 0:
        insights.append("今天还没有新提交；可以从复习或推荐下一题开始。")

    struggling = facts.get("struggling") or []
    if struggling and len(insights) < 3:
        top = struggling[0]
        insights.append(
            f"「{top.get('problem_id')}. {top.get('title')}」挣扎指数偏高，适合拆小步复盘。"
        )

    weak = list(facts.get("weak_tags") or [])
    weak_items = [{"kind": "tag", "label": t} for t in weak[:5]]
    if not weak_items and struggling:
        for s in struggling[:3]:
            weak_items.append(
                {
                    "kind": "problem",
                    "label": f"{s.get('problem_id')}. {s.get('title')}",
                    "problem_id": s.get("problem_id"),
                }
            )

    error_hint = ""
    errs = facts.get("top_errors") or []
    if errs:
        top = errs[0]
        error_hint = f"近期常见未过状态：{top.get('status')}（约 {top.get('count')} 次）。"

    if not insights:
        insights.append("数据还不多，多刷几题后我会给出更具体的进度洞察。")

    return {
        "insights": insights[:3],
        "weak_points": weak_items,
        "error_hint": error_hint,
        "empty": not weak_items and due == 0 and attempts == 0,
        "source": "rules",
    }


def _polish_with_api(facts: dict[str, Any], base: dict[str, Any]) -> dict[str, Any] | None:
    settings = get_llm_settings()
    if settings.get("provider") != "api" or not settings.get("api_key"):
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from leetcode_tracker.llm.provider import build_chat_model

        model = build_chat_model()
        prompt = (
            "根据以下 JSON 事实，写 1～3 句口语化中文进度洞察，并列出最多 5 个薄弱点标签/题目名。"
            "不得编造事实中没有的数据。只输出 JSON："
            '{"insights":["..."],"weak_points":[{"kind":"tag|problem","label":"..."}],'
            '"error_hint":"可选一句"}。\n\n'
            + json.dumps(facts, ensure_ascii=False)
        )
        resp = model.invoke(
            [
                SystemMessage(content="你是刷题教练文案助手，只基于事实润色，输出 JSON。"),
                HumanMessage(content=prompt),
            ]
        )
        text = str(getattr(resp, "content", "") or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        insights = [str(x).strip() for x in (data.get("insights") or []) if str(x).strip()]
        weak_points = []
        for item in data.get("weak_points") or []:
            if isinstance(item, dict) and item.get("label"):
                weak_points.append(
                    {
                        "kind": str(item.get("kind") or "tag"),
                        "label": str(item["label"]),
                        **(
                            {"problem_id": item["problem_id"]}
                            if item.get("problem_id") is not None
                            else {}
                        ),
                    }
                )
            elif isinstance(item, str) and item.strip():
                weak_points.append({"kind": "tag", "label": item.strip()})
        if not insights:
            return None
        return {
            "insights": insights[:3],
            "weak_points": weak_points[:5] or base.get("weak_points") or [],
            "error_hint": str(data.get("error_hint") or base.get("error_hint") or ""),
            "empty": False,
            "source": "api",
        }
    except Exception:  # noqa: BLE001
        return None


def get_smart_insights(
    conn: sqlite3.Connection, *, refresh: bool = False
) -> dict[str, Any]:
    ensure_side_cache_schema(conn)
    facts = aggregate_insight_facts(conn)
    day = str(facts.get("day") or china_today().isoformat())
    fp = _fingerprint(facts)
    if not refresh:
        cached = _get_cache(conn, kind=CACHE_KIND, day=day, fingerprint=fp)
        if cached:
            try:
                payload = json.loads(cached)
                if isinstance(payload, dict) and payload.get("insights") is not None:
                    payload["from_cache"] = True
                    payload["facts"] = {
                        "review_due_count": facts.get("review_due_count"),
                        "today_attempts": facts.get("today_attempts"),
                        "hot100_done": facts.get("hot100_done"),
                        "hot100_total": facts.get("hot100_total"),
                    }
                    return payload
            except json.JSONDecodeError:
                pass

    base = format_rule_insights(facts)
    polished = _polish_with_api(facts, base)
    result = polished or base
    result["from_cache"] = False
    result["day"] = day
    result["facts"] = {
        "review_due_count": facts.get("review_due_count"),
        "today_attempts": facts.get("today_attempts"),
        "hot100_done": facts.get("hot100_done"),
        "hot100_total": facts.get("hot100_total"),
    }
    _put_cache(
        conn,
        kind=CACHE_KIND,
        day=day,
        fingerprint=fp,
        reply=json.dumps(
            {
                "insights": result.get("insights"),
                "weak_points": result.get("weak_points"),
                "error_hint": result.get("error_hint"),
                "empty": result.get("empty"),
                "source": result.get("source"),
                "day": day,
            },
            ensure_ascii=False,
        ),
    )
    return result
