"""합성 구간의 옵션료가 계획·저장·현재 출발 안내까지 한 번만 전달된다."""
from copy import deepcopy
from datetime import timedelta

import pytest

from app.domains.travel_ops.instances.mobility.engine.errors import CaseInputError
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.taxi_budget import normalize_fees, selected_fee, with_option_fee
from .test_departure_taxi_v1 import NOW, call
from .test_review_fixes_plan import _rt, PLACES
from .test_taxi_cost_components_v1 import service


def quote(**changes):
    return {**{'from': PLACES[0]['key'], 'to': PLACES[1]['key'], 'fee_won': 2500,
               'valid_from': (NOW-timedelta(hours=1)).isoformat(),
               'valid_until': (NOW+timedelta(hours=2)).isoformat(), 'source': '호출 화면 입력'}, **changes}


def scene(values=None):
    runtime = _rt()
    runtime._v.car = service()
    planner = Planner(runtime, modes={'taxi'}, taxi_option_fees=values)
    deadline = NOW+timedelta(hours=1)
    got, reason = planner.leg(PLACES[0], PLACES[1], deadline, {}, False, 'taxi_fee')
    assert got, reason
    return runtime, planner.departure_context, got[0], deadline


def test_known_fee_is_added_once_without_multiplying_the_reserve():
    original = service().leg((127,37.5),(127.01,37.5),NOW,taxi=True)
    snapshot = deepcopy(original)
    updated = with_option_fee(original, quote())
    assert updated['fare_won'] == original['fare_won']+2500
    for key in ('meter_won','planning_reserve_won','toll_won','planning_reserve_rate'):
        assert updated[key] == original[key]
    assert '옵션료 2,500원' in updated['fare_basis']
    assert '확인 옵션료 포함' in updated['fare_basis'] and '미포함' not in updated['fare_basis']
    assert original == snapshot
    with pytest.raises(CaseInputError, match='중복'):
        with_option_fee(updated, quote())


def test_selected_quote_survives_plan_context_and_current_departure():
    values = [quote()]
    saved = deepcopy(values)
    runtime, context, route, deadline = scene(values)
    assert route['options'][0]['fare_krw'] == 14100
    assert context['options']['taxi']['taxi_option_fee'] == values[0]
    values[0]['fee_won'] = 99999
    result = call(runtime, context, deadline)
    assert result['status'] == 'model_revalidated'
    assert result['fare_krw'] == 14100
    assert '옵션료 2,500원' in result['route_label']
    assert context['options']['taxi']['taxi_option_fee'] == saved[0]


def test_default_general_has_official_zero_platform_fee():
    runtime, context, route, deadline = scene()
    assert 'taxi_option_fee' not in context['options']['taxi']
    result = call(runtime, context, deadline)
    assert result['fare_krw'] == 11600
    assert context['options']['taxi']['taxi_call_product'] == 'kakao_general'
    assert '일반호출 0원' in result['route_label']


@pytest.mark.parametrize('changes', [
    {'from': '다른_장소'}, {'to': '다른_목적지'},
    {'valid_until': NOW.isoformat(), 'valid_from': (NOW-timedelta(hours=1)).isoformat()},
    {'valid_from': (NOW+timedelta(hours=2)).isoformat(), 'valid_until': (NOW+timedelta(hours=3)).isoformat()},
])
def test_other_route_or_outdated_quote_does_not_apply(changes):
    _, context, route, _ = scene([quote(**changes)])
    assert route['options'][0]['fare_krw'] == 11600
    assert 'taxi_option_fee' not in context['options']['taxi']


def test_expired_saved_quote_requires_refresh_before_a_road_query():
    runtime, context, _, deadline = scene([quote()])
    runtime._v.car = None
    # 대체 조회가 아니라 옵션료 만료를 확인할 수 있도록 서비스 껍데기만 둔다.
    class Uncalled:
        def leg(self, *args, **kwargs):
            pytest.fail('만료된 옵션료를 새 도로 조회로 덮으면 안 됩니다')
    runtime._v.car = Uncalled()
    result = call(runtime, context, deadline+timedelta(hours=4), now=NOW+timedelta(hours=2))
    assert result['status'] == 'needs_replan'
    assert result['reason'] == 'taxi_option_fee_expired_or_changed'
    assert 'fare_krw' not in result


@pytest.mark.parametrize('bad', [True,-1,1.5,float('nan'),float('inf'),'2500'])
def test_bad_fee_is_rejected_before_a_model_query(bad):
    with pytest.raises(CaseInputError):
        normalize_fees([quote(fee_won=bad)])


@pytest.mark.parametrize('changes', [
    {'source':''}, {'valid_from':'2026-10-12T10:00:00'}, {'valid_until':'bad'},
    {'valid_until':(NOW-timedelta(days=1)).isoformat()}, {'extra':'unexpected'},
])
def test_incomplete_or_ambiguous_quote_is_rejected(changes):
    with pytest.raises(CaseInputError):
        normalize_fees([quote(**changes)])


def test_duplicate_and_reversed_route_and_boundary_are_distinguished():
    with pytest.raises(CaseInputError, match='중복'):
        normalize_fees([quote(),quote()])
    fees = normalize_fees([quote(fee_won=0)])
    assert selected_fee(fees,PLACES[1],PLACES[0],NOW) is None
    assert selected_fee(fees,PLACES[0],PLACES[1],NOW)['fee_won'] == 0
    assert selected_fee(fees,PLACES[0],PLACES[1],NOW+timedelta(hours=2)) is None
