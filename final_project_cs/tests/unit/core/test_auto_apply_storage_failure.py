"""결과 반영(C 단계) 중 저장소 쓰기 실패 — 일반 500 이 아니라 명시적 escalated 로 닫는다(수용 F03, 2026-10-26 묶음 L).

★DB 없이 `_apply_auto_proposals` 의 경계만 본다. 실제 savepoint 롤백 · Case 전이 · 바깥함 0건은
  `tests/integration/controller/test_auto_apply_proposals.py` 의 DB 시험이 본다.
"""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from app.application.controller import Controller
from app.core.actions import ActionHandlers
from app.core.case_lifecycle.events import EventType
from app.core.contracts import ActionProposal
from app.core.registry import TeamRegistry

PRIVATE = "CONTROLLED_PRIVATE_SQL_DETAIL tenant=x params=(010-1234-5678)"


class _Conn:
    def transaction(self):
        return nullcontext()


class _Handler:
    action_type = "demo.apply"
    auto_apply = True

    def __init__(self, error):
        self.error, self.calls = error, 0

    def subject(self, arguments):
        return str(arguments["target"])

    def apply(self, conn, *, tenant_id, customer_id, case_id, arguments):
        self.calls += 1
        raise self.error


def _controller(handler):
    repository = SimpleNamespace(find_action_request=lambda conn, **kw: None,
                                 get_case=lambda conn, **kw: None)
    return Controller(TeamRegistry([]), connection_factory=lambda: None, repository=repository,
                      policy_search=lambda *a, **k: [], action_handlers=ActionHandlers([handler]))


def _proposal():
    return ActionProposal(action_type="demo.apply", arguments={"target": "thing-1"},
                          idempotency_key="team-" + uuid4().hex, approval_required=False, risk_level="low")


def _case():
    return {"case_id": uuid4(), "tenant_id": "unit-storage", "customer_id": uuid4(), "state_json": {}}


@pytest.mark.parametrize("error", [psycopg.OperationalError(PRIVATE), psycopg.errors.LockNotAvailable(PRIVATE)])
def test_a_storage_write_failure_while_applying_escalates_explicitly_without_private_text(error):
    handler = _Handler(error)
    outcome = _controller(handler)._apply_auto_proposals(_Conn(), _case(), [_proposal()])
    assert handler.calls == 1
    assert isinstance(outcome, tuple), "저장 실패가 예외(→ HTTP 500)로 새면 안 된다"
    event, payload, outbox = outcome
    assert event is EventType.GUARDRAIL_ESCALATED
    assert payload == {"guardrail": "action_storage_failed", "observed": [type(error).__name__]}
    assert outbox == []                                 # 반영 실패면 안내도 내보내지 않는다
    assert "010" not in str(payload) and "CONTROLLED_PRIVATE" not in str(payload)


@pytest.mark.parametrize("error", [psycopg.IntegrityError("dup"), psycopg.ProgrammingError("bad sql"),
                                   RuntimeError("bug")])
def test_code_defects_while_applying_are_not_relabelled_as_storage_failures(error):
    # ★저장소 운영 실패(OperationalError 계열)만 명시 실패로 닫는다 — 코드 결함은 그대로 시끄럽게 올라간다(무음 폴백 금지)
    with pytest.raises(type(error)):
        _controller(_Handler(error))._apply_auto_proposals(_Conn(), _case(), [_proposal()])
