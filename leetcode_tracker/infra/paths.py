"""路径常量（数据库路径固定）。"""

from __future__ import annotations

from pathlib import Path


def data_dir() -> Path:
    return Path.home() / ".local" / "share" / "leetcode-tracker"


def db_path() -> Path:
    return data_dir() / "leetcode.db"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
