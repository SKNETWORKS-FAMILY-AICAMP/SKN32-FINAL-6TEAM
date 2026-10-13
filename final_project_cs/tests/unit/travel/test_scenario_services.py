"""대본 계산의 입력 고정과 팀 관문을 검증한다. 이동 정확도 시험이 아니다."""
from datetime import UTC, datetime, timedelta

import pytest

from app.core.service_bindings import bind_services
from app.core.team_availability import TeamUnavailable
from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.scenarios.case_engine import CaseEngine
from app.domains.travel_ops.scenarios.replay_services import replay_leg_services


def seed():
    return {"places": [{"key": "a", "name": "출발", "lat": 37.5, "lon": 127.0},
                       {"key": "b", "name": "도착", "lat": 37.55, "lon": 127.0}],
            "items": [{"seq": 1, "place": "a"}, {"seq": 2, "route": "ab"}, {"seq": 3, "place": "b"}],
            "routes": {"ab": {"planned": "r", "options": [{"id": "r", "eta_min": 17, "uses": ["대본 노선"]}]}}}


def test_replay_uses_recorded_duration_and_does_not_share_mutable_route_data():
    data = seed()
    services = replay_leg_services(data)
    planner = services[("legs", "leg_planner")](2, {})
    data["routes"]["ab"]["options"][0]["eta_min"] = 999
    arrive = datetime(2026, 10, 11, 12, tzinfo=UTC)
    a, b = seed()["places"]
    got, why = planner(a, b, arrive)
    assert why is None and got["eta_min"] == 17
    assert got["starts_at"] == arrive - timedelta(minutes=17)
    got["route"]["options"][0]["uses"].clear()
    again, _ = planner(a, b, arrive)
    assert again["route"]["options"][0]["uses"] == ["대본 노선"]


def test_replay_does_not_invent_a_route_outside_the_recorded_area():
    a, b = seed()["places"]
    planner = replay_leg_services(seed())[("legs", "leg_planner")](2, {})
    got, why = planner({**a, "lat": 38.0}, b, datetime.now(UTC))
    assert got is None and why["code"] == "scenario_route_not_recorded"


@pytest.mark.parametrize("state", ["disabled", "not_installed"])
def test_explicit_scenario_provider_cannot_activate_a_missing_team(monkeypatch, state):
    from app.core import project_config

    config = project_config.load_project_config().model_copy(deep=True)
    if state == "disabled":
        next(t for t in config.teams if t.team_id == "mobility").active = False
    else:
        config.teams = [t for t in config.teams if t.team_id != "mobility"]
    monkeypatch.setattr(project_config, "load_project_config", lambda: config)
    engine = CaseEngine(tenant_id="synthetic_test", check=lambda **kwargs: {}, route_events=None,
                        classifier=None, report_extractor=None, clock=lambda: datetime.now(UTC),
                        service_overrides=replay_leg_services(seed()))
    with bind_services(engine.controller.service_bindings), pytest.raises(TeamUnavailable) as exc:
        legs.leg_planner(2, {})
    assert exc.value.reason == state
