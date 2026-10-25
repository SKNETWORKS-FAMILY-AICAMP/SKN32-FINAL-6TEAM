"""L02a — 채팅 변경 답도 공통 writer 를 거친다(내부 근거만). 공개 응답 필드는 늘지 않는다(L02b 보류).

앱 · DB · 모델 없이 실제 `_run_decision` 과 공개 투영(`trip_api` 의 `_web_view`)을 부른다. 합성 일정만 쓴다.
"""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest

from app.domains.travel_ops.components.response import change as ch

NOW = datetime(2031, 3, 10, tzinfo=timezone.utc)


@pytest.mark.parametrize("status, closure", [
    ("adjusted", "answered"), ("already_applied", "answered"), ("clarify", "needs_input"),
    ("ask_target", "needs_input"), ("edit_refused", "unsupported"), ("no_alternate", "unsupported"),
    ("unhandled_lock_item", "failed"), (None, "failed")])
def test_change_status_maps_to_one_explicit_closure(status, closure):
    got = ch.compose_change_response(action="lock_item", outcome={"status": status}, answer="확인된 문장",
                                     version=3, scope=None)
    assert [q.status for q in got.questions] == [closure]
    assert got.completion == ("complete" if closure == "answered" else "partial")
    assert got.answer == "확인된 문장" and got.source == "chat_change"


def test_needs_location_is_never_answered():
    got = ch.compose_change_response(action="change_time", outcome={"status": "adjusted", "needs_location": True},
                                     answer="위치를 알려 주세요", version=1, scope=None)
    assert got.questions[0].status == "needs_input"


def test_blank_answer_is_recorded_as_writing_failure_not_hidden():
    basis = ch.change_basis({"kind": "edit"}, action="lock_item", outcome={"status": "adjusted"}, answer="  ",
                            version=1, scope=None)
    assert basis["response_writing"] == {"status": "failed", "error": "ValueError"}
    assert "response" not in basis and basis["kind"] == "edit"


def _run(monkeypatch, outcome, action="lock_item"):
    from app.domains.travel_ops.components.conversation import trip_messages as tm, decision_unit as du, chat_log
    from app.application import classification
    from app.core import settings, transition
    from app.core.case_lifecycle.events import EventType
    from app.infrastructure.db import repository
    trip_id, case_id, customer_id = uuid4(), uuid4(), uuid4()
    stop = SimpleNamespace(item_id=uuid4(), title="솔빛전시관", kind="activity", seq=1, detail={},
                           starts_at=NOW + timedelta(days=1), ends_at=NOW + timedelta(days=1, hours=1),
                           place={"name": "솔빛전시관", "attributes": {}})
    trip = {"trip_id": trip_id, "customer_id": customer_id, "version": 7}
    conn = SimpleNamespace(commit=lambda: None, transaction=lambda: nullcontext())
    store = SimpleNamespace(latest=lambda *a: (trip, [stop]), versions=lambda *a: [])
    patches, edits = [], []
    monkeypatch.setattr(tm, "get_connection", lambda: nullcontext(conn))
    monkeypatch.setattr(repository, "get_case", lambda *a, **kw: {"version": 1, "status": "running"})
    monkeypatch.setattr(classification, "classify_case", lambda *a, **kw: EventType.CLASSIFIED)
    monkeypatch.setattr(transition, "transition_case", lambda *a, **kw: patches.append(kw.get("payload", {})))
    monkeypatch.setattr(settings, "get_guardrails", lambda: SimpleNamespace(get=lambda key: 1800))
    monkeypatch.setattr(chat_log, "recent", lambda *a, **kw: [])
    desk = SimpleNamespace(edit=lambda **kw: edits.append(kw) or dict(outcome))
    decision = du.Decision(action, stop, None, "", None, "")
    result = tm._run_decision(conn, tenant="tenant-real", trip_id=trip_id, case_id=case_id, message="이건 고정해 줘",
                              request_id="req", at=NOW, desk=desk, store=store, items=[stop], decision=decision,
                              failure=None, actor_id="actor", policy_search=None, place_source=None, selected=None)
    return result, patches, edits, trip


