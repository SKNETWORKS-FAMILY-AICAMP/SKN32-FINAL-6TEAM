"""승인 뒤 실행(`Controller._apply_approved`) 중 저장소 쓰기 실패 — 예외로 새지 않고 명시적 escalated 로 닫는다.

`[2026-10-26 묶음 M · F03 같은 결함 — 남은 일 3]` 수용 F03 과 같은 종류(psycopg `OperationalError` 계열)가 승인된 제안을 적용하는
savepoint 안에서 나면, 전에는 그대로 올라가 `run_case` 의 A 단계 전체가 되돌려졌다(Case `resuming` 잔류 · 승인만 남고 결과 없음).

★DB 없이 `_apply_approved` 의 경계만 본다. 실제 savepoint 롤백 · 예약 원장 그대로 · Case 전이는
  `tests/integration/controller/test_travel_approval_proposal_reaches_waiting.py` 의 DB 시험이 본다.
"""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from app.application import controller as controller_module
from app.application.controller import Controller
from app.core.actions import ActionHandlers
from app.core.case_lifecycle.events import EventType
from app.core.registry import TeamRegistry

PRIVATE = "CONTROLLED_PRIVATE_SQL_DETAIL tenant=x params=(010-1234-5678)"


class _Conn:
    def transaction(self):
        return nullcontext()


class _Handler:
    action_type = "demo.book"
    auto_apply = False

    def __init__(self, error=None):
        self.error, self.calls = error, 0

    def subject(self, arguments):
        return str(arguments["target"])

    def apply(self, conn, *, tenant_id, customer_id, case_id, arguments):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(result_ref="demo:ok", summary={}, outbox=[], ledger=lambda: {})


def _world(monkeypatch, handler, *, status_error=None):
    statuses, transitions = [], []

    def set_action_status(conn, *, tenant_id, action_id, status, **kw):
        if status == "succeeded" and status_error is not None:
            raise status_error                       # 적용기는 됐는데 실행 장부 쓰기(같은 savepoint)가 실패
        statuses.append((str(action_id), status))

    def transition(conn, **kw):
        transitions.append(kw)
        return SimpleNamespace(status=kw["event_type"], version=2)

    monkeypatch.setattr(controller_module, "transition_case", transition)
    repository = SimpleNamespace(set_action_status=set_action_status)
    controller = Controller(TeamRegistry([]), connection_factory=lambda: None, repository=repository,
                            policy_search=lambda *a, **k: [], action_handlers=ActionHandlers([handler]))
    case = {"case_id": uuid4(), "tenant_id": "unit-storage", "customer_id": uuid4(), "version": 1, "state_json": {}}
    action = {"action_id": uuid4(), "action_type": "demo.book", "arguments": {"target": "thing-1"}}
    run = lambda: controller._apply_approved(_Conn(), case, [action], "ops-1")  # noqa: E731
    return run, action, statuses, transitions


@pytest.mark.parametrize("error", [psycopg.OperationalError(PRIVATE), psycopg.errors.LockNotAvailable(PRIVATE),
                                   psycopg.errors.DiskFull(PRIVATE)])
def test_a_storage_failure_while_applying_an_approved_action_escalates_explicitly(monkeypatch, caplog, error):
    handler = _Handler(error)
    run, action, statuses, transitions = _world(monkeypatch, handler)
    run()                                           # ★예외로 새면(→ run_case 전체 롤백 · HTTP 500) 안 된다
    assert handler.calls == 1
    assert statuses == [(str(action["action_id"]), "failed")]
    assert len(transitions) == 1
    assert transitions[0]["event_type"] is EventType.GUARDRAIL_ESCALATED
    assert transitions[0]["payload"] == {"guardrail": "action_storage_failed", "observed": [type(error).__name__]}
    assert not transitions[0].get("outbox")             # 실행하지 못했으면 안내도 내보내지 않는다
    for text in (str(transitions[0]), caplog.text):     # ★기록 · 로그에는 예외 종류만 — 메시지 · SQL 인자(고객 값)는 없다
        assert "010-1234-5678" not in text and "CONTROLLED_PRIVATE" not in text


