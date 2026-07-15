"""本机桥接 HTTP 服务（标准库）。"""

from __future__ import annotations

import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from leetcode_tracker.db import init_db
from leetcode_tracker.store import StoreError, count_submissions, save_submission

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8763


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "LeetcodeTrackerBridge/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[bridge] {self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

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
        path = urlparse(self.path).path
        if path == "/health":
            self._handle_health()
            return
        self._send_json(404, {"status": "error", "message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/submit":
            self._handle_submit()
            return
        self._send_json(404, {"status": "error", "message": "not found"})

    def _handle_health(self) -> None:
        try:
            conn = init_db()
            try:
                count = count_submissions(conn)
            finally:
                conn.close()
            self._send_json(
                200,
                {
                    "status": "ok",
                    "db_connected": True,
                    "submissions_count": count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                500,
                {
                    "status": "error",
                    "db_connected": False,
                    "message": str(exc),
                },
            )

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


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    init_db().close()
    try:
        httpd = ThreadingHTTPServer((host, port), BridgeHandler)
    except OSError as exc:
        raise SystemExit(
            f"无法绑定 {host}:{port}（可能已被占用）: {exc}"
        ) from exc

    print(f"leetcode-tracker bridge listening on http://{host}:{port}")
    print("Endpoints: GET /health  POST /submit")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        httpd.server_close()
