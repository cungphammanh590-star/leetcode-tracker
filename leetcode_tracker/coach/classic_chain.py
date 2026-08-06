"""经典陪练：LangChain 链式路径（替换 LocalGraph/ApiGraph）。"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from typing import Any, Optional

from leetcode_tracker.coach.answer_egress import build_answer_egress
from leetcode_tracker.coach.exit_detect import is_repetitive_reply, should_offer_exit
from leetcode_tracker.coach.graphs.common import (
    GenerationCancelled,
    append_unique,
    build_system_content,
    close_summary_from_state,
    emit_stream_event,
    extract_identifiers,
    extract_negations,
    fallback_local_text,
    last_human_text,
    messages_after_code_epoch,
    stream_model_reply,
    stream_writer_scope,
    trim_messages_for_local,
    update_vague_counter,
)
from leetcode_tracker.coach.graphs.skill_nodes import (
    prepare_intent_update,
    route_after_intent,
    run_daily_review_node,
    run_optimize_local,
    run_recommend_node,
    run_review_node,
)
from leetcode_tracker.coach.sessions import abandon_session
from leetcode_tracker.coach.state import API_COMPRESS_AFTER_TURNS
from leetcode_tracker.infra.db import init_db

_HISTORY_TABLE = "classic_coach_history"


def _ensure_history(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_HISTORY_TABLE} (
            session_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT
        )
        """
    )
    conn.commit()


