"""智能教练首轮/空闲意图：规则优先 + 可选轻量标签。"""

from __future__ import annotations

import re
from typing import Any, Optional

from leetcode_tracker.coach.smart_agent.phases import SmartIntent

_OFF_TOPIC = (
    "天气",
    "写诗",
    "讲个笑话",
    "股票",
    "恋爱",
    "今天吃什么",
    "帮我写小说",
    "chatgpt",
)
_STATUS = (
    "今天怎么样",
    "今日总结",
    "刷得怎么样",
    "薄弱",
    "掌握",
    "进度",
    "due",
    "复习队列",
    "今天进度",
)
_CONTINUE = (
    "继续",
    "接着做",
    "还没过",
    "没过的",
    "上次那题",
    "继续刷",
    "接着刷",
)
_NEW = (
    "下一题",
    "换一题",
    "推荐",
    "开刷",
    "刷什么",
    "做哪题",
    "新题",
)
_META = (
    "你能做什么",
    "怎么用",
    "你是谁",
    "帮助",
    "功能",
)
_FULL_ANSWER = (
    "完整代码",
    "完整解法",
    "直接给代码",
    "把答案给我",
    "AC代码",
    "全部代码",
    "整段代码",
    "可运行代码",
)
_CODE_原文 = (
    "代码原文",
    "写出代码",
    "写出来",
    "贴代码",
    "这段代码",
    "这句代码",
    "循环写出来",
    "给我代码",
    "把这句",
)


def wants_code_原文(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return any(p in t for p in _CODE_原文)


def classify_smart_intent(
    text: str,
    *,
    bound_problem_id: int = 0,
    action: str = "",
) -> tuple[SmartIntent, float]:
    """返回 (intent, confidence 0~1)。"""
    t = (text or "").strip()
    act = str(action or "").strip()
    if act in {"close", "diagnose", "deep_analysis"}:
        return "in_problem_help", 0.95
    if not t:
        return "clarify", 0.4

    if any(p in t for p in _FULL_ANSWER):
        return "want_full_answer", 0.9
    if any(p in t for p in _OFF_TOPIC) and not any(
        x in t for x in ("题", "刷", "leetcode", "力扣", "算法")
    ):
        return "off_topic", 0.85
    if any(p in t for p in _META) and len(t) < 40:
        return "meta_product", 0.8
    if any(p in t for p in _STATUS):
        return "status_review", 0.85
    if any(p in t for p in _CONTINUE):
        return "practice_continue", 0.8
    if any(p in t for p in _NEW):
        return "practice_new", 0.8

    # 题号 / 标题暗示
    if re.search(r"\b\d{1,4}\b", t) or "题" in t:
        return "in_problem_help", 0.75 if bound_problem_id <= 0 else 0.9

    if bound_problem_id > 0:
        return "in_problem_help", 0.7

    # 低置信：偏闲聊空闲
    if len(t) <= 6 and t in {"你好", "在吗", "嗨", "hello", "hi"}:
        return "meta_product", 0.6

    return "clarify", 0.45


def intent_to_phase(intent: SmartIntent, *, bound: bool) -> str:
    if bound and intent in {
        "in_problem_help",
        "want_full_answer",
        "clarify",
    }:
        return "in_problem"
    mapping = {
        "practice_continue": "lobby",
        "practice_new": "prep",
        "status_review": "today_brief",
        "in_problem_help": "in_problem" if bound else "lobby",
        "meta_product": "lobby",
        "off_topic": "lobby",
        "want_full_answer": "in_problem" if bound else "prep",
        "clarify": "lobby",
    }
    return mapping.get(intent, "lobby")


def should_reclassify(*, phase: str, turn_count: int, user_text: str) -> bool:
    if turn_count <= 1:
        return True
    if phase in {"lobby", "today_brief", "prep", "wrap"}:
        return True
    # 题内：仅明显换话题
    t = user_text or ""
    if any(p in t for p in _OFF_TOPIC + _STATUS + _NEW + _CONTINUE + _META):
        return True
    return False
