"""중립 연결로 분리해도 시험 입력·추출 기간의 기존 의미를 보존한다."""
from datetime import UTC, datetime, timedelta
from itertools import combinations
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.customer import service_improvement as improvement
from app.domains.travel_ops.components.watch import simulation
from app.domains.travel_ops.ports.data_sources import simulation_hook
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck


@pytest.mark.parametrize("selected", [choice for n in range(7) for choice in combinations(simulation.CATEGORIES, n)])
def test_registered_simulation_keeps_all_64_combinations_and_full_safety_records(monkeypatch, selected):
    calls, records = [], []
    current = {"categories": list(selected), "started_at": datetime.now(UTC).isoformat(), "run_id": "test-run"}
    provider = SimpleNamespace(resolve=lambda place: current if selected else None, inputs=simulation.inputs,
                               record_result=lambda state, report, **kw: records.append((report, kw["safety_only"])))
    monkeypatch.setattr(simulation_hook, "_provider", None)
    simulation_hook.register(provider)
    checker = DisruptionCheck(SimpleNamespace())
    for method, category in [("_forecast", "forecast"), ("_warning", "weather_warning"),
                             ("_disaster", "disaster_msg"), ("_traffic", "traffic_control"),
                             ("_air", "air_quality"), ("_earthquake", "earthquake")]:
        def clear(*args, category=category):
            calls.append(category)
            return {"category": category, "status": "ok"}
        monkeypatch.setattr(checker, method, clear)
    place = {"place_id": "seoul-test", "weather_sensitive": True}
    report = checker.check(place=place, starts_at=datetime.now(UTC))
    assert {c["category"] for c in report["disruptions"] + report["advisories"]} == set(selected)
    assert set(calls) == set(simulation.CATEGORIES) - set(selected)
    assert bool(records) == bool(selected)
    calls.clear()
    records.clear()
    safety = checker.check_safety(place=place, starts_at=datetime.now(UTC))
    assert {c["category"] for c in safety["checks"]} == {"disaster_msg", "earthquake"}
    if selected:
        assert [safety_only for _, safety_only in records] == [False, True]
        assert len(records[0][0]["checks"]) == 6
    else:
        assert set(calls) == {"disaster_msg", "earthquake"} and not records


def test_unregistered_source_is_absent_and_incomplete_registration_is_rejected(monkeypatch):
    monkeypatch.setattr(simulation_hook, "_provider", None)
    assert simulation_hook.resolve({}) is None
    with pytest.raises(TypeError):
        simulation_hook.register(SimpleNamespace(resolve=lambda place: None))
    with pytest.raises(RuntimeError, match="not registered"):
        simulation_hook.inputs({}, {})
    with pytest.raises(RuntimeError, match="not registered"):
        simulation_hook.record_result({}, {}, safety_only=False)


@pytest.mark.parametrize("adjusted,member_days,expected_hours", [(12, 365, 12), (None, 365, 168), (168, 2, 48)])
def test_improvement_uses_operator_slot_default_and_shorter_member_retention(monkeypatch, adjusted, member_days, expected_hours):
    seen = []
    now = datetime.now(UTC)
    conn = SimpleNamespace(execute=lambda query, params: seen.append((query, params)) or SimpleNamespace(fetchall=lambda: []))
    monkeypatch.setattr(improvement, "operator_setting", lambda tenant, name: adjusted)
    monkeypatch.setattr(improvement, "get_guardrails", lambda: SimpleNamespace(get=lambda name: 168))
    monkeypatch.setattr(improvement.retention, "effective", lambda conn, tenant: {"member_idle_days": member_days})
    assert improvement._features(conn, "travel-test", "current-terms", now) == []
    query, params = seen[0]
    assert params == ("travel-test", now - timedelta(hours=expected_hours), "current-terms", "travel-test")
    assert "cc.agreed AND cc.terms_version=%s" in query
    assert "DISTINCT ON (t.customer_id)" in query
