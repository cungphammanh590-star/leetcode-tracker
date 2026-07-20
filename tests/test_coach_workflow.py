from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from leetcode_tracker.api import routes_coach
from leetcode_tracker.coach import service
from leetcode_tracker.db import connect, init_db
from leetcode_tracker.llm.provider import build_chat_model
from leetcode_tracker.store import save_submission


def _seed_db(path: Path) -> None:
    conn = init_db(connect(path))
    try:
        save_submission(
            conn,
            {
                "submission_id": "sub-53",
                "problem_id": 53,
                "title": "最大子数组和",
                "slug": "maximum-subarray",
                "difficulty": "Medium",
                "status": "Wrong Answer",
                "language": "java",
            },
        )
        save_submission(
            conn,
            {
                "submission_id": "sub-53-new",
                "problem_id": 53,
                "title": "最大子数组和",
                "slug": "maximum-subarray",
                "difficulty": "Medium",
                "status": "Accepted",
                "language": "java",
            },
        )
    finally:
        conn.close()


@pytest.fixture()
def coach_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "coach.sqlite"
    _seed_db(path)
    monkeypatch.setattr(service, "db_path", lambda: path)
    return path


def test_prepare_is_template_first_and_does_not_build_model(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        service,
        "build_chat_model",
        lambda: (_ for _ in ()).throw(AssertionError("prepare must not call LLM")),
    )
    conn = connect(coach_db)
    try:
        result = service.prepare(conn, "sub-53-new")
    finally:
        conn.close()

    assert result["opening_source"] == "template"
    assert result["reused"] is False
    assert result["resolved_submission_id"] == "sub-53-new"
    assert result["opening"]


def test_ollama_client_is_loopback_bounded_and_ignores_proxy() -> None:
    model = build_chat_model()
    assert model.base_url == "http://127.0.0.1:11434"
    assert model._client._client._trust_env is False
    assert model._client._client.timeout.read == 45.0


def test_prepare_falls_back_to_latest_submission_for_problem(coach_db: Path) -> None:
    conn = connect(coach_db)
    try:
        result = service.prepare(conn, "missing", problem_id=53)
    finally:
        conn.close()

    assert result["fallback_used"] is True
    assert result["requested_submission_id"] == "missing"
    assert result["resolved_submission_id"] == "sub-53-new"


