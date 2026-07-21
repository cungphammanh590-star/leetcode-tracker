"""静态页面路由。"""

from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter()


def _load_static_html(filename: str) -> bytes:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "leetcode_tracker" / "static" / filename)
        candidates.append(Path(meipass) / "static" / filename)
    candidates.append(
        Path(sys.executable).resolve().parent / "leetcode_tracker" / "static" / filename
    )
    candidates.append(Path(__file__).resolve().parent.parent / "static" / filename)

    for path in candidates:
        try:
            if path.is_file():
                return path.read_bytes()
        except OSError:
            continue
    try:
        return resources.files("leetcode_tracker").joinpath(f"static/{filename}").read_bytes()
    except Exception as exc:  # noqa: BLE001
        raise FileNotFoundError(f"static file not found: {filename}") from exc


def _html(filename: str) -> Response:
    try:
        body = _load_static_html(filename)
    except FileNotFoundError as exc:
        return Response(str(exc), status_code=404, media_type="text/plain")
    return HTMLResponse(content=body.decode("utf-8"))


@router.get("/")
@router.get("/index.html")
def dashboard() -> Response:
    return _html("index.html")


@router.get("/coach")
@router.get("/coach.html")
def coach_page() -> Response:
    return _html("coach.html")


@router.get("/ops")
@router.get("/ops.html")
def ops_page() -> Response:
    return _html("ops.html")


@router.get("/problems/{problem_id}")
def problem_page(problem_id: int) -> Response:  # noqa: ARG001
    return _html("problem.html")
