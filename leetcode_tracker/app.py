"""pywebview 桌面壳。"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Optional

from leetcode_tracker.config import load_config
from leetcode_tracker.server import start_server_background


def _health_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def run_app(host: Optional[str] = None, port: Optional[int] = None) -> int:
    cfg = load_config()
    host = host or str(cfg["host"])
    port = port or int(cfg["port"])
    base = f"http://{host}:{port}"
    health = f"{base}/health"

    owned_server = None
    if not _health_ok(health):
        try:
            owned_server = start_server_background(host=host, port=port)
        except OSError as exc:
            print(f"无法启动桥接服务: {exc}")
            return 1
        for _ in range(20):
            if _health_ok(health):
                break
            time.sleep(0.1)
        else:
            print(f"桥接服务启动超时，请手动运行: leetcode-tracker serve")
            return 1

    try:
        import webview
    except ImportError:
        print("未安装 pywebview。请执行: pip install 'leetcode-tracker[app]' 或 pip install pywebview")
        print(f"也可直接在浏览器打开: {base}/")
        return 1

    webview.create_window("LeetCode Tracker", f"{base}/", width=980, height=760)
    webview.start()
    if owned_server is not None:
        owned_server.shutdown()
    return 0
