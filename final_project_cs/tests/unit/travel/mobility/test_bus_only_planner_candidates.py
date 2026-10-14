"""버스만 선택해도 환승 후보를 탐색하고 지하철을 끼우지 않는다."""
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine import plan as P
from app.domains.travel_ops.instances.mobility.engine.candidates import MixedGenerator
from tests.unit.travel.mobility.test_bus_to_bus import _gen, _world, A, B


def test_bus_transfer_obeys_zero_transfer_limit():
    assert _gen(_world(), tlim=0).bus_to_bus(*A, *B, 1200) == []
    assert _gen(_world(), tlim=1).bus_to_bus(*A, *B, 1200)


def test_bus_only_earliest_sources_include_bus_transfer_and_no_subway():
    pl = P.Planner.__new__(P.Planner)
    pl.modes = {'bus'}
    candidate = SimpleNamespace(est_min=20, shape='C')           # 버스→버스 혼합 후보 모양
    def forbidden(*a, **kw):
        raise AssertionError('버스만 선택했는데 지하철 후보를 생성했다')
    # 추가운임 회피 대안은 진짜 생성기 구현을 그대로 부른다 — 버스→버스(모양 C)에는 대안을 만들지 않는다
    gen = SimpleNamespace(bus_to_subway=forbidden, subway_to_bus=forbidden,
                          bus_to_bus=lambda *a: [candidate], materialize=lambda c: True)
    gen.regular_alternative = lambda c: MixedGenerator.regular_alternative(gen, c)
    pl._mix_gen = lambda *a: gen
    pl._in_service = lambda *a: True
    place = {'lat': 37.5, 'lon': 127.0}
    stations = [('역', 100, {'02호선'})]
    assert pl._mixed_sources(place, place, stations, stations, 600, {}, False, 1200) == [candidate]


def test_subway_only_does_not_build_bus_generator():
    pl = P.Planner.__new__(P.Planner)
    pl.modes = {'subway'}
    pl.v = SimpleNamespace(bus=object(), sc=object())
    assert pl._mix_gen({}, False) is None
