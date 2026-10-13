"""감시가 실행 중 만난 필수 Team 부재에서 같은 Case를 복구한다."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.controller import Controller
from app.application.case_service import CaseService
from app.core.contracts import ContextPack, Evidence, NextAction, TeamResult
from app.core.case_lifecycle.events import EventType
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services, current_bindings, read_binding
from app.core.transition import transition_case
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.mobility import MobilityTeam
from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection

from .test_trip_api import _at, _create, api  # noqa: F401


class Broker:
    def build(self, inputs):
        return ContextPack(pack_id=uuid4(), case_id=inputs.case_id, tenant_id=inputs.tenant_id,
                           team_id=inputs.team_id, knowledge_scope=inputs.knowledge_scope,
                           current_state=inputs.current_state, estimated_input_tokens=0)


class DependentActivity:
    manifest = ActivityTeam.manifest.model_copy(deep=True)

    def __init__(self):
        self.calls = []

    async def execute(self, task):
        assert current_bindings() is not None
        self.calls.append(task.case_id)
        # 실제 공통 필수 계산 관문을 사용한다. 팀 실행이나 DB 실패를 흉내 내지 않는다.
        read_binding("legs", "walk_limit_m", required_team="mobility")()
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id,
                          outcome="completed", confidence=1, answer="서울 활동 점검을 마쳤습니다.",
                          evidence=[Evidence(evidence_id="watch:test", source_type="db",
                              source_id=str(task.case_id), claim="시험 활동 점검 완료", value=True,
                              observed_at=datetime.now(UTC), confidence=1)],
                          next_action=NextAction.RESPOND)


def _controller(team, *, enabled):
    registry = TeamRegistry([team])
    registry.declare_case_types("mobility", ["mobility"])
    if enabled:
        registry.register(type("MobilityProvider", (), {"manifest": MobilityTeam.manifest})())
    else:
        registry.declare_unavailable("mobility", "disabled")
    controller = Controller(registry, context_broker=Broker(), policy_search=lambda *a, **k: [])
    controller.composition_revision = "watch-on" if enabled else "watch-off"
    controller.service_bindings = BindingTable({("legs", "walk_limit_m"): lambda: 1200, ("watch_planners", "activity"): lambda *a: None}, registry,
                                               controller.composition_revision)
    return controller


def _saved(api, case_id):
    with get_connection() as conn, conn.cursor() as cur:
        case = repository.get_case(conn, tenant_id=api["tenant"], case_id=UUID(str(case_id)))
        cur.execute("SELECT status FROM agent_runs WHERE tenant_id=%s AND case_id=%s ORDER BY started_at",
                    (api["tenant"], case_id))
        return case, [row[0] for row in cur.fetchall()]


@pytest.mark.parametrize("batch", [False, True])
def test_reactivated_dependency_runs_the_same_watch_cases_without_reopening_or_success_fallback(api, monkeypatch, batch):
    # 이 독립 회귀는 예보 알림의 별도 스키마를 사용하지 않는다.
    monkeypatch.setattr("app.domains.travel_ops.components.watch.trip_watch_cases.forecast_attention", lambda *a, **k: None, raising=False)
    from app.core import settings
    actual = settings.get_guardrails()
    class Guard:
        def get(self, key, *args):
            override = {"travel.watch.batch_enabled": batch, "travel.watch.retry_max": 0,
                        "travel.watch.retry_cooldown_seconds": 3600}
            return override[key] if key in override else actual.get(key, *args)
    monkeypatch.setattr(settings, "get_guardrails", lambda: Guard())
    trip_id = UUID(_create(api)["trip_id"])
    team = DependentActivity()
    controller = _controller(team, enabled=False)

    def check(*, place, starts_at):
        return ({"verdict": "disrupted", "disruptions": [{"category": "traffic_control", "kind": "road_closed"}]}
                if place.get("kind") == "activity" else {"verdict": "clear", "disruptions": []})

    watcher = TripWatchCaseOpener(store=api["store"], check=check,
        connection_factory=get_connection, repository=repository, clock=lambda: _at("09:00"),
        run_case=lambda **kwargs: asyncio.run(controller.run_case(**kwargs)))

    def tick():
        with bind_services(controller.service_bindings):
            return watcher.tick(lookahead=timedelta(hours=14))

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s", (api["tenant"],))
        baseline_actions = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice'", (api["tenant"],))
        baseline_notices = cur.fetchone()[0]
    first = tick()
    assert first.opened and len([r for r in first.unavailable if r.get("case_id")]) == len(first.opened) and not first.ran
    case_ids = {row["case_id"] for row in first.opened}
    for case_id in case_ids:
        case, runs = _saved(api, case_id)
        assert str(case["status"]) == "running" and runs == ["failed"]
    blocked_calls = len(team.calls)
    still_off = tick()
    assert not still_off.opened and not still_off.ran and len(team.calls) == blocked_calls * 2
    # 동적 교차 의존성은 Team 실행 중에야 드러난다. 실패 기록은 같은 Case에 보존된다.
    for case_id in case_ids:
        assert _saved(api, case_id)[1] == ["failed", "failed"]
    controller = _controller(team, enabled=True)
    controller.registry.declare_unavailable("activity", "disabled")
    owner_off = tick()
    assert not owner_off.opened and not owner_off.ran and len(team.calls) == blocked_calls * 2
    for case_id in case_ids:
        assert _saved(api, case_id)[1] == ["failed", "failed"]

    controller = _controller(team, enabled=True)
    restored = tick()
    assert not restored.opened
    assert {row["case_id"] for row in restored.ran} == case_ids
    for case_id in case_ids:
        case, runs = _saved(api, case_id)
        assert str(case["status"]) == "resolved" and runs == ["failed", "failed", "succeeded"]
    assert not tick().ran
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == baseline_actions + len(case_ids)
        cur.execute("SELECT action_type FROM action_requests WHERE tenant_id=%s", (api["tenant"],))
        assert {row[0] for row in cur.fetchall()} == {"case.create"}
        cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice'", (api["tenant"],))
        assert cur.fetchone()[0] == baseline_notices  # 실패/재실행으로 변경 안내를 추가하지 않는다.
    with get_connection() as conn:
        assert api["store"].latest(conn, trip_id)[0]["version"] == 1


def test_active_successful_and_unstarted_running_cases_are_not_recovered(api):
    """실제 DB 조회 조건이 활성 실행·성공 이력·실행 이력 없음을 구별한다."""
    tenant, item_id = api["tenant"], uuid4()
    base_id = f"watch:{uuid4()}:{item_id}:test"
    service = CaseService()
    with get_connection() as conn, conn.transaction():
        case_id = repository.create_case(conn, tenant_id=tenant, customer_id=api["customer"], subject="서울 활동 점검")
        for version, event, payload in [
            (0, EventType.CREATED, {"channel": "system", "message": "서울 활동 점검", "state_patch": {"request_id": base_id}}),
            (1, EventType.CLASSIFIED, {"intent": "incident_report", "issue_code": "activity_other", "sentiment": "neutral"}),
            (2, EventType.ROUTED, {"owner_team_id": "activity", "capability": "activity.itinerary"}),
        ]:
            transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=version,
                            event_type=event, payload=payload, actor_type="test")
    watcher = TripWatchCaseOpener(store=api["store"], check=None, connection_factory=get_connection,
        repository=repository, clock=lambda: _at("09:00"), run_case=None)

    def attempt():
        with get_connection() as conn:
            return watcher._attempt(conn, base_id, item_id)

    assert attempt() == (None, str(case_id))  # 시작 이력이 없는 running은 복구 근거가 아니다.
    with get_connection() as conn, conn.transaction():
        run_id = service.start_run(conn, tenant_id=tenant, case_id=case_id)
        service.finish_run(conn, run_id, "failed")
    assert attempt() == (0, str(case_id))
    with get_connection() as conn, conn.transaction():
        active_id = service.start_run(conn, tenant_id=tenant, case_id=case_id)
    assert attempt() == (None, str(case_id))
    with get_connection() as conn, conn.transaction():
        service.finish_run(conn, active_id, "succeeded")
    assert attempt() == (None, str(case_id))  # 오래된 failed보다 최신 성공을 우선한다.
    with get_connection() as conn, conn.transaction():
        latest = repository.get_case(conn, tenant_id=tenant, case_id=case_id)
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=latest["version"],
            event_type=EventType.MISSING_INPUT, payload={"required_input_schema": {"required": ["minutes"]}}, actor_type="test")
        run_id = service.start_run(conn, tenant_id=tenant, case_id=case_id)
        service.finish_run(conn, run_id, "failed")
    assert attempt() == (None, str(case_id))  # 입력 대기는 failed 이력만으로 풀지 않는다.


def test_controller_timeout_is_escalated_and_not_a_running_recovery(api, monkeypatch):
    """Team 제한시간 종료는 이전 닫힌 업무 규칙을 유지한다."""
    from app.application.case_intake import open_case

    team = DependentActivity()

    async def time_out(task):
        raise asyncio.TimeoutError

    monkeypatch.setattr(team, "execute", time_out)
    controller = _controller(team, enabled=True)
    trip_id = UUID(_create(api)["trip_id"])
    with get_connection() as conn:
        opened = open_case(conn, repository=repository, tenant_id=api["tenant"], customer_id=api["customer"],
            request_id=f"watch:{trip_id}:timeout:test", message="서울 활동 점검", channel="system", actor_type="system", actor_id="trip_watch",
            labels={"intent": "incident_report", "issue_code": "activity_other", "sentiment": "neutral"})
    with bind_services(controller.service_bindings):
        outcome = asyncio.run(controller.run_case(tenant_id=api["tenant"], case_id=opened.case_id))
    assert outcome["status"] == "escalated"
    case, runs = _saved(api, opened.case_id)
    assert runs == ["failed"]
    watcher = TripWatchCaseOpener(store=api["store"], check=None, connection_factory=get_connection,
        repository=repository, clock=lambda: _at("09:00"), run_case=None)
    with get_connection() as conn:
        attempt, covered = watcher._attempt(conn, case["state_json"]["request_id"], uuid4())
    # 새 running 복구는 사용하지 않는다. 기존 cooldown 뒤 새 사건 재시도 정책은 별도다.
    assert attempt is None and covered == str(opened.case_id)