def test_a_storage_failure_writing_the_ledger_after_the_handler_also_escalates(monkeypatch):
    # ★적용기 뒤 실행 장부(`set_action_status succeeded`)도 같은 savepoint 안이다 — 둘 다 되돌려지고 escalated 로 닫는다
    handler = _Handler()
    run, action, statuses, transitions = _world(monkeypatch, handler,
                                                status_error=psycopg.errors.QueryCanceled(PRIVATE))
    run()
    assert statuses == [(str(action["action_id"]), "failed")]
    assert transitions[0]["payload"] == {"guardrail": "action_storage_failed", "observed": ["QueryCanceled"]}


@pytest.mark.parametrize("error", [psycopg.IntegrityError("dup"), psycopg.ProgrammingError("bad sql"),
                                   RuntimeError("bug")])
def test_code_defects_while_applying_an_approved_action_are_not_relabelled(monkeypatch, error):
    # ★저장소 운영 실패만 명시 실패로 닫는다 — 코드 결함은 그대로 시끄럽게 올라간다(무음 폴백 금지)
    run, _, statuses, transitions = _world(monkeypatch, _Handler(error))
    with pytest.raises(type(error)):
        run()
    assert statuses == [] and transitions == []


def test_when_the_connection_itself_is_gone_the_failure_is_not_hidden(monkeypatch):
    # ★되돌린 뒤 실패 기록 · 전이도 못 쓰면(연결이 죽었다) 그 예외가 올라간다 — 「적용 안 됨」을 확정하지 못했으니 숨기지 않는다
    run, _, _, _ = _world(monkeypatch, _Handler(psycopg.OperationalError(PRIVATE)))

    def dead(conn, **kw):
        raise psycopg.OperationalError("the connection is closed")

    monkeypatch.setattr(controller_module, "transition_case", dead)
    with pytest.raises(psycopg.OperationalError):
        run()


@pytest.mark.parametrize("where", ["create", "ledger"])
def test_auto_apply_ledger_write_storage_failure_escalates_explicitly(monkeypatch, where):
    # ★`[2026-10-27 C 전수검사]` 승인 없는 자동 적용도 적용기 **뒤** 실행 장부 쓰기(create_action_request ·
    #   set_action_status succeeded)가 같은 savepoint 안이다. 전에는 적용기 호출만 감싸 장부 쓰기 OperationalError 가
    #   그대로 새어 run_case 전체가 되돌려졌다(HTTP 500 · Case running 잔류).
    class _AutoHandler(_Handler):
        auto_apply = True

    handler = _AutoHandler()
    handler_outcome = SimpleNamespace(result_ref="demo:ok", summary={}, outbox=[], answer=None,
                                      ledger=lambda: {"reason": "r"})
    handler.apply = lambda conn, **kw: handler_outcome

    def create_action_request(conn, **kw):
        if where == "create":
            raise psycopg.errors.LockNotAvailable(PRIVATE)
        return uuid4()

    def set_action_status(conn, **kw):
        raise psycopg.errors.QueryCanceled(PRIVATE)

    repository = SimpleNamespace(find_action_request=lambda conn, **kw: None,
                                 create_action_request=create_action_request, set_action_status=set_action_status)
    controller = Controller(TeamRegistry([]), connection_factory=lambda: None, repository=repository,
                            policy_search=lambda *a, **k: [], action_handlers=ActionHandlers([handler]))
    case = {"case_id": uuid4(), "tenant_id": "unit-storage", "customer_id": uuid4(), "version": 1,
            "state_json": {}, "request_id": "r-1"}
    proposal = SimpleNamespace(action_type="demo.book", risk_level="low", arguments={"target": "thing-1"})
    monkeypatch.setattr(controller_module, "request_id_for_case", lambda case: "r-1")
    outcome = controller._apply_auto_proposals(_Conn(), case, [proposal])
    assert isinstance(outcome, tuple) and outcome[0] is EventType.GUARDRAIL_ESCALATED, outcome
    expected = "LockNotAvailable" if where == "create" else "QueryCanceled"
    assert outcome[1] == {"guardrail": "action_storage_failed", "observed": [expected]}
    assert "010-1234" not in str(outcome)
