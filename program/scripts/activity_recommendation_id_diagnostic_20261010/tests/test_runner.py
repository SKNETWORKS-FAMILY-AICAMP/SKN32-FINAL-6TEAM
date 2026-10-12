"""Response-double tests only: no provider SDK, credentials or live API calls."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('id_diagnostic_runner',HERE/'runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
sys.path.insert(0,str(runner.SHARED))
from fixtures import prepare_case,public_case

DATA=runner.ROOT/'datasets/travel/activity_recommendation_bench_20261009/retest-20261010'
CASES=[json.loads(line) for line in (DATA/'raw/v2/eval.jsonl').read_text(encoding='utf-8').splitlines()]
CONFIG=json.loads((runner.SHARED/'config.json').read_text(encoding='utf-8'))


def compact(public):
    result={k:v for k,v in public.items() if k!='candidates'}
    result['candidates']=[{'id':c['id'],'category':c['category'],'description':c['description'],
        'description_evidence_id':c['description_evidence_id'],'facts':{k:f['value'] for k,f in c['facts'].items()}} for c in public['candidates']]
    return result


def response(answer,status='completed'):
    return {'status':status,'model':'unit-response-double','usage':{'input_tokens':100,'output_tokens':10},
            'output':[{'content':[{'type':'output_text','text':json.dumps(answer)}]}]}


@pytest.fixture
def ready():
    return next(copy.deepcopy(c) for c in CASES if prepare_case(c)['status']=='ready' and len(prepare_case(c)['feasible_ids'])>=3)


def public_for(case):return public_case(case,prepare_case(case)['feasible_ids'])


def test_fixed_population_schedule_and_expected_paid_counts():
    choice=runner.schedule('choice',CASES,prepare_case,128)
    rank=runner.schedule('rank',CASES,prepare_case,128)
    assert len(choice)==48 and sum(j['planned_paid_calls'] for j in choice)==29
    assert len(rank)==20 and sum(j['planned_paid_calls'] for j in rank)==20
    eligible=sorted([c['case_id'] for c in CASES if prepare_case(c)['status']=='ready' and len(prepare_case(c)['feasible_ids'])>=2])[:10]
    assert [j['case_id'] for j in rank[::2]]==eligible
    assert [(rank[i]['lane'],rank[i+1]['lane']) for i in range(0,20,2)]==[('nano','luna'),('luna','nano')]*5


def test_rank_selection_ignores_case_order_and_quality_values():
    original=[c['case_id'] for c in runner.select_cases('rank',CASES,prepare_case)]
    changed=copy.deepcopy(list(reversed(CASES)))
    for c in changed:
        for candidate in c['candidates']:
            candidate['oracle_taste']=1-candidate['oracle_taste'];candidate['oracle_similarity']=0
    assert [c['case_id'] for c in runner.select_cases('rank',changed,prepare_case)]==original


def test_identical_rank_schema_none_512_and_no_citation_prompt(ready):
    nano,_=runner.rank_request('nano',public_for(ready),CONFIG,compact)
    luna,_=runner.rank_request('luna',public_for(ready),CONFIG,compact)
    assert nano['text']==luna['text'] and nano['input']==luna['input'] and nano['instructions']==luna['instructions']
    assert nano['reasoning']==luna['reasoning']=={'effort':'none'}
    assert nano['max_output_tokens']==luna['max_output_tokens']==512 and not nano['store']
    assert set(nano['text']['format']['schema']['properties'])=={'ranking'}
    assert nano['text']['format']['strict'] is True
    assert '최종값=weights.taste*취향등급' in nano['instructions']
    assert 'requested_count개' in nano['instructions']
    assert '인용' not in nano['instructions'] and 'quote' not in nano['instructions'] and '이유' not in nano['instructions']
    assert 'oracle_' not in nano['input']


@pytest.mark.parametrize('answer_kind',['extra','missing','short','long','duplicate','unknown','non_string','object','incomplete'])
def test_parser_rejects_every_invalid_contract_without_repair(ready,answer_kind):
    request,parse=runner.rank_request('nano',public_for(ready),CONFIG,compact)
    ids=request['text']['format']['schema']['properties']['ranking']['items']['enum'][:3]
    answer={'ranking':ids}
    if answer_kind=='extra':answer['reasons']=[]
    if answer_kind=='missing':answer={}
    if answer_kind=='short':answer['ranking']=ids[:2]
    if answer_kind=='long':answer['ranking']=ids+ids[:1]
    if answer_kind=='duplicate':answer['ranking']=[ids[0],ids[0],ids[2]]
    if answer_kind=='unknown':answer['ranking']=['unknown']+ids[1:]
    if answer_kind=='non_string':answer['ranking']=[{}]+ids[1:]
    if answer_kind=='object':answer['ranking']={}
    before=copy.deepcopy(answer)
    with pytest.raises((ValueError,TypeError)):
        parse(response(answer,'incomplete' if answer_kind=='incomplete' else 'completed'))
    assert answer==before


def test_parser_accepts_exact_two_and_three_ids_and_retains_order(ready):
    for case in (ready,next(c for c in CASES if len(prepare_case(c)['feasible_ids'])==2)):
        request,parse=runner.rank_request('luna',public_for(case),CONFIG,compact)
        schema=request['text']['format']['schema']['properties']['ranking']
        ids=list(reversed(schema['items']['enum']))[:schema['minItems']]
        assert schema['maxItems']==len(ids)
        assert parse(response({'ranking':ids}))['ranking']==ids


def runtime(events,initial_calls=0,fail=False,change_file=None):
    class FakeBudget:
        def __init__(self,path,cap,max_calls,baseline):
            events.append(('budget',str(path),cap,max_calls,baseline));self.count=initial_calls;self.locked=False
        @contextlib.contextmanager
        def run_lock(self):
            self.locked=True;events.append(('lock_enter',))
            try:yield
            finally:self.locked=False;events.append(('lock_exit',))
        def snapshot(self):return {'reserved_calls':self.count,'committed_usd':0.0,'cap_usd':.5,'max_calls':600}
    class FakeProviders:
        def __init__(self,budget,directory):
            assert budget.locked;self.budget=budget;self.directory=directory;events.append(('provider_init',))
        def call(self,lane,request,parser):
            self.budget.count+=1;events.append(('call',lane))
            if fail:raise RuntimeError('unit_abort')
            if change_file:change_file.write_text('changed by unit test',encoding='utf-8')
            enum=request['text']['format']['schema']['properties']['ranking']['items']['enum']
            count=request['text']['format']['schema']['properties']['ranking']['minItems']
            raw=response({'ranking':enum[:count]});call_id='unit-'+str(self.budget.count)
            runner.write_new(self.directory/'responses'/(call_id+'.json'),raw)
            return {'status':'ok',**parser(raw),'call_ids':[call_id],'usage':raw['usage'],'cost_usd':.00001,'latency_ms':5.0,'model':raw['model']}
        def choice(self,public):
            self.budget.count+=1;events.append(('choice',))
            raw={'answers':{},'model':'unit-choice','usage':{'input_tokens':90,'output_tokens':0}}
            call_id='choice-'+str(self.budget.count);runner.write_new(self.directory/'responses'/(call_id+'.json'),raw)
            return {'status':'ok','ranking':[public['candidates'][0]['id']],'call_ids':[call_id],'usage':raw['usage'],'cost_usd':.00001,'latency_ms':4.0,'model':'unit-choice'}
    def metrics(case,result,choice=False):
        events.append(('root_metrics',choice))
        return {'valid':True,'choice_scope':choice,'k':1 if choice else min(3,len(prepare_case(case)['feasible_ids']))}
    return SimpleNamespace(config=CONFIG,prepare=prepare_case,public=public_case,compact=compact,
                           Budget=FakeBudget,Providers=FakeProviders,root_metrics=metrics)


def test_state_and_single_bypass_do_not_construct_provider_or_call(ready,tmp_path):
    cases=[next(c for c in CASES if prepare_case(c)['status']=='facts_unresolved'),
           next(c for c in CASES if len(prepare_case(c)['feasible_ids'])==1)]
    events=[];rt=runtime(events)
    for case in cases:
        row=runner.execute_job({'lane':'jev','condition':'unit','arm':'unit'},case,rt,None,tmp_path)
        assert row['status']=='ok' and row['call_ids']==[] and row['cost_usd']==row['latency_ms']==0
        assert row['metrics']['choice_scope'] is True
    assert events==[('root_metrics',True),('root_metrics',True)]


def test_call_results_use_original_root_metrics_and_preserve_raw_usage(ready,tmp_path):
    events=[];rt=runtime(events);budget=rt.Budget(tmp_path/'unit-ledger',.5,600,.349834632)
    with budget.run_lock():
        provider=rt.Providers(budget,tmp_path)
        row=runner.execute_job({'lane':'nano','condition':'unit','arm':'unit'},ready,rt,provider,tmp_path)
    assert ('root_metrics',False) in events
    assert row['usage']==row['raw_call_records'][0]['usage']
    assert row['raw_call_records'][0]['response_file']=='responses/unit-1.json'
    assert row['cost_usd']==.00001 and row['latency_ms']==5
    assert row['human_review_count']==0 and not row['semantic_factuality_verified']
    assert not row['evidence_retrieval_performed'] and not row['citation_generation_requested']


def setup_run(tmp_path):
    source=tmp_path/'source.jsonl';source.write_text('unit source',encoding='utf-8')
    (tmp_path/'ledger.sqlite').touch()
    return source


def test_new_output_shared_budget_lock_and_frozen_metadata(ready,tmp_path):
    source=setup_run(tmp_path);events=[];rt=runtime(events)
    with contextlib.redirect_stdout(io.StringIO()):directory=runner.run('choice','unit-new',rt,[ready],source,tmp_path,[source,HERE/'runner.py'])
    assert events[0]==('budget',str(tmp_path/'ledger.sqlite'),.5,600,.349834632)
    assert events[1]==('lock_enter',) and events[-1]==('lock_exit',)
    metadata=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    finish=json.loads((directory/'finish.json').read_text(encoding='utf-8'))
    assert metadata['planned_paid_calls']==1 and metadata['auto_retries']==0
    assert metadata['human_review_count']==0 and finish['source_hashes_unchanged']
    assert finish['completed']==finish['planned']==1 and finish['stop'] is None
    before=(directory/'finish.json').read_bytes()
    with pytest.raises(FileExistsError):runner.run('choice','unit-new',rt,[ready],source,tmp_path,[source])
    assert (directory/'finish.json').read_bytes()==before


def test_call_slot_preflight_never_starts_provider(ready,tmp_path):
    source=setup_run(tmp_path);events=[]
    with pytest.raises(RuntimeError,match='insufficient_shared_call_slots'):
        runner.run('choice','unit-no-slots',runtime(events,initial_calls=600),[ready],source,tmp_path,[source])
    assert not (tmp_path/'runs/unit-no-slots').exists()
    assert not any(e[0]=='provider_init' for e in events)


def test_exception_has_no_retry_and_always_saves_finish(ready,tmp_path):
    source=setup_run(tmp_path);events=[]
    # rank stage requires ten eligible cases; a response double aborts the first.
    with pytest.raises(RuntimeError,match='unit_abort'),contextlib.redirect_stdout(io.StringIO()):
        runner.run('rank','unit-abort',runtime(events,fail=True),CASES,source,tmp_path,[source])
    assert sum(e[0]=='call' for e in events)==1
    finish=json.loads((tmp_path/'runs/unit-abort/finish.json').read_text(encoding='utf-8'))
    assert finish['completed']==0 and finish['stop']=='RuntimeError' and finish['source_hashes_unchanged']


def test_changed_frozen_file_is_detected_at_finish(tmp_path):
    source=setup_run(tmp_path);events=[]
    with pytest.raises(RuntimeError,match='frozen_sources_changed'),contextlib.redirect_stdout(io.StringIO()):
        runner.run('rank','unit-mutated',runtime(events,change_file=source),CASES,source,tmp_path,[source])
    finish=json.loads((tmp_path/'runs/unit-mutated/finish.json').read_text(encoding='utf-8'))
    assert not finish['source_hashes_unchanged']


def test_missing_shared_ledger_is_not_replaced(ready,tmp_path):
    source=tmp_path/'source';source.write_text('unit',encoding='utf-8')
    with pytest.raises(RuntimeError,match='existing_shared_ledger_required'):
        runner.run('choice','unit-missing',runtime([]),[ready],source,tmp_path,[source])
    assert not (tmp_path/'ledger.sqlite').exists()


@pytest.mark.parametrize('identifier',['../escape','a/b','a\\b','','x'*81])
def test_output_id_cannot_escape_new_run_directory(identifier,tmp_path):
    with pytest.raises(ValueError,match='invalid_run_id'):
        runner.run('choice',identifier,runtime([]),[],tmp_path/'source',tmp_path,[])


def test_hierarchical_choice_call_count_and_unknown_stage():
    assert [runner.choice_call_count(n,128) for n in (0,1,2,128,129,256)]==[0,0,1,1,3,3]
    with pytest.raises(ValueError):runner.schedule('unknown',CASES,prepare_case,128)
    with pytest.raises(ValueError):runner.choice_call_count(2,1)


def test_raw_call_records_preserve_multiple_responses_and_missing_raw(tmp_path):
    runner.write_new(tmp_path/'responses/a.json',{'usage':{'input_tokens':5,'output_tokens':0},'model':'first'})
    runner.write_new(tmp_path/'responses/b.json',{'usage':{'input_tokens':7,'output_tokens':0},'model':'second'})
    records=runner.response_records(tmp_path,{'call_ids':['a','b','failed-http']})
    assert sum(r.get('usage',{}).get('input_tokens',0) for r in records)==12
    assert [r.get('reported_model') for r in records]==['first','second',None]
    assert records[2]['response_file'] is None
    with pytest.raises(ValueError):runner.response_records(tmp_path,{'call_ids':['../outside']})
