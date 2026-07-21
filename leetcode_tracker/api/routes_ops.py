"""维护台 API：日报、日志清理、stats 重建、图谱与只读配置。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from leetcode_tracker.infra.autostart import clean_logs
from leetcode_tracker.coach.debug_log import clean_coach_debug_logs
from leetcode_tracker.infra.config import load_config, mask_config_for_display
from leetcode_tracker.infra.db import init_db
from leetcode_tracker.kg.import_maps import get_kg_status, import_maps
from leetcode_tracker.infra.paths import db_path
from leetcode_tracker.core.problem_stats import rebuild_stats
from leetcode_tracker.core.report import clean_reports, write_today_report

router = APIRouter()


def _json_error(message: str, *, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "message": message},
    )


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _require_confirm(body: dict[str, Any]) -> Optional[JSONResponse]:
    if body.get("confirm") is not True:
        return _json_error("confirm=true required")
    return None


@router.get("/api/ops/config")
def ops_config() -> dict[str, Any]:
    cfg = mask_config_for_display(load_config())
    payload = dict(cfg)
    payload["db_path_readonly"] = str(db_path())
    return {"status": "ok", "config": payload}


@router.get("/api/ops/kg")
def ops_kg_status() -> dict[str, Any]:
    conn = init_db()
    try:
        return {"status": "ok", **get_kg_status(conn)}
    finally:
        conn.close()


@router.post("/api/ops/kg/import")
async def ops_kg_import(request: Request) -> Any:
    body = await _body(request)
    denied = _require_confirm(body)
    if denied:
        return denied
    conn = init_db()
    try:
        result = import_maps(conn)
        return {"status": "ok", **result}
    except Exception as exc:  # noqa: BLE001
        return _json_error(str(exc), status_code=500)
    finally:
        conn.close()


@router.post("/api/ops/report/today")
def ops_report_today() -> Any:
    try:
        path = write_today_report()
        markdown = path.read_text(encoding="utf-8")
        return {
            "status": "ok",
            "path": str(path),
            "markdown": markdown,
        }
    except Exception as exc:  # noqa: BLE001
        return _json_error(str(exc), status_code=500)


@router.post("/api/ops/report/clean")
async def ops_report_clean(request: Request) -> Any:
    body = await _body(request)
    denied = _require_confirm(body)
    if denied:
        return denied
    today_only = bool(body.get("today_only"))
    removed = clean_reports(today_only=today_only)
    return {
        "status": "ok",
        "removed": [str(p) for p in removed],
        "count": len(removed),
    }


@router.post("/api/ops/logs/clean")
async def ops_logs_clean(request: Request) -> Any:
    body = await _body(request)
    denied = _require_confirm(body)
    if denied:
        return denied
    include_coach = body.get("include_coach_debug", True)
    service_removed = clean_logs()
    coach_removed: list = []
    if include_coach is not False:
        coach_removed = clean_coach_debug_logs()
    return {
        "status": "ok",
        "service_logs": [str(p) for p in service_removed],
        "coach_debug_logs": [str(p) for p in coach_removed],
        "count": len(service_removed) + len(coach_removed),
    }


@router.post("/api/ops/stats/rebuild")
async def ops_stats_rebuild(request: Request) -> Any:
    body = await _body(request)
    denied = _require_confirm(body)
    if denied:
        return denied
    from_scratch = body.get("from_scratch", True) is not False
    conn = init_db()
    try:
        count = rebuild_stats(conn, from_scratch=from_scratch)
        return {
            "status": "ok",
            "problems": count,
            "from_scratch": from_scratch,
        }
    except Exception as exc:  # noqa: BLE001
        return _json_error(str(exc), status_code=500)
    finally:
        conn.close()
