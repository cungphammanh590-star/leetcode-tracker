"""智能教练 SSE 对话流。"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from typing import Any, Optional

from leetcode_tracker.coach.graphs.common import GenerationCancelled
from leetcode_tracker.coach.guardrail import apply_code_block_guardrail
from leetcode_tracker.coach.smart_agent.history import load_history, save_history
from leetcode_tracker.coach.smart_agent.tools import (
    MAX_TOOL_ROUNDS,
    TOOL_SPECS,
    run_tool,
)
from leetcode_tracker.llm.provider import build_chat_model, get_llm_settings

_SYSTEM = """你是「智能教练」：苏格拉底式刷题陪练，用中文简短回应。

规则：
1. 会话可能尚未绑定题目（大厅模式）。用户提到题号或标题时，先用 bind_problem 绑定，再辅导。
2. 可用工具：get_session_binding / bind_problem / get_current_code / get_error_summary / get_last_advice。
3. 优先提问与定位，不要直接给完整可运行解法；禁止输出 markdown 代码块与整段源码。
4. 对照上次建议验收时：若最新提交无变化，须明确说明「库里还没有更新的提交」，不要假装已验证。
5. 绝不索取或复述历史 Accepted 源码；工具也不会提供。
6. 每次回复控制在几段以内，可给 1～2 个可执行的小检查点。
"""


def _action_prompt(action: str) -> str:
    mapping = {
        "close": "请收束本轮：总结我当前卡点与下一步，然后结束对话口吻收尾。",
        "diagnose": "请给出简短代码审查式诊断（2～4 点），引用真实标识符，不要给完整解法。",
        "deep_analysis": "请用文字步骤 + 伪代码级说明讲清思路，仍禁止完整可运行代码与代码块。",
        "optimize": "请从可读性/复杂度角度给优化方向，不要贴完整重构代码。",
        "show_skeleton": "请用文字骨架描述思路步骤，禁止完整源码与代码块。",
    }
    return mapping.get(action, "")


def chat_stream(
    conn: sqlite3.Connection,
    session: dict[str, Any],
    message: str,
    *,
    action: str = "",
    cancel_event: Optional[threading.Event] = None,
) -> Iterator[dict[str, Any]]:
    """Agent 单回合；事件含 ready/token/done/error。"""
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

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

    history = load_history(conn, session_id)
    if not history and session.get("opening"):
        history.append(
            {"role": "assistant", "content": str(session.get("opening") or "")}
        )

    outbound: list[Any] = [SystemMessage(content=_SYSTEM)]
    for item in history:
        if item["role"] == "user":
            outbound.append(HumanMessage(content=item["content"]))
        else:
            outbound.append(AIMessage(content=item["content"]))
    outbound.append(HumanMessage(content=user_text))

    try:
        model = build_chat_model()
        bound = model.bind_tools(TOOL_SPECS)
        tool_rounds = 0
        while tool_rounds < MAX_TOOL_ROUNDS:
            if stop.is_set():
                raise GenerationCancelled()
            ai = bound.invoke(outbound)
            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                # 无工具：流式再生成最终回复（避免 invoke 已消耗一轮时重复计费）
                content = getattr(ai, "content", "") or ""
                if isinstance(content, list):
                    content = "".join(
                        str(p.get("text") if isinstance(p, dict) else p) for p in content
                    )
                reply = str(content).strip()
                if not reply:
                    # 兜底再 stream 一次
                    reply = _stream_text(model, outbound, stop)
                reply, _ = apply_code_block_guardrail(reply)
                if reply:
                    yield {"type": "token", "text": reply}
                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": reply})
                save_history(conn, session_id, history)
                done = action in {"close", "diagnose"}
                yield {
                    "type": "done",
                    "done": done,
                    "reply": reply,
                    "graph": "smart",
                }
                return

            outbound.append(ai)
            for call in tool_calls:
                if stop.is_set():
                    raise GenerationCancelled()
                if isinstance(call, dict):
                    name = str(call.get("name") or "")
                    call_id = str(call.get("id") or name or "tool")
                    args = call.get("args") or call.get("arguments") or {}
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
                result = run_tool(
                    name,
                    conn=conn,
                    session=session,
                    history=history,
                    args=args,
                )
                outbound.append(
                    ToolMessage(content=result, tool_call_id=call_id)
                )
            tool_rounds += 1

        # 工具轮次用尽：强制无工具作答
        if stop.is_set():
            raise GenerationCancelled()
        outbound.append(
            HumanMessage(
                content="（系统）工具调用已达上限，请基于已有观察直接作答，勿再调工具。"
            )
        )
        reply = _stream_text(model, outbound, stop)
        reply, _ = apply_code_block_guardrail(reply)
        if reply:
            yield {"type": "token", "text": reply}
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        save_history(conn, session_id, history)
        done = action in {"close", "diagnose"}
        yield {"type": "done", "done": done, "reply": reply, "graph": "smart"}
    except GenerationCancelled:
        return
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}


def _stream_text(model: Any, outbound: list[Any], stop: threading.Event) -> str:
    accumulated = ""
    for chunk in model.stream(outbound):
        if stop.is_set():
            raise GenerationCancelled()
        piece = getattr(chunk, "content", None)
        if not piece:
            continue
        text = piece if isinstance(piece, str) else str(piece)
        if text:
            accumulated += text
    if not accumulated.strip():
        raise RuntimeError("模型未返回内容")
    return accumulated.strip()
