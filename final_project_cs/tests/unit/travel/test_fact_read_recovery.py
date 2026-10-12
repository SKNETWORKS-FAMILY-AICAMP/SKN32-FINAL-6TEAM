"""사실 읽기 복구의 권한·원래 입력·상태 전이를 외부 IO 없이 확인한다."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.contracts import StateConflict
from app.domains.travel_ops.components.conversation import fact_read_retry as reads
from app.domains.travel_ops.components.conversation.decision_unit import Decision


@pytest.fixture
def saved():
    at = datetime(2030, 1, 1, tzinfo=timezone.utc)
    item = SimpleNamespace(item_id=uuid4(), kind="activity", title="경복궁", place=None,
                           starts_at=at, ends_at=None, detail={}, seq=1)
    trip = {"trip_id": uuid4(), "version": 1, "customer_id": uuid4()}
    decision = Decision("answer_fact", item, None, "address", None, "")
    snapshot = reads.read_snapshot(decision, at=at, selected=item.item_id, trip=trip, turns=[])
    return trip, item, decision, snapshot, {"decision": decision.record(), "fact_read_snapshot": snapshot}


def test_snapshot_excludes_coordinates_customer_text_and_raw_model_payload(saved):
    trip, item, decision, snapshot, _ = saved
    decision.raw = {"message": "합성 고객 문장", "latitude": 37.5, "longitude": 127.0}
    snapshot = reads.read_snapshot(decision, at=item.starts_at, selected=item.item_id, trip=trip, turns=[])
    assert not {"raw", "message", "latitude", "longitude", "location"}.intersection(snapshot)
    assert snapshot["at"] == item.starts_at.isoformat()


def test_fact_first_pure_read_choices_have_same_effective_action(saved):
    trip, item, _, _, _ = saved
    decision = Decision("clarify", None, None, "none", None, "", choices=[
        {"action": "answer_fact", "item": item, "change": None, "fact": "none"}])
    snapshot = reads.read_snapshot(decision, at=item.starts_at, selected=None, trip=trip, turns=[])
    restored, _, _ = reads.restore(snapshot, state={"decision": decision.record()}, trip=trip, items=[item])
    assert restored.action == "answer_fact" and restored.fact == "detail" and restored.item is item


def test_mixed_business_choice_is_never_a_read_snapshot(saved):
    trip, item, _, _, _ = saved
    decision = Decision("clarify", None, None, "none", None, "", choices=[
        {"action": "answer_fact", "item": item, "change": None, "fact": "address"},
        {"action": "apply_change", "item": item, "change": None, "fact": "none"}])
    assert reads.read_snapshot(decision, at=item.starts_at, selected=None, trip=trip, turns=[]) is None


@pytest.mark.parametrize("mutation", ["business", "mixed", "wrong_trip", "version", "location",
                                     "unknown_fact", "target", "time", "naive", "schema"])
def test_unsafe_or_changed_snapshot_requires_a_new_request(saved, mutation):
    trip, item, _, snapshot, state = saved
    snapshot = deepcopy(snapshot)
    if mutation == "business":
        state["decision"]["action"] = "apply_change"
    elif mutation == "mixed":
        state["decision"].update(action="clarify", choices=[{"action": "apply_change", "fact": "address"}])
    elif mutation == "wrong_trip":
        snapshot["trip_id"] = str(uuid4())
    elif mutation == "version":
        trip["version"] += 1
    elif mutation == "location":
        snapshot["fact"] = state["decision"]["fact"] = "route_here"
    elif mutation == "unknown_fact":
        snapshot["fact"] = state["decision"]["fact"] = "invented"
    elif mutation == "target":
        snapshot["item_id"] = state["decision"]["item_id"] = str(uuid4())
    elif mutation == "time":
        snapshot["at"] = "invalid"
    elif mutation == "naive":
        snapshot["at"] = "2030-01-01T00:00:00"
    else:
        snapshot["schema"] = 2
    with pytest.raises(StateConflict, match="새 요청 번호"):
        reads.restore(snapshot, state=state, trip=trip, items=[item])


class Conn:
    def __init__(self, *, active=False, error=None):
        self.sql = []
        self.active, self.error = active, error
        self.commits = self.rollbacks = 0

    def cursor(self):
        return nullcontext(self)

    def transaction(self):
        return nullcontext()

    def execute(self, sql, params):
        self.sql.append(sql)
        if self.error is not None:
            raise self.error

    def fetchone(self):
        return (1,) if "FOR UPDATE" in self.sql[-1] or self.active else None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.mark.parametrize("field", ["conversation_dispatch", "subject_ref", "resume_requests", "customer_input_history"])
def test_read_cannot_bypass_business_or_resume_guard(monkeypatch, saved, field):
    *_, state = saved
    state[field] = [] if field.endswith("history") else {"action": "apply_change"}
    if field.endswith("history"):
        state[field] = ["합성 답변"]
    monkeypatch.setattr(reads.repository, "get_case", lambda *a, **k: {"state_json": state})
    with pytest.raises(StateConflict):
        reads.lock_read_case(Conn(), tenant="travel", case_id=uuid4())


def test_only_nowait_lock_conflict_is_translated_to_409(monkeypatch):
    from psycopg.errors import LockNotAvailable, OperationalError
    conn = Conn(error=LockNotAvailable("synthetic lock"))
    with pytest.raises(StateConflict, match="처리 중"):
        reads.lock_read_case(conn, tenant="travel", case_id=uuid4())
    assert conn.rollbacks == 1 and "NOWAIT" in conn.sql[0]
    failure = OperationalError("synthetic connection failure")
    with pytest.raises(OperationalError) as observed:
        reads.lock_read_case(Conn(error=failure), tenant="travel", case_id=uuid4())
    assert observed.value is failure


def test_active_team_run_is_not_replaced_by_read_recovery(monkeypatch, saved):
    *_, state = saved
    monkeypatch.setattr(reads.repository, "get_case", lambda *a, **k: {"state_json": state})
    with pytest.raises(StateConflict, match="담당 팀"):
        reads.lock_read_case(Conn(active=True), tenant="travel", case_id=uuid4())


@pytest.mark.parametrize("stage", ["classifying", "routing", "running"])
def test_saved_read_resumes_actual_reducer_without_model_or_team_or_middle_commit(
        monkeypatch, saved, stage, gap=None, enrichment_rollback=False):
    from app.application import classification
    from app.core import settings, transition
    from app.core.case_lifecycle.case import CaseProjection, apply_event
    from app.core.case_lifecycle.events import EventType
    from app.domains.travel_ops.components.conversation import trip_messages, trip_facts

    trip, item, decision, snapshot, state = saved
    if enrichment_rollback:
        item.place = {"name": "경복궁"}
        decision.fact = snapshot["fact"] = state["decision"]["fact"] = "detail"
    case = dict(case_id=uuid4(), status="classifying", version=1, state_json=state,
                intent=None, issue_code=None, sentiment=None, owner_team_id=None)
    events = []

    def move(conn, *, event_type, payload, expected_version, **kwargs):
        assert case["version"] == expected_version
        keys = ("status", "version", "state_json", "intent", "issue_code", "sentiment", "owner_team_id")
        case.update(asdict(apply_event(CaseProjection(**{k: case[k] for k in keys}), event_type, payload)))
        case["status"] = case["status"].value  # DB projection과 같은 문자열 모양으로 반환한다.
        events.append(event_type.value)

    if stage in ("routing", "running"):
        move(None, event_type=EventType.CLASSIFIED, expected_version=1,
             payload={"intent": "confirm_request", "issue_code": "activity_other", "sentiment": "neutral"})
    if stage == "running":
        move(None, event_type=EventType.ROUTED, expected_version=2,
             payload={"owner_team_id": "activity", "capability": "trip_desk.answer_fact"})
    monkeypatch.setattr(classification, "transition_case", move)
    monkeypatch.setattr(transition, "transition_case", move)
    monkeypatch.setattr(reads.repository, "get_case", lambda *a, **k: deepcopy(case))
    monkeypatch.setattr(settings, "get_guardrails", lambda: SimpleNamespace(get=lambda key: 1800))
    extra_conn = Conn()
    monkeypatch.setattr(trip_messages, "get_connection", lambda: nullcontext(extra_conn))
    observed = []
    monkeypatch.setattr(trip_facts, "fact_reply", lambda *a, **k: (observed.append(k) or "경복궁 주소", {}))
    store = SimpleNamespace(latest=lambda *a: (trip, [item]), versions=lambda *a: [{"version": 1}])
    if gap:
        lookups = []

        def latest(*args):
            lookups.append(args)
            version = 2 if gap == "context" or len(lookups) >= 2 else 1
            return {**trip, "version": version}, [item]

        store.latest = latest
    controller = SimpleNamespace(run_case=lambda **k: pytest.fail("읽기 복구에서 Team 실행 금지"))
    conn = Conn()
    if enrichment_rollback:
        def extras(connection, *args):
            assert connection is extra_conn and connection is not conn
            connection.rollback()
            return ""

        monkeypatch.setattr(trip_messages, "_place_extras", extras)

    def retry():
        return reads.retry_read(conn, case=deepcopy(case), tenant="travel", trip=trip, items=[item],
            actor_id="test", desk=None, store=store, message="경복궁 주소 알려줘", request_id="same-read",
            policy_search=None, place_source=None, controller=controller)

    if gap:
        with pytest.raises(StateConflict, match="새 요청 번호"):
            retry()
        assert not observed
        return
    result = retry()
    assert result["status"] == "answered" and result["case_status"] == "resolved"
    assert events == ["classified", "routed", "completed"]
    assert observed[0]["now"] == item.starts_at and observed[0]["item"].item_id == item.item_id
    assert conn.commits == 0  # 연결 바깥의 성공 커밋까지 같은 Case 잠금을 유지한다.
    if enrichment_rollback:
        assert extra_conn.rollbacks == 1 and conn.rollbacks == 0


@pytest.mark.parametrize("phase", ["context", "fresh"])
def test_version_drift_after_preflight_rejects_before_answer(monkeypatch, saved, phase):
    test_saved_read_resumes_actual_reducer_without_model_or_team_or_middle_commit(
        monkeypatch, saved, "classifying", gap=phase)


def test_detail_component_rollback_keeps_case_transaction_and_lock(monkeypatch, saved):
    test_saved_read_resumes_actual_reducer_without_model_or_team_or_middle_commit(
        monkeypatch, saved, "classifying", enrichment_rollback=True)


def test_legacy_stored_read_answer_returns_without_snapshot_or_recompute(monkeypatch, saved):
    trip, item, _, _, state = saved
    state.pop("fact_read_snapshot")
    state["answer"] = "저장된 경복궁 주소"
    case = {"case_id": uuid4(), "status": "classifying", "state_json": state}
    monkeypatch.setattr(reads.repository, "get_case", lambda *a, **k: case)
    result = reads.retry_read(Conn(), case=case, tenant="travel", trip=trip, items=[item], actor_id="test",
        desk=None, store=None, message="경복궁 주소", request_id="legacy", policy_search=None,
        place_source=None, controller=None)
    assert result["answer"] == state["answer"] and result["status"] == "duplicate"


@pytest.mark.parametrize("status,decision,expected", [
    ("classifying", None, True), ("routing", None, False), ("running", None, False),
    ("classifying", {"action": "apply_change"}, False)])
def test_legacy_off_cache_is_limited_to_unclassified_fact_response(monkeypatch, saved, status, decision, expected):
    trip, item, _, _, _ = saved
    state = {"answer": "저장된 여행 하루 요약"}
    if decision:
        state["decision"] = decision
    case = {"case_id": uuid4(), "status": status, "state_json": state}
    monkeypatch.setattr(reads.repository, "get_case", lambda *a, **k: case)
    result = reads.retry_read(Conn(), case=case, tenant="travel", trip=trip, items=[item], actor_id="test",
        desk=None, store=None, message="하루 일정 요약", request_id="legacy-off", policy_search=None,
        place_source=None, controller=None)
    assert (result is not None) is expected
    if expected:
        assert result["answer"] == state["answer"]
