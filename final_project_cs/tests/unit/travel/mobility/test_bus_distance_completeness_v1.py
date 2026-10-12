"""구간 행 누락을0m·일부 합으로 만들지 않는다. 실운행/결제 검증이 아니다."""
import pytest

from .test_bus_stop_identity_v1 import world
from .test_departure_observer_v1 import scene, call, prediction


@pytest.mark.parametrize('route,start,end', [('999', 5, 8), ('100', 8, 5), ('100', 5, 5),
    ('100', True, 8), ('100', 5.0, 8), ('100', 0, 8), ('100', 5, 99)])
def test_invalid_interval_has_no_distance(route, start, end):
    bus, _, _ = world()
    assert bus.distance_m(route, start, end) is None


@pytest.mark.parametrize('sequence', [5, 6, 8])
def test_missing_endpoint_or_interior_is_not_a_partial_distance(sequence):
    bus, _, _ = world()
    bus.stops['100'] = [r for r in bus.stops['100'] if r['seq'] != sequence]
    assert bus.distance_m('100', 5, 8) is None


def test_duplicate_interior_is_not_double_counted():
    bus, _, rows = world()
    bus.stops['100'].append(dict(rows[5]))
    assert bus.distance_m('100', 5, 8) is None


def test_different_route_row_is_not_summed():
    bus, _, _ = world()
    bus.stops['100'][5]['route_id'] = '200'
    assert bus.distance_m('100', 5, 8) is None


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), True, '1000', None])
def test_invalid_distance_does_not_enter_the_sum(value):
    bus, _, _ = world()
    bus.stops['100'][5]['sect_dist_m'] = value
    assert bus.distance_m('100', 5, 8) is None


def test_complete_interval_excludes_incoming_distance_to_boarding_stop():
    bus, _, _ = world()
    bus.stops['100'][4]['sect_dist_m'] = None
    assert bus.distance_m('100', 5, 8) == 3000
    bus.stops['100'][5]['sect_dist_m'] = 0
    assert bus.distance_m('100', 5, 8) == 2000


def test_current_departure_with_missing_interior_does_not_use_shortened_ride():
    runtime, context = scene()
    runtime._v.bus.stops['100'] = [r for r in runtime._v.bus.stops['100'] if r['seq'] != 6]
    got = call(runtime, context, bus_arrival=prediction)
    assert got['status'] == 'fatal', got
    assert 'departure_at' not in got and 'eta_min' not in got
