"""공항철도 공식 카드 운임을 거리 추정과 분리하여 제품 요금 계산까지 검증한다."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.line_order import LineOrder
from app.domains.travel_ops.instances.mobility.engine.special_rail import published_od_fare
from app.domains.travel_ops.instances.mobility.engine.verify_time import leg_txt


@pytest.fixture
def verifier():
    engine = Path(O.__file__).parent
    rules = json.loads((engine / 'rules/rules_v0.3.json').read_text(encoding='utf8'))
    policy = json.loads((engine / 'rules/special_rail_fares_v1.json').read_text(encoding='utf8'))
    rules['fare']['subway']['published_od_fares'] = policy['published_od_fares']
    rules['fare']['subway']['special_lines'] = policy['lines']
    stations = policy['published_od_fares']['공항철도']['stations']
    lo = LineOrder({'built_at': '2026-10-12', 'lines': {'공항철도': {
        'stations': [{'station_nm': s} for s in stations],
        'edges': [{'a': a, 'b': b, 'distance_m': None, 'grade': '확정', 'travel_min': 3}
                  for a, b in zip(stations, stations[1:])]}}})
    return SimpleNamespace(R=rules, lo=lo, sc=None, tw=None)


def leg(a, b, **kwargs):
    return {'mode': 'subway', 'line': '공항철도', 'from': a, 'to': b, **kwargs}


def rides(legs, board=650):
    return [SimpleNamespace(label=leg_txt(item), depart_min=board) for item in legs]


@pytest.mark.parametrize('a,b,expected', [
    ('공덕', '홍대입구', 1550), ('서울역', '김포공항', 1750),
    ('홍대입구', '마곡나루', 1650), ('디지털미디어시티', '청라국제도시', 1950),
    ('서울역', '청라국제도시', 2150), ('계양', '청라국제도시', 1650),
    ('검암', '청라국제도시', 1550)])
@pytest.mark.parametrize('reverse', [False, True])
def test_official_varied_fare_bands_reach_product_fare(verifier, a, b, expected, reverse):
    if reverse:
        a, b = b, a
    legs = [leg(a, b)]
    assert O.fare_of(verifier, legs, rides(legs)) == expected
    assert O.subway_fare_upper(verifier, legs, rides(legs)) == expected
    assert not O.fare_is_est(verifier, legs, rides(legs))


def test_policy_covers_exactly_all_nine_station_pairs(verifier):
    config = verifier.R['fare']['subway']['published_od_fares']['공항철도']
    assert len(config['stations']) == 9
    assert len(config['fares']) == 36
    pairs = {frozenset((item['a'], item['b'])) for item in config['fares']}
    assert len(pairs) == 36
    for a in config['stations']:
        for b in config['stations']:
            if a != b:
                assert frozenset((a, b)) in pairs


@pytest.mark.parametrize('reverse', [False, True])
def test_same_journey_split_uses_endpoints_once(verifier, reverse):
    legs = [leg('서울역', '공덕'), leg('공덕', '홍대입구'), leg('홍대입구', '김포공항')]
    if reverse:
        legs = [leg(item['to'], item['from']) for item in reversed(legs)]
    assert O.fare_of(verifier, legs, rides(legs)) == 1750


@pytest.mark.parametrize('minute,expected,upper', [
    (360, 1440, 1440), (389, 1440, 1440), (390, None, 1750),
    (395, None, 1750), (404, None, 1750), (405, 1750, 1750)])
def test_early_bird_discounts_only_base_and_preserves_gate_uncertainty(
        verifier, minute, expected, upper):
    legs = [leg('서울역', '김포공항')]
    results = rides(legs, minute)
    assert O.fare_of(verifier, legs, results) == expected
    assert O.subway_fare_upper(verifier, legs, results) == upper
    assert O.subway_fare_upper(verifier, legs, results, apply_early_bird=False) == 1750


@pytest.mark.parametrize('legs', [
    [leg('청라국제도시', '영종')], [leg('서울역', '인천공항1터미널')],
    [leg('공덕', '홍대입구', express=True)],
    [leg('공덕', '홍대입구', service_type='express')],
    [leg('공덕', '홍대입구'), leg('김포공항', '계양')],
    [leg('공덕', '김포공항'), leg('김포공항', '홍대입구')],
    [leg('공덕', '홍대입구'), {'line': '02호선', 'from': '홍대입구', 'to': '신촌'}],
    [leg('공덕', '없는역')], [leg('공덕', '공덕')]])
def test_published_table_does_not_leak_to_unsupported_journeys(verifier, legs):
    assert published_od_fare(verifier, legs, False) is None
    assert O.fare_of(verifier, legs, rides(legs)) is None
    assert O.subway_fare_upper(verifier, legs, rides(legs)) is None


def test_bus_mixed_upper_uses_undiscounted_single_arex_component(verifier, monkeypatch):
    bus = {'mode': 'bus', 'route': '공개 시험 노선', 'from': 'A', 'to': 'B'}
    legs = [bus, leg('공덕', '홍대입구')]
    monkeypatch.setattr(O, 'bus_fare_upper', lambda *_args: 1500)
    assert O.fare_of(verifier, legs, rides(legs, 360)) is None
    assert O.fare_upper_of(verifier, legs, rides(legs, 360)) == 3050


def test_mismatched_ride_result_does_not_create_published_fare(verifier):
    legs = [leg('공덕', '홍대입구')]
    assert O.fare_of(verifier, legs, rides([leg('서울역', '홍대입구')])) is None


def test_missing_published_policy_does_not_become_base_fare(verifier):
    del verifier.R['fare']['subway']['published_od_fares']
    legs = [leg('공덕', '홍대입구')]
    assert O.fare_of(verifier, legs, rides(legs)) is None
    assert O.subway_fare_upper(verifier, legs, rides(legs)) is None
