"""Contract tests using response doubles; no provider API calls or credentials."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

BENCH_PATH=Path(__file__).resolve().parents[1]/'bench.py'
spec=importlib.util.spec_from_file_location('activity_recommendation_bench_contract',BENCH_PATH)
bench=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


@pytest.fixture(autouse=True)
def isolated_config_and_no_network(monkeypatch):
    monkeypatch.setattr(bench,'CONFIG',copy.deepcopy(bench.CONFIG))
    def forbidden(*args,**kwargs):
        raise AssertionError('real provider calls are forbidden in contract tests')
    monkeypatch.setattr(bench.httpx,'post',forbidden)
    monkeypatch.setattr(bench,'OpenAI',forbidden)


def candidate(cid,taste,**overrides):
    row={'id':cid,'name':'가상시설','description':'직접 조립하는 체험을 합니다','category':'공방',
         'travel_min':10,'visit_min':30,'cost_krw':1000,'open':True,'unsafe':False,
         'step_free':True,'outdoor':False,'distance_km':1,
         'oracle_taste':taste,'oracle_similarity':1,'oracle_features':{'hidden':True}}
    row.update(overrides)
    return row


@pytest.fixture
def case():
    return {'case_id':'contract','group':'unit','customer':{'text':'직접 만드는 경험이 좋습니다',
        'preferences':{'likes':[{'trait':'체험','importance':1}],
                       'dislikes':[{'trait':'군중','penalty':.75}]}},
        'weights':{'taste':1,'travel':0,'similarity':0},'origin':{'category':'공방'},
        'constraints':{'budget_krw':1000,'time_budget_min':40,'require_step_free':True,
                       'rain':False,'allow_outdoor':True},
        'candidates':[candidate('best',1),candidate('second',.8),candidate('third',.6),candidate('fourth',.2)]}


def test_private_fields_are_removed_recursively_without_mutation():
    value={'customer':{'oracle_hidden':99,'text':'고객'},'candidates':[{'id':'x','oracle_taste':1,
            'nested':[{'gold':'answer','expected':'x','labels':[1],'description':'공개'}]}],
            'weights':{'taste':.5},'oracle_features':{'x':True}}
    original=copy.deepcopy(value)
    result=bench.public(value)
    assert result=={'customer':{'text':'고객'},'candidates':[{'id':'x','nested':[{'description':'공개'}]}],
                    'weights':{'taste':.5}}
    assert value==original
    result['customer']['text']='수정'
    assert value['customer']['text']=='고객'


@pytest.mark.parametrize('change',[
    {'open':False},{'unsafe':True},{'cost_krw':1001},{'visit_min':31},{'step_free':False}])
def test_each_hard_constraint_rejects_candidate(case,change):
    assert not bench.feasible(case,candidate('invalid',1,**change))


def test_constraint_boundaries_are_inclusive(case):
    assert bench.feasible(case,candidate('boundary',1))


@pytest.mark.parametrize('rain,allow,outdoor,expected',[
    (False,True,True,True),(True,True,True,False),(False,False,True,False),
    (True,False,False,True)])
def test_outdoor_restrictions(case,rain,allow,outdoor,expected):
    case['constraints'].update(rain=rain,allow_outdoor=allow)
    assert bench.feasible(case,candidate('outdoor',1,outdoor=outdoor)) is expected


def test_stepfree_is_required_only_when_customer_requires_it(case):
    case['constraints']['require_step_free']=False
    assert bench.feasible(case,candidate('stairs',1,step_free=False))


def test_gold_uses_hidden_oracle_not_public_keyword_scores(case,monkeypatch):
    case['candidates'][0]['description']='説明の内容で順位を変えない'
    monkeypatch.setattr(bench,'rule_scores',lambda *_:(0,0))
    assert [c['id'] for c in bench.gold(case)]==['best','second','third','fourth']
    case['candidates'][0]['open']=False
    assert bench.gold(case)[0]['id']=='second'


def test_travel_score_uses_minutes_not_straight_distance(case):
    case['weights']={'taste':0,'travel':1,'similarity':0}
    c=candidate('travel',1,travel_min=15,distance_km=100)
    assert bench.utility(case,c,0,0)==pytest.approx(.75)
    c['distance_km']=.001
    assert bench.utility(case,c,0,0)==pytest.approx(.75)
    c['travel_min']=90
    assert bench.utility(case,c,0,0)==0


def test_ndcg_and_recall_are_computed_from_gold_utility(case):
    scores=bench.evaluate(case,['second','best','fourth'])
    ideal=1+.8/math.log2(3)+.6/math.log2(4)
    selected=.8+1/math.log2(3)+.2/math.log2(4)
    assert scores['ndcg3']==pytest.approx(selected/ideal)
    assert scores['recall3']==pytest.approx(2/3)
    assert scores['top1_correct'] is False
    assert scores['regret_top1']==pytest.approx(.2)


def test_failed_output_has_zero_quality_and_keeps_a_case(case):
    scores=bench.evaluate(case,[])
    assert scores['ndcg3']==0
    assert scores['recall3']==0
    assert scores['top1_correct'] is False
    assert scores['regret_top1']==1


def test_unknown_and_hard_invalid_ids_are_not_replaced_with_gold(case):
    case['candidates'].append(candidate('closed',1,open=False))
    scores=bench.evaluate(case,['not-a-candidate','closed','fourth'])
    assert scores['selected']==['not-a-candidate','closed','fourth']
    assert scores['hard_violations']==2
    assert scores['ndcg3']<.1


class RecordingBudget:
    def __init__(self):self.events=[]
    def reserve(self,*args,**kwargs):
        self.events.append(('reserve',args,kwargs));return 'unit01',1.0
    def finish(self,*args):
        self.events.append(('finish',args));return .001


def fake_provider(tmp_path,response,events):
    provider=object.__new__(bench.Providers)
    provider.directory=tmp_path
    provider.budget=RecordingBudget()
    provider.jev_key='unit-test-placeholder'
    def create(**request):
        assert provider.budget.events[0][0]=='reserve'
        events.append(request)
        if isinstance(response,Exception):raise response
        return response
    provider.openai=SimpleNamespace(responses=SimpleNamespace(create=create))
    return provider


def response_double(answer,status='completed'):
    raw={'model':'test-model','id':'test-response','status':status,'output_text':json.dumps(answer),
         'usage':{'input_tokens':10,'output_tokens':5}}
    return SimpleNamespace(model=raw['model'],id=raw['id'],status=status,output_text=raw['output_text'],
                           model_dump=lambda **_:copy.deepcopy(raw))


def test_rank_reserves_before_call_and_never_sends_oracle(case,tmp_path):
    events=[];before=copy.deepcopy(case)
    provider=fake_provider(tmp_path,response_double({'ranking':['best','second','third'],
        'reasons':['좋음','다음','다음']}),events)
    result=provider.rank('nano',case,case['candidates'])
    request=events[0]
    assert 'oracle_' not in request['input']
    assert request['store'] is False
    assert 'tools' not in request
    assert case==before
    assert result['ranking']==['best','second','third']
    assert provider.budget.events[-1][0]=='finish'


@pytest.mark.parametrize('answer',[
    {'ranking':['best','best','third'],'reasons':['a','b','c']},
    {'ranking':['unknown','second','third'],'reasons':['a','b','c']},
    {'ranking':['best','second'],'reasons':['a','b','c']},
    {'ranking':['best','second','third'],'reasons':['a']},
    {'ranking':['best','second','third'],'reasons':[None,None,None]},
    {'ranking':['best','second','third'],'reasons':['a','b','c'],'extra':'unexpected'},
])
def test_invalid_rank_contract_is_rejected_not_repaired(case,tmp_path,answer):
    provider=fake_provider(tmp_path,response_double(answer),[])
    result=provider.rank('nano',case,case['candidates'])
    assert result['status']=='failed'
    assert 'ranking' not in result
    saved=json.loads((tmp_path/'responses'/'unit01.json').read_text(encoding='utf-8'))
    assert json.loads(saved['output_text'])==answer


def test_incomplete_response_and_transport_failure_keep_failure(case,tmp_path):
    provider=fake_provider(tmp_path,response_double({'ranking':['best','second','third'],
        'reasons':['a','b','c']},status='incomplete'),[])
    assert provider.rank('nano',case,case['candidates'])['status']=='failed'
    provider=fake_provider(tmp_path,TimeoutError('unit timeout'),[])
    result=provider.rank('luna',case,case['candidates'])
    assert result['status']=='failed'
    assert provider.budget.events[-1][1][2] is None


def test_saved_response_cannot_overwrite_existing_output(tmp_path):
    provider=object.__new__(bench.Providers);provider.directory=tmp_path
    provider.save_response('same',{'original':1})
    with pytest.raises(RuntimeError,match='response_already_exists'):
        provider.save_response('same',{'replacement':2})
    assert json.loads((tmp_path/'responses'/'same.json').read_text(encoding='utf-8'))=={'original':1}


@pytest.fixture
def budget(tmp_path,monkeypatch):
    config=copy.deepcopy(bench.CONFIG)
    config['budget_usd']=1
    config['max_paid_calls']=100
    config['prices_per_million_usd']['nano']={'input':1,'cached_input':.1,'cache_write':2,'output':3}
    monkeypatch.setattr(bench,'CONFIG',config)
    return bench.Budget(tmp_path)


def test_unknown_usage_keeps_full_reservation(budget):
    call,upper=budget.reserve('nano',{'content':'짧은 입력'},output_limit=100)
    assert budget.spent()==upper
    assert budget.finish(call,'nano',None,upper)==upper
    assert budget.spent()==upper
    reloaded=bench.Budget(budget.path.parent)
    assert reloaded.spent()==upper


def test_cache_read_write_are_charged_at_distinct_rates(budget):
    call,upper=budget.reserve('nano',{},output_limit=100)
    usage={'input_tokens':1000,'output_tokens':100,
           'input_tokens_details':{'cached_tokens':200,'cache_write_tokens':300}}
    amount=budget.finish(call,'nano',usage,upper)
    assert amount==pytest.approx((500*1+200*.1+300*2+100*3)/1e6)
    assert budget.spent()==amount


def test_top_level_cache_usage_is_supported(budget):
    call,upper=budget.reserve('nano',{},output_limit=100)
    usage={'input_tokens':1000,'output_tokens':0,'cached_input_tokens':400,'cache_creation_input_tokens':100}
    assert budget.finish(call,'nano',usage,upper)==pytest.approx((500+40+200)/1e6)


@pytest.mark.parametrize('usage',[
    {'input_tokens':-1,'output_tokens':0}, {'input_tokens':1,'output_tokens':-1},
    {'input_tokens':100,'output_tokens':1,'cached_input_tokens':-1},
    {'input_tokens':100,'output_tokens':1,'cache_creation_input_tokens':-1},
    {'input_tokens':True,'output_tokens':1},
    {'input_tokens':100,'output_tokens':1,'cached_input_tokens':101},
])
def test_invalid_token_usage_cannot_reduce_budget(budget,usage):
    call,upper=budget.reserve('nano',{})
    with pytest.raises((RuntimeError,ValueError,TypeError)):
        budget.finish(call,'nano',usage,upper)
    assert budget.spent()>=upper


def test_budget_rejects_request_before_reserving_when_limit_too_small(budget,monkeypatch):
    bench.CONFIG['budget_usd']=0
    with pytest.raises(RuntimeError,match='budget_stop'):
        budget.reserve('nano',{'content':'x'})
    assert not budget.rows


def test_paid_call_limit_is_preserved_across_restarts(budget):
    bench.CONFIG['max_paid_calls']=1
    budget.reserve('nano',{})
    reloaded=bench.Budget(budget.path.parent)
    with pytest.raises(RuntimeError,match='budget_stop'):
        reloaded.reserve('nano',{})


def test_actual_reservation_excess_is_charged_and_future_calls_stop(budget):
    call,upper=budget.reserve('nano',{})
    actual=100000*1/1e6
    with pytest.raises(RuntimeError,match='reservation_exceeded'):
        budget.finish(call,'nano',{'input_tokens':100000,'output_tokens':0},upper)
    assert budget.spent()>=actual
    with pytest.raises(RuntimeError):budget.reserve('nano',{})


def test_jev_questions_never_receive_private_fields(case,tmp_path,monkeypatch):
    provider=fake_provider(tmp_path,None,[])
    captured=[]
    def post(url,**kwargs):
        request=kwargs['json'];captured.append(request)
        assert provider.budget.events[0][0]=='reserve'
        assert 'oracle_' not in json.dumps(request)
        raw={'answers':{k:{'noul':.5} for k in request['questions']},'usage':None,'model':'decision-test'}
        return SimpleNamespace(is_success=True,json=lambda:raw)
    monkeypatch.setattr(bench.httpx,'post',post)
    result=provider.score(case,case['candidates'])
    assert result['status']=='ok'
    assert len(captured[0]['questions'])==8
    assert len(result['ranking'])==4


@pytest.mark.parametrize('answer',[-.1,1.1,True,None,float('nan')])
def test_jev_invalid_probability_is_failure_not_zero_default(case,tmp_path,monkeypatch,answer):
    provider=fake_provider(tmp_path,None,[])
    def post(url,**kwargs):
        raw={'answers':{k:{'noul':answer} for k in kwargs['json']['questions']},'usage':None}
        return SimpleNamespace(is_success=True,json=lambda:raw)
    monkeypatch.setattr(bench.httpx,'post',post)
    result=provider.score(case,case['candidates'])
    assert result['status']=='failed'
    assert 'ranking' not in result


def test_run_persists_failed_direct_and_blocked_cascade_cases(case,tmp_path,monkeypatch,capsys):
    config=copy.deepcopy(bench.CONFIG)
    config.update(dataset_directory='fixture',pause_seconds=0,repeats=1)
    monkeypatch.setattr(bench,'CONFIG',config)
    monkeypatch.setattr(bench,'ROOT',tmp_path)
    data=tmp_path/'fixture'/'raw';data.mkdir(parents=True)
    second=copy.deepcopy(case);second['case_id']='contract2'
    text='\n'.join(json.dumps(x,ensure_ascii=False) for x in (case,second))+'\n'
    for name in ('smoke.jsonl','scenarios.jsonl','smoke-v2.jsonl','scenarios-v2.jsonl'):
        (data/name).write_text(text,encoding='utf-8')
    class NoCostBudget:
        def __init__(self,*args):pass
        def spent(self):return 0
    class FailureProviders:
        def __init__(self,*args):pass
        def rank(self,*args):return {'status':'failed','cost_usd':0,'latency_ms':0}
        def score(self,*args):return {'status':'failed','call_id':'failed-filter','cost_usd':0,'latency_ms':0}
    monkeypatch.setattr(bench,'Budget',NoCostBudget)
    monkeypatch.setattr(bench,'Providers',FailureProviders)
    bench.run(argparse.Namespace(run_id='unit-only',smoke=True))
    rows=[json.loads(s) for s in (tmp_path/'fixture'/'runs'/'unit-only'/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    for arm in ('nano_direct','luna_direct','jev_nano','jev_luna'):
        selected=[r for r in rows if r['arm']==arm]
        assert len(selected)==2
        assert sum(r['metrics']['top1_correct'] for r in selected)==0
        assert all(r['metrics']['ndcg3']==0 for r in selected)
        assert all(r['status']!='ok' for r in selected)


def test_unit_suite_does_not_mutate_code_config_prompt():
    # This assertion documents the mutable-vs-frozen boundary. Tests only replace
    # in-memory references and response doubles; fixture directories are temporary.
    for path in (BENCH_PATH,BENCH_PATH.parent/'config.json',BENCH_PATH.parent/'rank-prompt.txt'):
        before=hashlib.sha256(path.read_bytes()).hexdigest()
        bench.public({'oracle_secret':1,'text':'보존'})
        assert hashlib.sha256(path.read_bytes()).hexdigest()==before
