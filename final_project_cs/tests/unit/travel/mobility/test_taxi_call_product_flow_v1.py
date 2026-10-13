"""사전 상품·견적의 계획→저장→현재 출발 경로. 합성 여행이며 결제 측정이 아니다."""
from copy import deepcopy
from datetime import timedelta

import pytest

from app.domains.travel_ops.instances.mobility.engine.errors import CaseInputError
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.taxi_pricing import with_call_product
from .test_departure_taxi_v1 import NOW, call
from .test_review_fixes_plan import _rt, PLACES
from .test_taxi_cost_components_v1 import service


def quote(**changes):
    return {**{'from':'P1','to':'P2','fee_won':2500,
               'quoted_at':(NOW-timedelta(hours=2)).isoformat(),
               'valid_from':(NOW-timedelta(hours=1)).isoformat(),
               'valid_until':(NOW+timedelta(hours=2)).isoformat(),
               'source':'호출 전 앱 화면의 이용료'},**changes}


def scene(**kwargs):
    runtime=_rt()
    runtime._v.car=service()
    planner=Planner(runtime,modes={'taxi'},**kwargs)
    deadline=NOW+timedelta(hours=1)
    got,why=planner.leg(PLACES[0],PLACES[1],deadline,{},False,'taxi')
    assert got,why
    return runtime,planner.departure_context,got[0],deadline


def test_default_is_explicit_general_call_with_official_zero_platform_fee():
    runtime,context,route,deadline=scene()
    assert context['options']['taxi']['taxi_call_product']=='kakao_general'
    assert 'taxi_call_quote' not in context['options']['taxi']
    assert '일반호출 0원' in route['options'][0]['label']
    result=call(runtime,context,deadline)
    assert result['fare_krw']==route['options'][0]['fare_krw']==11600
    assert '일반호출 0원' in result['route_label']
    assert '실제 결제 상한 아님' in result['route_label']


def test_legacy_helper_cannot_add_a_second_fee_to_new_product_budget():
    from app.domains.travel_ops.instances.mobility.engine.taxi_budget import with_option_fee
    model=with_call_product({'fare_won':10000},'capsi_immediate',NOW)
    before=deepcopy(model)
    with pytest.raises(CaseInputError,match='중복'):
        with_option_fee(model,{'fee_won':3000})
    assert model==before


@pytest.mark.parametrize('product',['km_blue_immediate','turu_blue_immediate','capsi_immediate','mycap_immediate'])
def test_catalog_upper_bound_is_added_once_and_recomputed_at_night(product):
    runtime,context,route,deadline=scene(taxi_call_product=product)
    before=deepcopy(context)
    assert route['options'][0]['fare_krw']==14600
    assert '0~3,000원(상단반영)' in route['options'][0]['label']
    now=NOW.replace(hour=22)
    result=call(runtime,context,now+timedelta(hours=1),now=now)
    base=service().leg((127,37.5),(127.01,37.5),now,taxi=True)
    assert result['fare_krw']==base['fare_won']+5000
    assert '0~5,000원(상단반영)' in result['route_label']
    assert context==before


@pytest.mark.parametrize('product',['mycap_immediate','capsi_immediate','blue_partners_immediate'])
def test_pretrip_quote_is_carried_without_using_a_receipt(product):
    values=[quote()]
    runtime,context,route,deadline=scene(taxi_call_product=product,taxi_call_quotes=values)
    saved=deepcopy(context)
    values[0]['fee_won']=99999
    assert route['options'][0]['fare_krw']==14100
    assert context['options']['taxi']['taxi_call_quote']['fee_won']==2500
    result=call(runtime,context,deadline)
    assert result['fare_krw']==14100
    assert '2,500원(사전견적)' in result['route_label']
    assert context==saved


@pytest.mark.parametrize('product',['blue_partners_immediate','reservation','unknown'])
def test_unconfirmed_product_never_gets_zero_fee(product):
    with pytest.raises(CaseInputError):
        scene(taxi_call_product=product)


