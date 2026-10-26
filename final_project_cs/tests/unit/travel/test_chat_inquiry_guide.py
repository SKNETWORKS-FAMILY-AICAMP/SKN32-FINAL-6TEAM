"""D-024 채팅 미해결 답의 문의함 안내 계약 — `trip_replies.INQUIRY_GUIDE`.

계약(wiki `external/chat-inquiry-guide.md`): 채팅 한 통의 결과가 Case `escalated`·`failed`로 끝났고 고객에게 답(`answered`)도
되묻기(`waiting_input`·`clarify`)도 아니면, 답 끝에 문의함 작성 경로를 한 번 안내한다. 처리 완료·되묻기·사실 답에는 붙이지 않는다.
상담원 연결·운영자 대신 수정·외부 알림을 약속하지 않는다.
"""
import asyncio
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest


def test_guide_wording_points_to_the_inquiry_screen_without_agent_handoff():
    from app.domains.travel_ops.components.conversation import trip_replies

    guide = trip_replies.INQUIRY_GUIDE
    assert "문의함" in guide and "문의 작성" in guide
    assert trip_replies.INQUIRY_PATH == "/support/new"
    # 사람 대기·대신 수정 약속 금지(D-024 · D-CS-014)
    for banned in ("상담원", "연결해", "넘겼", "대신 고쳐", "대신 바꿔"):
        assert banned not in guide


@pytest.mark.parametrize("case_status,status", [("escalated", "escalated"), ("failed", "failed"),
                                                ("escalated", "unhandled_change"),
                                                ("escalated", "question_needs_policy_answer"),
                                                ("escalated", "duplicate")])
def test_unresolved_chat_results_end_with_the_inquiry_guide(case_status, status):
    from app.domains.travel_ops.components.conversation import trip_replies

    result = {"case_status": case_status, "status": status, "answer": "요청을 완료하지 못했어요."}
    guided = trip_replies.with_inquiry_guide(result)
    assert guided["answer"] == "요청을 완료하지 못했어요.\n" + trip_replies.INQUIRY_GUIDE
    assert guided["inquiry_path"] == trip_replies.INQUIRY_PATH
    assert result["answer"] == "요청을 완료하지 못했어요."          # 입력은 바꾸지 않는다
    # 두 번 붙이지 않는다(재전송 · 중복 답)
    assert trip_replies.with_inquiry_guide(guided)["answer"] == guided["answer"]


def test_web_variant_of_the_answer_gets_the_same_guide():
    from app.domains.travel_ops.components.conversation import trip_replies

    guided = trip_replies.with_inquiry_guide({"case_status": "escalated", "status": "escalated",
                                              "answer": "글", "answer_web": "웹 글"})
    assert guided["answer_web"] == "웹 글\n" + trip_replies.INQUIRY_GUIDE


@pytest.mark.parametrize("case_status,status", [("resolved", "adjusted"), ("waiting_input", "clarify"),
                                                ("resolved", "clarify"), ("escalated", "answered"),
                                                ("routing", "answered"), ("resolved", "duplicate")])
def test_resolved_answers_questions_and_fact_answers_are_left_alone(case_status, status):
    from app.domains.travel_ops.components.conversation import trip_replies

    result = {"case_status": case_status, "status": status, "answer": "답"}
    assert trip_replies.with_inquiry_guide(result) == result


