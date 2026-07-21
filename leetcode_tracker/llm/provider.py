"""LLM 提供方：Ollama 本地 或 DeepSeek（OpenAI 兼容）云端。"""

from __future__ import annotations

from typing import Any

from leetcode_tracker.infra.config import load_config

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_TIMEOUT_SECONDS = 45.0

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
API_TIMEOUT_SECONDS = 45.0


def get_llm_settings() -> dict[str, str]:
    cfg = load_config()
    llm = cfg.get("llm") or {}
    provider = str(llm.get("provider") or "ollama").strip().lower()
    if provider not in {"ollama", "api"}:
        provider = "ollama"
    api_provider = str(llm.get("api_provider") or "").strip().lower()
    if provider == "api" and not api_provider:
        api_provider = "deepseek"
    coach_model = str(llm.get("coach_model") or "").strip()
    if not coach_model:
        coach_model = (
            DEEPSEEK_DEFAULT_MODEL
            if provider == "api"
            else "qwen2.5:7b-instruct-q4_K_M"
        )
    return {
        "provider": provider,
        "coach_model": coach_model,
        "api_provider": api_provider,
        "api_key": str(llm.get("api_key") or "").strip(),
        "base_url": str(llm.get("base_url") or "").strip(),
    }


def build_chat_model():
    settings = get_llm_settings()
    if settings["provider"] == "ollama":
        return _build_ollama(settings)
    if settings["provider"] == "api":
        return _build_api(settings)
    raise RuntimeError(f"未知 llm.provider: {settings['provider']}")


def probe_chat_model() -> dict[str, Any]:
    """发一条极短请求验证当前配置是否可用。"""
    model = build_chat_model()
    settings = get_llm_settings()
    reply = model.invoke("只回复：ok")
    content = getattr(reply, "content", reply)
    text = content if isinstance(content, str) else str(content)
    return {
        "provider": settings["provider"],
        "api_provider": settings["api_provider"],
        "coach_model": settings["coach_model"],
        "reply_preview": text[:120],
    }


def _build_ollama(settings: dict[str, str]):
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise RuntimeError(
            "缺少 langchain-ollama。请执行: pip install 'leetcode-tracker[coach]'"
        ) from exc
    return ChatOllama(
        model=settings["coach_model"],
        temperature=0.4,
        base_url=OLLAMA_BASE_URL,
        client_kwargs={
            "timeout": OLLAMA_TIMEOUT_SECONDS,
            "trust_env": False,
        },
        async_client_kwargs={
            "timeout": OLLAMA_TIMEOUT_SECONDS,
            "trust_env": False,
        },
    )


def _build_api(settings: dict[str, str]):
    api_provider = settings["api_provider"] or "deepseek"
    if api_provider != "deepseek":
        raise RuntimeError(
            f"暂仅支持 DeepSeek API（llm.api_provider=deepseek），收到: {api_provider}"
        )
    if not settings["api_key"]:
        raise RuntimeError("未配置 DeepSeek API Key。请在维护台填写或执行 config set。")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "缺少 langchain-openai。请执行: pip install 'leetcode-tracker[coach]'"
        ) from exc
    base_url = settings["base_url"] or DEEPSEEK_BASE_URL
    return ChatOpenAI(
        model=settings["coach_model"] or DEEPSEEK_DEFAULT_MODEL,
        api_key=settings["api_key"],
        base_url=base_url,
        temperature=0.4,
        timeout=API_TIMEOUT_SECONDS,
        max_retries=1,
    )
