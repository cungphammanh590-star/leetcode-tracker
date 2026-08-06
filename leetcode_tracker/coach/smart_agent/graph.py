"""智能教练 LangGraph：意图 → 阶段 → 拒答/提议/Agent。"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Annotated, Literal, Optional, TypedDict

from leetcode_tracker.coach.graphs.common import (
    GenerationCancelled,
    close_checkpoint_graph,
    open_checkpoint_conn,
)
from leetcode_tracker.coach.smart_agent.intent_smart import (
    classify_smart_intent,
    intent_to_phase,
    should_reclassify,
    wants_code_原文,
)
from leetcode_tracker.coach.smart_agent.offer import build_offer_payload, status_one_liner
from leetcode_tracker.coach.smart_agent.phases import coerce_phase, transition
from leetcode_tracker.coach.smart_agent.policy import (
    apply_smart_reply_policy,
    build_refuse_nudge,
)
from leetcode_tracker.coach.smart_agent.tools import MAX_TOOL_ROUNDS, TOOL_SPECS, run_tool
from leetcode_tracker.llm.provider import build_chat_model


def _add_messages(left: list[Any], right: list[Any]) -> list[Any]:
    return list(left or []) + list(right or [])


class SmartState(TypedDict, total=False):
    messages: Annotated[list[Any], _add_messages]
    phase: str
    intent: str
    turn_count: int
    pending_action: str
    problem_id: int
    allow_code_原文: bool
    route: str
    reply: str
    done: bool
    offer_cta: str
    user_profile: dict[str, Any]
    refuse_short: bool


_SYSTEM = """你是「智能教练」：苏格拉底式刷题陪练，用中文简短回应。

