"""고객용 완료 상태: 앱·DB·모델 없이 실제 경로를 호출한다.

role-manager L02a 이식: writer 내부 계약만 싣는다. 공개 response_status/question_status 를 단언하던 시험
(JSON/SSE 투영 · 저장 상태 재전송 · 형식 오류 거절)은 L02b 보류와 함께 scratch `held-l02b/` 에 원문 보존했다.
"""
from dataclasses import asdict, replace
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import asyncio
import json

import pytest

from app.domains.travel_ops.components.response import writing as w


def writer_input():
    return w.ResponseInput(source="inquiry", scope=None, version=1, question_ids=("q1",),
        questions=(w.QuestionResult(question_id="q1", request={}, text="확인된 답", status="answered",
            evidence={}, checked_at="2031-01-01T00:00:00+00:00", target={}),),
        execution={"status": "read_only"}, workflow={}, followup=None)


@pytest.mark.parametrize("bad_id", ["", " ", "\t"])
def test_writer_rejects_blank_question_identifier(bad_id):
    data = writer_input()
    with pytest.raises(ValueError):
        w.write_response(replace(data, question_ids=(bad_id,),
            questions=(replace(data.questions[0], question_id=bad_id),)))


def test_writer_rejects_answered_with_unresolved_evidence():
    data = writer_input()
    with pytest.raises(ValueError):
        w.write_response(replace(data, questions=(replace(data.questions[0], evidence={"unresolved": "price"}),)))

def duplicate_reply(monkeypatch, reply):
    from datetime import datetime, timezone
    from app.domains.travel_ops.components.conversation import trip_messages as tm, fact_read_retry, case_dispatch
    from app.infrastructure.db import repository
    trip_id, case_id, customer_id = uuid4(), uuid4(), uuid4()
    conn = SimpleNamespace(cursor=lambda: nullcontext(cursor))
    cursor = SimpleNamespace(execute=lambda *a: None, fetchone=lambda: (case_id,))
    case = {"subject": "질문", "status": "completed", "state_json": {"answer": "기존 답", "chat_reply": reply}}
    monkeypatch.setattr(tm, "get_connection", lambda: nullcontext(conn))
    monkeypatch.setattr(tm.TripStore, "latest", lambda *a: ({"trip_id": trip_id, "customer_id": customer_id, "version": 1}, []))
    monkeypatch.setattr(repository, "get_case", lambda *a, **kw: case)
    monkeypatch.setattr(fact_read_retry, "retry_read", lambda *a, **kw: None)
    monkeypatch.setattr(case_dispatch, "retry_initial", lambda *a, **kw: None)
    return tm.handle_trip_message(tenant="tenant", trip_id=trip_id, request_id="same", message="질문",
        at=datetime(2031, 1, 1, tzinfo=timezone.utc), classifier=None, chat=None, desk=None, actor_id="actor")


def test_legacy_duplicate_does_not_invent_completion(monkeypatch):
    result = duplicate_reply(monkeypatch, {"more": "기존 더보기"})
    assert result["more"] == "기존 더보기"
    assert "response_status" not in result and "question_status" not in result

@pytest.mark.parametrize("status", ["answered", "needs_input", "unsupported", "failed"])
def test_public_status_exposes_all_and_only_closure_enums(status):
    from app.domains.travel_ops.components.response.public import response_status
    data = writer_input()
    question = replace(data.questions[0], status=status, request={"text": "PRIVATE"}, target={"item_id": "PRIVATE"})
    result = asdict(w.write_response(replace(data, questions=(question,))))
    public = response_status({"basis": {"response": result}})
    assert public == {"response_status": "complete" if status == "answered" else "partial", "question_status": [status]}
    assert "PRIVATE" not in json.dumps(public)


@pytest.mark.parametrize("response", [None, {}, {"completion": "partial", "questions": [None]},
    {"completion": "partial", "questions": [{"status": "PRIVATE"}]},
    {"completion": "complete", "questions": [{"status": "failed"}]}])
def test_malformed_internal_new_response_is_not_silently_hidden(response):
    from app.domains.travel_ops.components.response.public import response_status
    with pytest.raises(ValueError):
        response_status({"basis": {"response": response}})


def test_duplicate_does_not_project_status_while_public_fields_are_held(monkeypatch):
    """L02b 보류 동안: 저장된 답에 상태 enum 이 있어도 duplicate 공개 응답에 싣지 않는다(allowlist 그대로)."""
    result = duplicate_reply(monkeypatch, {"more": "기존 더보기", "response_status": "partial",
                                           "question_status": ["answered", "failed"], "scope": "PRIVATE-CUSTOMER"})
    assert result["more"] == "기존 더보기"
    assert not {"response_status", "question_status", "scope"}.intersection(result)
