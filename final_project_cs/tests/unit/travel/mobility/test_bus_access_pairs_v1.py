"""버스 직행은 최소 승차 구간 외에 가까운 접근 정류장도 판정한다."""
import pytest

from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes


def network():
    stops = [
        dict(route_id='travel', seq=1, station_nm='출발앞', lat=37.5, lng=127.0),
        dict(route_id='travel', seq=2, station_nm='먼승차', lat=37.504, lng=127.0),
        dict(route_id='travel', seq=3, station_nm='먼하차', lat=37.516, lng=127.0),
        dict(route_id='travel', seq=4, station_nm='목적앞', lat=37.52, lng=127.0),
    ]
    return BusRoutes([dict(route_id='travel', route_nm='여행01')], stops)


def test_default_keeps_existing_shortest_section_pair():
    rows = network().routes_between(37.5, 127., 37.52, 127., 500)
    assert [(x['seq'], y['seq']) for _, x, y, *_ in rows] == [(2, 3)]


def test_access_pair_is_added_without_discarding_shortest_section():
    rows = network().routes_between(37.5, 127., 37.52, 127., 500, True)
    assert [(x['seq'], y['seq']) for _, x, y, *_ in rows] == [(2, 3), (1, 4)]
    assert rows[0][4] + rows[0][5] > 800
    assert rows[1][4] + rows[1][5] == 0


def test_same_pair_is_not_duplicated():
    rows = network().routes_between(37.5, 127., 37.52, 127., 50, True)
    assert len(rows) == 1
    assert (rows[0][1]['seq'], rows[0][2]['seq']) == (1, 4)


@pytest.mark.parametrize('radius', [0, 50, 200, 500, 1000])
def test_radius_direction_and_two_pairs_per_route_are_preserved(radius):
    rows = network().routes_between(37.5, 127., 37.52, 127., radius, True)
    assert 1 <= len(rows) <= 2
    for _, x, y, _, da, db in rows:
        assert x['seq'] < y['seq']
        assert da <= radius and db <= radius


def test_backwards_stops_cannot_make_an_access_pair():
    assert network().routes_between(37.52, 127., 37.5, 127., 500, True) == []


def test_equal_access_distance_has_stable_tie_break():
    bus = network()
    a = bus.routes_between(37.502, 127., 37.518, 127., 500, True)
    bus.stops['travel'].reverse()
    b = bus.routes_between(37.502, 127., 37.518, 127., 500, True)
    assert a == b


def test_earliest_arrival_also_checks_the_closer_access_pair():
    from datetime import datetime
    from types import SimpleNamespace
    from tests.unit.travel.mobility.test_earliest_v1 import _bare

    planner = _bare()
    planner.modes = {'bus'}
    planner.v.bus = network()
    planner._stop_walk = lambda place, stop, distance: distance
    planner._mixed_sources = lambda *args: []
    seen = []

    def verify(case):
        leg = case['legs'][0]
        pair = (leg['from_sequence'], leg['to_sequence'])
        seen.append(pair)
        ride = 10 if pair == (2, 3) else 15
        return SimpleNamespace(out={'verdict': 'feasible', 'arrive_min': case['depart_at'] + ride,
                                    'margin_min': 0})

    planner._vc = verify
    a = dict(name='출발', lat=37.5, lon=127.)
    b = dict(name='목적', lat=37.52, lon=127.)
    _, targets, _ = planner._earliest_targets(
        a, b, datetime.fromisoformat('2026-10-08T10:00:00+09:00'), {}, False, 'travel')
    assert (2, 3) in seen and (1, 4) in seen
    assert targets[0] == 615, '더 가까운 정류장을 이용한 10:15 도착도 목표가 된다'
