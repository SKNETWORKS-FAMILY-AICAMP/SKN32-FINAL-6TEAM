"""초기 요청 재시도가 대기 답변·실행 중·미완료 상태를 대신하지 않도록 확인한다."""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.contracts import StateConflict
from app.domains.travel_ops.components.conversation import case_dispatch


class Conn:
    def __init__(self, active=False):
        self.active = active
        self.commits = 0

    def cursor(self):
        return nullcontext(self)

    def execute(self, *args):
        pass

    def fetchone(self):
        return (1,) if self.active else None

    def commit(self):
        self.commits += 1


def call(monkeypatch, status, state=None, *, active=False, run_error=None):
    conn = Conn(active)
    case = dict(status=status, state_json=state or {}, intent="adjust", subject="점심 변경")
    monkeypatch.setattr(case_dispatch.repository, "get_case", lambda *a, **k: case)
    calls = []
    def run_case(**kwargs):
        calls.append(kwargs)
        if run_error is not None:
            raise run_error

    controller = SimpleNamespace(require_team=lambda *a, **k: object(),
        registry=SimpleNamespace(capability_for=lambda *a, **k: "change"),
        _capability_state=lambda c: c["state_json"], run_case=run_case)
    return conn, calls, lambda: case_dispatch.retry_initial(conn, controller=controller, tenant="travel-test",
        trip={"trip_id": "travel-test", "version": 1}, case_id=uuid4(), items=[], actor_id="test")


@pytest.mark.parametrize("status", ["new", "classifying", "resuming"])
def test_incomplete_request_is_conflict_instead_of_success_duplicate(monkeypatch, status):
    conn, calls, retry = call(monkeypatch, status)
    with pytest.raises(StateConflict, match="미완료 요청"):
        retry()
    assert not calls and conn.commits == 0


@pytest.mark.parametrize("status", ["waiting_input", "waiting_approval", "waiting_external", "resolved", "escalated", "failed", "cancelled"])
def test_waiting_or_terminal_case_keeps_existing_duplicate_policy(monkeypatch, status):
    conn, calls, retry = call(monkeypatch, status)
    assert retry() is None
    assert not calls and conn.commits == 0


@pytest.mark.parametrize("field", ["resume_requests", "customer_input_history"])
def test_initial_request_cannot_replace_an_in_progress_customer_reply(monkeypatch, field):
    conn, calls, retry = call(monkeypatch, "running", {field: ["합성 답변"]})
    with pytest.raises(StateConflict, match="원래 답변 요청"):
        retry()
    assert not calls and conn.commits == 0


@pytest.mark.parametrize("status", ["routing", "running"])
def test_old_incomplete_case_without_descriptor_requires_explicit_recovery(monkeypatch, status):
    conn, calls, retry = call(monkeypatch, status)
    with pytest.raises(StateConflict, match="저장된 실행 계획"):
        retry()
    assert not calls and conn.commits == 0


def test_active_run_is_never_replayed(monkeypatch):
    state = {"conversation_dispatch": {"team_id": "dining", "subject_ref": {
        "kind": "trip", "id": "travel-test", "base_version": 1, "request": {"action": "apply_change"}}}}
    conn, calls, retry = call(monkeypatch, "running", state, active=True)
    with pytest.raises(StateConflict, match="아직 실행 중"):
        retry()
    assert not calls and conn.commits == 0


def test_changed_itinerary_is_not_rebased_silently(monkeypatch):
    state = {"conversation_dispatch": {"team_id": "dining", "subject_ref": {
        "kind": "trip", "id": "travel-test", "base_version": 0, "request": {"action": "apply_change"}}}}
    conn, calls, retry = call(monkeypatch, "running", state)
    with pytest.raises(StateConflict, match="일정이 바뀌었습니다"):
        retry()
    assert not calls and conn.commits == 0


def test_run_started_after_preflight_is_a_conflict_instead_of_unhandled_error(monkeypatch):
    from app.application.case_service import ActiveRunError

    state = {"conversation_dispatch": {"team_id": "dining", "subject_ref": {
        "kind": "trip", "id": "travel-test", "base_version": 1, "request": {"action": "apply_change"}}}}
    conn, calls, retry = call(monkeypatch, "running", state, run_error=ActiveRunError("synthetic race"))
    with pytest.raises(StateConflict, match="아직 실행 중"):
        retry()
    assert len(calls) == 1 and conn.commits == 1


def test_routing_retry_also_preserves_the_run_winner_when_execute_races(monkeypatch):
    from app.application.case_service import ActiveRunError

    state = {"conversation_dispatch": {"team_id": "dining", "subject_ref": {
        "kind": "trip", "id": "travel-test", "base_version": 1, "request": {"action": "apply_change"}}}}
    conn, calls, retry = call(monkeypatch, "routing", state)
    executions = []

    def execute(*args, **kwargs):
        executions.append(kwargs)
        raise ActiveRunError("synthetic routing race")

    monkeypatch.setattr(case_dispatch, "execute", execute)
    with pytest.raises(StateConflict, match="아직 실행 중"):
        retry()
    assert not calls and len(executions) == 1 and conn.commits == 1
    assert state["conversation_dispatch"]["subject_ref"]["base_version"] == 1


@pytest.mark.parametrize("winner_status", ["running", "resolved"])
def test_actual_execute_checks_latest_status_before_routing(monkeypatch, winner_status):
    conn = Conn()
    initial = dict(status="routing", version=2, state_json={}, intent="adjust", subject="점심 변경")
    winner = {**initial, "status": winner_status, "version": 4}
    cases = iter((initial, winner))
    monkeypatch.setattr(case_dispatch.repository, "get_case", lambda *a, **k: next(cases))
    monkeypatch.setattr(case_dispatch, "_prepare_candidates", lambda *a, **k: None)

    def transition(*a, **k):
        raise AssertionError("winner state must not be transitioned")

    monkeypatch.setattr(case_dispatch, "transition_case", transition)
    controller = SimpleNamespace(require_team=lambda *a, **k: object(),
        registry=SimpleNamespace(capability_for=lambda *a, **k: "change"),
        _capability_state=lambda c: c["state_json"])
    with pytest.raises(StateConflict, match="이미 실행 중이거나 처리"):
        case_dispatch.execute(conn, controller=controller, tenant="travel-test",
            trip={"trip_id": str(uuid4()), "version": 1}, case_id=uuid4(), team="dining",
            request={"action": "apply_change"}, actor_id="test")
    assert conn.commits == 1 and winner["status"] == winner_status and winner["version"] == 4
