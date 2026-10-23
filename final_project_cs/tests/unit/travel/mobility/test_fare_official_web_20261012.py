"""공식 버스 표와 신분당선 약관의 새 회귀 표본. 실제 결제 측정은 아니다."""
from copy import deepcopy
from datetime import datetime

import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O, plan as P
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.bus_identity import bus_leg
from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
from app.domains.travel_ops.instances.mobility.engine.verify_time import LegResult, Timetable, Verifier, leg_txt
from .test_special_rail_fare import verifier
from .test_transfer_fare_product_v1 import scenario
from .test_review_fixes_plan import PLACES


@pytest.mark.parametrize('kind,board,expected', [
    ('광역', 370, 2400), ('광역', 410, 3000), ('광역', 385, None),
    ('간선', 370, 1200), ('지선', 370, 1200), ('순환', 370, 1120),
    ('마을', 370, 960), ('심야', 370, 2500),
])
def test_seoul_published_adult_card_early_bird_bus_table(kind, board, expected):
    # 서울시 버스정책과 archives/1706: 시행 2023-08-12, 수정 2026-03-09.
    v, legs, results = scenario()
    v.bus.route('101').route_type_nm = kind
    results[0].depart_min = board
    results[0].arrive_min = board + 5
    assert O.bus_fare(v, legs[:1], results[:1]) == expected


def rail_bus_rail(first, second):
    v = verifier()
    rows = [dict(route_id='r1', seq=1, station_id='s1', station_nm='갑'),
            dict(route_id='r1', seq=2, station_id='s2', station_nm='을', sect_dist_m=2000)]
    v.bus = BusRoutes([dict(route_id='r1', route_nm='101', route_type_nm='간선', term_min=10)], rows)
    legs = [dict(mode='subway', line='신분당선', **{'from': first[0], 'to': first[1]}),
            bus_leg(v.bus.route('101'), *rows),
            dict(mode='subway', line='신분당선', **{'from': second[0], 'to': second[1]})]
    results = [LegResult(i+1, leg_txt(leg), 'feasible', '', depart_min=720+i*20,
                         arrive_min=725+i*20, wait_min=5) for i, leg in enumerate(legs)]
    return Verifier(Timetable(), v.lo, v.R, set(), bus=v.bus), legs, results


@pytest.mark.parametrize('first,second,expected', [
    (('강남', '양재'), ('양재시민의숲', '청계산입구'), 2550),
    (('신사', '논현'), ('신논현', '강남'), 2250),
    (('강남', '양재'), ('동천', '수지구청'), 3050),
    (('신사', '논현'), ('강남', '양재'), 3250),
])
def test_shinbundang_surcharge_is_combined_once_across_an_eligible_bus_transfer(first, second, expected):
    # 신분당선 여객약관 제9조6항: 인정된 환승 연쇄에서 별도운임은 1회만 합산.
    v, legs, results = rail_bus_rail(first, second)
    assert O.mixed_fare_estimate(v, legs, results) == expected


def test_expired_transfer_does_not_receive_the_once_only_surcharge():
    v, legs, results = rail_bus_rail(('강남', '양재'), ('동천', '수지구청'))
    results[2].depart_min = 800
    results[2].arrive_min = 805
    assert O.mixed_fare_estimate(v, legs, results) is None


def test_combined_surcharge_reaches_the_public_planner_option(monkeypatch):
    v, legs, results = rail_bus_rail(('강남', '양재'), ('양재시민의숲', '청계산입구'))
    planner = P.Planner(Runtime(v, timetable_built_at='controlled', rules_version='controlled', stats={}),
                        modes=['bus', 'subway'])
    option = {'eta_min': 45, 'uses': P.uses_of(legs), '_legs': legs, '_route': P.label_of(legs),
              '_start': 720, '_transfers': 2, '_n': 1, '_key': ('mixed', 0, 1), '_mixed': True,
              '_margin': 0, '_slack': 0, '_walk_min': 0, '_walk_m': 0, '_fare': None,
              '_severe': [], '_covered': False, '_lr': results, '_day_type': '평일'}
    monkeypatch.setattr(planner, '_station_pairs', lambda *args: ([], [], []))
    monkeypatch.setattr(planner, '_bus_direct', lambda *args: [])
    monkeypatch.setattr(planner, '_bike_direct', lambda *args: ([], None))
    monkeypatch.setattr(planner, '_mixed', lambda *args: [deepcopy(option)])
    got, why = planner.leg(PLACES[0], PLACES[1], datetime.fromisoformat('2026-10-12T12:45:00+09:00'),
                           {}, True, 'official-web-fare')
    assert why is None
    public = got[0]['options'][0]
    assert public['fare_krw'] == 2550
    assert '1인 1카드' in public['label'] and '승하차 태그' in public['label']
    assert '환승 할인 예상액' in public['label']
