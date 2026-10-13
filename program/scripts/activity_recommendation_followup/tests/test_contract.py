"""Self-authored development tests; no provider API, credentials or app imports."""
import copy
from datetime import datetime,timedelta
import importlib.util
import json
from pathlib import Path
import random
import sys

import pytest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from contract import FACT_TYPES,prepare,validate_output
from dev_suite import answer_for,make_fixture,run_development


def controlled(n=4):
    payload=make_fixture(n)
    for i,candidate in enumerate(payload['candidates']):
        candidate['taste']=(i+1)/(n+1);candidate['similarity']=.5
        values={'open':True,'unsafe':False,'cost_krw':1000,'travel_min':10,
                'visit_min':20,'step_free':True,'outdoor':False}
        for k,v in values.items():candidate['facts'][k]['value']=v
    return payload


@pytest.mark.parametrize('n,expected,count',[(0,'no_feasible_candidates',0),(1,'ready',1),(2,'ready',2),(3,'ready',3),(4,'ready',3)])
def test_candidate_counts_do_not_invent_three_recommendations(n,expected,count):
    result=prepare(controlled(n))
    assert result['status']==expected
    assert result['requested_count']==count
    assert result['human_review_count']==0
    if count:assert validate_output(result,answer_for(result))['valid']


@pytest.mark.parametrize('name,reason',[('open','closed'),('unsafe','unsafe'),('cost_krw','budget'),
    ('travel_min','total_time'),('step_free','step_free'),('outdoor','outdoor_restriction')])
def test_each_hard_constraint_blocks_candidate(name,reason):
    payload=controlled(1)
    change={'open':False,'unsafe':True,'cost_krw':20001,'travel_min':81,'step_free':False,'outdoor':True}
    payload['customer']['allow_outdoor']=False
    payload['candidates'][0]['facts'][name]['value']=change[name]
    result=prepare(payload)
    assert result['status']=='no_feasible_candidates'
    assert reason in result['rejected'][0]['reasons']


def test_budget_and_total_time_boundaries_are_inclusive():
    payload=controlled(1)
    payload['customer'].update(budget_krw=1000,time_budget_min=30)
    assert prepare(payload)['status']=='ready'


@pytest.mark.parametrize('rain,allowed,outdoor,ready',[(False,True,True,True),(True,True,True,False),
    (False,False,True,False),(True,False,False,True)])
def test_rain_and_outdoor_permissions(rain,allowed,outdoor,ready):
    payload=controlled(1);payload['customer'].update(rain=rain,allow_outdoor=allowed)
    payload['candidates'][0]['facts']['outdoor']['value']=outdoor
    assert (prepare(payload)['status']=='ready') is ready


def test_low_taste_is_soft_and_does_not_remove_feasible_candidate():
    payload=controlled(1);payload['candidates'][0]['taste']=0
    assert prepare(payload)['status']=='ready'


@pytest.mark.parametrize('seconds,status',[(0,'ready'),(60,'ready'),(61,'facts_unresolved'),(-1,'facts_unresolved')])
def test_fact_age_and_future_timestamp(seconds,status):
    payload=controlled(1)
    payload['candidates'][0]['facts']['open']['observed_at']=(datetime.fromisoformat(payload['as_of'])-timedelta(seconds=seconds)).isoformat()
    result=prepare(payload)
    assert result['status']==status
    if status=='facts_unresolved':assert result['requested_count']==0


@pytest.mark.parametrize('edit,reason',[
    (lambda c:c['facts'].pop('open'),'missing_fact'),
    (lambda c:c.pop('facts'),'missing_fact'),
    (lambda c:c['facts']['open'].pop('value'),'missing_value'),
    (lambda c:c['facts']['open'].update(value=None),'missing_value'),
    (lambda c:c['facts']['open'].pop('observed_at'),'missing_timestamp'),
    (lambda c:c['facts']['open'].pop('evidence_id'),'missing_evidence')])
def test_missing_fact_blocks_whole_request_instead_of_normal_fallback(edit,reason):
    payload=controlled(4);edit(payload['candidates'][0])
    result=prepare(payload)
    assert result['status']=='facts_unresolved'
    assert result['eligible']==[] and result['ranked_ids']==[]
    assert reason in [r['reason'] for r in result['unresolved_facts']]


