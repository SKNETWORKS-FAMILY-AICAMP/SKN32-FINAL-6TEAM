"""실제 보행 그래프의 계단 시간과 현재 출발 안내를 연결한다."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.bike import BikeRouter
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from .test_departure_observer_v1 import NOW
from .test_review_fixes_plan import _rt, PLACES
from .test_walk_duration_contract_v1 import stair_router


def scene():
    runtime = _rt()
    runtime._v.bike_router = BikeRouter(stair_router())
    planner = Planner(runtime, modes={'walk'})
    got, reason = planner.leg(PLACES[0], PLACES[1], NOW+timedelta(hours=1), {}, False, 'walk')
    assert got, reason
    return runtime, planner.departure_context, got[0]['options'][0]


def call(runtime, context, **kwargs):
    args = dict(now=NOW, deadline=NOW+timedelta(hours=1), origin=PLACES[0], destination=PLACES[1])
    args.update(kwargs)
    return observe(runtime, context, 'walk', **args)


def test_generated_context_identifies_walk_and_real_stairs_are_rechecked():
    runtime, context, planned = scene()
    original = deepcopy(context)
    assert context['options']['walk']['path_kind'] == 'direct_walk'
    context['options']['walk']['eta_min'] = 999
    got = call(runtime, context, bus_arrival=lambda *a, **k: pytest.fail('버스 조회 금지'))
    assert got['status'] == 'model_revalidated' and got['eta_min'] == planned['eta_min'], got
    assert got['observations'][0]['source'] == 'walking_network'
    assert got['observations'][0]['foot_timing']
    assert context['options']['walk']['eta_min'] == 999
    context['options']['walk']['eta_min'] = original['options']['walk']['eta_min']
    assert context == original


def test_current_graph_duration_replaces_saved_route_duration():
    runtime, context, planned = scene()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True,
        route=lambda *a: {'distance_m': 600}, last_error=None)
    got = call(runtime, context)
    assert got['eta_min'] != planned['eta_min'] and got['walk_m'] == 600


def test_seconds_are_rounded_up_and_eta_includes_departure_rounding():
    runtime, context, planned = scene()
    got = call(runtime, context, now=NOW+timedelta(seconds=1))
    assert got['departure_at'].endswith('10:01:00+09:00')
    assert got['eta_min'] == planned['eta_min']+1


@pytest.mark.parametrize('marker', [None, 'vehicle', 'unknown'])
def test_empty_vehicle_or_legacy_context_is_not_inferred_to_be_walk(marker):
    runtime, context, _ = scene()
    context['options']['walk']['path_kind'] = marker
    assert call(runtime, context)['reason'] == 'route_check_missing_or_changed'


@pytest.mark.parametrize('problem', ['check', 'legs'])
def test_inconsistent_walk_context_is_held(problem):
    runtime, context, _ = scene()
    context['options']['walk'][problem] = {} if problem == 'check' else [{'mode': 'bus'}]
    assert call(runtime, context)['reason'] == 'walk_context_changed'


def test_explicit_no_path_is_held_and_not_replaced_by_straight_formula():
    runtime, context, _ = scene()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True,
        route=lambda *a: None, last_error={'kind': 'no_path'})
    got = call(runtime, context)
    assert got['status'] == 'needs_replan' and got['reason'] == 'no_walk_path'
    assert got['observations'][0]['status'] == 'no_path'


@pytest.mark.parametrize('router', [None, SimpleNamespace(available=lambda: True,
    route=lambda *a: None, last_error={'kind': 'router_down'})])
def test_missing_router_prevents_numeric_departure_guidance(router):
    runtime, context, _ = scene()
    runtime._v.bike_router = router
    got = call(runtime, context)
    assert got['status'] == 'fatal' and got['reason'] == 'walk_source_unavailable'
    assert got['observations'][0]['source'] == 'walking_network'
    assert got['observations'][0]['status'] == 'unavailable'
    assert not {'eta_min', 'arrival_at', 'departure_at'} & got.keys()


def test_operating_margin_is_required_even_when_walk_arrives_before_deadline():
    runtime, context, _ = scene()
    baseline = call(runtime, context)
    assert baseline['margin_min'] > 0
    deadline = NOW+timedelta(minutes=baseline['eta_min']+baseline['margin_min'])
    assert call(runtime, context, deadline=deadline)['status'] == 'model_revalidated'
    got = call(runtime, context, deadline=deadline-timedelta(seconds=1))
    assert got['reason'] == 'walk_arrive_late_or_margin'


def test_party_walk_policy_is_checked_again():
    runtime, context, _ = scene()
    runtime._v.R = deepcopy(runtime._v.R)
    runtime._v.R['limits']['walk_m']['default']['value'] = 1
    assert call(runtime, context)['reason'] == 'walk_limit_exceeded'


@pytest.mark.parametrize('distance', [-1, float('nan'), float('inf')])
def test_invalid_current_distance_is_never_published(distance):
    runtime, context, _ = scene()
    runtime._v.bike_router = SimpleNamespace(available=lambda: True,
        route=lambda *a: {'distance_m': distance}, last_error=None)
    assert call(runtime, context)['status'] == 'fatal'
