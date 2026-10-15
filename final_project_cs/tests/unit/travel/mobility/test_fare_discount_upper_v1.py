"""할인 여부의 불확실성이 알려진 일반 요금 상단을 없애지 않는다."""
from copy import deepcopy
from datetime import datetime

import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O, plan as P
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
from tests.unit.travel.mobility.test_mixed_fare_upper_v1 import fixture, rides
from tests.unit.travel.mobility.test_review_fixes_plan import PLACES


@pytest.mark.parametrize('rail_first', [True, False])
@pytest.mark.parametrize('first_board', [375, 385])
def test_mixed_upper_does_not_depend_on_early_bird_or_a_crossing_boarding_window(rail_first, first_board):
    v, bus, rail = fixture()
    legs = [rail, bus] if rail_first else [bus, rail]
    results = rides(legs)
    for i, lr in enumerate(results):
        lr.depart_min = first_board + i * 10
        lr.arrive_min = lr.depart_min + 8
    assert O.fare_of(v, legs, results) is None
    assert O.fare_upper_of(v, legs, results) == 3150


def test_midday_mixed_upper_is_preserved():
    v, bus, rail = fixture()
    assert O.fare_upper_of(v, [bus, rail], rides([bus, rail])) == 3150


@pytest.mark.parametrize('kind,won', [('간선', 1500), ('지선', 1500), ('순환', 1400),
                                   ('마을', 1200), ('광역', 3000), ('심야', 2500)])
def test_known_bus_upper_uses_the_rule_amount_without_a_discount(kind, won):
    v, bus, _ = fixture()
    v.bus.route('101').route_type_nm = kind
    result = rides([bus])
    result[0].depart_min = 385
    assert O.bus_fare_upper(v, [bus], result) == won


@pytest.mark.parametrize('kind', ['공항', '투어', '없는유형', None])
def test_unsupported_bus_has_no_upper_amount(kind):
    v, bus, _ = fixture()
    v.bus.route('101').route_type_nm = kind
    assert O.bus_fare_upper(v, [bus], rides([bus])) is None


@pytest.mark.parametrize('amount', [-1, float('nan'), float('inf'), True, '1500', None])
def test_invalid_rule_amount_does_not_become_a_budget_value(amount):
    v, bus, _ = fixture()
    v.R['fare']['bus']['by_type']['value']['간선'] = amount
    assert O.bus_fare_upper(v, [bus], rides([bus])) is None


def test_unknown_bus_or_unmatched_ride_is_not_filled():
    v, bus, _ = fixture()
    bad = dict(bus, route='없는노선')
    assert O.bus_fare_upper(v, [bad], rides([bad])) is None
    assert O.bus_fare_upper(v, [bus], []) is None


@pytest.mark.parametrize('rail_first', [True, False])
def test_public_mixed_option_carries_undiscounted_upper_and_explanation(monkeypatch, rail_first):
    v, bus, rail = fixture()
    runtime = Runtime(v, timetable_built_at='controlled', rules_version='controlled', stats={})
    planner = P.Planner(runtime, modes=['bus', 'subway'])
    legs = [rail, bus] if rail_first else [bus, rail]
    results = rides(legs)
    for i, lr in enumerate(results):
        lr.depart_min = 370 + i * 10
        lr.arrive_min = lr.depart_min + 8
    option = {'eta_min': 40, 'uses': P.uses_of(legs), '_legs': legs, '_route': P.label_of(legs),
              '_start': 370, '_transfers': 1, '_n': 1, '_key': ('mixed', 0, 1), '_mixed': True,
              '_margin': 0, '_slack': 0, '_walk_min': 0, '_walk_m': 0, '_fare': None,
              '_severe': [], '_covered': False, '_lr': results, '_day_type': '평일'}
    snapshot = deepcopy(option)
    monkeypatch.setattr(planner, '_station_pairs', lambda *args: ([], [], []))
    monkeypatch.setattr(planner, '_bus_direct', lambda *args: [])
    monkeypatch.setattr(planner, '_bike_direct', lambda *args: ([], None))
    monkeypatch.setattr(planner, '_mixed', lambda *args: [deepcopy(option)])
    got, why = planner.leg(PLACES[0], PLACES[1], datetime.fromisoformat('2026-10-09T06:50:00+09:00'),
                           {}, True, 'controlled-mixed')
    assert why is None
    public = got[0]['options'][0]
    assert public['fare_krw'] == 3150
    assert '환승 할인 전 예상액 상단' in public['label']
    assert '조조 할인 미적용' in public['label']
    assert option == snapshot


def test_standalone_rail_early_bird_policy_is_preserved():
    v, _, rail = fixture()
    result = rides([rail])
    result[0].depart_min = 370
    assert O.subway_fare_upper(v, [rail], result) == 1340
