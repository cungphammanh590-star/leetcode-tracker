"""陪练开发调试日志：每轮发给大模型的完整内容落盘到仓库 log/。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from leetcode_tracker.paths import data_dir, ensure_dir


def coach_log_dir() -> Path:
    """优先写仓库根目录/log（开发）；非 checkout 安装则落到 data_dir/log。"""
    repo_root = Path(__file__).resolve().parents[2]
    if (repo_root / "pyproject.toml").is_file():
        return repo_root / "log"
    return data_dir() / "log"


def _safe_name(value: str, *, max_len: int = 36) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in value.strip())
    return (cleaned or "unknown")[:max_len]


def _message_role(message: Any) -> str:
    role = getattr(message, "type", None)
    if role:
        return str(role)
    name = type(message).__name__.removesuffix("Message").lower()
    return name or "message"


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if content is None:
        return ""
    return content if isinstance(content, str) else str(content)


def _format_messages(messages: Sequence[Any]) -> str:
    parts: list[str] = []
    for i, msg in enumerate(messages, start=1):
        role = _message_role(msg)
        body = _message_content(msg)
        parts.append(f"### [{i}] {role}\n\n{body}\n")
    return "\n".join(parts) if parts else "(empty)\n"


def log_llm_turn(
    *,
    session_id: str,
    thread_id: str = "",
    messages: Sequence[Any],
    reply: str = "",
    error: str = "",
    meta: Optional[dict[str, Any]] = None,
) -> Optional[Path]:
    """写入一轮 LLM 请求/回复；失败时静默返回 None，不影响陪练主路径。"""
    try:
        root = coach_log_dir() / "coach"
        ensure_dir(root)
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%d-%H%M%S-%f")[:-3]
        sid = _safe_name(session_id)
        path = root / f"{stamp}_{sid}.md"

        meta_lines = [
            f"- utc: {now.isoformat()}",
            f"- session_id: {session_id}",
            f"- thread_id: {thread_id or session_id}",
            f"- message_count: {len(messages)}",
        ]
        if meta:
            for key, value in meta.items():
                meta_lines.append(f"- {key}: {value}")

        sections = [
            "# Coach LLM turn",
            "",
            *meta_lines,
            "",
            "## Messages sent to model",
            "",
            _format_messages(messages),
        ]
        if reply:
            sections.extend(["## Model reply", "", reply, ""])
        if error:
            sections.extend(["## Error", "", error, ""])

        path.write_text("\n".join(sections), encoding="utf-8")
        return path
    except Exception:  # noqa: BLE001 - 调试日志绝不可拖垮主流程
        return None


def clean_coach_debug_logs() -> list[Path]:
    """删除陪练调试日志（仓库 log/coach 或 data_dir/log/coach）。"""
    root = coach_log_dir() / "coach"
    if not root.is_dir():
        return []
    removed: list[Path] = []
    for path in sorted(root.glob("*.md")):
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed
