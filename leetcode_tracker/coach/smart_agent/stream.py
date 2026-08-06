"""智能教练 SSE：LangGraph 阶段图驱动。"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from typing import Any, Optional

from leetcode_tracker.coach.graphs.common import (
    GenerationCancelled,
    close_checkpoint_graph,
)
from leetcode_tracker.coach.profile import build_user_profile
from leetcode_tracker.coach.smart_agent.graph import (
    _action_prompt,
    compile_smart_graph,
)
from leetcode_tracker.coach.smart_agent.phases import coerce_phase
from leetcode_tracker.llm.provider import get_llm_settings


def chat_stream(
    conn: sqlite3.Connection,
    session: dict[str, Any],
    message: str,
    *,
    action: str = "",
    cancel_event: Optional[threading.Event] = None,
) -> Iterator[dict[str, Any]]:
    """Smart LangGraph 单回合；事件含 ready/token/info/done/error。"""
    from langchain_core.messages import AIMessage, HumanMessage

    stop = cancel_event or threading.Event()
    session_id = str(session["session_id"])
    thread_id = str(session.get("thread_id") or session_id)
    settings = get_llm_settings()
    if settings.get("provider") != "api" or not settings.get("api_key"):
        yield {
            "type": "error",
            "message": "智能教练需要云端 API Key。请到维护台配置后重试。",
        }
        return

    user_text = str(message or "").strip()
    extra = _action_prompt(action)
    if extra:
        user_text = f"{user_text}\n\n（系统指令）{extra}".strip() if user_text else extra
    if not user_text:
        yield {"type": "error", "message": "message 或 action 必填其一"}
        return

    yield {
        "type": "ready",
        "session_id": session_id,
        "graph": "smart",
        "actions_hint": ["diagnose", "deep_analysis", "close"],
    }

    graph = None
    try:
        profile = build_user_profile(conn)
        graph = compile_smart_graph(stop, session=session)
        config = {"configurable": {"thread_id": f"smart:{thread_id}"}}
        snapshot = graph.get_state(config)
        values = (snapshot.values if snapshot else {}) or {}
        prior = list(values.get("messages") or [])
        phase = coerce_phase(values.get("phase"))
        turn_count = int(values.get("turn_count") or 0)
        refuse_short = bool(values.get("refuse_short"))

        messages: list[Any] = []
        if not prior and session.get("opening"):
            messages.append(AIMessage(content=str(session.get("opening") or "")))
        messages.append(HumanMessage(content=user_text))

        bound_pid = int(session.get("problem_id") or 0)
        # prepare 已带题 → 直接题内
        if bound_pid > 0 and phase == "lobby" and turn_count == 0:
            phase = "in_problem"

        graph_input = {
            "messages": messages,
            "phase": phase,
            "intent": str(values.get("intent") or ""),
            "turn_count": turn_count,
            "pending_action": action,
            "problem_id": bound_pid,
            "allow_code_原文": False,
            "route": "",
            "reply": "",
            "done": False,
            "offer_cta": "",
            "user_profile": profile,
            "refuse_short": refuse_short,
        }

        reply = ""
        done = False
        for mode, data in graph.stream(
            graph_input,
            config,
            stream_mode=["custom", "updates"],
        ):
            if stop.is_set():
                raise GenerationCancelled()
            if mode == "custom" and isinstance(data, dict):
                event = dict(data)
                if event.get("type") == "token":
                    reply = str(event.get("text") or reply)
                yield event
            elif mode == "updates" and isinstance(data, dict):
                for _node, update in data.items():
                    if isinstance(update, dict):
                        if update.get("reply"):
                            reply = str(update.get("reply") or reply)
                        if "done" in update:
                            done = bool(update.get("done"))

        final = graph.get_state(config)
        if final and final.values:
            done = bool(final.values.get("done")) or done
            reply = str(final.values.get("reply") or reply)

        yield {
            "type": "done",
            "done": done,
            "reply": reply,
            "graph": "smart",
            "phase": coerce_phase(
                (final.values if final else {}).get("phase") if final else phase
            ),
        }
    except GenerationCancelled:
        return
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
    finally:
        if graph is not None:
            close_checkpoint_graph(graph)
