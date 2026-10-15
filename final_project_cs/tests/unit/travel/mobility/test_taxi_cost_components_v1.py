"""실제 요금식의 예산 구성과 미포함 옵션료가 계획·출발 안내까지 보존된다.

합성 서울 여행 구간이며 개인 이용 기록·실제 결제·실시간 교통 시험이 아니다.
"""
import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch.trip_reminders import build_departure
from app.domains.travel_ops.instances.mobility.engine.car import CarService, taxi_fare_description
from app.domains.travel_ops.instances.mobility.engine.plan import Planner, taxi_label
from .test_departure_taxi_v1 import call, scene, NOW
from ..test_departure_observer_notice_v1 import NoEvents


ROOT = Path(__file__).resolve().parents[4]
RULES = json.loads((ROOT / "app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json").read_text(encoding="utf-8"))


def service():
    result = dict(distance_m=5000, slow_m=1000, slow_s=300,
                  coverage_pct={"class": 0, "default": 0},
                  topis_time_s=600, gh_time_s=600, depart="14:00", arrive="14:10",
                  day_type="평일", hour_start=14, coverage_m={}, n_edges=1, links=[], n_links=0)
    return CarService(SimpleNamespace(compute=lambda *a, **kw: deepcopy(result)),
                      SimpleNamespace(route=lambda *a: {}), RULES)


@pytest.mark.parametrize("airport", [False, True])
@pytest.mark.parametrize("kind", ["중형", "대형_모범"])
def test_calculated_cost_components_remain_separate_in_the_product_label(airport, kind):
    start = (126.4505, 37.4602) if airport else (127, 37.5)
    result = service().leg(start, (127.01, 37.5), datetime(2026, 10, 11, 14), taxi=True, kind=kind)
    before = deepcopy(result)
    label = taxi_label(result)
    assert result["fare_won"] == result["meter_won"] + result["planning_reserve_won"] + result["toll_won"]
    assert f"미터 추정 {result['meter_won']:,}원" in label
    assert f"예산 여유 {result['planning_reserve_won']:,}원" in label
    assert f"통행료 {result['toll_won']:,}원" in label
    assert "호출·옵션료 미포함" in label and "별도 확인" in label
    assert "실제 결제 상한 아님" in label
    assert "옵션료 0원" not in label
    assert result["fare_basis"] in label and result == before
    assert len(result["fare_basis"]) <= 100, "기존 car_leg 근거 문구 계약 상한"
    assert result["planning_reserve_rate"] == (0.37 if kind == "중형" else 0.10)


def test_partial_legacy_summary_does_not_invent_component_or_option_amounts():
    label = taxi_label({"distance_m": 5000, "fare_won": 12000, "grade": "추정"})
    assert "12,000원" in label and "구성 금액 미전달" in label
    assert "미터 추정" not in label and "통행료" not in label
    assert "호출·옵션료 미포함" in label and "옵션료 0원" not in label


def test_missing_fare_is_not_presented_as_free_or_an_all_in_budget():
    label = taxi_fare_description({})
    assert "계산 안 됨" in label and "별도 확인" in label
    assert "0원" not in label and "여유 포함" not in label


def test_planner_uses_the_calculated_components_without_changing_option_contract():
    planner = object.__new__(Planner)
    planner.v = SimpleNamespace(car=service())
    planner.modes = {"taxi"}
    start = {"lon": 127, "lat": 37.5}
    end = {"lon": 127.01, "lat": 37.5}
    option = planner._taxi_option(start, end, date(2026, 10, 11), 14 * 60, 10, [])
    assert option["_fare"] == 11600
    assert "미터 추정 8,400원 + 예산 여유 3,200원 + 통행료 0원" in option["_route"]
    assert "호출·옵션료 미포함" in option["_route"]


def test_recalculated_components_and_general_call_reach_departure_notice():
    runtime, context, route, deadline = scene()
    runtime._v.car = service()
    observed = call(runtime, context, deadline)
    assert observed["status"] == "model_revalidated"
    move = Item(item_id=uuid4(), seq=1, kind="mobility", title="서울 택시 이동", place_id=None,
                starts_at=NOW, ends_at=NOW + timedelta(minutes=10), detail={"route_def": route})
    following = Item(item_id=uuid4(), seq=2, kind="activity", title="서울 관람", place_id=None,
                     starts_at=deadline, ends_at=deadline + timedelta(hours=1), detail={})
    before = deepcopy(move)
    status, phrase = build_departure(move, [move, following], route_events=NoEvents(), routes=None,
        now=NOW, departure_observer=lambda *a, **kw: observed)
    assert status == "ok"
    text = phrase.render()
    assert "미터 추정 8,400원 + 예산 여유 3,200원 + 통행료 0원" in text
    assert "일반호출 0원" in text and "실제 결제 상한 아님" in text
    assert "11,600원" in text and move == before
