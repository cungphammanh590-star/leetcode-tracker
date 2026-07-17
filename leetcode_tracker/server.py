"""本机桥接 HTTP 服务（标准库）+ 仪表盘。"""

from __future__ import annotations

import json
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from leetcode_tracker.coach_deps import coach_dependencies_available, coach_import_error_message
from leetcode_tracker.config import load_config
from leetcode_tracker.db import init_db
from leetcode_tracker.kg.import_maps import get_kg_status, kg_is_imported
from leetcode_tracker.problem_stats import (
    ensure_stats_materialized,
    get_daily_stats_rows,
    get_llm_context,
    get_problem_stats_row,
    get_problem_submissions,
    list_problem_stats,
)
from leetcode_tracker.stats import get_overview, overview_to_dict
from leetcode_tracker.submissions import get_problem_id_by_slug

from leetcode_tracker.store import StoreError, count_submissions, save_submission

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8763


def _static_html(filename: str) -> bytes:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "leetcode_tracker" / "static" / filename)
        candidates.append(Path(meipass) / "static" / filename)
    candidates.append(
        Path(sys.executable).resolve().parent / "leetcode_tracker" / "static" / filename
    )
    candidates.append(Path(__file__).with_name("static") / filename)

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


def _dashboard_html() -> bytes:
    return _static_html("index.html")


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "LeetcodeTrackerBridge/0.3.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[bridge] {self.address_string()} - {fmt % args}")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self._send_bytes(200, _dashboard_html(), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._handle_health()
            return
        if path == "/api/stats":
            self._handle_stats()
            return
        if path == "/api/problems":
            self._handle_problem_list()
            return
        if path.startswith("/api/problems/"):
            self._handle_problem_api(path)
            return
        if path.startswith("/problems/"):
            self._send_bytes(200, _static_html("problem.html"), "text/html; charset=utf-8")
            return
        if path in {"/coach", "/coach.html"}:
            self._send_bytes(200, _static_html("coach.html"), "text/html; charset=utf-8")
            return
        if path == "/api/coach/hint" or path.startswith("/api/coach/hint/"):
            self._handle_coach_hint(path, parsed.query)
            return
        self._send_json(404, {"status": "error", "message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/submit":
            self._handle_submit()
            return
        if path == "/api/coach/engage":
            self._handle_coach_engage()
            return
        if path == "/api/coach/chat":
            self._handle_coach_chat()
            return
        self._send_json(404, {"status": "error", "message": "not found"})

    def _handle_health(self) -> None:
        cfg = load_config()
        port = int(cfg["port"])
        try:
            conn = init_db()
            try:
                count = count_submissions(conn)
                kg_imported = kg_is_imported(conn)
            finally:
                conn.close()
            self._send_json(
                200,
                {
                    "status": "ok",
                    "db_connected": True,
                    "submissions_count": count,
                    "port": port,
                    "host": str(cfg["host"]),
                    "kg_imported": kg_imported,
                    "coach_available": coach_dependencies_available(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                500,
                {
                    "status": "error",
                    "db_connected": False,
                    "port": port,
                    "host": str(cfg["host"]),
                    "kg_imported": False,
                    "coach_available": coach_dependencies_available(),
                    "message": str(exc),
                },
            )

    def _coach_unavailable(self) -> None:
        self._send_json(
            503,
            {
                "status": "error",
                "message": coach_import_error_message(),
            },
        )

    def _resolve_problem_id(self, path: str, query: str) -> Optional[int]:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "coach" and parts[2] == "hint":
            try:
                return int(parts[3])
            except ValueError:
                pass
        params = parse_qs(query)
        if params.get("problem_id"):
            try:
                return int(params["problem_id"][0])
            except (TypeError, ValueError):
                pass
        slug_vals = params.get("slug")
        if slug_vals and slug_vals[0]:
            conn = init_db()
            try:
                return get_problem_id_by_slug(conn, slug_vals[0].strip())
            finally:
                conn.close()
        return None

    def _handle_coach_hint(self, path: str, query: str) -> None:
        try:
            problem_id = self._resolve_problem_id(path, query)
            if problem_id is None:
                self._send_json(
                    400,
                    {
                        "status": "error",
                        "message": "需要 problem_id 或已在库中的 slug；先在题目页提交一次可自动同步题号",
                    },
                )
                return
            from leetcode_tracker.coach.hint import build_problem_hint

            conn = init_db()
            try:
                ensure_stats_materialized(conn)
                hint = build_problem_hint(conn, problem_id)
            finally:
                conn.close()
            self._send_json(200, {"status": "ok", **hint})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})

    def _handle_coach_engage(self) -> None:
        if not coach_dependencies_available():
            self._coach_unavailable()
            return
        try:
            payload = self._read_json()
            submission_id = str(payload.get("submission_id") or "").strip()
            if not submission_id:
                self._send_json(400, {"status": "error", "message": "submission_id required"})
                return
            from leetcode_tracker.coach import service as coach_service

            conn = init_db()
            try:
                ensure_stats_materialized(conn)
                if not kg_is_imported(conn):
                    self._send_json(
                        409,
                        {
                            "status": "error",
                            "message": "知识图谱未导入，请先运行: leetcode-tracker kg import",
                        },
                    )
                    return
                result = coach_service.engage(conn, submission_id)
            finally:
                conn.close()
            self._send_json(200, {"status": "ok", **result})
        except ValueError as exc:
            self._send_json(404, {"status": "error", "message": str(exc)})
        except json.JSONDecodeError:
            self._send_json(400, {"status": "error", "message": "invalid JSON"})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})

    def _handle_coach_chat(self) -> None:
        if not coach_dependencies_available():
            self._coach_unavailable()
            return
        try:
            payload = self._read_json()
            session_id = str(payload.get("session_id") or "").strip()
            message = str(payload.get("message") or "").strip()
            if not session_id or not message:
                self._send_json(
                    400,
                    {"status": "error", "message": "session_id and message required"},
                )
                return
            from leetcode_tracker.coach import service as coach_service

            conn = init_db()
            try:
                result = coach_service.chat(conn, session_id, message)
            finally:
                conn.close()
            self._send_json(200, {"status": "ok", **result})
        except ValueError as exc:
            self._send_json(404, {"status": "error", "message": str(exc)})
        except json.JSONDecodeError:
            self._send_json(400, {"status": "error", "message": "invalid JSON"})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})

    def _handle_stats(self) -> None:
        try:
            conn = init_db()
            try:
                ensure_stats_materialized(conn)
                stats = get_overview(conn)
            finally:
                conn.close()
            self._send_json(200, overview_to_dict(stats))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})

    def _handle_problem_list(self) -> None:
        try:
            conn = init_db()
            try:
                ensure_stats_materialized(conn)
                items = list_problem_stats(conn)
            finally:
                conn.close()
            self._send_json(200, {"problems": items})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})

    def _handle_problem_api(self, path: str) -> None:
        parts = [p for p in path.split("/") if p]
        # /api/problems/{id}/stats | /api/problems/{id}/llm-context
        if len(parts) < 4 or parts[0] != "api" or parts[1] != "problems":
            self._send_json(404, {"status": "error", "message": "not found"})
            return
        try:
            problem_id = int(parts[2])
        except ValueError:
            self._send_json(400, {"status": "error", "message": "invalid problem id"})
            return
        action = parts[3]
        try:
            conn = init_db()
            try:
                ensure_stats_materialized(conn)
                if action == "stats":
                    row = get_problem_stats_row(conn, problem_id)
                    if row is None:
                        self._send_json(404, {"status": "error", "message": "not found"})
                        return
                    daily = get_daily_stats_rows(conn, problem_id, limit=90)
                    submissions = get_problem_submissions(conn, problem_id, limit=80)
                    self._send_json(
                        200,
                        {"problem": row, "daily": daily, "submissions": submissions},
                    )
                    return
                if action == "llm-context":
                    text = get_llm_context(conn, problem_id)
                    self._send_json(200, {"problem_id": problem_id, "markdown": text})
                    return
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})
        self._send_json(404, {"status": "error", "message": "not found"})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise StoreError("JSON body must be an object", status_code=400)
        return data

    def _handle_submit(self) -> None:
        try:
            payload = self._read_json()
            conn = init_db()
            try:
                result = save_submission(conn, payload)
            finally:
                conn.close()
            if result.created:
                self._send_json(
                    200,
                    {
                        "status": "success",
                        "message": "Submission saved",
                        "submission_id": result.submission_id,
                        "created": True,
                    },
                )
            else:
                self._send_json(
                    200,
                    {
                        "status": "success",
                        "message": "Submission already exists",
                        "submission_id": result.submission_id,
                        "created": False,
                    },
                )
        except StoreError as exc:
            self._send_json(
                exc.status_code,
                {"status": "error", "message": exc.message},
            )
        except json.JSONDecodeError:
            self._send_json(400, {"status": "error", "message": "invalid JSON"})
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_json(500, {"status": "error", "message": str(exc)})


def create_server(
    host: Optional[str] = None, port: Optional[int] = None
) -> ThreadingHTTPServer:
    cfg = load_config()
    host = host if host is not None else str(cfg["host"])
    port = port if port is not None else int(cfg["port"])
    init_db().close()
    try:
        return ThreadingHTTPServer((host, port), BridgeHandler)
    except OSError as exc:
        raise OSError(f"无法绑定 {host}:{port}（可能已被占用）: {exc}") from exc


def run_server(host: Optional[str] = None, port: Optional[int] = None) -> None:
    httpd = create_server(host=host, port=port)
    host, port = httpd.server_address[:2]
    print(f"leetcode-tracker bridge listening on http://{host}:{port}")
    print("Endpoints: GET /  GET /coach  GET /problems/{id}  GET /api/stats")
    print("           POST /api/coach/engage  POST /api/coach/chat")
    print("           GET /api/problems/{id}/llm-context  GET /health  POST /submit")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        httpd.server_close()


def start_server_background(
    host: Optional[str] = None, port: Optional[int] = None
) -> ThreadingHTTPServer:
    httpd = create_server(host=host, port=port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd
