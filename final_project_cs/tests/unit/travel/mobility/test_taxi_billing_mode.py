from datetime import datetime
from types import SimpleNamespace
import json
from pathlib import Path

from app.modules.travel_ops.mobility.engine.car import CarService, taxi_fare, taxi_planning_fare


def test_medium_taxi_counts_distance_also_on_slow_edges():
    root = Path(__file__).resolve().parents[4]
    rules = json.loads((root / "app/modules/travel_ops/mobility/engine/rules/rules_v0.3.json").read_text(encoding="utf-8"))
    result = dict(distance_m=5000, slow_m=1000, slow_s=300, coverage_pct={"class": 0, "default": 0},
                  topis_time_s=600, gh_time_s=600, depart="14:00", arrive="14:10", day_type="평일",
                  hour_start=14, coverage_m={}, n_edges=1, links=[], n_links=0)
    service = CarService(SimpleNamespace(compute=lambda *a, **k: result),
                         SimpleNamespace(route=lambda *a: {}), rules)
    medium = service.leg((127, 37.5), (127.01, 37.5), datetime(2026, 10, 8, 14), taxi=True)
    large = service.leg((127, 37.5), (127.01, 37.5), datetime(2026, 10, 8, 14), taxi=True, kind="대형_모범")
    assert medium["meter_won"] == taxi_fare(service.F, "중형", 5000, 300, "14:00") == 8400
    assert large["meter_won"] == taxi_fare(service.F, "대형_모범", 4000, 300, "14:00")
    assert "예상 요금" in medium["fare_basis"]
    assert medium["fare_won"] == 11600 and medium["planning_reserve_won"] == 3200
    assert large["planning_reserve_rate"] == 0.10  # 중형 자료로 다른 차종을 보정하지 않는다.


def test_budget_reserve_is_separate_from_meter_and_toll():
    policy = dict(reserve_rate=0.37, minimum_reserve_won=1000, round_unit_won=100)
    assert taxi_planning_fare(4800, **policy) == (6600, 1800)
    assert taxi_planning_fare(12300, 2000, **policy) == (18900, 4600)
    assert taxi_planning_fare(10000, **policy) == (13700, 3700)  # 부동소수점 오차로 100원 더 올리지 않는다.
    minimum = dict(reserve_rate=0.01, minimum_reserve_won=1000, round_unit_won=100)
    assert taxi_planning_fare(4800, **minimum) == (5800, 1000)