def test_real_chat_change_answer_goes_through_writer_internally(monkeypatch):
    result, patches, edits, trip = _run(monkeypatch, {"status": "adjusted", "text": "솔빛전시관을 고정했어요.", "version": 8})
    assert len(edits) == 1                                        # 실행은 기존 `TripDesk.edit` 한 번뿐(writer 는 실행 권한 없음)
    response = result["basis"]["response"]
    assert response["source"] == "chat_change" and response["completion"] == "complete"
    assert [q["status"] for q in response["questions"]] == ["answered"]
    assert response["answer"] == result["answer"]                 # 고객 문장은 writer 를 거쳐도 그대로
    assert response["scope"] == {"tenant_id": "tenant-real", "customer_id": str(trip["customer_id"]),
                                 "trip_id": str(trip["trip_id"])}
    assert response["version"] == 7 and response["execution"] == {"status": "adjusted", "saved_version": 8}
    kept = next(p["state_patch"]["trip_outcome"] for p in patches if "trip_outcome" in p.get("state_patch", {}))
    assert kept["basis"]["response"]["completion"] == "complete"  # Case 기록(내부)에 남는다
    # 공개 필드는 늘지 않는다 — response_status/question_status 는 L02b 보류
    assert "response_status" not in result and "question_status" not in result
    reply = next((p["state_patch"]["chat_reply"] for p in patches if "chat_reply" in p.get("state_patch", {})), {})
    assert "response_status" not in reply and "question_status" not in reply


def test_refused_change_is_closed_unsupported_and_text_unchanged(monkeypatch):
    result, _, _, _ = _run(monkeypatch, {"status": "edit_refused", "text": "지난 일정은 바꿀 수 없어요."})
    response = result["basis"]["response"]
    assert response["completion"] == "partial" and [q["status"] for q in response["questions"]] == ["unsupported"]
    assert response["answer"] == result["answer"]


@pytest.mark.parametrize("dev", ["off", "on"])
def test_public_projection_adds_no_status_field_and_dev_view_drops_scope(monkeypatch, dev):
    """실제 `POST /v1/web/trips/{trip_id}/messages` JSON 과 SSE result 가 같고, 공개 상태 필드가 없다."""
    import asyncio
    from copy import deepcopy
    from fastapi import BackgroundTasks
    from starlette.requests import Request
    from app.domains.travel_ops.entry import trip_api
    from app.domains.travel_ops.components.conversation import trip_messages, chat_log
    from app.domains.travel_ops.modules.web_account import web_guard
    from app.domains.travel_ops.modules.live_progress import op_stream
    raw, _, _, trip = _run(monkeypatch, {"status": "adjusted", "text": "솔빛전시관을 고정했어요.", "version": 8})
    raw = json.loads(json.dumps(raw, ensure_ascii=False, default=str))
    customer = trip["customer_id"]
    monkeypatch.setattr(web_guard, "assert_human_check_configured", lambda: None)
    monkeypatch.setattr(web_guard, "values", lambda tenant: {"web.dev_mode": dev})
    monkeypatch.setattr(web_guard, "count", lambda *a, **kw: None)
    monkeypatch.setattr(trip_api, "get_connection", lambda: nullcontext(object()))
    monkeypatch.setattr(trip_api.TripStore, "latest", lambda *a: ({"customer_id": customer}, []))
    monkeypatch.setattr(chat_log, "record", lambda *a, **kw: None)
    monkeypatch.setattr(trip_messages, "handle_trip_message", lambda **kw: deepcopy(raw))
    monkeypatch.setattr(op_stream, "limits", lambda op: {"beat_seconds": .01, "slow_seconds": 1,
        "max_per_user": 2, "max_seconds": 5})
    router = trip_api.build_trip_router()
    endpoint = next(route.endpoint for route in router.routes if route.path == "/v1/web/trips/{trip_id}/messages")

    def http(stream):
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        return Request({"type": "http", "headers": [(b"accept", b"text/event-stream" if stream else b"application/json")],
            "client": ("127.0.0.1", 1), "app": SimpleNamespace(state=SimpleNamespace(runtime=SimpleNamespace(controller=None)))}, receive)

    request = trip_api.WebMessageIn(request_id="request", message="이건 고정해 줘")
    plain = endpoint(trip["trip_id"], request, http(False), BackgroundTasks(), ("tenant-real", customer))
    stream = endpoint(trip["trip_id"], request, http(True), BackgroundTasks(), ("tenant-real", customer))

    async def consume():
        return "".join([chunk async for chunk in stream.body_iterator])
    events = asyncio.run(consume())
    results = [json.loads(event.split("data: ", 1)[1]) for event in events.split("\n\n") if event.startswith("event: result\n")]
    assert len(results) == 1 and results[0] == plain
    assert "response_status" not in plain and "question_status" not in plain
    assert plain["answer"] == raw["answer"]
    if dev == "off":
        assert "basis" not in plain
    else:
        assert "scope" not in plain["basis"]["response"]
        assert all("request" not in q for q in plain["basis"]["response"]["questions"])
