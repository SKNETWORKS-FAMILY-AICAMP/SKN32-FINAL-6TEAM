"""보행망의 계단 시간을 일정까지 전달한다. 공개 응답에 내부 시간 칸을 추가하지 않는다."""
import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.bike import BikeRouter
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, FOOT_MPS, STEPS_MPS
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from .test_graph_router import encode_polyline
from .test_review_fixes_plan import _rt, PLACES


def stair_router():
    points = [(126.98, 37.57), (126.98, 37.5727)]
    records = {'nodes': [dict(id=i+1, lon=p[0], lat=p[1], r=1) for i, p in enumerate(points)],
               'edges': [dict(u=1, v=2, way=10, sa=0, sb=1, len=300, ow=0, hw='steps', ms=None,
                              car=0, bike=0, bow=0, foot=1, st=1, main=0, bmain=0, fmain=1,
                              g=encode_polyline(points))]}
    return GraphRouter(records=records)


def test_real_graph_stairs_survive_adapter_and_final_departure_time():
    runtime = _rt()
    runtime._v.bike_router = BikeRouter(stair_router())
    planner = Planner(runtime, modes=['walk'])
    target = datetime(2026, 10, 8, 12, tzinfo=timezone(timedelta(hours=9)))
    (route, start, *_rest), why = planner.leg(PLACES[0], PLACES[1], target, {}, False, 'stairs')
    option = next(o for o in route['options'] if o['id'] == 'walk')
    graph = runtime._v.bike_router.route('foot', PLACES[0]['lat'], PLACES[0]['lon'], PLACES[1]['lat'], PLACES[1]['lon'])
    expected = math.ceil(graph['foot_timing']['seconds'] * FOOT_MPS / planner.speed / 60)
    assert option['eta_min'] == expected
    assert option['eta_min'] > math.ceil(option['walk_m'] / planner.speed / 60)
    assert start <= 720 - expected
    assert set(option) == {'id', 'label', 'eta_min', 'uses', 'walk_m', 'fare_krw'}
    assert graph['foot_timing']['stairs_m'] > 290
    assert graph['foot_timing']['seconds'] == pytest.approx(graph['distance_m'] / STEPS_MPS, abs=.1)


def test_off_network_access_seconds_are_included_without_rounding_loss():
    graph = stair_router()
    path = graph.route((126.9801, 37.57), (126.9801, 37.5727), profile='foot')['paths'][0]
    stairs = path['foot_timing']['stairs_m']
    assert path['foot_timing']['seconds'] == pytest.approx(
        stairs / STEPS_MPS + (path['distance'] - stairs) / FOOT_MPS, abs=.01)
    assert path['foot_timing']['seconds'] > stairs / STEPS_MPS


def planner_with_result(result):
    planner = Planner(_rt(), modes=['walk'])
    planner.v.bike_router = SimpleNamespace(available=lambda: True, route=lambda *a: result, last_error=None)
    return planner


def test_unverified_access_is_not_extended_by_an_arbitrary_detour_factor():
    planner = planner_with_result({'distance_m': 300, 'optimistic': True,
        'foot_timing': {'flat_mps': FOOT_MPS, 'seconds': 300 / STEPS_MPS}})
    evidence = {}
    assert planner._walk_path(PLACES[0], PLACES[1], 400, evidence=evidence) == (None, None, True)
    assert evidence['status'] == 'unavailable'
    assert evidence['reason'] == 'unverified_walk_access'


def test_provider_without_internal_timing_keeps_legacy_distance_contract():
    planner = planner_with_result({'distance_m': 300, 'time_s': 500})
    distance, minutes, missing = planner._walk_path(PLACES[0], PLACES[1], 280)
    assert distance == 300 and minutes == 300 / planner.speed / 60 and not missing
    assert planner._walk_net(PLACES[0], PLACES[1], 280) == (300, False)


@pytest.mark.parametrize('seconds', [-1, float('nan'), float('inf')])
def test_corrupt_internal_seconds_are_rejected(seconds):
    planner = planner_with_result({'distance_m': 300, 'foot_timing': {'flat_mps': FOOT_MPS, 'seconds': seconds}})
    with pytest.raises(ValueError, match='보행망 내부 시간'):
        planner._walk_path(PLACES[0], PLACES[1], 280)


def test_zero_distance_internal_timing_stays_zero():
    planner = planner_with_result({'distance_m': 0, 'foot_timing': {'flat_mps': FOOT_MPS, 'seconds': 0}})
    assert planner._walk_path(PLACES[0], PLACES[0], 0) == (0, 0, False)
