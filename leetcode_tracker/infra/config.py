"""本机 JSON 配置（不含数据库路径）。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

LLM_DEFAULTS: dict[str, Any] = {
    "provider": "ollama",
    "coach_model": "qwen2.5:7b-instruct-q4_K_M",
    "api_provider": "",
    "api_key": "",
}

DEFAULTS: dict[str, Any] = {
    "host": "127.0.0.1",
    "port": 8763,
    "report_dir": str(Path.home() / "leetcode-reports"),
    "report_time": "23:00",
    "autostart": False,
    "llm": deepcopy(LLM_DEFAULTS),
}

CONFIG_KEYS = sorted(
    {
        "host",
        "port",
        "report_dir",
        "report_time",
        "autostart",
        "llm.provider",
        "llm.coach_model",
        "llm.api_provider",
        "llm.api_key",
    }
)


def config_dir() -> Path:
    return Path.home() / ".config" / "leetcode-tracker"


def config_path() -> Path:
    return config_dir() / "config.json"


def _expand_report_dir(value: str) -> str:
    return str(Path(value).expanduser())


def _merge_llm(target: dict[str, Any], raw: Any) -> None:
    if not isinstance(raw, dict):
        return
    for key in LLM_DEFAULTS:
        if key in raw:
            target[key] = raw[key]


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    data["port"] = int(data["port"])
    data["autostart"] = bool(data["autostart"])
    data["report_dir"] = _expand_report_dir(str(data["report_dir"]))
    data["host"] = str(data["host"])
    data["report_time"] = str(data["report_time"])
    llm = data.get("llm")
    if not isinstance(llm, dict):
        data["llm"] = deepcopy(LLM_DEFAULTS)
    else:
        merged = deepcopy(LLM_DEFAULTS)
        _merge_llm(merged, llm)
        data["llm"] = merged
    data["llm"]["provider"] = str(data["llm"]["provider"])
    data["llm"]["coach_model"] = str(data["llm"]["coach_model"])
    data["llm"]["api_provider"] = str(data["llm"]["api_provider"])
    data["llm"]["api_key"] = str(data["llm"]["api_key"])
    return data


def load_config() -> dict[str, Any]:
    path = config_path()
    data = deepcopy(DEFAULTS)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in ("host", "port", "report_dir", "report_time", "autostart"):
                    if key in raw:
                        data[key] = raw[key]
                if "llm" in raw:
                    _merge_llm(data["llm"], raw["llm"])
        except (json.JSONDecodeError, OSError):
            pass
    return _normalize_config(data)


def save_config(data: dict[str, Any]) -> Path:
    merged = _normalize_config(deepcopy(data))
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _set_nested(cfg: dict[str, Any], key: str, value: str) -> None:
    if key == "db_path":
        raise ValueError(f"不支持的配置项: {key}")
    if key.startswith("llm."):
        sub = key.split(".", 1)[1]
        if sub not in LLM_DEFAULTS:
            raise ValueError(f"不支持的配置项: {key}")
        cfg.setdefault("llm", deepcopy(LLM_DEFAULTS))
        cfg["llm"][sub] = value
        return
    if key not in DEFAULTS or key == "llm":
        raise ValueError(f"不支持的配置项: {key}")
    if key == "port":
        cfg[key] = int(value)
    elif key == "autostart":
        cfg[key] = value.strip().lower() in {"1", "true", "yes", "on"}
    else:
        cfg[key] = value


def set_config_value(key: str, value: str) -> dict[str, Any]:
    cfg = load_config()
    _set_nested(cfg, key, value)
    save_config(cfg)
    return load_config()


def mask_config_for_display(cfg: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(cfg)
    api_key = out.get("llm", {}).get("api_key", "")
    if api_key:
        out["llm"]["api_key"] = "***" + api_key[-4:] if len(api_key) > 4 else "***"
    return out
