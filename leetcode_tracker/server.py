"""本机桥接入口：FastAPI + uvicorn。"""

from __future__ import annotations

import threading
from typing import Optional

from leetcode_tracker.config import load_config
from leetcode_tracker.db import init_db

_UVICORN_APP = "leetcode_tracker.api.app:create_app"


class BridgeServerHandle:
    """后台 uvicorn 句柄；供 pywebview 调用 shutdown()。"""

    def __init__(self, server: object, thread: threading.Thread) -> None:
        self._server = server
        self._thread = thread

    def shutdown(self) -> None:
        if hasattr(self._server, "should_exit"):
            self._server.should_exit = True
        if hasattr(self._server, "force_exit"):
            self._server.force_exit = True

    @property
    def thread(self) -> threading.Thread:
        return self._thread


def _resolve_bind(
    host: Optional[str] = None, port: Optional[int] = None
) -> tuple[str, int]:
    cfg = load_config()
    host = host if host is not None else str(cfg["host"])
    port = port if port is not None else int(cfg["port"])
    return host, port


def run_server(host: Optional[str] = None, port: Optional[int] = None) -> None:
    import uvicorn

    host, port = _resolve_bind(host, port)
    init_db().close()
    print(f"leetcode-tracker bridge (FastAPI) listening on http://{host}:{port}")
    print("Endpoints: GET /  GET /coach  GET /problems/{id}  GET /api/stats")
    print("           POST /submit  (capture only)")
    print("           POST /api/coach/prepare  POST /api/coach/stream (SSE)")
    print("           POST /api/coach/chat  GET /api/coach/session  GET /api/coach/hint")
    print("           GET /api/problems/{id}/llm-context  GET /health")
    try:
        uvicorn.run(
            _UVICORN_APP,
            factory=True,
            host=host,
            port=port,
            log_level="info",
        )
    except OSError as exc:
        raise OSError(f"无法绑定 {host}:{port}（可能已被占用）: {exc}") from exc


def start_server_background(
    host: Optional[str] = None, port: Optional[int] = None
) -> BridgeServerHandle:
    import uvicorn

    host, port = _resolve_bind(host, port)
    init_db().close()
    config = uvicorn.Config(
        _UVICORN_APP,
        factory=True,
        host=host,
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run, name="leetcode-tracker-uvicorn", daemon=True
    )
    try:
        thread.start()
    except OSError as exc:
        raise OSError(f"无法绑定 {host}:{port}（可能已被占用）: {exc}") from exc
    return BridgeServerHandle(server, thread)
