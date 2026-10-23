"""Create and execute self-authored development fixtures without network access."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import random
from statistics import median
import time

from contract import FACT_TYPES,prepare,validate_output

SEED=20261010
AS_OF='2026-10-10T12:00:00+09:00'
HERE=Path(__file__).resolve().parent


def make_fixture(size,seed=SEED):
    """Opaque identity and candidate properties use separate random streams."""
    identity=random.Random(seed+1000003)
    values=random.Random(seed+2000003)
    observed=(datetime.fromisoformat(AS_OF)-timedelta(seconds=30)).isoformat()
    candidates=[]
    for _ in range(size):
        cid=f'{identity.getrandbits(96):024x}'
        attrs={'open':values.random()>.12,'unsafe':values.random()<.06,
               'cost_krw':values.choice((0,3000,8000,18000,25000)),
               'travel_min':values.randint(0,50),'visit_min':values.randint(15,50),
               'step_free':values.random()>.15,'outdoor':values.random()<.2}
        candidates.append({'id':cid,'description':'자체 합성 수치 속성을 가진 개발용 가상시설입니다.',
            'category':'개발용 합성 활동','taste':values.choice((0,.25,.5,.75,1)),
            'similarity':values.choice((0,.5,1)),
            'facts':{k:{'value':v,'observed_at':observed,'evidence_id':f'ev_{cid}_{k}'} for k,v in attrs.items()}})
    return {'as_of':AS_OF,'max_age_seconds':60,
            'customer':{'budget_krw':20000,'time_budget_min':100,'require_step_free':True,'rain':False,'allow_outdoor':True},
            'weights':{'taste':.6,'travel':.25,'similarity':.15},'candidates':candidates}


def answer_for(prepared,ranking=None):
    ranking=prepared['ranked_ids'][:prepared['requested_count']] if ranking is None else ranking
    candidates={c['id']:c for c in prepared['eligible']}
    return {'ranking':ranking,'reasons':[{'candidate_id':cid,
            'evidence_ids':[candidates[cid]['evidence_ids']['open']],
            'text':'자체 합성 시설의 준비된 근거 ID를 참조합니다. 의미 사실성은 별도 검증 대상입니다.'} for cid in ranking]}


def run_development(output_dir,seed=SEED,timing_repeats=11):
    if type(timing_repeats) is not int or timing_repeats<1:raise ValueError('timing_repeats must be positive int')
    destination=Path(output_dir)
    if destination.exists():raise FileExistsError('existing_output_directory')
    fixtures=[];outcomes=[];timings=[]
    for size in (16,64,256):
        fixture=make_fixture(size,seed+size)
        prepared=prepare(fixture)
        assert prepared['status']=='ready'
        response=answer_for(prepared)
        validation=validate_output(prepared,response)
        assert validation['valid'] and validation['ranking_matches_gold']
        fixtures.append({'case_id':f'candidate_scale_{size}','source':'self-authored synthetic development fixture',
                         'seed':seed+size,'identity_seed':seed+size+1000003,
                         'property_seed':seed+size+2000003,'request':fixture})
        # One unmeasured warmup per size; measured operation is code only.
        validate_output(prepare(fixture),response)
        elapsed=[]
        for _ in range(timing_repeats):
            start=time.perf_counter_ns()
            trial=prepare(fixture);validate_output(trial,response)
            elapsed.append((time.perf_counter_ns()-start)/1e6)
        ordered=sorted(elapsed);position=(len(ordered)-1)*.95
        lo=int(position);hi=min(len(ordered)-1,lo+1)
        p95=ordered[lo]+(ordered[hi]-ordered[lo])*(position-lo)
        timings.append({'candidate_count':size,'repeats':timing_repeats,'durations_ms':elapsed,
                        'p50_ms':median(elapsed),'p95_ms':p95,'min_ms':min(elapsed),'max_ms':max(elapsed),
                        'measured_operation':'Python fact freshness/filter/sort/output ID/reference validation only',
                        'llm_latency_measured':False})
        outcomes.append({'case_id':f'candidate_scale_{size}','status':prepared['status'],
                         'candidate_count':size,'eligible_count':len(prepared['eligible']),
                         'rejected_count':len(prepared['rejected']),'requested_count':prepared['requested_count'],
                         'response':response,'validation':validation})
    # Boundary cases are derived only for development, never held-out model evaluation.
    baseline=make_fixture(16,seed+999)
    for label,edit in (
        ('missing_fact',lambda c:c['facts'].pop('open')),
        ('stale_fact',lambda c:c['facts']['open'].update(observed_at='2026-10-10T11:58:59+09:00')),
        ('future_fact',lambda c:c['facts']['open'].update(observed_at='2026-10-10T12:00:01+09:00')),
        ('negative_cost',lambda c:c['facts']['cost_krw'].update(value=-1)),
        ('no_feasible',lambda c:c['facts']['open'].update(value=False)),
    ):
        changed=copy.deepcopy(baseline)
        if label=='no_feasible':
            for candidate in changed['candidates']:edit(candidate)
        else:edit(changed['candidates'][0])
        result=prepare(changed)
        expected='no_feasible_candidates' if label=='no_feasible' else ('invalid_input' if label=='negative_cost' else 'facts_unresolved')
        assert result['status']==expected
        fixtures.append({'case_id':label,'source':'self-authored synthetic development boundary fixture','request':changed})
        outcomes.append({'case_id':label,'status':result['status'],'expected_status':expected,
                         'requested_count':result['requested_count'],'unresolved_facts':result['unresolved_facts']})
    payload=''.join(json.dumps(row,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n' for row in fixtures)
    fixture_bytes=payload.encode('utf-8')
    summary={'schema_version':1,'date_kst':'2026-10-10','seed':seed,'development_cases':len(fixtures),
             'passed_cases':len(outcomes),'scale_cases':3,'boundary_cases':5,'human_review_count':0,
             'paid_api_calls':0,'provider_sdk_imports':0,'serving_app_imports':0,'network_used':False,
             'claim_scope':'self-authored development contract verification, not human review, held-out evaluation or LLM performance',
             'fixture_sha256':hashlib.sha256(fixture_bytes).hexdigest(),
             'fixture_sha256_scope':'stored fixtures.jsonl bytes: UTF-8 without BOM and LF line endings',
             'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'contract.py',HERE/'dev_suite.py')},
             'timing_repeats_per_size':timing_repeats,'timing_total_measured_operations':3*timing_repeats,
             'timing_scope':'code-only single-process measurement; no search, model, network or end-to-end serving measurement',
             'semantic_reason_factuality_verified':False,'limits':['fixture taste/similarity are explicit synthetic numbers',
               'evidence reference existence does not establish semantic truth','development fixtures are not unused held-out model evaluation data',
               'real place freshness and source trust were not measured','code timing cannot establish serving latency']}
    destination.mkdir(parents=True,exist_ok=False)
    (destination/'fixtures.jsonl').write_bytes(fixture_bytes)
    (destination/'outcomes.json').write_text(json.dumps(outcomes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (destination/'timings.json').write_text(json.dumps(timings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (destination/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description='비용 없는 합성 개발 계약 시험입니다.')
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--seed',type=int,default=SEED)
    parser.add_argument('--timing-repeats',type=int,default=11)
    args=parser.parse_args(argv)
    print(json.dumps(run_development(args.output_dir,args.seed,args.timing_repeats),ensure_ascii=False))


if __name__=='__main__':main()