def _load_state(conn: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    _ensure_history(conn)
    row = conn.execute(
        f"SELECT state_json FROM {_HISTORY_TABLE} WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["state_json"] or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_state(conn: sqlite3.Connection, session_id: str, state: dict[str, Any]) -> None:
    from leetcode_tracker.infra.timeutil import china_now_iso

    _ensure_history(conn)
    # messages 不可直接 JSON：存 role/content
    serial_msgs = []
    for m in state.get("messages") or []:
        if isinstance(m, dict):
            serial_msgs.append(m)
            continue
        role = "assistant" if "AI" in m.__class__.__name__ else "user"
        if "System" in m.__class__.__name__:
            continue
        serial_msgs.append(
            {"role": role, "content": str(getattr(m, "content", "") or "")}
        )
    payload = {
        k: v
        for k, v in state.items()
        if k
        not in {
            "messages",
            "user_profile",
            "current_code",
            "candidate_recommendations",
        }
    }
    payload["messages"] = serial_msgs[-40:]
    conn.execute(
        f"""
        INSERT INTO {_HISTORY_TABLE} (session_id, state_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
          state_json = excluded.state_json,
          updated_at = excluded.updated_at
        """,
        (session_id, json.dumps(payload, ensure_ascii=False), china_now_iso()),
    )
    conn.commit()


def _hydrate_messages(raw: list[Any]) -> list[Any]:
    from langchain_core.messages import AIMessage, HumanMessage

    out: list[Any] = []
    for item in raw or []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "")
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant" and content:
            out.append(AIMessage(content=content))
    return out


def chat_stream(
    conn: sqlite3.Connection,
    session: dict[str, Any],
    message: str,
    *,
    action: str = "",
    cancel_event: Optional[threading.Event] = None,
    user_profile: Optional[dict[str, Any]] = None,
    current_code: str = "",
    context_markdown: str = "",
    code_epoch_bumped: bool = False,
    provider: str = "ollama",
) -> Iterator[dict[str, Any]]:
    """经典链单回合；yield SSE 事件（无 ready，由 service 先发）。"""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    stop = cancel_event or threading.Event()
    session_id = str(session["session_id"])
    thread_id = str(session.get("thread_id") or session_id)
    is_api = provider == "api"
    provider_key = "api" if is_api else "ollama"

    events: list[dict[str, Any]] = []

    def _writer(ev: dict[str, Any]) -> None:
        events.append(dict(ev))

    prior = _load_state(conn, session_id)
    messages = _hydrate_messages(list(prior.get("messages") or []))
    if not messages and session.get("opening"):
        messages.append(AIMessage(content=str(session.get("opening") or "")))
    if code_epoch_bumped:
        messages = [HumanMessage(content=message)]
    else:
        messages.append(HumanMessage(content=message))

    state: dict[str, Any] = {
        **{k: v for k, v in prior.items() if k != "messages"},
        "messages": messages,
        "context_markdown": context_markdown
        or str(session.get("context_markdown") or ""),
        "submission_status": str(session.get("submission_status") or ""),
        "pending_action": action,
        "problem_id": int(session.get("problem_id") or 0),
        "user_profile": user_profile or {},
        "current_code": current_code,
        "code_epoch_bumped": code_epoch_bumped,
        "done": bool(prior.get("done")),
        "fallback_turn_count": int(prior.get("fallback_turn_count") or 0),
        "turn_count": int(prior.get("turn_count") or 0),
        "rejected_suspicions": list(prior.get("rejected_suspicions") or []),
        "mentioned_identifiers": list(prior.get("mentioned_identifiers") or []),
        "exit_offered": bool(prior.get("exit_offered")),
        "degraded": bool(prior.get("degraded")),
        "last_assistant_text": str(prior.get("last_assistant_text") or ""),
        "guardrail_stripped": bool(prior.get("guardrail_stripped")),
        "consecutive_vague": int(prior.get("consecutive_vague") or 0),
        "context_summary": str(prior.get("context_summary") or ""),
        "intent": str(prior.get("intent") or ""),
        "generation_error": "",
    }

    with stream_writer_scope(_writer):
        try:
            state.update(prepare_intent_update(state, provider=provider_key))
            route = route_after_intent(state, provider=provider_key)

            if route == "close_session":
                summary = close_summary_from_state(state)
                emit_stream_event({"type": "token", "text": summary})
                abandon_session(conn, session_id)
                state["messages"] = list(state["messages"]) + [
                    AIMessage(content=summary)
                ]
                state["done"] = True
                state["pending_action"] = ""
            elif route == "offer_exit":
                _offer, reason = should_offer_exit(state)
                note = {
                    "hard_turn_limit": "这题已经聊了不少轮。可以结束，或点「推荐下一题」换题巩固。",
                    "vague_loop": "对话有点空转了。要结束、看思路，还是去推荐下一题？",
                    "guardrail": "模型回复不稳定。建议结束、看思路，或推荐下一题。",
                    "degraded": "模型表现下降。建议结束、看思路，或推荐下一题。",
                    "repeat": "出现重复引导。建议结束、看思路，或推荐下一题。",
                }.get(reason, "可以结束本轮；需要换题请点「推荐下一题」。")
                emit_stream_event(
                    {
                        "type": "offer_exit",
                        "reason": reason or "manual",
                        "message": note,
                        "actions": ["close", "show_skeleton", "recommend", "review"],
                        "auto_end": False,
                    }
                )
                tip = f"（系统）{note}"
                emit_stream_event({"type": "token", "text": tip})
                state["messages"] = list(state["messages"]) + [AIMessage(content=tip)]
                state["exit_offered"] = True
                state["degraded"] = True
            elif route == "answer_egress":
                payload = build_answer_egress(
                    conn,
                    int(state.get("problem_id") or 0),
                    degraded=bool(state.get("degraded")),
                )
                text = str(payload["text"])
                emit_stream_event(
                    {
                        "type": "answer_egress",
                        "text": text,
                        "source": payload.get("source"),
                    }
                )
                emit_stream_event({"type": "token", "text": text})
                state["messages"] = list(state["messages"]) + [AIMessage(content=text)]
                state["pending_action"] = ""
                state["exit_offered"] = True
            elif route == "recommend":
                upd = run_recommend_node(
                    state,
                    cancel_event=stop,
                    session_id=session_id,
                    thread_id=thread_id,
                    provider="api" if is_api else "local",
                )
                state.update(upd)
            elif route == "review":
                upd = run_review_node(
                    state,
                    cancel_event=stop,
                    session_id=session_id,
                    thread_id=thread_id,
                    provider="api" if is_api else "local",
                )
                state.update(upd)
            elif route == "daily_review":
                upd = run_daily_review_node(
                    state,
                    cancel_event=stop,
                    session_id=session_id,
                    thread_id=thread_id,
                    provider="api" if is_api else "local",
                )
                state.update(upd)
            elif route == "optimize":
                if is_api:
                    upd = _api_guided(
                        state,
                        cancel_event=stop,
                        session_id=session_id,
                        thread_id=thread_id,
                        extra="请从复杂度/可读性给优化方向，不要完整重构代码。",
                        node="optimize",
                    )
                else:
                    upd = run_optimize_local(
                        state,
                        cancel_event=stop,
                        session_id=session_id,
                        thread_id=thread_id,
                    )
                state.update(upd)
            elif route == "diagnose":
                emit_stream_event({"type": "diagnose", "source": "api"})
                upd = _api_guided(
                    state,
                    cancel_event=stop,
                    session_id=session_id,
                    thread_id=thread_id,
                    extra="请给出简短诊断（2～4点），引用真实标识符，不要完整解法。收束本轮。",
                    node="diagnose",
                    end_session=True,
                )
                state.update(upd)
            elif route == "deep_analysis":
                emit_stream_event({"type": "deep_analysis", "source": "api"})
                upd = _api_guided(
                    state,
                    cancel_event=stop,
                    session_id=session_id,
                    thread_id=thread_id,
                    extra="请用文字步骤+伪代码讲清思路，禁止完整可运行代码。",
                    node="deep_analysis",
                )
                state.update(upd)
            else:
                # coach_reply
                if is_api:
                    upd = _api_guided(
                        state,
                        cancel_event=stop,
                        session_id=session_id,
                        thread_id=thread_id,
                        extra="",
                        node="api_coach_reply",
                    )
                else:
                    upd = _local_reply(
                        state,
                        cancel_event=stop,
                        session_id=session_id,
                        thread_id=thread_id,
                    )
                state.update(upd)
                # local may request offer_exit after reply
                if not is_api and upd.get("_offer_exit"):
                    for ev in events:
                        yield ev
                    events.clear()
                    _offer, reason = should_offer_exit({**state, **upd})
                    note = "可以结束本轮，或点「看思路 / 推荐下一题」。"
                    emit_stream_event(
                        {
                            "type": "offer_exit",
                            "reason": reason or "after_reply",
                            "message": note,
                            "actions": ["close", "show_skeleton", "recommend"],
                            "auto_end": False,
                        }
                    )
                    state["exit_offered"] = True

        except GenerationCancelled:
            return
        except Exception as exc:  # noqa: BLE001
            if not is_api:
                reply = fallback_local_text(int(state.get("fallback_turn_count") or 0))
                emit_stream_event(
                    {
                        "type": "fallback",
                        "text": reply,
                        "message": f"模型不可用，已切换降级陪练：{exc}",
                    }
                )
                state["messages"] = list(state["messages"]) + [
                    AIMessage(content=reply)
                ]
                state["fallback_turn_count"] = int(
                    state.get("fallback_turn_count") or 0
                ) + 1
                state["degraded"] = True
                state["last_assistant_text"] = reply
            else:
                yield {"type": "error", "message": str(exc)}
                return

    for ev in events:
        yield ev

    # 补齐 last_assistant_text
    if not state.get("last_assistant_text"):
        for m in reversed(list(state.get("messages") or [])):
            if "AI" in getattr(m, "__class__", type(m)).__name__:
                state["last_assistant_text"] = str(getattr(m, "content", "") or "")
                break
            if isinstance(m, dict) and m.get("role") == "assistant":
                state["last_assistant_text"] = str(m.get("content") or "")
                break

    _save_state(conn, session_id, state)
    yield {
        "type": "done",
        "done": bool(state.get("done")),
        "reply": str(state.get("last_assistant_text") or ""),
        "graph": "api" if is_api else "local",
    }


def _local_reply(
    state: dict[str, Any],
    *,
    cancel_event: threading.Event,
    session_id: str,
    thread_id: str,
) -> dict[str, Any]:
    from langchain_core.messages import AIMessage, SystemMessage

    raw_messages = list(state.get("messages") or [])
    if bool(state.get("code_epoch_bumped")):
        messages = messages_after_code_epoch(raw_messages)
    else:
        messages = trim_messages_for_local(raw_messages)
    user_text = last_human_text(raw_messages)
    last_asst = str(state.get("last_assistant_text") or "")
    rejected = append_unique(
        list(state.get("rejected_suspicions") or []),
        extract_negations(user_text, last_asst),
    )
    idents = append_unique(
        list(state.get("mentioned_identifiers") or []),
        extract_identifiers(user_text + "\n" + last_asst),
    )
    vague_n = update_vague_counter(state, user_text)
    working = {**state, "rejected_suspicions": rejected}
    system = SystemMessage(
        content=build_system_content(working, include_full_context=False)
    )
    outbound = [system, *messages]
    turn = int(state.get("turn_count") or 0)
    fallback_turn = int(state.get("fallback_turn_count") or 0)
    reply, stripped = stream_model_reply(
        outbound=outbound,
        cancel_event=cancel_event,
        session_id=session_id,
        thread_id=thread_id,
        meta={
            "node": "classic_local_reply",
            "graph": "local",
            "fallback_turn": fallback_turn,
        },
    )
    emit_stream_event({"type": "token", "text": reply})
    offer = False
    if is_repetitive_reply(last_asst, reply):
        offer = True
    out = {
        "messages": list(raw_messages) + [AIMessage(content=reply)],
        "done": False,
        "turn_count": turn + 1,
        "rejected_suspicions": rejected,
        "mentioned_identifiers": idents,
        "last_assistant_text": reply,
        "guardrail_stripped": stripped,
        "consecutive_vague": vague_n,
        "pending_action": "",
        "code_epoch_bumped": False,
        "generation_error": "",
    }
    probe = {**state, **out, "last_assistant_text": reply}
    if should_offer_exit(probe, user_message=user_text)[0] and not state.get(
        "exit_offered"
    ):
        out["_offer_exit"] = True
    return out


def _api_guided(
    state: dict[str, Any],
    *,
    cancel_event: threading.Event,
    session_id: str,
    thread_id: str,
    extra: str,
    node: str,
    end_session: bool = False,
) -> dict[str, Any]:
    from langchain_core.messages import AIMessage, SystemMessage

    messages = list(state.get("messages") or [])
    if bool(state.get("code_epoch_bumped")):
        messages = messages_after_code_epoch(messages)
    # 压缩
    turn = int(state.get("turn_count") or 0)
    context_summary = str(state.get("context_summary") or "")
    if turn >= API_COMPRESS_AFTER_TURNS and len(messages) > 5:
        keep = messages[-4:]
        old = messages[:-4]
        bits = []
        for m in old:
            role = "用户" if "Human" in m.__class__.__name__ else "助手"
            bits.append(f"- {role}：{str(getattr(m, 'content', '') or '')[:120]}")
        context_summary = (
            (context_summary + "\n" if context_summary else "")
            + "\n".join(bits[-12:])
        ).strip()[:2000]
        messages = [
            AIMessage(content="（系统已压缩更早轮次。）"),
            *keep,
        ]

    user_text = last_human_text(messages)
    last_asst = str(state.get("last_assistant_text") or "")
    rejected = append_unique(
        list(state.get("rejected_suspicions") or []),
        extract_negations(user_text, last_asst),
    )
    idents = append_unique(
        list(state.get("mentioned_identifiers") or []),
        extract_identifiers(user_text + "\n" + last_asst),
    )
    vague_n = update_vague_counter(state, user_text)
    working = {
        **state,
        "messages": messages,
        "rejected_suspicions": rejected,
        "context_summary": context_summary,
    }
    system = SystemMessage(content=build_system_content(working, extra=extra))
    outbound = [system, *messages]
    reply, stripped = stream_model_reply(
        outbound=outbound,
        cancel_event=cancel_event,
        session_id=session_id,
        thread_id=thread_id,
        meta={"node": node, "graph": "api"},
    )
    emit_stream_event({"type": "token", "text": reply})
    out: dict[str, Any] = {
        "messages": list(state.get("messages") or []) + [AIMessage(content=reply)],
        "done": bool(end_session),
        "turn_count": turn + 1,
        "rejected_suspicions": rejected,
        "mentioned_identifiers": idents,
        "last_assistant_text": reply,
        "guardrail_stripped": stripped,
        "consecutive_vague": vague_n,
        "pending_action": "",
        "context_summary": context_summary,
        "code_epoch_bumped": False,
        "exit_offered": True,
        "generation_error": "",
    }
    if end_session:
        end_conn = init_db()
        try:
            abandon_session(end_conn, session_id)
        finally:
            end_conn.close()
    return out
