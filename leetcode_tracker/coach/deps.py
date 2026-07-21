"""检测陪练可选依赖是否已安装。"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def coach_dependencies_available() -> bool:
    try:
        import langgraph  # noqa: F401
        import langchain_core  # noqa: F401
        import langchain_ollama  # noqa: F401
        import langgraph.checkpoint.sqlite  # noqa: F401
    except ImportError:
        return False
    return True


def coach_import_error_message() -> str:
    return (
        "陪练功能需要安装可选依赖：pip install 'leetcode-tracker[coach]'"
        "（另需本机 Ollama 与模型，见 README）"
    )
