"""PyInstaller / 桌面入口：双击或命令行启动仪表盘窗口。"""

from __future__ import annotations

import sys


def main() -> int:
    from leetcode_tracker.app import run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
