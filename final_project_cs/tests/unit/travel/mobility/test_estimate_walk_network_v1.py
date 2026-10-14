"""시간대 추정도 같은 보행망 거리·계단 시간을 사용합니다. 합성 경로 시험입니다."""
import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine.bike import BikeRouter
from app.domains.travel_ops.instances.mobility.engine.graph_router import FOOT_MPS
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.plan_estimate import Estimator, estimate
from .test_review_fixes_plan import _rt, PLACES
from .test_walk_duration_contract_v1 import stair_router


def run_estimate(result=None, error=None, modes=None, runtime=None, public=False):
    rt = runtime or _rt()
    calls = []
    if runtime is None:
        def route(*args):
            calls.append(args)
            return result
        rt._v.bike_router = SimpleNamespace(available=lambda: True, route=route,
                                           last_error=error)
    samples = []
    kwargs = dict(modes=modes or ['walk'], window=(720, 740), step=5, samples=samples)
    if public:
        kwargs.pop('window')
        out = estimate(PLACES[0], PLACES[1], '2026-10-09', '오후', runtime=rt, **kwargs)
    else:
        est = Estimator(rt, modes=kwargs.pop('modes'))
        out = est.estimate(PLACES[0], PLACES[1], '2026-10-09', '오후', **kwargs)
    return out, samples, calls


@pytest.mark.parametrize('distance', [150, 650, 1500])
def test_routed_distance_controls_time_with_existing_straight_policy(distance):
    out, samples, calls = run_estimate({'distance_m': distance})
    expected = max(1, math.ceil(distance / Planner(_rt(), modes=['walk']).speed / 60))
    assert {x['eta'] for x in samples} == {expected}
    assert out['eta']['p50_min'] == expected
    assert len(calls) == 1, '같은 시간창의 직접 도보는 한 번만 조회합니다'
    assert out['walk_basis']['source'] == 'walking_network'


def test_real_synthetic_stair_graph_has_same_time_as_schedule():
    rt = _rt()
    rt._v.bike_router = BikeRouter(stair_router())
    out, samples, _ = run_estimate(runtime=rt)
    p = Planner(rt, modes=['walk'])
    target = datetime(2026, 10, 9, 12, tzinfo=timezone(timedelta(hours=9)))
    (route, *_), _reason = p.leg(PLACES[0], PLACES[1], target, {}, False, 'estimate-stairs')
    option = next(x for x in route['options'] if x['id'] == 'walk')
    assert out['eta']['p50_min'] == option['eta_min']
    assert {x['eta'] for x in samples} == {option['eta_min']}
    assert option['eta_min'] > math.ceil(option['walk_m'] / p.speed / 60)
    assert out['walk_basis']['foot_timing'] is True


def test_missing_network_path_is_not_a_feasible_direct_walk():
    out, samples, calls = run_estimate(error={'kind': 'no_path'})
    assert out['verdict'] == 'no_data'
    assert '보행망' in out['reason']
    assert out['walk_basis']['status'] == 'no_path'
    assert not samples and len(calls) == 1


@pytest.mark.parametrize('error', ['router_down', 'bad_response', 'out_of_area'])
def test_route_failure_does_not_generate_distance_or_eta(error):
    out, samples, calls = run_estimate(error={'kind': error})
    assert out['verdict'] == 'no_data'
    assert out['walk_basis']['source'] == 'walking_network'
    assert out['walk_basis']['status'] == 'unavailable'
    assert out['walk_basis']['reason'] == error
    assert len(calls) == 1 and not samples


def test_unverified_access_does_not_get_a_straight_distance_correction():
    result = {'distance_m': 100, 'optimistic': True,
              'foot_timing': {'flat_mps': FOOT_MPS, 'seconds': 100 / (FOOT_MPS * .6)}}
    out, samples, _ = run_estimate(result)
    assert out['verdict'] == 'no_data' and not samples
    assert out['walk_basis']['reason'] == 'unverified_walk_access'


def test_disabled_walk_does_not_query_walking_network():
    out, _samples, calls = run_estimate({'distance_m': 650}, modes=['subway'])
    assert not calls and 'walk_basis' not in out
    assert out['verdict'] == 'no_data'


def test_public_estimate_function_carries_new_basis_and_version():
    out, _samples, calls = run_estimate({'distance_m': 650}, public=True)
    assert out['walk_basis']['source'] == 'walking_network'
    assert out['basis']['estimate_version'] == 'estimate-v1.2'
    assert len(calls) == 1


def test_no_router_reports_unavailable_without_eta():
    rt = _rt()
    rt._v.bike_router = None
    out, _samples, _ = run_estimate(runtime=rt)
    assert out['verdict'] == 'no_data'
    assert 'eta' not in out or out['eta'] is None
    assert out['walk_basis'] == {'source': 'walking_network', 'status': 'unavailable',
                                 'reason': 'walking_router_unavailable'}
