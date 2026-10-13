"""첫 버스 조조할인은 기본운임에 한 번만, 불명확한 모델 창은 할인하지 않는다."""
from copy import deepcopy
from datetime import datetime

import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O, plan as P
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.bus_identity import bus_leg
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
from app.domains.travel_ops.instances.mobility.engine.verify_time import leg_txt
from .test_transfer_fare_product_v1 import scenario
from .test_review_fixes_plan import PLACES


def early(kind='간선', bus_m=2000, rail_m=6000):
    v, legs, results = scenario(bus_m=bus_m, rail_m=rail_m)
    v.bus.route('101').route_type_nm = kind
    for i, lr in enumerate(results):
        lr.depart_min, lr.arrive_min = 370 + 20*i, 380 + 20*i
    return v, legs, results


@pytest.mark.parametrize('kind,expected', [('간선', 1250), ('지선', 1250),
                                         ('순환', 1270), ('마을', 1310), ('광역', 2400)])
def test_first_bus_base_only_is_discounted(kind, expected):
    v, legs, results = early(kind)
    assert O.mixed_fare_estimate(v, legs, results) == expected


def test_official_village_then_city_example_is_960_plus_300_not_1500_times_80_percent():
    v, legs, results = early('마을')
    rows = [dict(route_id='r2', seq=1, station_id='t1', station_nm='병'),
            dict(route_id='r2', seq=2, station_id='t2', station_nm='정', sect_dist_m=2000)]
    v.bus = BusRoutes([dict(route_id='r1', route_nm='101', route_type_nm='마을', term_min=10),
                      dict(route_id='r2', route_nm='102', route_type_nm='간선', term_min=10)],
                     [*v.bus.stops['r1'], *rows])
    legs[1] = bus_leg(v.bus.route('102'), *rows)
    results[1].label = leg_txt(legs[1])
    assert O.mixed_fare_estimate(v, legs, results) == 1260


def test_distance_surcharge_is_not_discounted():
    v, legs, results = early(bus_m=10001, rail_m=0)
    assert O.mixed_fare_estimate(v, legs, results) == 1350  # 1550−300+100


def test_separate_rail_surcharge_is_not_discounted():
    v, legs, results = early()
    # 추가운임 조각만 통제한다. 실제 9호선에 이 요금이 있다는 뜻은 아니다.
    v.R['fare']['subway']['special_lines'] = {'09호선': {
        'stations': ['A', 'B', 'C'], 'confirmed_edges': [],
        'zones': [{'id': 'z1', 'from': 'A', 'to': 'C'}], 'surcharges': {'z1': 700}}}
    assert O.mixed_fare_estimate(v, legs, results) == 1950


@pytest.mark.parametrize('board,expected', [(384, 1250), (385, 1550), (390, 1550), (400, 1550)])
def test_entire_first_boarding_window_must_be_before_0630(board, expected):
    v, legs, results = early()
    results[0].depart_min, results[0].arrive_min = board, board + 10
    results[1].depart_min, results[1].arrive_min = board + 20, board + 30
    assert O.mixed_fare_estimate(v, legs, results) == expected


@pytest.mark.parametrize('wait,term', [(None, 10), (True, 10), (float('nan'), 10),
                                     (float('inf'), 10), (-1, 10), (11, 10),
                                     (5, None), (5, 0), (5, True)])
def test_unconfirmed_first_boarding_keeps_the_undiscounted_transfer_estimate(wait, term):
    v, legs, results = early()
    results[0].wait_min = wait
    v.bus.route('101').term_min = term
    assert O.mixed_fare_estimate(v, legs, results) == 1550


def test_subway_first_keeps_existing_conservative_amount():
    v, legs, results = early()
    legs.reverse()
    for i, lr in enumerate(results):
        lr.label = leg_txt(legs[i])
    assert O.mixed_fare_estimate(v, legs, results) == 1550


def test_failed_transfer_keeps_the_separate_undiscounted_upper():
    v, legs, results = early()
    results[1].depart_min, results[1].arrive_min = 441, 451
    assert O.mixed_fare_estimate(v, legs, results) is None
    assert O.fare_upper_of(v, legs, results) == 3050


@pytest.mark.parametrize('board,expected,text', [(370, 1250, '첫 버스 조조 반영'),
                                               (385, 1550, '조조 미적용')])
def test_public_amount_and_label_agree(monkeypatch, board, expected, text):
    v, legs, results = early()
    for i, lr in enumerate(results):
        lr.depart_min, lr.arrive_min = board + i*20, board + i*20 + 10
    planner = P.Planner(Runtime(v, timetable_built_at='controlled', rules_version='controlled', stats={}),
                        modes=['bus', 'subway'])
    option = {'eta_min': 40, 'uses': P.uses_of(legs), '_legs': legs, '_route': P.label_of(legs),
              '_start': board, '_transfers': 1, '_n': 1, '_key': ('early', 0, 1), '_mixed': True,
              '_margin': 0, '_slack': 0, '_walk_min': 0, '_walk_m': 0, '_fare': None,
              '_severe': [], '_covered': False, '_lr': results, '_day_type': '평일'}
    monkeypatch.setattr(planner, '_station_pairs', lambda *args: ([], [], []))
    monkeypatch.setattr(planner, '_bus_direct', lambda *args: [])
    monkeypatch.setattr(planner, '_bike_direct', lambda *args: ([], None))
    monkeypatch.setattr(planner, '_mixed', lambda *args: [deepcopy(option)])
    got, why = planner.leg(PLACES[0], PLACES[1], datetime.fromisoformat('2026-10-12T07:00:00+09:00'),
                           {}, True, 'mixed-early-bird')
    assert why is None
    public = got[0]['options'][0]
    assert public['fare_krw'] == expected and text in public['label']
    assert '1인 1카드' in public['label'] and '승하차 태그' in public['label']
