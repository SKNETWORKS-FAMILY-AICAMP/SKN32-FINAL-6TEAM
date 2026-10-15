"""환승 할인 계산을 성인 카드 조건부 예상액으로 제품 경로에 연결한다."""
from copy import deepcopy
from datetime import datetime

import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O, plan as P
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.bus_identity import bus_leg
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
from app.domains.travel_ops.instances.mobility.engine.verify_time import LegResult, leg_txt
from .test_mixed_fare_upper_v1 import fixture
from .test_review_fixes_plan import PLACES


def scenario(bus_m=2000, rail_m=6000):
    v, _bus, rail = fixture({('09호선', 'A', 'B'): rail_m / 2,
                             ('09호선', 'B', 'C'): rail_m / 2})
    rows = [dict(route_id='r1', seq=1, station_id='s1', station_nm='갑'),
            dict(route_id='r1', seq=2, station_id='s2', station_nm='을', sect_dist_m=bus_m)]
    v.bus = BusRoutes([dict(route_id='r1', route_nm='101', route_type_nm='간선', term_min=10)], rows)
    v.R['fare']['transfer']['bus_distance'] = {
        'value': 'selected_contiguous_sections', 'grade': '추정'}
    v.R['fare']['transfer']['max_ride_min'] = {'value': {'subway': 300, 'bus': 300, '마을': 60}}
    bus = bus_leg(v.bus.route('101'), *rows)
    legs = [bus, rail]
    results = [LegResult(i + 1, leg_txt(leg), 'feasible', '', depart_min=720 + i * 20,
                         arrive_min=730 + i * 20, wait_min=5) for i, leg in enumerate(legs)]
    return v, legs, results


@pytest.mark.parametrize('reverse', [False, True])
def test_card_discount_reaches_both_mixed_orders(reverse):
    v, legs, lr = scenario()
    if reverse:
        legs.reverse()
        lr = [LegResult(i + 1, leg_txt(leg), 'feasible', '', depart_min=720 + i * 20,
                        arrive_min=730 + i * 20, wait_min=5) for i, leg in enumerate(legs)]
    assert O.mixed_fare_estimate(v, legs, lr) == 1550
    assert O.fare_upper_of(v, legs, lr) == 3050


@pytest.mark.parametrize('meters,expected', [(10000, 1550), (10001, 1650), (15000, 1650),
                                             (15001, 1750), (60000, 2550)])
def test_combined_distance_steps_use_transfer_rule(meters, expected):
    v, legs, lr = scenario(bus_m=meters, rail_m=0)
    # 명시된 0m 간선도 거리 누락과 구분한다.
    assert O.mixed_fare_estimate(v, legs, lr) == expected


@pytest.mark.parametrize('break_kind', [
    'missing_distance', 'negative', 'infinite', 'bool_distance', 'missing_identity',
    'wrong_stop_id', 'wrong_sequence', 'unknown_type', 'unknown_rail', 'misaligned',
    'infeasible', 'missing_clock', 'overlap', 'expired', 'disabled', 'too_long',
])
def test_unsupported_discount_inputs_preserve_separate_fare_fallback(break_kind):
    v, legs, lr = scenario()
    if break_kind == 'missing_distance':
        v.bus.stops['r1'][1].pop('sect_dist_m')
    elif break_kind in ('negative', 'infinite', 'bool_distance'):
        v.bus.stops['r1'][1]['sect_dist_m'] = {'negative': -1, 'infinite': float('inf'),
                                             'bool_distance': True}[break_kind]
    elif break_kind == 'missing_identity':
        legs[0] = {k: legs[0][k] for k in ('mode', 'route', 'from', 'to')}
    elif break_kind == 'wrong_stop_id':
        legs[0]['to_stop_id'] = 'other'
    elif break_kind == 'wrong_sequence':
        legs[0]['to_sequence'] = 3
    elif break_kind == 'unknown_type':
        v.bus.route('101').route_type_nm = '공항'
    elif break_kind == 'unknown_rail':
        legs[1]['line'] = '모르는철도'
        lr[1].label = leg_txt(legs[1])
    elif break_kind == 'misaligned':
        lr.reverse()
    elif break_kind == 'infeasible':
        lr[0].verdict = 'infeasible'
    elif break_kind == 'missing_clock':
        lr[0].arrive_min = None
    elif break_kind == 'overlap':
        lr[1].depart_min = 729
    elif break_kind == 'expired':
        lr[1].depart_min = 761
        lr[1].arrive_min = 771
    elif break_kind == 'disabled':
        v.R['fare']['transfer']['bus_distance']['value'] = None
    elif break_kind == 'too_long':
        lr[0].depart_min = 400
    assert O.mixed_fare_estimate(v, legs, lr) is None


