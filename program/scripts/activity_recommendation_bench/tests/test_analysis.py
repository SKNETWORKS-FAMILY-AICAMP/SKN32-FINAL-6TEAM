"""Synthetic result analysis tests; no serving app or provider API imports."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

PATH=Path(__file__).resolve().parents[1]/'analyze.py'
spec=importlib.util.spec_from_file_location('activity_analysis_contract',PATH)
analysis=importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


@pytest.fixture
def fixture():
    cases=[{'case_id':'case1','group':'small1'},{'case_id':'case2','group':'small2'}]
    metadata={'repeats':3,'independent_cases':2,'config':{'seed':20261009,'bootstrap_samples':100},
              'config_hash':'config','prompt_hash':'prompt','dataset_hash':'dataset'}
    rows=[]
    ledger=[]
    call=0
    for ci,case in enumerate(cases):
        for repeat in range(3):
            for arm in analysis.ARMS:
                top1=arm!='nano_direct' or ci==0
                ranking=['a','b','c'] if top1 else ['b','a','c']
                row={'case_id':case['case_id'],'group':case['group'],'repeat':repeat,'arm':arm,'status':'ok',
                     'ranking':ranking,'candidate_order':['a','b','c','d'] if repeat<2 else ['d','b','a','c'],
                     'metrics':{'top1_correct':top1,'ndcg3':1 if top1 else .8,'recall3':1,'hard_violations':0,
                                'gold_top3':['a','b','c']},
                     'cost_usd':0 if arm=='rule' else .01,'latency_ms':0 if arm=='rule' else 1000}
                if arm!='rule':
                    call+=1
                    row.update(call_id=str(call),requested_model=arm+'-alias',model=arm+'-version',
                       usage={'input_tokens':100,'output_tokens':20,'input_tokens_details':{'cached_tokens':30,'cache_write_tokens':40},
                              'output_tokens_details':{'reasoning_tokens':10}})
                    ledger.extend([{'event':'reserved','call_id':str(call),'cost_usd':.02},
                                   {'event':'finished','call_id':str(call),'cost_usd':.01,'usage_known':True}])
                if arm in ('jev_nano','jev_luna'):
                    row.update(filter_call_id='shared-filter',filter_top1_preserved=True,filter_top3_recall=1)
                rows.append(row)
    return metadata,cases,rows,ledger


def test_complete_scheduled_means_and_conditional_means(fixture):
    result=analysis.analyze(*fixture)
    assert result['complete'] is True
    assert result['scheduled_rows']==36
    assert result['arms']['nano_direct']['all_scheduled_means']['top1_correct']==.5
    assert result['arms']['luna_direct']['all_scheduled_means']['top1_correct']==1
    assert result['paired_case_bootstrap']['luna_direct_minus_nano_direct']['top1_correct']['mean_difference']==.5


def test_failures_are_zero_even_when_saved_partial_metrics_claim_success(fixture):
    metadata,cases,rows,ledger=fixture
    for row in rows:
        if row['arm']=='nano_direct' and row['case_id']=='case1':row['status']='failed'
    result=analysis.analyze(metadata,cases,rows,ledger)
    arm=result['arms']['nano_direct']
    assert arm['scheduled_attempts']==6
    assert arm['successful_outputs']==3
    assert arm['all_scheduled_means']['top1_correct']==0
    assert arm['successful_only_means']['top1_correct']==0
    assert arm['status_counts']=={'failed':3,'ok':3}


def test_missing_attempts_remain_in_scheduled_denominator(fixture):
    metadata,cases,rows,ledger=fixture
    rows=[r for r in rows if r['case_id']=='case1']
    result=analysis.analyze(metadata,cases,rows,ledger)
    assert result['complete'] is False
    assert result['observed_rows']==18
    assert result['scheduled_rows']==36
    assert result['arms']['luna_direct']['all_scheduled_means']['top1_correct']==.5
    assert result['arms']['luna_direct']['successful_only_means']['top1_correct']==1
    assert result['arms']['luna_direct']['status_counts']['unattempted']==3


def test_bootstrap_unit_is_case_mean_not_six_repeat_observations(fixture):
    result=analysis.analyze(*fixture)
    b=result['paired_case_bootstrap']['luna_direct_minus_nano_direct']['top1_correct']
    assert b['independent_cases']==2
    assert b['resamples']==100
    assert b['ci95']==[0,1]


def test_paired_bootstrap_constant_effect_and_reproducibility():
    assert analysis.paired_bootstrap([.25]*24,5000)['ci95']==[.25,.25]
    assert analysis.paired_bootstrap([-1,0,1],1000,12)==analysis.paired_bootstrap([-1,0,1],1000,12)


@pytest.mark.parametrize('b,c,expected',[(0,0,1),(1,0,1),(10,0,2/1024),(5,5,1)])
def test_exact_mcnemar_two_sided_probability(b,c,expected):
    assert analysis.mcnemar_exact(b,c)==pytest.approx(expected)


def test_mcnemar_uses_first_repeat_only(fixture):
    metadata,cases,rows,ledger=fixture
    for r in rows:
        if r['arm']=='luna_direct' and r['repeat']>0:r['metrics']['top1_correct']=False
    m=analysis.analyze(metadata,cases,rows,ledger)['mcnemar_nano_vs_luna_first_repeat']
    assert m['scheduled_pairs']==2
    assert m['nano_only_correct']==0
    assert m['luna_only_correct']==1


def test_empty_failed_rankings_are_not_reported_as_consistent(fixture):
    metadata,cases,rows,ledger=fixture
    for r in rows:
        if r['arm']=='nano_direct':r.update(status='failed',ranking=[])
    value=analysis.analyze(metadata,cases,rows,ledger)['consistency']['nano_direct']['same_input']
    assert value['scheduled_pairs']==2
    assert value['both_successful_pairs']==0
    assert value['identical_top3_pairs']==0
    assert value['agreement_all_scheduled']==0
    assert value['agreement_both_successful'] is None


def test_same_input_and_permutation_consistency_are_separate(fixture):
    metadata,cases,rows,ledger=fixture
    for row in rows:
        if row['arm']=='luna_direct' and row['repeat']==2 and row['case_id']=='case2':
            row['ranking']=['b','a','c']
    consistency=analysis.analyze(metadata,cases,rows,ledger)['consistency']['luna_direct']
    assert consistency['same_input']['agreement_all_scheduled']==1
    assert consistency['same_input']['same_candidate_order_pairs']==2
    assert consistency['permuted_input']['agreement_all_scheduled']==.5
    assert consistency['permuted_input']['same_candidate_order_pairs']==0


def test_cost_ledger_deduplicates_shared_filter_and_keeps_unknown_bounds():
    rows=[{'event':'reserved','call_id':'filter','cost_usd':.1},
          {'event':'finished','call_id':'filter','cost_usd':.01,'usage_known':True},
          {'event':'reserved','call_id':'unknown','cost_usd':.03},
          {'event':'finished','call_id':'unknown','cost_usd':.03,'usage_known':False},
          {'event':'reserved','call_id':'pending','cost_usd':.04}]
    totals=analysis.ledger_totals(rows)
    assert totals['unique_paid_calls']==3
    assert totals['usage_known_cost_estimate_usd']==.01
    assert totals['usage_unknown_reservation_upper_usd']==pytest.approx(.07)
    assert totals['total_cost_accounted_usd']==pytest.approx(.08)
    assert totals['unfinished_reservations']==1
    assert analysis.ledger_totals(rows,{'filter'})['total_cost_accounted_usd']==.01


def test_duplicate_ledger_reservation_is_rejected():
    row={'event':'reserved','call_id':'same','cost_usd':.1}
    with pytest.raises(ValueError,match='duplicate_ledger_reservation'):
        analysis.ledger_totals([row,row])


def test_usage_collects_read_write_reasoning_and_counts_shared_call_once():
    row={'call_id':'same','usage':{'input_tokens':100,'output_tokens':20,
       'input_tokens_details':{'cached_tokens':40,'cache_write_tokens':30},
       'output_tokens_details':{'reasoning_tokens':10}}}
    missing={'call_id':'missing','usage':None}
    total=analysis.usage_totals([row,row,missing])
    assert total=={'input_tokens':100,'output_tokens':20,'cached_read_tokens':40,'cache_write_tokens':30,
                  'reasoning_output_tokens':10,'usage_known_calls':1,'usage_unknown_calls':1}


def test_path_latency_percentiles_and_actual_models(fixture):
    metadata,cases,rows,ledger=fixture
    selected=[r for r in rows if r['arm']=='jev_luna']
    for i,row in enumerate(selected):row['latency_ms']=i*1000
    result=analysis.analyze(metadata,cases,rows,ledger)
    assert result['arms']['jev_luna']['path_latency_p50_ms']==2500
    assert result['arms']['jev_luna']['path_latency_p95_ms']==4750
    assert result['arms']['jev_luna']['returned_models']==['jev_luna-version']
    assert result['arms']['jev_luna']['path_cost_sum_usd']==pytest.approx(.06)
    assert result['actual_spend_this_run']['total_cost_accounted_usd']==pytest.approx(.30)


def test_groups_count_customer_cases_not_repeats(fixture):
    group=analysis.analyze(*fixture)['groups']['small1']
    assert group['independent_cases']==1
    assert group['scheduled_repeats_per_arm']==3
    assert 'small' in group['interpretation']


def test_filter_only_retention_is_separate_from_rule_protected_union(fixture):
    metadata,cases,rows,ledger=fixture
    metadata['config']['shortlist_keep']=2
    for row in rows:
        if row['arm']=='jev_code':row['ranking']=['d','b','c','a']
    result=analysis.analyze(metadata,cases,rows,ledger)
    retention=result['arms']['jev_luna']['filter']
    assert retention['top1_preserved_all_scheduled']==1
    assert retention['jev_only_top1_preserved_all_scheduled']==0
    assert retention['jev_only_top3_recall_all_scheduled']==pytest.approx(1/3)
    assert retention['jev_only_successful_filter_outputs']==6


@pytest.mark.parametrize('change', ['duplicate','wrong_case','wrong_arm','wrong_repeat'])
def test_invalid_result_coordinates_are_rejected(fixture,change):
    metadata,cases,rows,ledger=fixture
    if change=='duplicate':rows.append(copy.deepcopy(rows[0]))
    elif change=='wrong_case':rows[0]['case_id']='not-scheduled'
    elif change=='wrong_arm':rows[0]['arm']='unknown'
    else:rows[0]['repeat']=3
    with pytest.raises(ValueError):analysis.analyze(metadata,cases,rows,ledger)


def test_cli_refuses_existing_output_directory_and_does_not_mutate_inputs(fixture,tmp_path,monkeypatch):
    metadata,cases,rows,ledger=fixture
    metadata['config'].update(evaluation_file='fixtures.jsonl')
    data=tmp_path/'dataset';run=data/'runs'/'unit-main';run.mkdir(parents=True)
    source=data/'raw'/'fixtures.jsonl';source.parent.mkdir()
    source.write_text(''.join(json.dumps(c)+'\n' for c in cases),encoding='utf-8')
    metadata['dataset_hash']=hashlib.sha256(source.read_bytes()).hexdigest()
    (run/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
    (run/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (data/'ledger.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in ledger),encoding='utf-8')
    scripts=tmp_path/'scripts';scripts.mkdir();(scripts/'config.json').write_text(json.dumps({'dataset_directory':'dataset'}),encoding='utf-8')
    monkeypatch.setattr(analysis,'ROOT',tmp_path);monkeypatch.setattr(analysis,'HERE',scripts)
    before={p:p.read_bytes() for p in (source,run/'metadata.json',run/'results.jsonl',data/'ledger.jsonl')}
    destination=tmp_path/'new-analysis'
    analysis.main(['--run-id','unit-main','--output-dir',str(destination)])
    assert json.loads((destination/'summary.json').read_text(encoding='utf-8'))['complete'] is True
    with pytest.raises(FileExistsError):analysis.main(['--run-id','unit-main','--output-dir',str(destination)])
    assert all(p.read_bytes()==old for p,old in before.items())


def test_dataset_hash_mismatch_stops_before_writing(tmp_path,monkeypatch):
    scripts=tmp_path/'scripts';scripts.mkdir();(scripts/'config.json').write_text(json.dumps({'dataset_directory':'dataset'}),encoding='utf-8')
    run=tmp_path/'dataset'/'runs'/'unit-main';run.mkdir(parents=True)
    raw=tmp_path/'dataset'/'raw';raw.mkdir();(raw/'fixtures.jsonl').write_text('{}\n',encoding='utf-8')
    (run/'metadata.json').write_text(json.dumps({'config':{'evaluation_file':'fixtures.jsonl'},'dataset_hash':'wrong'}),encoding='utf-8')
    monkeypatch.setattr(analysis,'ROOT',tmp_path);monkeypatch.setattr(analysis,'HERE',scripts)
    destination=tmp_path/'new-analysis'
    with pytest.raises(ValueError,match='dataset_hash_mismatch'):
        analysis.main(['--run-id','unit-main','--output-dir',str(destination)])
    assert not destination.exists()


def test_markdown_identifies_estimate_bounds_and_synthetic_limits(fixture):
    text=analysis.render_markdown(analysis.analyze(*fixture))
    assert '결제 명세서 확인 값은 아닙니다' in text
    assert '사람 검수가 아닙니다' in text
    assert '전체 실제 지출로 쓰면 안 됩니다' in text
