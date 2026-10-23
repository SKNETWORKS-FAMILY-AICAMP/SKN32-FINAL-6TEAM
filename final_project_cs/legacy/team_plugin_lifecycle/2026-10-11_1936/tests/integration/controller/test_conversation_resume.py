"""여행 고객의 질문 대기·답변 재개를 실제 로컬 DB에서 검증한다."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.controller import Controller, ControllerError
from app.core.contracts import ContextPack, Evidence, NextAction, StateConflict, TeamManifest, TeamResult
from app.core.registry import TeamRegistry
from app.core.transition import transition_case
from app.core.case_lifecycle.events import EventType
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.presentation.api.cases import build_router
from app.presentation.security import Principal


class TravelInputTeam:
    manifest = TeamManifest(
        team_id="travel_input_test", display_name="여행 추가 답변 시험",
        contract_name="a_cop.team_task", supported_contract_versions=["1.0"],
        capabilities=["dining.delay"], accepted_case_types=["dining"],
        required_context=["case_state"], allowed_tools=[], knowledge_scope=["dining"],
        implementation_revision="resume-regression",
    )

    def __init__(self):
        self.tasks = []

    async def execute(self, task):
        self.tasks.append(task)
        evidence = [Evidence(evidence_id="travel:question", source_type="db", source_id=str(task.case_id),
                             claim="고객의 식당 지연 요청", value={"subject": "식당에 늦어요"},
                             observed_at=datetime.now(UTC), confidence=1)]
        if not task.context.current_state.get("customer_input") or task.context.current_state["customer_input"] == "아직 몰라요":
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
                              outcome="waiting", confidence=1, answer="몇 분쯤 늦으시나요?", evidence=evidence,
                              decisions=[{"reason": "missing_delay_minutes"}],
                              next_action=NextAction.WAIT_FOR_INPUT, wait_reason="customer_input",
                              required_input_schema={"type": "object", "required": ["minutes"]})
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
                          outcome="completed", confidence=1, answer="추가 답변을 받아 일정을 확인했습니다.",
                          evidence=evidence, decisions=[{"reason": "customer_replied"}], next_action=NextAction.RESPOND)


class TravelBroker:
    def build(self, inputs):
        return ContextPack(pack_id=uuid4(), case_id=inputs.case_id, tenant_id=inputs.tenant_id,
                           team_id=inputs.team_id, knowledge_scope=inputs.knowledge_scope,
                           current_state=inputs.current_state, estimated_input_tokens=0)


@pytest.fixture
def travel():
    tenant = "resume_travel_" + uuid4().hex
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,%s)", (tenant, "여행 재개 시험"))
                cur.execute("INSERT INTO customers(tenant_id,external_id) VALUES(%s,%s) RETURNING customer_id", (tenant, uuid4().hex))
                customer = cur.fetchone()[0]
            case_id = repository.create_case(conn, tenant_id=tenant, customer_id=customer, subject="식당에 늦어요")
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=0,
                            event_type=EventType.CREATED, payload={"channel": "web", "message": "식당에 늦어요"}, actor_type="test")
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=1,
                            event_type=EventType.CLASSIFIED,
                            payload={"intent": "incident_report", "issue_code": "dining_delay", "sentiment": "neutral"}, actor_type="test")
        conn.commit()
    team = TravelInputTeam()
    controller = Controller(TeamRegistry([team]), context_broker=TravelBroker())
    first = asyncio.run(controller.run_case(tenant_id=tenant, case_id=case_id))
    try:
        yield controller, team, tenant, customer, case_id, first
    finally:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    for table in ("team_tasks", "llm_calls"):
                        cur.execute(f"DELETE FROM {table} WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
                    for table in ("agent_runs", "action_requests", "case_events", "outbox", "customer_cases", "customers", "tenants"):
                        cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))


def saved(tenant, case_id):
    with get_connection() as conn:
        return repository.get_case(conn, tenant_id=tenant, case_id=case_id)


def resume(travel, **kw):
    controller, _, tenant, _, case_id, first = travel
    return asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=first["resume_token"],
                                         event_id=kw.pop("event_id", "reply-1"), message=kw.pop("message", "30분이요"), **kw))


def test_wait_question_and_evidence_are_durable_without_raw_token(travel):
    _, _, tenant, _, case_id, first = travel
    state = saved(tenant, case_id)["state_json"]
    assert first["status"] == "waiting_input"
    assert state["answer"] == "몇 분쯤 늦으시나요?"
    assert state["required_input_schema"]["required"] == ["minutes"]
    assert state["evidence"][0]["evidence_id"] == "travel:question"
    assert state["decisions"] == [{"reason": "missing_delay_minutes"}]
    assert first["resume_token"] not in str(state)


def test_latest_reply_original_request_and_masked_history_reach_team(travel):
    _, team, tenant, _, case_id, first = travel
    outcome = resume(travel, message="30분이요. 연락처 010-1234-5678", expected_version=first["version"])
    task = team.tasks[-1]
    assert outcome["status"] == "resolved"
    assert task.resume is True and task.resume_node == "validate_input"
    assert "식당에 늦어요" in task.input_text and "30분이요" in task.input_text
    assert task.context.current_state["customer_input"] == "30분이요. 연락처 010-****-5678"
    assert task.context.current_state["customer_input_history"] == ["30분이요. 연락처 010-****-5678"]
    assert task.context.current_state["original_request"] == "식당에 늦어요"
    with get_connection() as conn:
        events = repository.get_case_events(conn, tenant_id=tenant, case_id=case_id)
    assert "010-1234-5678" not in str(events) + str(saved(tenant, case_id))
    assert outcome["resume_token"] is None


def test_blank_input_does_not_consume_token(travel):
    with pytest.raises(ValueError, match="blank"):
        resume(travel, message="  ")
    assert resume(travel)["status"] == "resolved"


def test_wrong_token_does_not_destroy_waiting_case(travel):
    controller, team, tenant, _, case_id, first = travel
    with pytest.raises(ControllerError, match="invalid resume token"):
        asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token="not-customer-token", message="30분"))
    assert saved(tenant, case_id)["version"] == first["version"]
    assert saved(tenant, case_id)["status"] == "waiting_input"
    assert len(team.tasks) == 1
    assert resume(travel)["status"] == "resolved"


def test_expected_version_conflict_keeps_reply_and_token_unconsumed(travel):
    _, _, tenant, _, case_id, first = travel
    with pytest.raises(StateConflict):
        resume(travel, expected_version=first["version"] - 1)
    assert "customer_input" not in saved(tenant, case_id)["state_json"]
    assert resume(travel, expected_version=first["version"])["status"] == "resolved"


def test_same_request_same_reply_executes_once_different_reply_conflicts(travel):
    _, team, _, _, _, first = travel
    resume(travel, expected_version=first["version"])
    assert resume(travel, expected_version=first["version"])["idempotent"] is True
    with pytest.raises(StateConflict, match="different message"):
        resume(travel, message="60분이요")
    assert len(team.tasks) == 2


def test_concurrent_duplicate_replies_have_single_team_execution(travel):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: resume(travel), range(2)))
    assert sum(bool(r.get("idempotent")) for r in results) == 1
    assert len(travel[1].tasks) == 2


def test_internal_web_resume_checks_customer_and_is_idempotent(travel):
    controller, team, tenant, customer, case_id, _ = travel
    with pytest.raises(ControllerError, match="does not own"):
        asyncio.run(controller.resume_customer_input(tenant_id=tenant, case_id=case_id,
                        customer_id=uuid4(), message="30분", event_id="web-1"))
    kw = dict(tenant_id=tenant, case_id=case_id, customer_id=customer, message="30분", event_id="web-1")
    assert asyncio.run(controller.resume_customer_input(**kw))["status"] == "resolved"
    assert asyncio.run(controller.resume_customer_input(**kw))["idempotent"] is True
    assert len(team.tasks) == 2


def test_repeated_questions_preserve_history_and_old_request_replay(travel):
    controller, team, tenant, customer, case_id, _ = travel
    again = resume(travel, message="아직 몰라요")
    assert again["status"] == "waiting_input"
    assert again["resume_token"] != travel[-1]["resume_token"]
    assert resume(travel, message="아직 몰라요")["idempotent"] is True
    asyncio.run(controller.resume_customer_input(tenant_id=tenant, case_id=case_id, customer_id=customer,
                                                message="30분이요", event_id="web-2"))
    assert team.tasks[-1].context.current_state["customer_input_history"] == ["아직 몰라요", "30분이요"]
    assert resume(travel, message="아직 몰라요")["idempotent"] is True


def test_valid_expired_token_escalates_but_wrong_token_cannot_expire_it(travel):
    controller, _, tenant, _, case_id, first = travel
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE customer_cases SET state_json=jsonb_set(state_json,'{resume_token_expires_at}',to_jsonb(%s::text)) WHERE tenant_id=%s AND case_id=%s",
                        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), tenant, case_id))
    with pytest.raises(ControllerError, match="expired"):
        resume(travel)
    assert saved(tenant, case_id)["status"] == "escalated"


def test_callback_compatibility_without_customer_message(travel):
    controller, team, tenant, _, case_id, first = travel
    result = asyncio.run(controller.resume(tenant_id=tenant, case_id=case_id, token=first["resume_token"], event_id="callback"))
    assert result["status"] == "waiting_input"
    assert team.tasks[-1].resume is True
    assert "customer_input" not in team.tasks[-1].context.current_state


@pytest.mark.parametrize("with_token", [True, False])
def test_message_endpoint_forwards_body_and_case_version(travel, with_token):
    controller, team, tenant, _, case_id, first = travel
    application = FastAPI()
    application.include_router(build_router(controller=controller))
    # 라우터가 만든 의존 함수 자체를 찾아 인증 주체만 시험용으로 주입한다.
    route = next(r for r in application.routes if getattr(r, "path", "") == "/v1/cases/{case_id}/messages")
    principal_dependency = route.dependant.dependencies[0].call
    application.dependency_overrides[principal_dependency] = lambda: Principal(tenant_id=tenant, key_id="resume-test", scopes=frozenset({"case:write"}))
    with TestClient(application) as client:
        body = {"request_id": "api-reply", "message": "30분이요", "expected_version": first["version"]}
        if with_token:
            body["token"] = first["resume_token"]
        response = client.post(f"/v1/cases/{case_id}/messages", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"
    assert response.json()["answer"]
    assert team.tasks[-1].context.current_state["customer_input"] == "30분이요"


def test_customer_choice_can_reroute_same_case_before_team_execution(travel):
    controller, dining, tenant, _, case_id, first = travel
    class SelectedActivityTeam(TravelInputTeam):
        @staticmethod
        def select_capability(intent, input_text, state=None):
            return "activity.change" if input_text == "활동 일정이요" else "activity.verify"

    activity = SelectedActivityTeam()
    activity.manifest = activity.manifest.model_copy(update={
        "team_id": "activity_input_test", "capabilities": ["activity.verify", "activity.change"],
        "accepted_case_types": ["activity"], "knowledge_scope": ["activity"],
    })
    controller.registry.register(activity)

    def route(case, message):
        assert case["status"] == "resuming"
        assert case["state_json"]["customer_input"] == message == "활동 일정이요"
        return activity.manifest.team_id

    result = resume(travel, message="활동 일정이요", expected_version=first["version"], resume_route=route)
    assert result["status"] == "resolved"
    assert len(dining.tasks) == 1 and len(activity.tasks) == 1
    assert activity.tasks[0].team_id == "activity_input_test"
    assert activity.tasks[0].capability == "activity.change"
    assert activity.tasks[0].resume is True
    assert saved(tenant, case_id)["owner_team_id"] == "activity_input_test"
    with get_connection() as conn:
        events = repository.get_case_events(conn, tenant_id=tenant, case_id=case_id)
    assert [event["event_type"] for event in events][-4:] == ["valid_input", "routed", "resumed", "completed"]


def test_failed_reroute_rolls_back_answer_and_token_consumption(travel):
    from app.core.registry import RegistryError

    with pytest.raises(RegistryError):
        resume(travel, resume_route=lambda case, message: "unregistered-travel-team")
    _, _, tenant, _, case_id, first = travel
    assert saved(tenant, case_id)["status"] == "waiting_input"
    assert saved(tenant, case_id)["version"] == first["version"]
    assert "customer_input" not in saved(tenant, case_id)["state_json"]
    assert resume(travel)["status"] == "resolved"


@pytest.mark.parametrize("execution_answer", ["바꾸기 전에 추가 확인이 필요합니다.", None])
def test_actual_apply_answer_overrides_calculated_answer_and_survives_replay(travel, execution_answer):
    from app.core.actions import ActionHandlers, AppliedAction
    from app.core.contracts import ActionProposal

    controller, team, tenant, _, case_id, _ = travel

    class DeferredTravelChange:
        action_type = "travel.defer_change"
        auto_apply = True
        calls = 0

        def subject(self, arguments):
            return arguments["target"]

        def apply(self, conn, **kwargs):
            self.calls += 1
            return AppliedAction(result_ref="travel:pending-proposal", summary={"status": "asked"},
                                 answer=execution_answer)

    handler = DeferredTravelChange()
    controller.action_handlers = ActionHandlers([handler])
    produced = []

    async def propose_change(task):
        team.tasks.append(task)
        result = TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
                            outcome="completed", confidence=1, answer="일정을 바꿨습니다.",
                            evidence=[Evidence(evidence_id="travel:change", source_type="db",
                                               source_id=str(case_id), claim="고객 변경 요청", value={"ok": True},
                                               observed_at=datetime.now(UTC), confidence=1)],
                            action_proposals=[ActionProposal(action_type=handler.action_type,
                                                arguments={"target": str(case_id)}, idempotency_key="untrusted-team-key",
                                                approval_required=False, risk_level="low")],
                            next_action=NextAction.RESPOND)
        produced.append(result)
        return result

    team.execute = propose_change
    assert resume(travel)["status"] == "resolved"
    case = saved(tenant, case_id)
    expected_answer = execution_answer or "일정을 바꿨습니다."
    assert case["state_json"]["answer"] == expected_answer
    assert case["state_json"]["applied_actions"][0]["summary"] == {"status": "asked"}
    with get_connection() as conn:
        event, payload, outbox = controller._event_for_result(conn, case, produced[0])
    assert event is EventType.COMPLETED
    assert payload["state_patch"]["answer"] == expected_answer
    assert payload["state_patch"]["applied_actions"][0]["replayed"] is True
    assert outbox == [] and handler.calls == 1


@pytest.mark.parametrize("different_owner", [False, True])
def test_resume_route_persists_typed_request_for_same_or_different_owner(travel, different_owner):
    controller, dining, tenant, _, case_id, _ = travel
    owner = dining
    if different_owner:
        owner = TravelInputTeam()
        owner.manifest = owner.manifest.model_copy(update={
            "team_id": "activity_input_test", "capabilities": ["activity.change"],
            "accepted_case_types": ["activity"], "knowledge_scope": ["activity"],
        })
        controller.registry.register(owner)
    trip_id, part_id = str(uuid4()), str(uuid4())
    request = {"type": "change", "part_id": part_id}
    patch = {"subject_ref": {"kind": "trip", "id": trip_id, "part_id": part_id, "request": request},
             "required_input_schema": {"x-conversation": {"request": request, "part_id": part_id}}}

    def route(case, message):
        assert case["status"] == "resuming"
        assert message == "선택한 일정을 바꿔주세요"
        return {"owner_team_id": owner.manifest.team_id, "state_patch": patch}

    outcome = resume(travel, message="선택한 일정을 바꿔주세요", resume_route=route)
    assert outcome["status"] == "resolved"
    task = owner.tasks[-1]
    assert task.context.current_state["subject_ref"] == patch["subject_ref"]
    assert task.context.current_state["required_input_schema"] == patch["required_input_schema"]
    assert task.context.current_state["customer_input_history"] == ["선택한 일정을 바꿔주세요"]
    with get_connection() as conn:
        events = repository.get_case_events(conn, tenant_id=tenant, case_id=case_id)
    routed = [event for event in events if event["event_type"] == "routed"][-1]
    assert routed["payload_json"]["state_patch"] == patch
    assert saved(tenant, case_id)["owner_team_id"] == owner.manifest.team_id