@pytest.mark.parametrize('value',[-1,float('nan'),float('inf'),True,'1',10**1000])
def test_invalid_numeric_fact_is_invalid_input(value):
    payload=controlled(1);payload['candidates'][0]['facts']['travel_min']['value']=value
    assert prepare(payload)['status']=='invalid_input'


@pytest.mark.parametrize('edit',[
    lambda p:p.update(extra=True),lambda p:p['customer'].update(extra=True),
    lambda p:p['weights'].update(extra=True),lambda p:p['candidates'][0].update(extra=True),
    lambda p:p['candidates'][0]['facts'].update(extra=True),
    lambda p:p['candidates'][0]['facts']['open'].update(extra=True)])
def test_unknown_fields_are_rejected_at_every_contract_level(edit):
    payload=controlled(1);edit(payload)
    assert prepare(payload)['status']=='invalid_input'


@pytest.mark.parametrize('edit',[
    lambda p:p['candidates'][0]['facts']['open'].update(value=1),
    lambda p:p['customer'].update(rain=1),lambda p:p['weights'].update(taste=True),
    lambda p:p['weights'].update(taste=-.2),lambda p:p.update(max_age_seconds=0),
    lambda p:p.update(as_of='2026-10-10T12:00:00'),
    lambda p:p['candidates'][0]['facts']['open'].update(observed_at='2026-10-10T12:00:00')])
def test_invalid_boolean_weight_and_timestamp_contracts(edit):
    payload=controlled(1);edit(payload)
    assert prepare(payload)['status']=='invalid_input'


def test_duplicate_candidate_id_is_rejected():
    payload=controlled(2);payload['candidates'][1]['id']=payload['candidates'][0]['id']
    assert prepare(payload)['status']=='invalid_input'


def test_preparation_and_validation_do_not_mutate_request():
    payload=controlled(4);before=copy.deepcopy(payload)
    result=prepare(payload);response=answer_for(result);response_before=copy.deepcopy(response)
    validate_output(result,response)
    assert payload==before and response==response_before


@pytest.mark.parametrize('edit',[
    lambda r:r.update(extra=1),lambda r:r['ranking'].append('unknown'),
    lambda r:r['ranking'].__setitem__(0,'unknown'),
    lambda r:r['ranking'].__setitem__(0,r['ranking'][1]),
    lambda r:r['reasons'][0].update(extra=1),lambda r:r['reasons'][0].update(text=''),
    lambda r:r['reasons'][0].update(evidence_ids=['not-present']),
    lambda r:r['reasons'][0].update(evidence_ids=[]),
    lambda r:r['reasons'][0].update(candidate_id='unknown')])
def test_invalid_model_output_is_rejected_without_repair(edit):
    prepared=prepare(controlled(4));response=answer_for(prepared);edit(response)
    before=copy.deepcopy(response)
    assert validate_output(prepared,response)['valid'] is False
    assert response==before


def test_other_candidates_evidence_cannot_support_selected_candidate():
    prepared=prepare(controlled(4));response=answer_for(prepared)
    response['reasons'][0]['evidence_ids']=response['reasons'][1]['evidence_ids']
    assert validate_output(prepared,response)['valid'] is False


def test_existing_evidence_id_does_not_prove_reason_semantics():
    prepared=prepare(controlled(4));response=answer_for(prepared)
    response['reasons'][0]['text']='이 시설에서는 달에 착륙할 수 있습니다.'
    result=validate_output(prepared,response)
    assert result['valid'] and result['evidence_references_exist']
    assert result['semantic_factuality_verified'] is False
    assert result['human_review_count']==0


def test_tied_top_candidates_accept_multiple_correct_rankings():
    payload=controlled(4);payload['weights']={'taste':1,'travel':0,'similarity':0}
    for c in payload['candidates']:c['taste']=.8
    prepared=prepare(payload)
    alternate=list(reversed(prepared['ranked_ids']))[:3]
    assert len(prepared['gold_score_groups'])==1
    assert validate_output(prepared,answer_for(prepared,alternate))['ranking_matches_gold']


def test_valid_but_wrong_order_is_quality_failure_not_format_failure():
    prepared=prepare(controlled(4))
    wrong=list(reversed(prepared['ranked_ids'][:3]))
    result=validate_output(prepared,answer_for(prepared,wrong))
    assert result['valid'] and not result['ranking_matches_gold']


