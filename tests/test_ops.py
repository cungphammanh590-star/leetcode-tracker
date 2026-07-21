"""维护台 API 与去桌面入口冒烟测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from leetcode_tracker.api import routes_ops, routes_pages
from leetcode_tracker.cli import build_parser
from leetcode_tracker.db import connect, init_db
from leetcode_tracker.store import save_submission


@pytest.fixture()
def ops_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "ops.sqlite"
    conn = init_db(connect(path))
    try:
        save_submission(
            conn,
            {
                "submission_id": "ops-1",
                "problem_id": 1,
                "title": "两数之和",
                "slug": "two-sum",
                "difficulty": "Easy",
                "status": "Accepted",
                "language": "python3",
                "code": "class Solution: pass\n",
            },
        )
    finally:
        conn.close()

    monkeypatch.setattr(routes_ops, "init_db", lambda: connect(path))
    monkeypatch.setattr(
        routes_ops,
        "write_today_report",
        lambda: _fake_report(tmp_path),
    )
    monkeypatch.setattr(
        routes_ops,
        "clean_reports",
        lambda *, today_only=False: [tmp_path / ("today.md" if today_only else "all.md")],
    )
    monkeypatch.setattr(routes_ops, "clean_logs", lambda: [tmp_path / "out.log"])
    monkeypatch.setattr(
        routes_ops, "clean_coach_debug_logs", lambda: [tmp_path / "coach.md"]
    )
    return path


def _fake_report(tmp_path: Path) -> Path:
    path = tmp_path / "reports" / "2026-07-20.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# 日报\n\nok\n", encoding="utf-8")
    return path


@pytest.fixture()
def ops_client(ops_db: Path) -> TestClient:
    app = FastAPI()
    app.include_router(routes_ops.router)
    app.include_router(routes_pages.router)
    return TestClient(app)


def test_cli_no_longer_has_app_command() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["app"])


def test_ops_page_served(ops_client: TestClient) -> None:
    response = ops_client.get("/ops")
    assert response.status_code == 200
    assert "维护台" in response.text


def test_ops_config_readonly(ops_client: TestClient) -> None:
    response = ops_client.get("/api/ops/config")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "port" in body["config"]
    assert "db_path_readonly" in body["config"]


def test_destructive_ops_require_confirm(ops_client: TestClient) -> None:
    for path in (
        "/api/ops/report/clean",
        "/api/ops/logs/clean",
        "/api/ops/stats/rebuild",
        "/api/ops/kg/import",
    ):
        response = ops_client.post(path, json={})
        assert response.status_code == 400
        assert "confirm" in response.json()["message"]


def test_report_today_returns_markdown(ops_client: TestClient) -> None:
    response = ops_client.post("/api/ops/report/today")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "# 日报" in body["markdown"]
    assert body["path"].endswith(".md")


def test_logs_clean_with_confirm(ops_client: TestClient) -> None:
    response = ops_client.post(
        "/api/ops/logs/clean",
        json={"confirm": True, "include_coach_debug": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["count"] == 2


def test_stats_rebuild_with_confirm(ops_client: TestClient) -> None:
    response = ops_client.post(
        "/api/ops/stats/rebuild",
        json={"confirm": True, "from_scratch": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["problems"] >= 1