def test_concurrent_prepare_returns_one_session(coach_db: Path) -> None:
    def run() -> str:
        conn = connect(coach_db)
        try:
            return str(service.prepare(conn, "sub-53-new")["session_id"])
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        session_ids = list(pool.map(lambda _i: run(), range(2)))

    conn = connect(coach_db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM coach_sessions WHERE submission_id = ?",
            ("sub-53-new",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert session_ids[0] == session_ids[1]
    assert count == 1


class _StreamingModel:
    def __init__(self, seen: list[list[object]]) -> None:
        self.seen = seen

    def stream(self, messages: list[object]):
        self.seen.append(messages)
        yield SimpleNamespace(content="先检查")
        yield SimpleNamespace(content="边界。")


def test_langgraph_persists_opening_and_multiple_turns(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[object]] = []
    monkeypatch.setattr(service, "build_chat_model", lambda: _StreamingModel(seen))
    conn = connect(coach_db)
    try:
        session = service.prepare(conn, "sub-53-new")
        first = service.chat(conn, session["session_id"], "我怀疑边界")
        second = service.chat(conn, session["session_id"], "我检查了空数组")
    finally:
        conn.close()

    assert first["reply"] == "先检查边界。"
    assert second["reply"] == "先检查边界。"
    second_contents = [str(getattr(message, "content", "")) for message in seen[1]]
    assert session["opening"] in second_contents
    assert "我怀疑边界" in second_contents
    assert "先检查边界。" in second_contents
    assert "我检查了空数组" in second_contents


def test_model_failure_uses_checkpointed_fallback(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenModel:
        def stream(self, _messages: list[object]):
            raise TimeoutError("model timeout")
            yield  # pragma: no cover

    monkeypatch.setattr(service, "build_chat_model", lambda: BrokenModel())
    conn = connect(coach_db)
    try:
        session = service.prepare(conn, "sub-53-new")
        result = service.chat(conn, session["session_id"], "不知道哪里错了")
    finally:
        conn.close()

    assert "最小的失败用例" in result["reply"]
    assert result["done"] is False


def test_end_message_is_routed_without_model(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        service,
        "build_chat_model",
        lambda: (_ for _ in ()).throw(AssertionError("end must not call LLM")),
    )
    conn = connect(coach_db)
    try:
        session = service.prepare(conn, "sub-53-new")
        result = service.chat(conn, session["session_id"], "先这样，谢谢")
    finally:
        conn.close()

    assert result["done"] is True
    assert "今天先到这里" in result["reply"]


def test_same_session_rejects_concurrent_turn(coach_db: Path) -> None:
    conn = connect(coach_db)
    try:
        session = service.prepare(conn, "sub-53-new")
        assert service.try_acquire_session(session["session_id"])
        events = list(service.chat_stream(conn, session["session_id"], "继续"))
    finally:
        service.release_session(session["session_id"])
        conn.close()

    assert events[0]["type"] == "error"
    assert events[0]["code"] == "session_busy"


def test_cancelled_stream_releases_session_lock(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[object]] = []
    monkeypatch.setattr(service, "build_chat_model", lambda: _StreamingModel(seen))
    stop = Event()
    stop.set()
    conn = connect(coach_db)
    try:
        session = service.prepare(conn, "sub-53-new")
        events = list(
            service.chat_stream(
                conn,
                session["session_id"],
                "继续",
                cancel_event=stop,
            )
        )
        assert service.try_acquire_session(session["session_id"])
    finally:
        service.release_session(session["session_id"])
        conn.close()

    assert [event["type"] for event in events] == ["ready"]


@pytest.fixture()
def coach_client(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    monkeypatch.setattr(routes_coach, "init_db", lambda: connect(coach_db))
    monkeypatch.setattr(routes_coach, "kg_is_imported", lambda _conn: True)
    monkeypatch.setattr(routes_coach, "coach_dependencies_available", lambda: True)
    app = FastAPI()
    app.include_router(routes_coach.router)
    return TestClient(app)


def test_prepare_and_session_http_contract(coach_client: TestClient) -> None:
    prepared = coach_client.post(
        "/api/coach/prepare",
        json={"submission_id": "sub-53-new", "problem_id": 53},
    )
    assert prepared.status_code == 200
    body = prepared.json()
    assert body["opening_source"] == "template"
    assert body["fallback_used"] is False

    cached = coach_client.get(
        "/api/coach/session", params={"submission_id": "sub-53-new"}
    )
    assert cached.status_code == 200
    assert cached.json()["session_id"] == body["session_id"]


def test_prepare_http_falls_back_by_problem(coach_client: TestClient) -> None:
    response = coach_client.post(
        "/api/coach/prepare",
        json={"submission_id": "unknown", "problem_id": 53},
    )
    assert response.status_code == 200
    assert response.json()["fallback_used"] is True
    assert response.json()["resolved_submission_id"] == "sub-53-new"


def test_stream_returns_409_for_busy_session(
    coach_client: TestClient, coach_db: Path
) -> None:
    prepared = coach_client.post(
        "/api/coach/prepare", json={"submission_id": "sub-53-new"}
    ).json()
    session_id = prepared["session_id"]
    assert service.try_acquire_session(session_id)
    try:
        response = coach_client.post(
            "/api/coach/stream",
            json={"session_id": session_id, "message": "继续"},
        )
    finally:
        service.release_session(session_id)
    assert response.status_code == 409
    assert response.json()["code"] == "session_busy"


def test_stream_model_failure_returns_fallback_and_done(
    coach_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenModel:
        def stream(self, _messages: list[object]):
            raise TimeoutError("model timeout")
            yield  # pragma: no cover

    monkeypatch.setattr(service, "build_chat_model", lambda: BrokenModel())
    prepared = coach_client.post(
        "/api/coach/prepare", json={"submission_id": "sub-53-new"}
    ).json()
    response = coach_client.post(
        "/api/coach/stream",
        json={"session_id": prepared["session_id"], "message": "我不知道"},
    )
    assert response.status_code == 200
    assert "event: ready" in response.text
    assert "event: fallback" in response.text
    assert "event: done" in response.text
