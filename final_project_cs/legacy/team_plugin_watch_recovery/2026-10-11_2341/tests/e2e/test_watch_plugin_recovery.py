"""감시가 실행 중 만난 필수 Team 부재에서 같은 Case를 복구한다."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.application.controller import Controller
from app.core.contracts import ContextPack, Evidence, NextAction, TeamResult
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services, current_bindings, read_binding
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


def test_reactivated_dependency_runs_the_same_watch_cases_without_reopening_or_success_fallback(api, monkeypatch):
    # 이 독립 회귀는 예보 알림의 별도 스키마를 사용하지 않는다.
    monkeypatch.setattr("app.domains.travel_ops.components.watch.trip_watch_cases.forecast_attention", lambda *a, **k: None)
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

    first = tick()
    assert first.opened and len([r for r in first.unavailable if r.get("case_id")]) == len(first.opened) and not first.ran
    case_ids = {row["case_id"] for row in first.opened}
    for case_id in case_ids:
        case, runs = _saved(api, case_id)
        assert str(case["status"]) == "running" and runs == ["failed"]
    blocked_calls = len(team.calls)
    still_off = tick()
    assert not still_off.opened and not still_off.ran and len(team.calls) == blocked_calls

    controller = _controller(team, enabled=True)
    restored = tick()
    assert not restored.opened
    assert {row["case_id"] for row in restored.ran} == case_ids
    for case_id in case_ids:
        case, runs = _saved(api, case_id)
        assert str(case["status"]) == "resolved" and runs == ["failed", "succeeded"]
    assert not tick().ran
    with get_connection() as conn:
        assert api["store"].latest(conn, trip_id)[0]["version"] == 1
