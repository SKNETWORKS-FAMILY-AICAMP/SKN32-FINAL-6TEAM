"""적용기의 실제 결과 안내가 계산 문장을 교체하는 공통 계약 시험."""
from contextlib import nullcontext
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.controller import Controller
from app.core.actions import ActionHandlers, AppliedAction
from app.core.case_lifecycle.events import EventType
from app.core.contracts import ActionProposal, Evidence, NextAction, TeamResult
from app.core.registry import TeamRegistry


class LocalActionRepository:
    def __init__(self):
        self.action = None

    def find_action_request(self, conn, **kwargs):
        return self.action

    def create_action_request(self, conn, **kwargs):
        self.action = {"action_id": uuid4(), "case_id": kwargs["case_id"],
                       "status": kwargs["status"], "provider_ref": kwargs["provider_ref"]}
        return self.action["action_id"]


class DeferredTravelHandler:
    action_type = "travel.change"
    auto_apply = True

    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def subject(self, arguments):
        return arguments["trip_id"]

    def apply(self, conn, **kwargs):
        self.calls += 1
        return AppliedAction(result_ref="proposal:travel-change", summary={"status": "asked"}, answer=self.answer)


@pytest.mark.parametrize("answer", ["일정을 바꾸기 전에 추가 확인이 필요합니다.", None])
def test_applied_answer_is_the_customer_answer_even_when_action_is_replayed(answer):
    repository = LocalActionRepository()
    handler = DeferredTravelHandler(answer)
    controller = Controller(TeamRegistry(), repository=repository, action_handlers=ActionHandlers([handler]))
    case = {"case_id": uuid4(), "tenant_id": "travel-answer-contract", "customer_id": uuid4(), "state_json": {}}
    result = TeamResult(task_id=uuid4(), run_id=uuid4(), team_id="dining", outcome="completed",
                        answer="일정을 바꿨습니다.", confidence=1, next_action=NextAction.RESPOND,
                        evidence=[Evidence(evidence_id="travel:change", source_type="db", source_id="trip",
                                           claim="고객 요청", value={"ok": True}, confidence=1, observed_at=datetime.now(UTC))],
                        action_proposals=[ActionProposal(action_type=handler.action_type,
                                            arguments={"trip_id": "trip-contract"}, approval_required=False,
                                            risk_level="low", idempotency_key="team-advisory")])
    conn = type("TransactionOnlyConnection", (), {"transaction": staticmethod(nullcontext)})()
    for attempt in range(2):
        event, payload, outbox = controller._event_for_result(conn, case, result)
        assert event is EventType.COMPLETED and outbox == []
        assert payload["state_patch"]["answer"] == (answer or result.answer)
        record = payload["state_patch"]["applied_actions"][0]
        assert record["summary"] == {"status": "asked"}
        if attempt:
            assert record["replayed"] is True
        case["state_json"] = payload["state_patch"]
    assert handler.calls == 1
