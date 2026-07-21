"""陪练会话服务：模板即时启动，LangGraph 管理多轮状态。"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Optional

from langgraph.graph import MessagesState

from leetcode_tracker.coach.context import build_coach_context
from leetcode_tracker.coach.debug_log import log_llm_turn
from leetcode_tracker.coach.guardrail import apply_code_block_guardrail
from leetcode_tracker.coach.opening import template_opening
from leetcode_tracker.coach.prompts import system_prompt_for_status
from leetcode_tracker.coach.sessions import (
    abandon_session,
    get_or_create_session,
    get_session,
    is_session_abandoned,
    touch_session,
)
from leetcode_tracker.infra.config import switch_to_ollama_keep_key
from leetcode_tracker.infra.db import init_db as _init_db_for_failover
from leetcode_tracker.infra.paths import db_path
from leetcode_tracker.llm.provider import build_chat_model, get_llm_settings

_END_PHRASES = ("结束", "够了", "先这样", "不用了", "谢谢")
_SESSION_LOCKS: dict[str, threading.Lock] = {}
_SESSION_LOCKS_GUARD = threading.Lock()


class CoachState(MessagesState):
    context_markdown: str
    submission_status: str
    done: bool
    fallback_turn_count: int
    generation_error: str
    provider_failover: bool


class GenerationCancelled(Exception):
    """客户端断开后停止消费模型流。"""


def _is_done_message(text: str) -> bool:
    t = text.strip().lower()
    return any(p in t for p in _END_PHRASES)


def _fallback_reply(turn: int) -> str:
    replies = (
        "模型暂时不可用，我们先不看答案。你能说出这次最小的失败用例，以及实际结果和预期结果分别是什么吗？",
        "先沿着你的思路排查：你认为哪个不变量应该始终成立？请挑一次循环或一次递归调用验证它。",
        "把问题再缩小一点：边界、状态转移和数据范围中，你现在最不确定哪一项？",
        "暂时不用改代码。请先用一句话说明当前做法为什么应该成立，再找一个能推翻这句话的输入。",
    )
    return replies[max(0, turn) % len(replies)]


def _session_lock(session_id: str) -> threading.Lock:
    with _SESSION_LOCKS_GUARD:
        return _SESSION_LOCKS.setdefault(session_id, threading.Lock())


def try_acquire_session(session_id: str) -> bool:
    return _session_lock(session_id).acquire(blocking=False)


def release_session(session_id: str) -> None:
    lock = _session_lock(session_id)
    if lock.locked():
        lock.release()


@contextmanager
def _graph_for_turn(
    cancel_event: threading.Event,
    *,
    session_id: str,
    thread_id: str,
):
    from langchain_core.messages import AIMessage, SystemMessage
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.config import get_stream_writer
    from langgraph.graph import END, START, StateGraph

    def route_turn(state: CoachState) -> str:
        if bool(state.get("done")):
            return "close_session"
        messages = list(state.get("messages") or [])
        last = messages[-1] if messages else None
        content = str(getattr(last, "content", "") or "")
        return "close_session" if _is_done_message(content) else "coach_reply"

    def close_session(_state: CoachState) -> dict[str, Any]:
        summary = (
            "好的，今天先到这里。记得把刚才怀疑的点记下来，"
            "下次提交前再对一遍。"
        )
        get_stream_writer()({"type": "token", "text": summary})
        return {"messages": [AIMessage(content=summary)], "done": True}

    def coach_reply(state: CoachState) -> dict[str, Any]:
        writer = get_stream_writer()
        status = str(state.get("submission_status") or "")
        prompt = system_prompt_for_status(status)
        context_markdown = str(state.get("context_markdown") or "")
        system = SystemMessage(
            content=f"{prompt}\n\n## 陪练上下文\n{context_markdown}"
        )
        outbound = [system, *list(state.get("messages") or [])]
        accumulated = ""
        fallback_turn = int(state.get("fallback_turn_count") or 0)
        try:
            model = build_chat_model()
            for chunk in model.stream(outbound):
                if cancel_event.is_set():
                    raise GenerationCancelled()
                piece = getattr(chunk, "content", None)
                if not piece:
                    continue
                text = piece if isinstance(piece, str) else str(piece)
                if not text:
                    continue
                accumulated += text
            if not accumulated:
                raise RuntimeError("模型未返回内容")
            # 先攒齐再过软护栏，再推 SSE，避免代码块先流到用户
            reply, stripped = apply_code_block_guardrail(accumulated)
            writer({"type": "token", "text": reply})
            log_llm_turn(
                session_id=session_id,
                thread_id=thread_id,
                messages=outbound,
                reply=reply,
                meta={
                    "node": "coach_reply",
                    "fallback_turn": fallback_turn,
                    "submission_status": status,
                    "prompt_mode": "ac" if status == "Accepted" else "debug",
                    "stripped": stripped,
                },
            )
            return {
                "messages": [AIMessage(content=reply)],
                "done": False,
                "fallback_turn_count": fallback_turn,
                "generation_error": "",
                "provider_failover": False,
            }
        except GenerationCancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            was_api = get_llm_settings().get("provider") == "api"
            log_llm_turn(
                session_id=session_id,
                thread_id=thread_id,
                messages=outbound,
                error=str(exc),
                meta={
                    "node": "coach_reply",
                    "fallback_turn": fallback_turn,
                    "submission_status": status,
                    "prompt_mode": "ac" if status == "Accepted" else "debug",
                    "provider_failover": was_api,
                },
            )
            return {
                "done": False,
                "fallback_turn_count": fallback_turn,
                "generation_error": str(exc),
                "provider_failover": was_api,
            }

    def route_after_reply(state: CoachState) -> str:
        return "fallback_reply" if state.get("generation_error") else "__end__"

    def fallback_reply(state: CoachState) -> dict[str, Any]:
        fallback_turn = int(state.get("fallback_turn_count") or 0)
        err = str(state.get("generation_error") or "unknown error")
        failover = bool(state.get("provider_failover"))

        if failover:
            switch_to_ollama_keep_key()
            failover_conn = _init_db_for_failover()
            try:
                abandon_session(failover_conn, session_id)
            finally:
                failover_conn.close()
            reply = (
                "DeepSeek 暂时不可达"
                + (f"（{err}）" if err else "")
                + "。已将设置切回本地 Ollama（API Key 仍保留）。"
                "本对话已结束，请关闭本页后重新打开陪练再继续。"
            )
            log_llm_turn(
                session_id=session_id,
                thread_id=thread_id,
                messages=list(state.get("messages") or []),
                reply=reply,
                error=err,
                meta={
                    "node": "fallback_reply",
                    "provider_failover": True,
                    "session_abandoned": True,
                },
            )
            get_stream_writer()(
                {
                    "type": "fallback",
                    "text": reply,
                    "message": "DeepSeek 不可达，已切回本地 Ollama；请重新打开陪练。",
                    "reopen_required": True,
                    "session_abandoned": True,
                }
            )
            return {
                "messages": [AIMessage(content=reply)],
                "done": True,
                "fallback_turn_count": fallback_turn + 1,
                "generation_error": "",
                "provider_failover": False,
            }

        reply = _fallback_reply(fallback_turn)
        log_llm_turn(
            session_id=session_id,
            thread_id=thread_id,
            messages=list(state.get("messages") or []),
            reply=reply,
            error=err,
            meta={"node": "fallback_reply", "fallback_turn": fallback_turn},
        )
        get_stream_writer()(
            {
                "type": "fallback",
                "text": reply,
                "message": f"模型不可用，已切换本地降级陪练：{err}",
            }
        )
        return {
            "messages": [AIMessage(content=reply)],
            "done": False,
            "fallback_turn_count": fallback_turn + 1,
            "generation_error": "",
            "provider_failover": False,
        }

    builder = StateGraph(CoachState)
    builder.add_node("coach_reply", coach_reply)
    builder.add_node("close_session", close_session)
    builder.add_node("fallback_reply", fallback_reply)
    builder.add_conditional_edges(
        START,
        route_turn,
        {
            "coach_reply": "coach_reply",
            "close_session": "close_session",
        },
    )
    builder.add_conditional_edges(
        "coach_reply",
        route_after_reply,
        {
            "fallback_reply": "fallback_reply",
            "__end__": END,
        },
    )
    builder.add_edge("fallback_reply", END)
    builder.add_edge("close_session", END)

    checkpoint_conn = sqlite3.connect(
        str(db_path()), check_same_thread=False, timeout=5.0
    )
    checkpoint_conn.execute("PRAGMA busy_timeout = 5000")
    try:
        graph = builder.compile(checkpointer=SqliteSaver(checkpoint_conn))
        yield graph
    finally:
        checkpoint_conn.close()


def _session_payload(
    session: dict[str, Any],
    *,
    opening_source: str,
    reused: bool,
    requested_submission_id: str,
    resolved_submission_id: str,
    fallback_used: bool,
    context_preview: str = "",
) -> dict[str, Any]:
    return {
        "session_id": session["session_id"],
        "opening": session["opening"],
        "problem_id": session["problem_id"],
        "submission_id": session["submission_id"],
        "submission_status": session.get("submission_status") or "",
        "requested_submission_id": requested_submission_id,
        "resolved_submission_id": resolved_submission_id,
        "fallback_used": fallback_used,
        "opening_source": opening_source,
        "reused": reused,
        "context_preview": context_preview
        or str(session.get("context_markdown") or "")[:400],
    }


def prepare(
    conn: sqlite3.Connection,
    submission_id: str = "",
    *,
    problem_id: Optional[int] = None,
    reuse_existing: bool = True,  # noqa: ARG001 - 保留 CLI/API 兼容参数
) -> dict[str, Any]:
    """只读提交事实并原子创建模板会话；绝不调用 LLM。"""
    ctx = build_coach_context(conn, submission_id, problem_id=problem_id)
    status = str(ctx["status"])
    opening = template_opening(
        problem_id=int(ctx["problem_id"]),
        title=str(ctx["title"]),
        status=status,
        placement=ctx.get("placement"),
        today_count=int(ctx["today_count"]),
    )
    session, created = get_or_create_session(
        conn,
        submission_id=str(ctx["resolved_submission_id"]),
        problem_id=int(ctx["problem_id"]),
        opening=opening,
        context_markdown=str(ctx["markdown"]),
        submission_status=status,
    )
    return _session_payload(
        session,
        opening_source="template" if created else "cached",
        reused=not created,
        requested_submission_id=str(ctx["requested_submission_id"]),
        resolved_submission_id=str(ctx["resolved_submission_id"]),
        fallback_used=bool(ctx["fallback_used"]),
        context_preview=str(ctx["markdown"])[:400],
    )


def chat(
    conn: sqlite3.Connection, session_id: str, message: str
) -> dict[str, Any]:
    """同步续聊（CLI 使用）。Web 优先走 chat_stream / SSE。"""
    chunks: list[str] = []
    done = False
    for event in chat_stream(conn, session_id, message):
        if event.get("type") in {"token", "fallback"}:
            chunks.append(str(event.get("text") or ""))
        elif event.get("type") == "done":
            done = bool(event.get("done"))
            if event.get("reply") and not chunks:
                chunks.append(str(event["reply"]))
        elif event.get("type") == "error":
            raise RuntimeError(str(event.get("message") or "chat failed"))
    return {"reply": "".join(chunks), "done": done}


def chat_stream(
    conn: sqlite3.Connection,
    session_id: str,
    message: str,
    *,
    cancel_event: Optional[threading.Event] = None,
    lock_acquired: bool = False,
) -> Iterator[dict[str, Any]]:
    """由 LangGraph 执行单回合并输出 ready/token/fallback/done/error。"""
    from langchain_core.messages import AIMessage, HumanMessage

    session = get_session(conn, session_id)
    if session is None:
        yield {"type": "error", "message": f"未找到会话: {session_id}"}
        return
    if is_session_abandoned(session):
        yield {
            "type": "error",
            "code": "session_abandoned",
            "message": "本对话已结束（云端不可达后已切回本地）。请重新打开陪练再继续。",
            "reopen_required": True,
        }
        return

    owns_lock = not lock_acquired
    if owns_lock and not try_acquire_session(session_id):
        yield {
            "type": "error",
            "code": "session_busy",
            "message": "该会话正在处理上一条消息",
        }
        return

    stop = cancel_event or threading.Event()
    reply_parts: list[str] = []
    done = False
    try:
        yield {"type": "ready", "session_id": session_id}
        thread_id = str(session["thread_id"])
        with _graph_for_turn(
            stop, session_id=session_id, thread_id=thread_id
        ) as graph:
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = graph.get_state(config)
            has_messages = bool(
                snapshot and snapshot.values and snapshot.values.get("messages")
            )
            messages: list[Any] = [HumanMessage(content=message)]
            if not has_messages:
                messages.insert(0, AIMessage(content=str(session["opening"])))
            graph_input = {
                "messages": messages,
                "context_markdown": str(session.get("context_markdown") or ""),
                "submission_status": str(session.get("submission_status") or ""),
                "done": bool(
                    snapshot.values.get("done")
                    if snapshot and snapshot.values
                    else False
                ),
                "fallback_turn_count": int(
                    snapshot.values.get("fallback_turn_count") or 0
                    if snapshot and snapshot.values
                    else 0
                ),
                "generation_error": "",
            }
            for mode, data in graph.stream(
                graph_input,
                config,
                stream_mode=["custom", "updates"],
            ):
                if stop.is_set():
                    raise GenerationCancelled()
                if mode != "custom" or not isinstance(data, dict):
                    continue
                event = dict(data)
                if event.get("type") in {"token", "fallback"}:
                    reply_parts.append(str(event.get("text") or ""))
                yield event
            final_snapshot = graph.get_state(config)
            done = bool(
                final_snapshot.values.get("done")
                if final_snapshot and final_snapshot.values
                else False
            )
        touch_session(conn, session_id)
        yield {"type": "done", "done": done, "reply": "".join(reply_parts)}
    except GenerationCancelled:
        return
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
    finally:
        if owns_lock:
            release_session(session_id)
