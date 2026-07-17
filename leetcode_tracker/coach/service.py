"""陪练会话服务：与采集解耦。

engage：用户打开陪练页时按需读库组上下文（模板开场，不调 LLM）。
chat：用户开口后才加载 LangGraph，并将 session 内已缓存的 context 注入模型。
"""

import sqlite3
from functools import lru_cache
from typing import Annotated, Any, TypedDict

from leetcode_tracker.coach.context import build_coach_context
from leetcode_tracker.coach.opening import template_opening
from leetcode_tracker.coach.prompts import COACH_SYSTEM_PROMPT
from leetcode_tracker.coach.sessions import create_session, get_session, touch_session
from leetcode_tracker.llm.provider import build_chat_model
from leetcode_tracker.paths import db_path

_END_PHRASES = ("结束", "够了", "先这样", "不用了", "谢谢")


def _is_done_message(text: str) -> bool:
    t = text.strip().lower()
    return any(p in t for p in _END_PHRASES)


def engage(conn: sqlite3.Connection, submission_id: str) -> dict[str, Any]:
    """按 submission 读库拼上下文 + 模板开场。不写 submissions，不阻塞采集。"""
    ctx = build_coach_context(conn, submission_id)
    placement = ctx.get("placement")
    opening = template_opening(
        problem_id=int(ctx["problem_id"]),
        title=str(ctx["title"]),
        status=str(ctx["status"]),
        placement=placement,
        today_count=int(ctx["today_count"]),
    )
    session = create_session(
        conn,
        submission_id=submission_id,
        problem_id=int(ctx["problem_id"]),
        opening=opening,
        context_markdown=str(ctx["markdown"]),
    )
    return {
        "session_id": session["session_id"],
        "opening": opening,
        "problem_id": session["problem_id"],
        "submission_id": submission_id,
        "context_preview": str(ctx["markdown"])[:400],
    }


@lru_cache(maxsize=1)
def _compiled_graph():
    from langchain_core.messages import SystemMessage
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, StateGraph
    from langgraph.graph.message import add_messages

    class CoachState(TypedDict):
        messages: Annotated[list, add_messages]
        context_markdown: str

    def coach_reply_node(state: CoachState) -> dict[str, Any]:
        model = build_chat_model()
        system = SystemMessage(
            content=f"{COACH_SYSTEM_PROMPT}\n\n## 陪练上下文\n{state['context_markdown']}"
        )
        response = model.invoke([system, *state["messages"]])
        return {"messages": [response]}

    builder = StateGraph(CoachState)
    builder.add_node("coach_reply", coach_reply_node)
    builder.set_entry_point("coach_reply")
    builder.add_edge("coach_reply", END)
    # from_conn_string 是 contextmanager；缓存编译图需要长生命周期连接
    ckpt_conn = sqlite3.connect(str(db_path()), check_same_thread=False)
    checkpointer = SqliteSaver(ckpt_conn)
    return builder.compile(checkpointer=checkpointer)


def chat(
    conn: sqlite3.Connection, session_id: str, message: str
) -> dict[str, Any]:
    from langchain_core.messages import AIMessage, HumanMessage

    session = get_session(conn, session_id)
    if session is None:
        raise ValueError(f"未找到会话: {session_id}")

    if _is_done_message(message):
        summary = (
            "好的，今天先到这里。记得把刚才怀疑的点记下来，下次提交前再对一遍。"
        )
        touch_session(conn, session_id)
        return {"reply": summary, "done": True}

    graph = _compiled_graph()
    config = {"configurable": {"thread_id": session["thread_id"]}}
    result = graph.invoke(
        {
            "messages": [HumanMessage(content=message)],
            "context_markdown": session["context_markdown"] or "",
        },
        config=config,
    )
    touch_session(conn, session_id)
    last = result["messages"][-1]
    reply = last.content if isinstance(last, AIMessage) else str(last)
    return {"reply": reply, "done": False}


def debrief_today(conn: sqlite3.Connection) -> str:
    from leetcode_tracker.stats import get_overview

    stats = get_overview(conn)
    wrong_n = len(stats.today_wrong)
    if stats.today_submissions == 0:
        return "今天还没有提交记录。刷一题后我可以帮你复盘。"
    return (
        f"今天共 {stats.today_submissions} 次提交，通过 {stats.today_accepted} 次，"
        f"错题 {wrong_n} 道，连续打卡 {stats.streak_days} 天。"
        "想从哪道题开始聊？输入题号或说「今日错题」。"
    )
