"""운행창·왕복 방향을 후보 상한 전에 확인한다. 경로별 계수 없이 일반 조건으로 검증한다."""
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from tests.unit.travel.mobility.test_bus_to_bus import A, B, _gen, _world, _stop, _route, FakeBus


def test_wrong_nearest_boarding_direction_does_not_hide_valid_boarding():
    def reverse_nearest(routes, stops):
        return routes, stops + [_stop('R1', 99, '반대방향', *A)]
    out = _gen(_world(x=reverse_nearest)).bus_to_bus(*A, *B, 800)
    assert out and out[0].legs[0]['from'] == '가출발'


def test_wrong_nearest_alighting_direction_does_not_hide_valid_alighting():
    def reverse_nearest(routes, stops):
        return routes, stops + [_stop('R2', 0, '반대방향', *B)]
    out = _gen(_world(x=reverse_nearest)).bus_to_bus(*A, *B, 800)
    assert out and out[0].legs[-1]['to'] == '나도착'


def test_service_filter_runs_before_top_limit():
    b = _world()
    r3 = _route('R3', '3333')
    stops = [s for rows in b.stops.values() for s in rows]
    stops += [_stop('R3', 2, '다환승', 37.5952, 126.9952), _stop('R3', 6, '다도착', 37.6101, 127.0102)]
    g = _gen(FakeBus([*b.by_id.values(), r3], stops))
    g.service_check = lambda c: c.legs[-1]['route'] == '3333'
    out = g.bus_to_bus(*A, *B, 800, top=1)
    assert len(out) == 1 and out[0].legs[-1]['route'] == '3333'
    assert g.skipped_service > 0


def _window(first=1380, last=180):
    p = Planner.__new__(Planner)
    r1 = SimpleNamespace(route_id='1', first_min=240, last_min=1560)
    r2 = SimpleNamespace(route_id='2', first_min=first, last_min=last)
    rows = {'1': [{'seq': 1}], '2': [{'seq': 1}]}
    p.v = SimpleNamespace(bus=SimpleNamespace(stops=rows))
    p._ride_est = lambda *args: 0.0
    mc = SimpleNamespace(bus_boards=[(r1, rows['1'][0]), (r2, rows['2'][0])])
    return p, mc


def test_second_night_bus_rejects_daytime_candidate():
    p, mc = _window()
    assert not p._in_service(mc, 600, 650)
    assert p._in_service(mc, 1410, 1430)
    assert p._in_service(mc, 1500, 1530), '자정 통과 운행창'


def test_missing_stop_travel_time_is_not_fabricated_as_zero():
    p, mc = _window()
    p._ride_est = lambda *args: None
    assert p._in_service(mc, 600, 650), '자료 부족은 불가 확정 근거가 아니다'


def test_valid_thirteenth_departure_route_is_not_lost_to_nearby_dead_ends():
    def add_dead_ends(routes, stops):
        for i in range(12):
            rid = f'D{i}'
            routes.append(_route(rid, f'막힌노선{i}'))
            stops.append(_stop(rid, 1, f'가까운출발{i}', *A))
        return routes, stops
    out = _gen(_world(x=add_dead_ends)).bus_to_bus(*A, *B, 800)
    assert out and out[0].route_nm == '1111→2222'
