"""本机 JSON 配置（不含数据库路径）。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "host": "127.0.0.1",
    "port": 8763,
    "report_dir": str(Path.home() / "leetcode-reports"),
    "report_time": "23:00",
    "autostart": False,
}


def config_dir() -> Path:
    return Path.home() / ".config" / "leetcode-tracker"


def config_path() -> Path:
    return config_dir() / "config.json"


def _expand_report_dir(value: str) -> str:
    return str(Path(value).expanduser())


def load_config() -> dict[str, Any]:
    path = config_path()
    data = deepcopy(DEFAULTS)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key in DEFAULTS:
                    if key in raw:
                        data[key] = raw[key]
        except (json.JSONDecodeError, OSError):
            pass
    data["port"] = int(data["port"])
    data["autostart"] = bool(data["autostart"])
    data["report_dir"] = _expand_report_dir(str(data["report_dir"]))
    data["host"] = str(data["host"])
    data["report_time"] = str(data["report_time"])
    return data


def save_config(data: dict[str, Any]) -> Path:
    merged = deepcopy(DEFAULTS)
    for key in DEFAULTS:
        if key in data:
            merged[key] = data[key]
    merged["port"] = int(merged["port"])
    merged["autostart"] = bool(merged["autostart"])
    merged["report_dir"] = _expand_report_dir(str(merged["report_dir"]))
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Persist report_dir as given expanded path for clarity
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def set_config_value(key: str, value: str) -> dict[str, Any]:
    if key == "db_path" or key not in DEFAULTS:
        raise ValueError(f"不支持的配置项: {key}")
    cfg = load_config()
    if key == "port":
        cfg[key] = int(value)
    elif key == "autostart":
        cfg[key] = value.strip().lower() in {"1", "true", "yes", "on"}
    else:
        cfg[key] = value
    save_config(cfg)
    return load_config()