def test_public_message_handler_applies_the_guide_to_every_unresolved_path(monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages as tm, trip_replies

    outcomes = iter([{"case_status": "escalated", "status": "escalated", "answer": "해석 실패"},
                     {"case_status": "waiting_input", "status": "clarify", "answer": "어느 일정인가요?"}])
    monkeypatch.setattr(tm, "_handle_trip_message", lambda **kw: next(outcomes))
    first = tm.handle_trip_message(tenant="t", trip_id=uuid4(), request_id="r", message="m",
                                   at=datetime.now(timezone.utc), classifier=None, chat=None, desk=None, actor_id="a")
    second = tm.handle_trip_message(tenant="t", trip_id=uuid4(), request_id="r2", message="m",
                                    at=datetime.now(timezone.utc), classifier=None, chat=None, desk=None, actor_id="a")
    assert first["answer"].endswith(trip_replies.INQUIRY_GUIDE)
    assert second["answer"] == "어느 일정인가요?" and "inquiry_path" not in second


def test_web_entrypoint_shows_and_logs_the_guide_for_a_decision_failure(monkeypatch):
    """실제 웹 입구(JSON·SSE) → 공개 처리기 → 결정 실패 답. 대화 기록에도 같은 문장이 남는다."""
    from fastapi import BackgroundTasks
    from starlette.requests import Request
    from app.domains.travel_ops.entry import trip_api
    from app.domains.travel_ops.components.conversation import trip_messages as tm, chat_log, trip_replies
    from app.domains.travel_ops.modules.web_account import web_guard
    from app.domains.travel_ops.modules.live_progress import op_stream
    from app.application import classification
    from app.infrastructure.db import repository

    customer, trip = uuid4(), uuid4()
    conn = object()
    case = {"version": 1, "status": "escalated"}
    saved_turns = []

    def classify(*args, **kwargs):
        with pytest.raises(RuntimeError):
            kwargs["classifier"]("합성 문장")
    monkeypatch.setattr(classification, "classify_case", classify)
    monkeypatch.setattr(repository, "get_case", lambda *a, **kw: case)

    def inner(**kw):
        return tm._run_decision(conn, tenant=kw["tenant"], trip_id=trip, case_id=uuid4(),
                                message=kw["message"], request_id=kw["request_id"], at=datetime.now(timezone.utc),
                                desk=None, store=None, items=[], decision=None, failure="SyntheticError: 합성",
                                actor_id="fixture", policy_search=None, place_source=None, selected=None)
    monkeypatch.setattr(tm, "_handle_trip_message", inner)
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    monkeypatch.setattr(web_guard, "values", lambda tenant: {"web.dev_mode": "off"})
    monkeypatch.setattr(web_guard, "count", lambda *a, **kw: None)
    monkeypatch.setattr(trip_api, "get_connection", lambda: nullcontext(conn))
    monkeypatch.setattr(trip_api.TripStore, "latest", lambda *a: ({"customer_id": customer}, []))
    monkeypatch.setattr(chat_log, "record", lambda *a, **kw: saved_turns.append(deepcopy(kw)))
    monkeypatch.setattr(op_stream, "limits", lambda op: {"beat_seconds": .01, "slow_seconds": 1, "max_per_user": 2, "max_seconds": 5})
    endpoint = next(r.endpoint for r in trip_api.build_trip_router().routes if r.path == "/v1/web/trips/{trip_id}/messages")

    def http(stream):
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        return Request({"type": "http", "headers": [(b"accept", b"text/event-stream" if stream else b"application/json")],
                        "client": ("127.0.0.1", 1),
                        "app": SimpleNamespace(state=SimpleNamespace(runtime=SimpleNamespace(controller=None)))}, receive)

    request = trip_api.WebMessageIn(request_id="fixture", message="합성 문장")
    plain = endpoint(trip, request, http(False), BackgroundTasks(), ("fixture", customer))
    stream = endpoint(trip, request, http(True), BackgroundTasks(), ("fixture", customer))

    async def consume():
        return "".join([chunk async for chunk in stream.body_iterator])
    wire = asyncio.run(consume())
    result = [json.loads(f.split("data: ", 1)[1]) for f in wire.split("\n\n") if f.startswith("event: result\n")][0]
    assert plain["status"] == "escalated" and plain["reason"] == "decision_failed"
    assert plain["answer"].endswith("\n" + trip_replies.INQUIRY_GUIDE)
    assert plain["inquiry_path"] == "/support/new"
    assert {k: v for k, v in result.items() if k != "case_id"} == {k: v for k, v in plain.items() if k != "case_id"}
    assert saved_turns and all(turn["answer"] == plain["answer"] for turn in saved_turns)
    assert "SyntheticError" not in json.dumps(plain, ensure_ascii=False) and "SyntheticError" not in wire
