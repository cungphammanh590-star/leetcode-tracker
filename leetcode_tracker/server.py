"""本机桥接入口：FastAPI + uvicorn。"""

from __future__ import annotations

from typing import Optional

from leetcode_tracker.infra.config import load_config
from leetcode_tracker.infra.db import init_db

_UVICORN_APP = "leetcode_tracker.api.app:create_app"


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
    print("Endpoints: GET /  GET /ops  GET /coach  GET /problems/{id}")
    print("           GET /api/stats  GET /api/ops/config  GET /health")
    print("           POST /submit  (capture only)")
    print("           POST /api/coach/prepare  POST /api/coach/stream (SSE)")
    print("           POST /api/ops/report/today  POST /api/ops/logs/clean …")
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
