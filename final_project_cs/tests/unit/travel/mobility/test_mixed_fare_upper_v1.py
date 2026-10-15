"""혼합 경로는 확인된 개별 요금 범위를 전달하되 거리 누락을 채우지 않는다."""
from copy import deepcopy
from datetime import datetime

import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O, plan as P
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
from app.domains.travel_ops.instances.mobility.engine.verify_time import LegResult, Timetable, Verifier, leg_txt
from tests.unit.travel.mobility.test_fare_est_v1 import _lo
from tests.unit.travel.mobility.test_review_fixes_plan import RULES, PLACES


def fixture(est=None):
    rules = deepcopy(RULES)
    rules['fare']['subway']['distance_estimate']['value']['lines'] = ['09호선']
    bus = BusRoutes([{'route_id': 'r1', 'route_nm': '101', 'route_type_nm': '간선',
                      'term_min': 10, 'first_time': '05:00', 'last_time': '23:00'}], [])
    v = Verifier(Timetable(), _lo(est=est if est is not None else {
        ('09호선', 'A', 'B'): 4000, ('09호선', 'B', 'C'): 6000}), rules, set(), bus=bus)
    bus_leg = {'mode': 'bus', 'route': '101', 'from': '갑', 'to': '을'}
    rail_leg = {'mode': 'subway', 'line': '09호선', 'from': 'A', 'to': 'C'}
    return v, bus_leg, rail_leg


def rides(legs):
    return [LegResult(i + 1, leg_txt(l), 'feasible', '', depart_min=700 + i * 20,
                      arrive_min=710 + i * 20, wait_min=5) for i, l in enumerate(legs)]


@pytest.mark.parametrize('rail_first', [True, False])
def test_both_mixed_orders_use_known_distance_upper_without_claiming_exact(rail_first):
    v, bus, rail = fixture()
    legs = [rail, bus] if rail_first else [bus, rail]
    assert O.fare_of(v, legs, rides(legs)) is None
    assert O.fare_upper_of(v, legs, rides(legs)) == 1500 + 1650


def test_missing_rail_edge_still_has_no_budget_amount():
    v, bus, rail = fixture({('09호선', 'A', 'B'): 4000})
    assert O.fare_upper_of(v, [bus, rail], rides([bus, rail])) is None


def test_unsupported_rail_line_still_has_no_budget_amount():
    v, bus, rail = fixture()
    v.R['fare']['subway']['distance_estimate']['value']['lines'] = ['02호선']
    assert O.fare_upper_of(v, [bus, rail], rides([bus, rail])) is None


def test_unknown_bus_and_misaligned_results_are_not_filled():
    v, bus, rail = fixture()
    bad = dict(bus, route='없는노선')
    assert O.fare_upper_of(v, [bad, rail], rides([bad, rail])) is None
    assert O.fare_upper_of(v, [bus, rail], list(reversed(rides([bus, rail])))) is None


def test_consecutive_rail_legs_are_one_group():
    v, bus, rail = fixture()
    legs = [bus, dict(rail, to='B'), dict(rail, **{'from': 'B'})]
    assert O.fare_upper_of(v, legs, rides(legs)) == 3150


def test_public_planner_option_preserves_upper_amount_and_estimate_wording(monkeypatch):
    v, bus, rail = fixture()
    runtime = Runtime(v, timetable_built_at='controlled', rules_version='controlled', stats={})
    planner = P.Planner(runtime, modes=['bus', 'subway'])
    legs = [bus, rail]
    results = rides(legs)
    option = {'eta_min': 40, 'uses': P.uses_of(legs), '_legs': legs, '_route': P.label_of(legs),
              '_start': 700, '_transfers': 1, '_n': 1, '_key': ('mixed', 0, 1), '_mixed': True,
              '_margin': 0, '_slack': 0, '_walk_min': 0, '_walk_m': 0, '_fare': None,
              '_severe': [], '_covered': False, '_lr': results, '_day_type': '평일'}
    monkeypatch.setattr(planner, '_station_pairs', lambda *args: ([], [], []))
    monkeypatch.setattr(planner, '_bus_direct', lambda *args: [])
    monkeypatch.setattr(planner, '_bike_direct', lambda *args: ([], None))
    monkeypatch.setattr(planner, '_mixed', lambda *args: [option])
    got, why = planner.leg(PLACES[0], PLACES[1], datetime.fromisoformat('2026-10-05T12:30:00+09:00'),
                           {}, True, 'controlled-mixed')
    assert why is None
    public = got[0]['options'][0]
    assert public['fare_krw'] == 3150
    assert '환승 할인 전 예상액 상단' in public['label']
    assert '결제 보장' not in public['label']
