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
                "tags": ["Array", "Divide and Conquer", "Dynamic Programming"],
                "status": "Wrong Answer",
                "language": "java",
                "code": "class Solution {\n  public int maxSubArray(int[] nums) {\n    return nums[0];\n  }\n}\n",
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
                "tags": ["Array", "Divide and Conquer", "Dynamic Programming"],
                "status": "Accepted",
                "language": "java",
                "code": "class Solution {\n  public int maxSubArray(int[] nums) {\n    int best = nums[0];\n    return best;\n  }\n}\n",
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
    assert "maxSubArray" in result["context_preview"]
    assert "Wrong Answer -> Accepted" in result["context_preview"]
    assert "运行用时：" in result["context_preview"]


def test_accepted_context_uses_refactor_hint(coach_db: Path) -> None:
    from leetcode_tracker.coach.context import build_coach_context

    conn = connect(coach_db)
    try:
        ctx = build_coach_context(conn, "sub-53-new")
    finally:
        conn.close()

    assert "**Accepted**" in ctx["markdown"]
    assert "重构顾问" in ctx["markdown"]
    assert "⚠️ 逻辑错误" not in ctx["markdown"]
    assert "运行用时：" in ctx["markdown"]
    assert "内存消耗：" in ctx["markdown"]
    assert "题目标签：Array、Divide and Conquer、Dynamic Programming" in ctx["markdown"]


def test_wrong_answer_hint_covers_index_value_convention(coach_db: Path) -> None:
    from leetcode_tracker.coach.context import build_coach_context

    conn = connect(coach_db)
    try:
        ctx = build_coach_context(conn, "sub-53")
    finally:
        conn.close()

    assert "**Wrong Answer**" in ctx["markdown"]
    assert "nums[i] 与 i/i+1" in ctx["markdown"]
    assert "返回的是下标、值，还是 n+1" in ctx["markdown"]
    assert "循环边界" not in ctx["markdown"]
    assert "题目标签：Array、Divide and Conquer、Dynamic Programming" in ctx["markdown"]


def test_prepare_stores_submission_status_and_ac_opening(coach_db: Path) -> None:
    from leetcode_tracker.coach.sessions import get_session

    conn = connect(coach_db)
    try:
        result = service.prepare(conn, "sub-53-new")
        session = get_session(conn, result["session_id"])
    finally:
        conn.close()

    assert result["submission_status"] == "Accepted"
    assert session is not None
    assert session["submission_status"] == "Accepted"
    assert "已通过" in result["opening"]
    assert "耗时、内存" in result["opening"]
    assert "卡在哪" not in result["opening"]


def test_prepare_debug_status_for_wrong_answer(coach_db: Path) -> None:
    conn = connect(coach_db)
    try:
        result = service.prepare(conn, "sub-53")
    finally:
        conn.close()

    assert result["submission_status"] == "Wrong Answer"
    assert "Wrong Answer" in result["opening"]


def test_system_prompt_routes_by_status() -> None:
    from leetcode_tracker.coach.prompts import (
        COACH_PROMPT_AC,
        COACH_PROMPT_DEBUG,
        system_prompt_for_status,
    )

    assert system_prompt_for_status("Accepted") is COACH_PROMPT_AC
    assert system_prompt_for_status("Wrong Answer") is COACH_PROMPT_DEBUG
    assert system_prompt_for_status("Compile Error") is COACH_PROMPT_DEBUG
    assert "重构顾问" in COACH_PROMPT_AC
    assert "Bug 排查" in COACH_PROMPT_DEBUG
    assert "```" in COACH_PROMPT_AC  # 禁令里提到代码块语法
    assert "最多 3 句" in COACH_PROMPT_DEBUG
    assert "禁止重复同一疑点" in COACH_PROMPT_DEBUG
    assert "nums[i] 与 i+1" in COACH_PROMPT_DEBUG
    assert "循环上界是 len(nums)" not in COACH_PROMPT_DEBUG


def test_code_block_guardrail_strips_and_appends() -> None:
    from leetcode_tracker.coach.guardrail import apply_code_block_guardrail

    raw = (
        "可以这样改：\n"
        "```java\n"
        "class Solution { public int[] rotate(int[] a){ return a; } }\n"
        "```\n"
        "你觉得呢？"
    )
    cleaned, stripped = apply_code_block_guardrail(raw)
    assert stripped is True
    assert "```" not in cleaned
    assert "class Solution" not in cleaned
    assert "不能直接贴" in cleaned


def test_chat_uses_ac_prompt_and_strips_leaked_code(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class LeakyModel:
        def stream(self, messages: list[object]):
            system = str(getattr(messages[0], "content", ""))
            assert "重构顾问" in system
            assert "Bug 排查" not in system
            yield SimpleNamespace(
                content=(
                    "三次反转即可。\n"
                    "```java\n"
                    "class Solution { void rotate(int[] nums, int k){} }\n"
                    "```\n"
                )
            )

    monkeypatch.setattr(service, "build_chat_model", lambda: LeakyModel())
    conn = connect(coach_db)
    try:
        session = service.prepare(conn, "sub-53-new")
        result = service.chat(conn, session["session_id"], "有没有更好的写法")
    finally:
        conn.close()

    assert "```" not in result["reply"]
    assert "class Solution" not in result["reply"]
    assert "不能直接贴" in result["reply"]


def test_chat_compile_error_uses_debug_prompt(
    coach_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(coach_db)
    try:
        save_submission(
            conn,
            {
                "submission_id": "sub-ce",
                "problem_id": 1,
                "title": "两数之和",
                "slug": "two-sum",
                "difficulty": "Easy",
                "status": "Compile Error",
                "language": "java",
                "code": "class Solution { int add(int a) { return a }\n",
            },
        )
    finally:
        conn.close()

    class CaptureModel:
        def __init__(self) -> None:
            self.system = ""

        def stream(self, messages: list[object]):
            self.system = str(getattr(messages[0], "content", ""))
            yield SimpleNamespace(content="括号可能没配对。你会怎么补？")

    model = CaptureModel()
    monkeypatch.setattr(service, "build_chat_model", lambda: model)
    conn = connect(coach_db)
    try:
        session = service.prepare(conn, "sub-ce")
        assert session["submission_status"] == "Compile Error"
        service.chat(conn, session["session_id"], "编译不过")
    finally:
        conn.close()

    assert "Bug 排查" in model.system
    assert "重构顾问" not in model.system


def test_prepare_refresh_context_on_reuse(coach_db: Path) -> None:
    from leetcode_tracker.coach.sessions import get_session

    conn = connect(coach_db)
    try:
        first = service.prepare(conn, "sub-53")
        session_id = first["session_id"]
        conn.execute(
            "UPDATE coach_sessions SET context_markdown = ? WHERE session_id = ?",
            ("## stale context", session_id),
        )
        conn.commit()
        second = service.prepare(conn, "sub-53")
        session = get_session(conn, session_id)
    finally:
        conn.close()

    assert second["reused"] is True
    assert second["session_id"] == session_id
    assert session is not None
    assert "stale context" not in str(session["context_markdown"])
    assert "nums[0]" in str(session["context_markdown"])
    assert "逻辑错误" in str(session["context_markdown"])


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
