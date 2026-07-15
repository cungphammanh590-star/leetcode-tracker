"""pywebview 桌面壳。"""

from __future__ import annotations

import os
import socket
import subprocess
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from leetcode_tracker.config import load_config
from leetcode_tracker.server import start_server_background

APP_LOG = Path.home() / "Library" / "Logs" / "leetcode-tracker-app.log"
_STARTUP_WAIT_S = 15.0
_STARTUP_POLL_S = 0.1


def _log(message: str) -> None:
    APP_LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with APP_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")


def _health_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _bridge_ready(host: str, port: int, health: str) -> bool:
    if not _port_open(host, port):
        return False
    return _health_ok(health)


def _alert(title: str, message: str) -> None:
    script = f'display alert "{title}" message "{message}" as warning'
    try:
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except OSError:
        pass


def _wait_for_bridge(host: str, port: int, health: str) -> bool:
    """等待桥接可用。打包 .app 在 GUI 主循环前，HTTP 自检可能慢于浏览器侧探测。"""
    attempts = int(_STARTUP_WAIT_S / _STARTUP_POLL_S)
    port_seen = False
    for i in range(attempts):
        if _port_open(host, port):
            port_seen = True
            if _health_ok(health):
                _log(f"bridge ready after {(i + 1) * _STARTUP_POLL_S:.1f}s")
                return True
        time.sleep(_STARTUP_POLL_S)

    if port_seen:
        _log("bridge port is open; proceeding without reliable /health self-check")
        return True

    _log("bridge startup timed out (port never opened)")
    return False


def _ensure_bridge(
    host: str, port: int, health: str
) -> tuple[Optional[object], bool]:
    """返回 (httpd 或 None, 是否由本进程启动)。"""
    if _bridge_ready(host, port, health):
        _log(f"bridge already running: {health}")
        return None, False

    try:
        httpd = start_server_background(host=host, port=port)
    except OSError as exc:
        _log(f"bridge bind failed: {exc}")
        if _bridge_ready(host, port, health):
            _log("reusing existing bridge after bind failure")
            return None, False
        msg = f"无法启动本机服务（{host}:{port}）。详情见 {APP_LOG}"
        print(msg)
        _alert("LeetCode Tracker", msg.replace('"', "'"))
        return None, False

    if _wait_for_bridge(host, port, health):
        _log(f"bridge started: {health}")
        return httpd, True

    if _port_open(host, port):
        _log("bridge port still open after wait; not shutting down")
        return httpd, True

    msg = f"本机服务启动超时。详情见 {APP_LOG}"
    print(msg)
    _alert("LeetCode Tracker", msg.replace('"', "'"))
    if httpd is not None:
        httpd.shutdown()
    return None, False


def _keep_alive() -> None:
    """窗口关闭后仍保持桥接在线，供浏览器扩展使用。"""
    _log("window closed; keeping bridge alive")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def run_app(host: Optional[str] = None, port: Optional[int] = None) -> int:
    os.environ.setdefault("PYWEBVIEW_GUI", "cocoa")

    cfg = load_config()
    host = host or str(cfg["host"])
    port = port or int(cfg["port"])
    base = f"http://{host}:{port}"
    health = f"{base}/health"

    owned_server, started_here = _ensure_bridge(host, port, health)
    if not _port_open(host, port):
        return 1

    try:
        import webview
    except ImportError as exc:
        _log(f"pywebview missing: {exc}")
        msg = f"未安装桌面窗口组件。浏览器打开 {base}/ ，日志：{APP_LOG}"
        print(msg)
        _alert("LeetCode Tracker", msg.replace('"', "'"))
        _keep_alive()
        return 0

    try:
        webview.create_window("LeetCode Tracker", f"{base}/", width=980, height=760)
        webview.start()
    except Exception:
        _log("webview failed:\n" + traceback.format_exc())
        msg = (
            f"桌面窗口打开失败，但本机服务已运行。请用浏览器打开 {base}/ 。"
            f"日志：{APP_LOG}"
        )
        print(msg)
        _alert("LeetCode Tracker", msg.replace('"', "'"))
        _keep_alive()
        return 0

    if started_here and owned_server is not None:
        _keep_alive()
        owned_server.shutdown()
    return 0
