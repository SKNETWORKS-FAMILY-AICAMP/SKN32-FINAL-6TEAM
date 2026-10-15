"""직행 존재만으로 더 빠른 버스 환승을 지우지 않는 제품 후보 경로."""
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import plan as P
from tests.unit.travel.mobility.test_bus_to_bus import A, B, _gen, _world, _stop


def direct_and_transfer():
    def reaches_destination(routes, stops):
        return routes, stops + [_stop('R1', 4, '우회후도착', 37.6102, 127.0102)]

    def ride(route, board, alight):
        if route.route_id == 'R1' and alight['seq'] == 4:
            return 100.0  # 마지막 구간을 오래 우회하는 직행, 환승점까지는 정상 운행.
        return (alight['seq'] - board['seq']) * 3.0

    return _gen(_world(x=reaches_destination), ride=ride)


def test_slower_direct_route_does_not_delete_the_faster_bus_transfer():
    gen = direct_and_transfer()
    got = gen.bus_to_bus(*A, *B, 1200)
    assert len(got) == 1
    assert got[0].route_nm == '1111→2222'
    assert got[0].est_min < 100
    assert [leg['route_id'] for leg in got[0].legs] == ['R1', 'R2']
    assert [(leg['from_sequence'], leg['to_sequence']) for leg in got[0].legs] == [(1, 3), (2, 4)]


@pytest.mark.parametrize('direct_eta,expected', [(100, 1), (10, 0)])
def test_existing_planner_compares_transfer_candidate_with_direct_result(direct_eta, expected):
    planner = P.Planner.__new__(P.Planner)
    planner.modes = {'bus'}
    planner.v = SimpleNamespace(R={'candidates': {'허용_소요_배수': {'value': 2.0}}})
    planner.detour, planner.speed = 1.4, 1.04
    planner._mix_gen = lambda *args: direct_and_transfer()
    planner._in_service = lambda *args: True

    # 최종 판정기의 외부 자료와 분리하여 기존 생성→비교 호출 연결을 확인한다.
    def verified_option(mc, *args):
        return {'eta_min': mc.est_min, '_legs': mc.legs, '_transfers': 1,
                '_walk_min': 2, '_route': mc.route_nm}, None

    planner._mixed_one = verified_option
    direct = {'eta_min': direct_eta, '_legs': [{'mode': 'bus', 'route': '1111'}],
              '_transfers': 0, '_walk_min': 2}
    left = []
    a, b = {'lat': A[0], 'lon': A[1]}, {'lat': B[0], 'lon': B[1]}
    kept = planner._mixed(a, b, [], [], None, None, 800, {}, False, 'competition', 1200, [direct], left)
    assert len(kept) == expected
    if kept:
        assert kept[0]['_route'] == '1111→2222'
        assert kept[0]['eta_min'] < direct_eta
    else:
        assert left and left[0]['code'] == 'mix_skipped'


def test_transfer_limit_still_applies_when_a_direct_route_exists():
    gen = direct_and_transfer()
    gen.tlim = 0
    assert gen.bus_to_bus(*A, *B, 1200) == []
