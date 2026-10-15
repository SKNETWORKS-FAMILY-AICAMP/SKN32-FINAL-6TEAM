"""후속 버스의 모델 승차 폭과30/60분 경계. 실제 태그·결제 측정 아님."""
import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.verify_time import LegResult, leg_txt
from .test_transfer_fare_product_v1 import scenario


def rail_then_bus(board=760, previous=730, wait=5, term=10):
    v, legs, _ = scenario()
    legs.reverse()
    v.bus.route('101').term_min = term
    results = [LegResult(1, leg_txt(legs[0]), 'feasible', '',
                         depart_min=previous-10, arrive_min=previous, wait_min=5),
               LegResult(2, leg_txt(legs[1]), 'feasible', '',
                         depart_min=board, arrive_min=board+10, wait_min=wait)]
    return v, legs, results


@pytest.mark.parametrize('board,expected', [(755, 1550), (756, None), (760, None)])
def test_daytime_following_bus_uses_full_boarding_window(board, expected):
    v, legs, results = rail_then_bus(board)
    assert O.mixed_fare_estimate(v, legs, results) == expected
    if expected is None:
        assert O.fare_upper_of(v, legs, results) == 3050


@pytest.mark.parametrize('board,previous,expected', [
    (1260, 1220, None),   # 20:55~21:05의 주간 쪽은 이미30분을 넘는다.
    (1260, 1229, None),   # 20:59~21:00 사이에30분을 넘는 부분이 있다.
    (1260, 1230, 1550),   # 20:55~21:00은30분 이내, 이후는60분 이내다.
    (420, 365, None),     # 06:55~07:05:07시부터주간30분으로 줄어든다.
    (415, 360, None),     # 구간 끝07:00도 주간이다.
    (410, 360, 1550),     # 06:45~06:55는야간60분 안이다.
    (1450, 1400, 1550),   # 자정을 넘겨도 야간창을 유지한다.
])
def test_night_boundaries_are_checked_for_every_part_of_the_interval(board, previous, expected):
    v, legs, results = rail_then_bus(board, previous)
    assert O.mixed_fare_estimate(v, legs, results) == expected


@pytest.mark.parametrize('wait,term', [
    (None, 10), (-1, 10), (11, 10), (True, 10), (float('nan'), 10),
    (float('inf'), 10), (5, None), (5, 0), (5, -1), (5, True), (5, float('inf')),
])
def test_missing_or_invalid_boarding_width_keeps_upper_fare(wait, term):
    v, legs, results = rail_then_bus(board=740, wait=wait, term=term)
    assert O.mixed_fare_estimate(v, legs, results) is None
    assert O.fare_upper_of(v, legs, results) == 3050


def test_boarding_interval_cannot_begin_before_previous_alighting():
    v, legs, results = rail_then_bus(board=732)
    assert O.mixed_fare_estimate(v, legs, results) is None


def test_upper_fare_is_published_when_discount_window_is_uncertain(monkeypatch):
    from datetime import datetime
    from .test_review_fixes_plan import PLACES
    from app.domains.travel_ops.instances.mobility.engine import plan as P
    from app.domains.travel_ops.instances.mobility.engine.runtime import Runtime
    v, legs, results = rail_then_bus()
    planner = P.Planner(Runtime(v, timetable_built_at='controlled', rules_version='controlled', stats={}),
                        modes=['bus', 'subway'])
    option = {'eta_min': 50, 'uses': P.uses_of(legs), '_legs': legs, '_route': P.label_of(legs),
              '_start': 720, '_transfers': 1, '_n': 1, '_key': ('mixed', 0, 1), '_mixed': True,
              '_margin': 0, '_slack': 0, '_walk_min': 0, '_walk_m': 0, '_fare': None,
              '_severe': [], '_covered': False, '_lr': results, '_day_type': '평일'}
    monkeypatch.setattr(planner, '_station_pairs', lambda *args: ([], [], []))
    monkeypatch.setattr(planner, '_bus_direct', lambda *args: [])
    monkeypatch.setattr(planner, '_bike_direct', lambda *args: ([], None))
    monkeypatch.setattr(planner, '_mixed', lambda *args: [option])
    got, why = planner.leg(PLACES[0], PLACES[1], datetime.fromisoformat('2026-10-05T12:50:00+09:00'),
                           {}, True, 'controlled-transfer-window')
    assert why is None
    public = got[0]['options'][0]
    assert public['fare_krw'] == 3050
    assert '할인 전 예상액 상단' in public['label']
    assert '환승 할인 예상액' not in public['label']
