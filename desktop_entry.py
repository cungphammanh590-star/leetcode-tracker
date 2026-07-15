"""PyInstaller / 桌面入口：双击或命令行启动仪表盘窗口。"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

LOG = Path.home() / "Library" / "Logs" / "leetcode-tracker-app.log"


def _write_crash_log() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(traceback.format_exc(), encoding="utf-8")


def main() -> int:
    os.environ.setdefault("PYWEBVIEW_GUI", "cocoa")
    try:
        from leetcode_tracker.app import run_app

        return run_app()
    except Exception:
        _write_crash_log()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