规则：
1. 先弄清用户处在：闲聊/看进度/选题/题内跟练。可用工具查画像、未通过题、掌握度、选题候选与当前代码。
2. 空闲时可提议：有未通过→续刷（给链接）；否则→新荐。用户确认后才 bind_problem。
3. 默认只讲思路与检查点；仅当用户明确要求代码原文时，才给≤10行片段；禁止整题完整可运行解法与大段代码块。
4. 对照上次建议验收时：若库无新提交须明确说明。
5. 绝不提供历史 Accepted 源码。题号只能来自工具返回的候选。
6. 每次回复控制在几段以内。
"""


def _action_prompt(action: str) -> str:
    mapping = {
        "close": "请收束本轮：总结卡点与下一步，结束口吻收尾。",
        "diagnose": "请给出简短诊断（2～4点），引用真实标识符，不要完整解法。",
        "deep_analysis": "请用文字步骤+伪代码讲思路，默认不要代码原文。",
        "optimize": "请给优化方向，不要完整重构代码。",
    }
    return mapping.get(action, "")


def compile_smart_graph(
    cancel_event: threading.Event,
    *,
    session: dict[str, Any],
):
    """编译智能教练图。

    注意：节点内不得闭包捕获外层 sqlite3.Connection。
    LangGraph / checkpointer 可能在其它线程执行节点，跨线程复用会触发
    「SQLite objects created in a thread can only be used in that same thread」。
    节点内用 init_db() 现场开连接并关闭。
    """
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.config import get_stream_writer
    from langgraph.graph import END, START, StateGraph

    from leetcode_tracker.infra.db import init_db

    history_ref: list[dict[str, str]] = []

    def _with_db(fn):  # type: ignore[no-untyped-def]
        conn = init_db()
        try:
            return fn(conn)
        finally:
            conn.close()

    def classify(state: SmartState) -> dict[str, Any]:
        from langgraph.config import get_stream_writer as _w

        msgs = list(state.get("messages") or [])
        user_text = ""
        for m in reversed(msgs):
            if "Human" in m.__class__.__name__:
                user_text = str(getattr(m, "content", "") or "")
                break
        turn = int(state.get("turn_count") or 0) + 1
        phase = coerce_phase(state.get("phase"))
        bound = int(state.get("problem_id") or session.get("problem_id") or 0)
        action = str(state.get("pending_action") or "")
        if should_reclassify(phase=phase, turn_count=turn, user_text=user_text):
            intent, _conf = classify_smart_intent(
                user_text, bound_problem_id=bound, action=action
            )
        else:
            intent = str(state.get("intent") or "in_problem_help") or "in_problem_help"
        new_phase = transition(
            phase, coerce_phase(intent_to_phase(intent, bound=bound > 0), default=phase)
        )
        if action in {"close", "diagnose"}:
            new_phase = "wrap"
        allow = wants_code_原文(user_text)
        # 路由
        if intent == "off_topic":
            route = "refuse"
        elif intent in {"practice_continue", "practice_new", "meta_product", "clarify"} and (
            new_phase in {"lobby", "prep", "wrap"} or bound <= 0
        ):
            route = "offer"
        elif intent == "status_review":
            route = "agent"
            new_phase = "today_brief"
        elif new_phase == "wrap" or action in {"close", "diagnose", "deep_analysis"}:
            route = "agent"
        else:
            route = "agent"
        # 一题结束无优化 → wrap+offer
        if action == "close" or (
            intent in {"clarify", "meta_product"} and phase == "in_problem" and "做完" in user_text
        ):
            route = "offer"
            new_phase = "wrap"
        try:
            _w()({"type": "info", "phase": new_phase, "intent": intent})
        except Exception:  # noqa: BLE001
            pass
        return {
            "intent": intent,
            "phase": new_phase,
            "turn_count": turn,
            "allow_code_原文": allow,
            "route": route,
            "problem_id": bound,
        }

    def route_after_classify(state: SmartState) -> str:
        return str(state.get("route") or "agent")

    def refuse_node(state: SmartState) -> dict[str, Any]:
        writer = get_stream_writer()
        profile = state.get("user_profile") or {}

        def _offer(conn: sqlite3.Connection) -> dict[str, Any]:
            return build_offer_payload(
                conn, weak_tags=list(profile.get("weak_tags") or [])
            )

        offer = _with_db(_offer)
        reply = build_refuse_nudge(
            status_line=status_one_liner(profile),
            cta=str(offer.get("cta") or ""),
            short=bool(state.get("refuse_short")),
        )
        writer({"type": "token", "text": reply})
        return {
            "messages": [AIMessage(content=reply)],
            "reply": reply,
            "done": False,
            "offer_cta": str(offer.get("cta") or ""),
            "refuse_short": True,
            "phase": "lobby",
        }

    def offer_node(state: SmartState) -> dict[str, Any]:
        writer = get_stream_writer()
        profile = state.get("user_profile") or {}

        def _offer(conn: sqlite3.Connection) -> dict[str, Any]:
            return build_offer_payload(
                conn, weak_tags=list(profile.get("weak_tags") or [])
            )

        offer = _with_db(_offer)
        prefix = ""
        if coerce_phase(state.get("phase")) == "wrap":
            prefix = "这题先收束。\n"
        reply = prefix + str(offer.get("cta") or "可以报题号继续。")
        writer({"type": "token", "text": reply})
        done = str(state.get("pending_action") or "") in {"close", "diagnose"}
        return {
            "messages": [AIMessage(content=reply)],
            "reply": reply,
            "done": done,
            "offer_cta": reply,
            "phase": "lobby" if not done else "wrap",
        }

    def agent_node(state: SmartState) -> dict[str, Any]:
        writer = get_stream_writer()
        if cancel_event.is_set():
            raise GenerationCancelled()
        model = build_chat_model()
        bound = model.bind_tools(TOOL_SPECS)
        msgs = list(state.get("messages") or [])
        # 同步 history 供 get_last_advice
        history_ref.clear()
        for m in msgs:
            name = m.__class__.__name__
            content = str(getattr(m, "content", "") or "")
            if "Human" in name:
                history_ref.append({"role": "user", "content": content})
            elif "AI" in name and content:
                history_ref.append({"role": "assistant", "content": content})

        phase = coerce_phase(state.get("phase"))
        intent = str(state.get("intent") or "")
        extra = (
            f"\n当前阶段 phase={phase} intent={intent}。"
            f" allow_code_原文={bool(state.get('allow_code_原文'))}。"
        )
        if intent == "want_full_answer" and not state.get("allow_code_原文"):
            extra += "用户想要完整答案：先讲思路与检查点，不要贴代码原文。"
        if intent == "status_review":
            extra += "请先调用 get_user_profile_summary 或 get_topic_mastery 再回答。"
        if phase in {"lobby", "prep"} and intent in {
            "practice_continue",
            "practice_new",
            "clarify",
        }:
            extra += "可调用 suggest_next_problems / list_unpassed_problems 做提议。"

        outbound: list[Any] = [SystemMessage(content=_SYSTEM + extra)]
        # 只送近若干轮，避免过长
        for m in msgs[-16:]:
            outbound.append(m)

        tool_rounds = 0
        final_ai: Any = None
        while tool_rounds < MAX_TOOL_ROUNDS:
            if cancel_event.is_set():
                raise GenerationCancelled()
            ai = bound.invoke(outbound)
            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                final_ai = ai
                break
            outbound.append(ai)
            for call in tool_calls:
                if isinstance(call, dict):
                    name = str(call.get("name") or "")
                    call_id = str(call.get("id") or name or "tool")
                    args = call.get("args") or {}
                else:
                    name = str(getattr(call, "name", "") or "")
                    call_id = str(getattr(call, "id", "") or name or "tool")
                    args = getattr(call, "args", None) or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                if not isinstance(args, dict):
                    args = {}
                def _run(conn: sqlite3.Connection) -> str:
                    return run_tool(
                        name,
                        conn=conn,
                        session=session,
                        history=history_ref,
                        args=args,
                    )

                result = _with_db(_run)
                outbound.append(ToolMessage(content=result, tool_call_id=call_id))
            tool_rounds += 1
            # 绑定后刷新 problem_id
            session["problem_id"] = int(session.get("problem_id") or 0)

        if final_ai is None:
            outbound.append(
                HumanMessage(content="（系统）请基于已有观察直接作答，勿再调工具。")
            )
            content = ""
            for chunk in model.stream(outbound):
                if cancel_event.is_set():
                    raise GenerationCancelled()
                piece = getattr(chunk, "content", None) or ""
                text = piece if isinstance(piece, str) else str(piece)
                content += text
            reply = content.strip()
        else:
            content = getattr(final_ai, "content", "") or ""
            if isinstance(content, list):
                content = "".join(
                    str(p.get("text") if isinstance(p, dict) else p) for p in content
                )
            reply = str(content).strip()
            if not reply:
                reply = ""
                for chunk in model.stream(outbound + [HumanMessage(content="请直接作答。")]):
                    if cancel_event.is_set():
                        raise GenerationCancelled()
                    piece = getattr(chunk, "content", None) or ""
                    reply += piece if isinstance(piece, str) else str(piece)
                reply = reply.strip()

        reply, _ = apply_smart_reply_policy(
            reply, allow_code_原文=bool(state.get("allow_code_原文"))
        )
        if not reply:
            reply = "我在。你可以报题号继续，或让我根据未通过题/薄弱点给你下一步。"
        writer({"type": "token", "text": reply})
        pid = int(session.get("problem_id") or 0)
        phase_out = "in_problem" if pid > 0 else coerce_phase(state.get("phase"))
        done = str(state.get("pending_action") or "") in {"close", "diagnose"}
        return {
            "messages": [AIMessage(content=reply)],
            "reply": reply,
            "done": done,
            "problem_id": pid,
            "phase": phase_out if not done else "wrap",
        }

    builder = StateGraph(SmartState)
    builder.add_node("classify", classify)
    builder.add_node("refuse", refuse_node)
    builder.add_node("offer", offer_node)
    builder.add_node("agent", agent_node)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {"refuse": "refuse", "offer": "offer", "agent": "agent"},
    )
    builder.add_edge("refuse", END)
    builder.add_edge("offer", END)
    builder.add_edge("agent", END)

    checkpoint_conn = open_checkpoint_conn()
    try:
        graph = builder.compile(checkpointer=SqliteSaver(checkpoint_conn))
        graph._leetcode_checkpoint_conn = checkpoint_conn  # type: ignore[attr-defined]
        return graph
    except Exception:
        checkpoint_conn.close()
        raise


def run_smart_turn(
    *,
    session: dict[str, Any],
    cancel_event: threading.Event,
) -> Any:
    """编译图并返回 graph（供 stream）。"""
    return compile_smart_graph(cancel_event, session=session)
