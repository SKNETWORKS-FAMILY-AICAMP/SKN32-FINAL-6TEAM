"""실측·대체 통행시간은 요청한 완전한 정류장 사슬만 누적한다."""
from copy import deepcopy

import pytest

from .test_bus_profile_unit import build, seg, H, STOPS, ONE, FB3
from .test_departure_observer_v1 import scene, call, prediction


def evaluate(stops, profile=None):
    profile = profile or build([])
    return profile.walk('R', stops, 1, 5, 600, ONE, 'p50', 5, FB3)


@pytest.mark.parametrize('sequence', [1, 3, 5])
def test_missing_stop_is_not_replaced_by_a_false_adjacent_segment(sequence):
    assert evaluate([s for s in STOPS if s['seq'] != sequence]).minutes is None


@pytest.mark.parametrize('sequence', [1, 3, 5])
def test_duplicate_stop_is_not_a_complete_segment(sequence):
    stops = deepcopy(STOPS)
    stops.insert(sequence, deepcopy(stops[sequence - 1]))
    assert evaluate(stops).minutes is None


@pytest.mark.parametrize('sequence', [True, 3.0, 0])
def test_invalid_sequence_cannot_enter_the_profile(sequence):
    stops = deepcopy(STOPS)
    stops[2]['seq'] = sequence
    assert evaluate(stops).minutes is None


def test_explicit_different_route_cannot_enter_the_profile():
    stops = deepcopy(STOPS)
    stops[2]['route_id'] = 'other'
    assert evaluate(stops).minutes is None


@pytest.mark.parametrize('distance', [-1, float('nan'), float('inf'), True, '600', None])
def test_invalid_distance_cannot_be_used_even_by_a_constant_fallback(distance):
    stops = deepcopy(STOPS)
    stops[2]['sect_dist_m'] = distance
    assert evaluate(stops).minutes is None


def test_valid_profile_does_not_require_distance_fallback():
    stops = deepcopy(STOPS)
    for s in stops:
        s['sect_dist_m'] = None
    profile = build([seg('R', i, f'S{i}', f'S{i+1}', H(60)) for i in range(1, 5)])
    got = evaluate(stops, profile)
    assert got.minutes == 4 and got.complete and got.used == 4


def test_zero_distance_can_be_used_by_a_valid_fallback():
    stops = deepcopy(STOPS)
    stops[2]['sect_dist_m'] = 0
    assert evaluate(stops).minutes == 12


def test_current_departure_with_real_profile_does_not_shorten_a_missing_chain():
    runtime, context = scene()
    runtime._v.bus_prof = build([])
    runtime._v.bus.stops['100'] = [r for r in runtime._v.bus.stops['100'] if r['seq'] != 6]
    got = call(runtime, context, bus_arrival=prediction)
    assert got['status'] == 'fatal', got
    assert 'departure_at' not in got and 'eta_min' not in got


def test_empty_stop_chain_has_no_ride_time():
    assert evaluate([]).minutes is None