def test_candidate_permutation_preserves_result_and_tie_groups():
    payload=controlled(4);before=prepare(payload)
    random.Random(123).shuffle(payload['candidates'])
    after=prepare(payload)
    assert before['ranked_ids']==after['ranked_ids']
    assert before['gold_score_groups']==after['gold_score_groups']


def test_bijective_opaque_id_rename_preserves_mapped_ranking():
    payload=controlled(4);before=prepare(payload)
    rng=random.Random(20261010)
    mapping={c['id']:f'{rng.getrandbits(96):024x}' for c in payload['candidates']}
    inverse={new:old for old,new in mapping.items()}
    assert len(inverse)==len(mapping)
    for c in payload['candidates']:c['id']=mapping[c['id']]
    after=prepare(payload)
    assert [inverse[cid] for cid in after['ranked_ids']]==before['ranked_ids']


def test_increased_travel_time_cannot_increase_numeric_utility():
    payload=controlled(1);payload['customer']['time_budget_min']=200
    before=prepare(payload)['eligible'][0]['score']
    payload['candidates'][0]['facts']['travel_min']['value']=40
    after=prepare(payload)['eligible'][0]['score']
    assert after<=before


def test_tighter_budget_cannot_add_feasible_candidates():
    payload=controlled(4)
    for c,price in zip(payload['candidates'],(0,1000,5000,10000)):c['facts']['cost_krw']['value']=price
    before={c['id'] for c in prepare(payload)['eligible']}
    payload['customer']['budget_krw']=1000
    after={c['id'] for c in prepare(payload)['eligible']}
    assert after<before


def test_preference_weight_reversal_changes_top_choice():
    payload=controlled(2)
    a,b=payload['candidates'];a['taste']=1;b['taste']=0
    a['facts']['travel_min']['value']=60;b['facts']['travel_min']['value']=0
    payload['weights']={'taste':1,'travel':0,'similarity':0}
    assert prepare(payload)['ranked_ids'][0]==a['id']
    payload['weights']={'taste':0,'travel':1,'similarity':0}
    assert prepare(payload)['ranked_ids'][0]==b['id']


@pytest.mark.parametrize('size',[16,64,256])
def test_candidate_scales_execute_actual_contract_code(size):
    fixture=make_fixture(size,20261010+size)
    assert len({c['id'] for c in fixture['candidates']})==size
    prepared=prepare(fixture)
    assert prepared['status']=='ready'
    assert validate_output(prepared,answer_for(prepared))['valid']


def test_development_runner_marks_scope_and_refuses_overwrite(tmp_path):
    output=tmp_path/'development-new'
    summary=run_development(output,timing_repeats=2)
    assert summary['passed_cases']==summary['development_cases']==8
    assert summary['human_review_count']==summary['paid_api_calls']==0
    timings=json.loads((output/'timings.json').read_text(encoding='utf-8'))
    assert [row['candidate_count'] for row in timings]==[16,64,256]
    assert all(row['repeats']==2 and not row['llm_latency_measured'] for row in timings)
    before=(output/'summary.json').read_bytes()
    with pytest.raises(FileExistsError):run_development(output,timing_repeats=2)
    assert (output/'summary.json').read_bytes()==before


def test_identity_seed_is_separate_from_property_seed():
    first=make_fixture(16,42);second=make_fixture(16,42)
    assert first==second
    rng=random.Random(42+1000003)
    assert [c['id'] for c in first['candidates']]==[f'{rng.getrandbits(96):024x}' for _ in range(16)]
    assert len({c['taste'] for c in first['candidates']})>1


def test_fixture_hash_matches_actual_saved_bytes_on_every_platform(tmp_path):
    import hashlib
    output=tmp_path/'new-byte-hash-regression'
    returned=run_development(output,timing_repeats=1)
    saved=json.loads((output/'summary.json').read_text(encoding='utf-8'))
    payload=(output/'fixtures.jsonl').read_bytes()
    assert b'\r\n' not in payload
    assert payload.count(b'\n')==saved['development_cases']==8
    assert hashlib.sha256(payload).hexdigest()==saved['fixture_sha256']==returned['fixture_sha256']
    assert 'stored fixtures.jsonl bytes' in saved['fixture_sha256_scope']
