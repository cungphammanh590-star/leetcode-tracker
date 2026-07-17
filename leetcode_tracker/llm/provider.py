"""Ollama 与配置加载。"""

from __future__ import annotations

from typing import Any

from leetcode_tracker.config import load_config


def get_llm_settings() -> dict[str, str]:
    cfg = load_config()
    llm = cfg.get("llm") or {}
    return {
        "provider": str(llm.get("provider") or "ollama"),
        "coach_model": str(llm.get("coach_model") or "qwen2.5:7b-instruct-q4_K_M"),
        "api_provider": str(llm.get("api_provider") or ""),
        "api_key": str(llm.get("api_key") or ""),
    }


def build_chat_model():
    settings = get_llm_settings()
    if settings["provider"] != "ollama":
        raise RuntimeError(
            "v0.3.0 仅实现 Ollama 本地陪练；云端 API 留待后续版本。"
        )
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise RuntimeError(
            "缺少 langchain-ollama。请执行: pip install 'leetcode-tracker[coach]'"
        ) from exc

    return ChatOllama(
        model=settings["coach_model"],
        temperature=0.4,
    )


def probe_ollama_available() -> tuple[bool, str]:
    try:
        build_chat_model()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
