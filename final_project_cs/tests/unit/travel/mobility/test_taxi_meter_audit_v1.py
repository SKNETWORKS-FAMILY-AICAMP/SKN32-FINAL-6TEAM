"""서울 공식 미터 요율·물리적 속도·같은 절대시각 경계를 검산한다. 실주행 시험 아님."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import car


RULE_FILE = Path(car.__file__).parent / 'rules/rules_v0.3.json'


def rules():
    return json.loads(RULE_FILE.read_text(encoding='utf-8'))


def graph(monkeypatch, speed=30.0, metres=1000):
    monkeypatch.setattr(car, 'hav', lambda *_: float(metres))
    g = object.__new__(car.CarGraph)
    g.holidays = g.cal_hol = set()
    g.wayinfo = {1: ('primary', [(127, 37.5), (127.01, 37.5)])}
    g.seg = {1: {(0, 'fwd'): 'L'}}
    g.prof = {('L', day, hour): speed for day in ('평일', '토요일', '휴일') for hour in range(24)}
    g.cf = {}
    g._way_dir_and_segs = lambda *_: ('primary', True, [0, 0])
    return g


def route():
    return {'paths': [{'points': {'coordinates': [[127, 37.5], [127.01, 37.5]]},
                       'details': {'osm_way_id': [[0, 1, 1]], 'road_class': [[0, 1, 'primary']]},
                       'distance': 1000, 'time': 120000}]}


@pytest.mark.parametrize('speed', [1.0, 2.0, 3.0])
def test_positive_profile_speed_is_not_silently_increased(monkeypatch, speed):
    result = graph(monkeypatch, speed).compute(route(), datetime(2026, 10, 12, 12), 15.72)
    assert result['topis_time_s'] == round(1000 / speed * 3.6)
    assert result['slow_s'] == round(1000 / speed * 3.6)


@pytest.mark.parametrize('hhmm,extra_units,official_base,official_step', [
    ('22:30', 0, 5800, 120), ('22:30', 2, 5800, 120),
    ('23:30', 0, 6700, 140), ('23:30', 1, 6700, 140),
    ('23:30', 4, 6700, 140),
])
def test_declared_night_base_and_increment_are_separate(hhmm, extra_units, official_base, official_step):
    # 정확히 완성된 거리단위만 사용해 단위 미만 처리의 별도 불확실성을 섞지 않는다.
    raw = official_base + official_step * extra_units
    expected = ((raw + 50) // 100) * 100
    assert car.taxi_fare(rules()['taxi']['fare'], '중형', 1600 + 131 * extra_units, 0, hhmm) == expected


def test_same_instant_uses_seoul_tariff_and_profile_hour(monkeypatch):
    g = graph(monkeypatch)
    service = car.CarService(g, SimpleNamespace(route=lambda *_: route()), rules())
    kst = timezone(timedelta(hours=9))
    departure = datetime(2026, 10, 12, 23, 30, tzinfo=kst)
    local = service.leg((127, 37.5), (127.01, 37.5), departure, taxi=True)
    utc = service.leg((127, 37.5), (127.01, 37.5), departure.astimezone(timezone.utc), taxi=True)
    assert local['meter_won'] == utc['meter_won']
    assert local['night_rate'] == utc['night_rate']
    assert local['hour_start'] == utc['hour_start'] == 23


def test_same_mean_speed_cannot_identify_stop_go_meter_time(monkeypatch):
    # 양쪽 모두 기본거리 이후 1km 구간이다. 정차로 인한 시간 요율만 비교한다.
    constant = [(120, 30)]
    stop_go = [(60, 0), (60, 60)]

    def measures(trace):
        seconds = sum(t for t, _ in trace)
        metres = sum(t * v / 3.6 for t, v in trace)
        slow = sum(t for t, v in trace if v < 15.72)
        return metres, seconds, slow

    assert measures(constant) == (1000, 120, 0)
    assert measures(stop_go) == (1000, 120, 60)
    g = graph(monkeypatch, speed=30)
    result = g.compute(route(), datetime(2026, 10, 12, 12), 15.72)
    assert result['topis_time_s'] == 120 and result['slow_s'] == 0
    # 현재 자료에는 두 궤적을 구분할 입력이 없다. 통과는 결함 해결이 아닌 정보손실 재현이다.
    fare = rules()['taxi']['fare']
    assert car.taxi_fare(fare, '중형', 2600, 60, '12:00') - car.taxi_fare(fare, '중형', 2600, 0, '12:00') == 200