def test_reboarding_same_bus_is_not_discounted_even_after_rail():
    v, legs, lr = scenario()
    legs.append(deepcopy(legs[0]))
    lr.append(LegResult(3, leg_txt(legs[2]), 'feasible', '', depart_min=760, arrive_min=770))
    assert O.mixed_fare_estimate(v, legs, lr) is None


def test_consecutive_subway_transfers_count_as_one_boarding():
    v, legs, lr = scenario()
    legs[1]['to'] = 'B'
    legs.append(dict(mode='subway', line='09호선', **{'from': 'B', 'to': 'C'}))
    lr[1].label = leg_txt(legs[1])
    lr.append(LegResult(3, leg_txt(legs[2]), 'feasible', '', depart_min=755, arrive_min=765))
    assert O.mixed_fare_estimate(v, legs, lr) == 1550


@pytest.mark.parametrize('count,expected', [(2, 1500), (5, 1500), (6, None)])
def test_distinct_bus_routes_discount_and_five_boarding_limit(count, expected):
    v, legs, lr = scenario()
    template = v.bus.stops['r1']
    routes, stops, legs, lr = [], [], [], []
    for i in range(count):
        rid, name = f'r{i}', str(100 + i)
        rows = [dict(row, route_id=rid) for row in template]
        routes.append(dict(route_id=rid, route_nm=name, route_type_nm='간선', term_min=10))
        stops.extend(rows)
    v.bus = BusRoutes(routes, stops)
    for i in range(count):
        route = v.bus.route(str(100 + i))
        leg = bus_leg(route, *v.bus.stops[route.route_id])
        legs.append(leg)
        lr.append(LegResult(i + 1, leg_txt(leg), 'feasible', '',
                            depart_min=720 + i * 20, arrive_min=730 + i * 20, wait_min=5))
    assert O.mixed_fare_estimate(v, legs, lr) == expected


def test_special_rail_surcharge_is_not_lost_after_integration():
    v, legs, lr = scenario()
    v.R['fare']['subway']['special_lines'] = {
        '09호선': {'stations': ['A', 'B', 'C'], 'confirmed_edges': [],
                  'zones': [{'id': 'z1', 'from': 'A', 'to': 'C'}], 'surcharges': {'z1': 700}}}
    assert O.mixed_fare_estimate(v, legs, lr) == 2250


@pytest.mark.parametrize('meters,expected', [(30000, 3000), (30001, 3100),
                                            (35000, 3100), (35001, 3200)])
def test_seoul_express_bus_uses_thirty_km_transfer_base(meters, expected):
    v, legs, lr = scenario(bus_m=meters, rail_m=0)
    v.bus.route('101').route_type_nm = '광역'
    assert O.mixed_fare_estimate(v, legs, lr) == expected


@pytest.mark.parametrize('start,gap,discounted', [(1200, 30, True), (1200, 31, False),
                                               (1250, 60, True), (1250, 61, False)])
def test_product_transfer_window_uses_following_board_time(start, gap, discounted):
    v, legs, lr = scenario()
    lr[0].depart_min, lr[0].arrive_min = start - 10, start
    lr[1].depart_min, lr[1].arrive_min = start + gap, start + gap + 10
    assert O.mixed_fare_estimate(v, legs, lr) == (1550 if discounted else None)


def test_public_planner_uses_discount_estimate_with_card_and_tag_condition(monkeypatch):
    v, legs, results = scenario()
    planner = P.Planner(Runtime(v, timetable_built_at='controlled', rules_version='controlled', stats={}),
                        modes=['bus', 'subway'])
    option = {'eta_min': 40, 'uses': P.uses_of(legs), '_legs': legs, '_route': P.label_of(legs),
              '_start': 720, '_transfers': 1, '_n': 1, '_key': ('mixed', 0, 1), '_mixed': True,
              '_margin': 0, '_slack': 0, '_walk_min': 0, '_walk_m': 0, '_fare': None,
              '_severe': [], '_covered': False, '_lr': results, '_day_type': '평일'}
    monkeypatch.setattr(planner, '_station_pairs', lambda *args: ([], [], []))
    monkeypatch.setattr(planner, '_bus_direct', lambda *args: [])
    monkeypatch.setattr(planner, '_bike_direct', lambda *args: ([], None))
    monkeypatch.setattr(planner, '_mixed', lambda *args: [option])
    got, why = planner.leg(PLACES[0], PLACES[1], datetime.fromisoformat('2026-10-05T12:30:00+09:00'),
                           {}, True, 'controlled-discount')
    assert why is None
    public = got[0]['options'][0]
    assert public['fare_krw'] == 1550
    assert '1인 1카드' in public['label'] and '승하차 태그' in public['label']
    assert '환승 할인 예상액' in public['label'] and '거리 모델' in public['label']
    assert '할인 전 예상액 상단' not in public['label']