@pytest.mark.parametrize('change',[
    {'taxi_call_product':None}, {'taxi_call_product':[]},
    {'taxi_call_product':'reservation'},
    {'taxi_call_quote':quote(to='different')},
    {'taxi_call_quote':quote(valid_until=NOW.isoformat())},
    {'taxi_call_quote':{k:v for k,v in quote().items() if k!='quoted_at'}},
    {'taxi_option_fee':{k:v for k,v in quote().items() if k!='quoted_at'}},
])
def test_saved_invalid_or_expired_quote_fails_before_road_query(change):
    runtime,context,_,deadline=scene(taxi_call_product='mycap_immediate',taxi_call_quotes=[quote()])
    context['options']['taxi'].update(change)
    class Uncalled:
        def leg(self,*a,**kw):
            pytest.fail('잘못된 사전 견적을 도로 조회로 덮으면 안 됩니다')
    runtime._v.car=Uncalled()
    result=call(runtime,context,deadline)
    assert result['status']=='needs_replan'
    assert 'fare_krw' not in result


def test_quote_without_product_and_legacy_conflict_are_explicit():
    runtime,context,_,deadline=scene(taxi_call_product='mycap_immediate',taxi_call_quotes=[quote()])
    del context['options']['taxi']['taxi_call_product']
    assert call(runtime,context,deadline)['reason']=='taxi_call_product_missing'
    with pytest.raises(CaseInputError,match='함께'):
        Planner(_rt(),taxi_option_fees=[],taxi_call_product='kakao_general')


def test_fee_never_multiplies_reserve_and_missing_components_are_not_zero():
    model=service().leg((127,37.5),(127.01,37.5),NOW,taxi=True)
    before=deepcopy(model)
    result=with_call_product(model,'km_blue_immediate',NOW)
    assert result['fare_won']==model['fare_won']+3000
    for key in ('meter_won','planning_reserve_won','toll_won','planning_reserve_rate'):
        assert result[key]==model[key]
    assert model==before
    with pytest.raises(CaseInputError,match='중복'):
        with_call_product(result,'km_blue_immediate',NOW)
    partial=with_call_product({'fare_won':12000},'kakao_general',NOW)
    assert '구성 금액 미전달' in partial['fare_basis']
    assert '미터 추정 0원' not in partial['fare_basis'] and '통행료 0원' not in partial['fare_basis']


@pytest.mark.parametrize('product',['km_blue_immediate','turu_blue_immediate','capsi_immediate','mycap_immediate'])
def test_wrong_product_or_reservation_quote_exceeding_official_bound_is_rejected(product):
    with pytest.raises(CaseInputError,match='범위'):
        scene(taxi_call_product=product,taxi_call_quotes=[quote(fee_won=10000)])


def test_invalid_product_is_checked_before_the_plan_road_query():
    runtime=_rt()
    class Uncalled:
        def leg(self,*a,**kw):
            pytest.fail('상품 검사 전 도로 조회 금지')
    runtime._v.car=Uncalled()
    planner=Planner(runtime,modes={'taxi'},taxi_call_product='reservation')
    with pytest.raises(CaseInputError):
        planner.leg(PLACES[0],PLACES[1],NOW+timedelta(hours=1),{},False,'taxi')


@pytest.mark.parametrize('changes',[
    {'taxi_call_product':'km_blue_immediate'},
    {'taxi_call_product':'capsi_immediate','taxi_call_quotes':[quote()]},
    {'taxi_option_fees':[{k:v for k,v in quote().items() if k!='quoted_at'}]},
])
def test_current_trip_pricing_change_cannot_keep_the_saved_general_price(monkeypatch,changes):
    from app.domains.travel_ops.instances.mobility import wiring
    runtime,context,_,deadline=scene()
    monkeypatch.setitem(wiring._STATE,'mode','enabled')
    monkeypatch.setitem(wiring._STATE,'kw',{})
    monkeypatch.setattr(wiring.engine_runtime,'get_verifier',lambda **kw:runtime)
    result=wiring.observe_departure(context,'taxi',trip={'constraints':changes,'party_size':2},
        now=NOW,deadline=deadline,origin=PLACES[0],destination=PLACES[1])
    assert result=={'status':'needs_replan','reason':'taxi_call_pricing_changed'}


def test_current_matching_quote_is_accepted_and_new_quote_requires_replan():
    from app.domains.travel_ops.instances.mobility.engine.taxi_pricing import matches_current_pricing
    _,context,_,_=scene(taxi_call_product='capsi_immediate',taxi_call_quotes=[quote()])
    option=context['options']['taxi']
    constraints={'taxi_call_product':'capsi_immediate','taxi_call_quotes':[quote()]}
    assert matches_current_pricing(option,constraints,PLACES[0],PLACES[1])
    constraints['taxi_call_quotes'][0]['fee_won']=3000
    assert not matches_current_pricing(option,constraints,PLACES[0],PLACES[1])
