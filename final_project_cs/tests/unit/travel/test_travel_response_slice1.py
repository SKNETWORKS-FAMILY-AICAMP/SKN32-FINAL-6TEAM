"""여행 작성 첫 slice: 실제 읽기 결과 작성, 네트워크·DB 실행 없음."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

NOW = datetime(2031, 3, 10, tzinfo=timezone.utc)


def writer():
    path = Path(__file__).resolve().parents[3] / "app/domains/travel_ops/components/response/writing.py"
    assert path.exists(), "공통 응대 작성 계약과 작성기가 아직 없습니다"
    return import_module("app.domains.travel_ops.components.response.writing")


def test_writer_composes_every_question_and_preserves_workflow_without_mutation():
    w = writer()
    workflow = {"proposals": [{"id": "p1", "approved": False}], "required_input_schema": {"type": "object"},
                "resume_token": "opaque", "status": "waiting_approval"}
    evidence = {"source": "여행 등록 자료", "checked_at": NOW.isoformat(), "omissions": ["latest_price"]}
    data = w.ResponseInput(source="inquiry", scope={"tenant_id": "t", "customer_id": "c", "trip_id": "trip"},
        version=7, question_ids=("q1", "q2"), questions=(
            w.QuestionResult(question_id="q1", request={"text": "언제?"}, text="등록 일정은 10:00입니다.",
                status="answered", evidence=evidence, checked_at=NOW.isoformat(), target={"item_id": "i1", "version": 7}),
            w.QuestionResult(question_id="q2", request={"text": "요금은?"}, text="최신 요금은 확인되지 않았어요.",
                status="failed", evidence={"unresolved": "price_text"}, checked_at=NOW.isoformat(), target={})),
        execution={"status": "read_only"}, workflow=workflow, followup={"item_id": "i1", "version": 7}, social="안녕하세요.")
    before = deepcopy(data)
    result = w.write_response(data)
    assert result.answer == "안녕하세요.\n\n등록 일정은 10:00입니다.\n\n최신 요금은 확인되지 않았어요."
    assert result.completion == "partial" and [q.status for q in result.questions] == ["answered", "failed"]
    assert result.workflow == workflow and result.version == 7 and result.scope == data.scope
    assert result.execution == data.execution and result.followup == data.followup
    assert result.questions[0].evidence == evidence and result.questions[0].target == {"item_id": "i1", "version": 7}
    result.workflow["proposals"][0]["approved"] = True
    result.questions[0].evidence["source"] = "changed"
    assert data == before


@pytest.mark.parametrize("ids,text,status", [(("q1", "q2"), "답", "answered"),
    (("q1", "q1"), "답", "answered"), (("other",), "답", "answered"),
    (("q1",), " ", "answered"), (("q1",), "답", "success")])
def test_writer_rejects_missing_duplicate_extra_empty_or_invalid_closures(ids, text, status):
    w = writer()
    data = w.ResponseInput(source="inquiry", scope=None, version=1, question_ids=ids,
        questions=(w.QuestionResult(question_id="q1", request={}, text=text, status=status,
            evidence={}, checked_at=NOW.isoformat(), target={}),), execution={"status": "read_only"},
        workflow={}, followup=None)
    with pytest.raises(ValueError):
        w.write_response(data)


def test_actual_multi_read_uses_writer_with_each_unresolved_question_closed(monkeypatch):
    from app.domains.travel_ops.components.conversation import decision_unit as du, read_requests
    w = writer()
    seen = []
    actual = w.write_response
    def record(data):
        seen.append(data)
        return actual(data)
    monkeypatch.setattr(w, "write_response", record)
    stop = SimpleNamespace(item_id=uuid4(), title="솔빛전시관", kind="activity", seq=1, detail={},
        starts_at=NOW, ends_at=NOW + timedelta(hours=1), place={"name": "솔빛전시관", "attributes": {}})
    requests = [dict(fact=fact, target_item="i1", reference="explicit", origin_item="none", query=None,
                     text=text, advice="") for fact, text in [("time", "언제 방문해?"), ("price", "요금은?")]]
    decision = du.Decision("answer_fact", None, None, "time", None, "", reads=requests)
    before = deepcopy(decision)
    outcome, basis, focus = read_requests.reply(decision, items=[stop], message="언제 방문해? 요금은?", selected=None,
        turns=[], version=7, now=NOW, context_now=NOW, ttl_seconds=1800, place_source=None)
    assert seen, "실제 복합 문의 경로가 공통 작성기를 사용하지 않습니다"
    assert outcome["status"] == "answered" and "솔빛전시관" in outcome["text"]
    assert basis["response"]["completion"] == "partial"
    assert [q["status"] for q in basis["response"]["questions"]] == ["answered", "failed"]
    assert basis["response"]["version"] == 7 and basis["response"]["execution"] == {"status": "read_only"}
    assert basis["response"]["scope"] is None
    assert basis["response"]["questions"][1]["request"] == requests[1]
    assert basis["response"]["questions"][1]["checked_at"] == NOW.isoformat()
    assert basis["response"]["questions"][1]["evidence"] == basis["questions"][1]
    assert basis["response"]["followup"] == focus and focus["version"] == 7
    assert decision == before


def test_inquiry_workflow_supplies_persisted_scope_to_real_writer(monkeypatch):
    from contextlib import nullcontext
    from app.domains.travel_ops.components.conversation import trip_messages, decision_unit as du, chat_log
    from app.application import classification
    from app.core import settings, transition
    from app.core.case_lifecycle.events import EventType
    from app.infrastructure.db import repository
    w = writer()
    captured = []
    actual = w.write_response
    def record(data):
        captured.append(data)
        return actual(data)
    monkeypatch.setattr(w, "write_response", record)
    trip_id, case_id, customer_id = uuid4(), uuid4(), uuid4()
    stop = SimpleNamespace(item_id=uuid4(), title="솔빛전시관", kind="activity", seq=1, detail={},
        starts_at=NOW, ends_at=NOW + timedelta(hours=1), place={"name": "솔빛전시관", "attributes": {}})
    trip = {"trip_id": trip_id, "customer_id": customer_id, "version": 7}
    conn = SimpleNamespace(commit=lambda: None, transaction=lambda: nullcontext())
    store = SimpleNamespace(latest=lambda *args: (trip, [stop]), versions=lambda *args: [])
    monkeypatch.setattr(trip_messages, "get_connection", lambda: nullcontext(conn))
    monkeypatch.setattr(repository, "get_case", lambda *args, **kwargs: {"version": 1, "status": "running"})
    monkeypatch.setattr(classification, "classify_case", lambda *args, **kwargs: EventType.CLASSIFIED)
    monkeypatch.setattr(transition, "transition_case", lambda *args, **kwargs: None)
    monkeypatch.setattr(settings, "get_guardrails", lambda: SimpleNamespace(get=lambda key: 1800))
    monkeypatch.setattr(chat_log, "recent", lambda *args, **kwargs: [])
    request = dict(fact="time", target_item="i1", reference="explicit", origin_item="none", query=None, text="언제?", advice="")
    decision = du.Decision("answer_fact", None, None, "time", None, "", reads=[request])
    result = trip_messages._run_decision(conn, tenant="tenant-real", trip_id=trip_id, case_id=case_id,
        message="언제?", request_id="req", at=NOW, desk=None, store=store, items=[stop], decision=decision,
        failure=None, actor_id="actor-not-customer", policy_search=None, place_source=None, selected=None)
    assert captured and captured[0].scope == {"tenant_id": "tenant-real", "customer_id": str(customer_id), "trip_id": str(trip_id)}
    assert captured[0].version == 7 and captured[0].execution == {"status": "read_only"}
    assert "솔빛전시관" in result["answer"] and result["status"] == "answered"
