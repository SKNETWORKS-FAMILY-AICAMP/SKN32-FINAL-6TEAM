"""Analyze a frozen recommendation run without provider calls or app imports."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
from statistics import mean

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
ARMS=('rule','nano_direct','luna_direct','jev_code','jev_nano','jev_luna')
PRIMARY_METRICS=('top1_correct','ndcg3','recall3')


def percentile(values, q):
    if not values:return None
    ordered=sorted(values)
    position=(len(ordered)-1)*q
    low=math.floor(position);high=math.ceil(position)
    return ordered[low]*(high-position)+ordered[high]*(position-low) if low!=high else ordered[low]


def paired_bootstrap(differences, samples=5000, seed=20261009):
    if not differences:return {'mean_difference':None,'ci95':[None,None],'independent_cases':0}
    rng=random.Random(seed)
    values=[mean(rng.choices(differences,k=len(differences))) for _ in range(samples)]
    return {'mean_difference':mean(differences),'ci95':[percentile(values,.025),percentile(values,.975)],
            'independent_cases':len(differences),'resamples':samples,'unit':'case mean across all scheduled repeats'}


def mcnemar_exact(left_only,right_only):
    n=left_only+right_only
    if not n:return 1.0
    tail=sum(math.comb(n,k) for k in range(min(left_only,right_only)+1))/(2**n)
    return min(1.0,2*tail)


def usage_totals(rows):
    total={'input_tokens':0,'output_tokens':0,'cached_read_tokens':0,'cache_write_tokens':0,
           'reasoning_output_tokens':0,'usage_known_calls':0,'usage_unknown_calls':0}
    seen=set()
    for row in rows:
        call=row.get('call_id')
        if not call or call in seen:continue
        seen.add(call)
        usage=row.get('usage')
        if usage is None:
            total['usage_unknown_calls']+=1;continue
        details=usage.get('input_tokens_details') or {}
        output_details=usage.get('output_tokens_details') or {}
        total['usage_known_calls']+=1
        total['input_tokens']+=usage['input_tokens']
        total['output_tokens']+=usage['output_tokens']
        total['cached_read_tokens']+=details.get('cached_tokens',usage.get('cached_input_tokens',0)) or 0
        total['cache_write_tokens']+=details.get('cache_write_tokens',usage.get('cache_creation_input_tokens',0)) or 0
        total['reasoning_output_tokens']+=output_details.get('reasoning_tokens',usage.get('reasoning_tokens',0)) or 0
    return total


def ledger_totals(rows, selected_call_ids=None):
    reservations={};finished={};exceeded=[]
    for row in rows:
        call=row.get('call_id')
        if selected_call_ids is not None and call not in selected_call_ids:continue
        if row['event']=='reserved':
            if call in reservations:raise ValueError('duplicate_ledger_reservation')
            reservations[call]=row
        elif row['event']=='finished':finished[call]=row
        elif row['event']=='reservation_exceeded':exceeded.append(call)
    unknown=0.0;known=0.0
    for call,reservation in reservations.items():
        final=finished.get(call,reservation)
        if final.get('usage_known') is True:known+=final['cost_usd']
        else:unknown+=final['cost_usd']
    return {'unique_paid_calls':len(reservations),'usage_known_cost_estimate_usd':known,
            'usage_unknown_reservation_upper_usd':unknown,'total_cost_accounted_usd':known+unknown,
            'unfinished_reservations':len(set(reservations)-set(finished)),
            'reservation_exceeded_call_ids':sorted(set(exceeded)),
            'billing_basis':'API usage repriced using frozen rates plus unknown-usage reservation bounds; not a provider invoice'}


def analyze(metadata,cases,rows,ledger):
    repeats=metadata['repeats'];config=metadata['config']
    ids=[c['case_id'] for c in cases]
    if len(set(ids))!=len(ids):raise ValueError('duplicate_case_id')
    if metadata['independent_cases']!=len(ids):raise ValueError('case_count_mismatch')
    actual={}
    for row in rows:
        key=(row['case_id'],row['repeat'],row['arm'])
        if key in actual:raise ValueError('duplicate_result_row')
        if key[0] not in ids or key[1] not in range(repeats) or key[2] not in ARMS:
            raise ValueError('unexpected_result_row')
        actual[key]=row
    scheduled=len(ids)*repeats
    def get(cid,repeat,arm):
        return actual.get((cid,repeat,arm),{'case_id':cid,'repeat':repeat,'arm':arm,'status':'unattempted','ranking':[],
            'metrics':{'top1_correct':False,'ndcg3':0,'recall3':0,'regret_top1':None,'hard_violations':0}})
    def score(row,metric):
        # Failed or unattempted outputs are never rescued by saved partial metrics.
        if row['status']!='ok':return 0.0
        return float(row['metrics'][metric])
    arms={}
    for arm in ARMS:
        planned=[get(cid,r,arm) for cid in ids for r in range(repeats)]
        observed=[r for r in planned if r['status']!='unattempted']
        valid=[r for r in observed if r['status']=='ok']
        arms[arm]={
            'scheduled_attempts':scheduled,'observed_attempts':len(observed),'successful_outputs':len(valid),
            'status_counts':dict(Counter(r['status'] for r in planned)),
            'all_scheduled_means':{m:mean(score(r,m) for r in planned) if planned else None for m in PRIMARY_METRICS},
            'successful_only_means':{m:mean(score(r,m) for r in valid) if valid else None for m in PRIMARY_METRICS},
            'hard_violations':sum(r.get('metrics',{}).get('hard_violations',0) for r in observed),
            'path_cost_sum_usd':sum(r.get('cost_usd',0) for r in observed),
            'path_cost_p50_usd':percentile([r.get('cost_usd',0) for r in observed],.5),
            'path_cost_p95_usd':percentile([r.get('cost_usd',0) for r in observed],.95),
            'path_latency_p50_ms':percentile([r.get('latency_ms',0) for r in observed],.5),
            'path_latency_p95_ms':percentile([r.get('latency_ms',0) for r in observed],.95),
            'cost_latency_denominator':'observed request paths, including failures; unattempted paths have no measured latency',
            'returned_models':sorted(set(r['model'] for r in observed if r.get('model'))),
            'requested_models':sorted(set(r['requested_model'] for r in observed if r.get('requested_model'))),
            'own_ranker_usage':usage_totals(observed),
            'http_failure_counts':dict(Counter(str(r['http_status']) for r in observed if r.get('http_status'))),
            'validation_failure_counts':dict(Counter(r['validation_error'] for r in observed if r.get('validation_error'))),
            'api_status_counts':dict(Counter(r['api_status'] for r in observed if r.get('api_status'))),
        }
        if arm.startswith('jev_') and arm!='jev_code':
            own_filter=[r for r in planned if 'filter_top1_preserved' in r]
            raw_retention=[]
            for cid in ids:
                for repeat in range(repeats):
                    raw_filter=get(cid,repeat,'jev_code')
                    gold_ids=raw_filter.get('metrics',{}).get('gold_top3',[])
                    selected_ids=raw_filter.get('ranking',[])[:config.get('shortlist_keep',4)] if raw_filter['status']=='ok' else []
                    raw_retention.append({'success':raw_filter['status']=='ok',
                        'top1':bool(gold_ids and gold_ids[0] in selected_ids),
                        'recall3':len(set(gold_ids[:3])&set(selected_ids))/3})
            successful_raw=[r for r in raw_retention if r['success']]
            arms[arm]['filter']={
                'scheduled_denominator':scheduled,'observed_filter_outputs':len(own_filter),
                'top1_preserved_all_scheduled':sum(r.get('filter_top1_preserved',False) for r in own_filter)/scheduled,
                'top3_recall_all_scheduled':sum(r.get('filter_top3_recall',0) for r in own_filter)/scheduled,
                'top1_preserved_observed':mean(float(r['filter_top1_preserved']) for r in own_filter) if own_filter else None,
                'top3_recall_observed':mean(r['filter_top3_recall'] for r in own_filter) if own_filter else None,
                'jev_only_successful_filter_outputs':len(successful_raw),
                'jev_only_top1_preserved_all_scheduled':sum(r['top1'] for r in raw_retention)/scheduled,
                'jev_only_top3_recall_all_scheduled':sum(r['recall3'] for r in raw_retention)/scheduled,
                'jev_only_top1_preserved_successful':mean(float(r['top1']) for r in successful_raw) if successful_raw else None,
                'jev_only_top3_recall_successful':mean(r['recall3'] for r in successful_raw) if successful_raw else None,
                'note':'top1_preserved fields include rule-protected candidates; jev_only fields exclude rule protection'}
    comparisons={}
    for left,right in itertools.combinations(ARMS,2):
        label=f'{right}_minus_{left}'
        comparisons[label]={}
        for metric in PRIMARY_METRICS:
            differences=[mean(score(get(cid,r,right),metric)-score(get(cid,r,left),metric) for r in range(repeats)) for cid in ids]
            salt=int.from_bytes(hashlib.sha256((label+metric).encode()).digest()[:4],'big')
            comparisons[label][metric]=paired_bootstrap(differences,config.get('bootstrap_samples',5000),config['seed']+salt)
    first=[(get(cid,0,'nano_direct'),get(cid,0,'luna_direct')) for cid in ids]
    b=sum(score(left,'top1_correct')==1 and score(right,'top1_correct')==0 for left,right in first)
    c=sum(score(left,'top1_correct')==0 and score(right,'top1_correct')==1 for left,right in first)
    mcnemar={'scheduled_pairs':len(ids),'nano_only_correct':b,'luna_only_correct':c,'exact_two_sided_p':mcnemar_exact(b,c),
             'both_observed_pairs':sum(l['status']!='unattempted' and r['status']!='unattempted' for l,r in first),
             'note':'first repeat only; failures and unattempted outputs count as incorrect'}
    consistency={}
    for arm in ARMS:
        consistency[arm]={}
        for left_repeat,right_repeat,label in ((0,1,'same_input'),(0,2,'permuted_input')):
            if max(left_repeat,right_repeat)>=repeats:continue
            pairs=[(get(cid,left_repeat,arm),get(cid,right_repeat,arm)) for cid in ids]
            valid=[(l,r) for l,r in pairs if l['status']=='ok' and r['status']=='ok']
            identical=sum(l['ranking'][:3]==r['ranking'][:3] for l,r in valid)
            consistency[arm][label]={'scheduled_pairs':len(ids),'both_successful_pairs':len(valid),
                 'identical_top3_pairs':identical,'agreement_all_scheduled':identical/len(ids),
                 'agreement_both_successful':identical/len(valid) if valid else None,
                 'same_candidate_order_pairs':sum(l.get('candidate_order')==r.get('candidate_order') for l,r in pairs
                                                   if l['status']!='unattempted' and r['status']!='unattempted')}
    groups={}
    for group in sorted(set(c['group'] for c in cases)):
        group_ids=[c['case_id'] for c in cases if c['group']==group]
        groups[group]={'independent_cases':len(group_ids),'scheduled_repeats_per_arm':len(group_ids)*repeats,
                       'interpretation':'small synthetic stratum; descriptive only; repeats are not independent customer samples',
                       'arms':{arm:{m:mean(score(get(cid,r,arm),m) for cid in group_ids for r in range(repeats))
                                    for m in PRIMARY_METRICS} for arm in ARMS}}
    run_calls=set(r['call_id'] for r in rows if r.get('call_id'))|set(r['filter_call_id'] for r in rows if r.get('filter_call_id'))
    unique_rows=[r for r in rows if r.get('call_id')]
    return {'analysis_version':'activity-recommendation-analysis-v1','run_id':metadata.get('run_id'),
            'independent_case_count':len(ids),'repeats':repeats,'arms':arms,'paired_case_bootstrap':comparisons,
            'mcnemar_nano_vs_luna_first_repeat':mcnemar,'consistency':consistency,'groups':groups,
            'actual_spend_all_study_runs':ledger_totals(ledger),
            'actual_spend_this_run':ledger_totals(ledger,run_calls),
            'deduplicated_usage_this_run':usage_totals(unique_rows),
            'scheduled_rows':scheduled*len(ARMS),'observed_rows':len(rows),'complete':len(rows)==scheduled*len(ARMS),
            'limits':['AI-authored synthetic labels; root agent review is not human review',
                      'shared candidate templates limit independence and external validity',
                      'confidence intervals describe this synthetic sample only',
                      'permutation comparisons also include ordinary model variation',
                      'recommendation reason factuality and actual user satisfaction were not scored',
                      'bootstrap intervals and McNemar are exploratory; no multiplicity adjustment applied'],
            'frozen_hashes':{k:metadata.get(k) for k in ('config_hash','prompt_hash','dataset_hash')}}


def render_markdown(summary):
    lines=['# 활동 대체 추천 실제 비교 분석','',
      '합성 문제의 예정 시도 전체를 분모로 계산했습니다. 실패와 실행되지 않은 시도는 점수 0으로 포함하고 정상 출력만의 점수를 별도로 보존했습니다.','',
      '| 할 일 | 상태 | 진행 |','|---|---|---|',
      f"| 예정 결과 기록 | {'완료' if summary['complete'] else '부분 실행'} | {summary['observed_rows']}/{summary['scheduled_rows']} = {summary['observed_rows']/summary['scheduled_rows']:.1%} |",'',
      '| 구성 | 정상/예정 | 1위 적중 | nDCG@3 | 상위3 회수율 | 경로 비용 합계 USD | 지연 p50/p95 ms |',
      '|---|---:|---:|---:|---:|---:|---:|']
    for arm,a in summary['arms'].items():
        m=a['all_scheduled_means'];p50=a['path_latency_p50_ms'];p95=a['path_latency_p95_ms']
        lines.append(f"| {arm} | {a['successful_outputs']}/{a['scheduled_attempts']} | {m['top1_correct']:.1%} | {m['ndcg3']:.4f} | {m['recall3']:.4f} | {a['path_cost_sum_usd']:.6f} | {p50} / {p95} |")
    actual=summary['actual_spend_all_study_runs']
    lines+=['',f"전체 연구 실행의 중복 제거 비용 기록: **USD {actual['total_cost_accounted_usd']:.6f}**. 그중 사용량이 알려진 가격 환산은 USD {actual['usage_known_cost_estimate_usd']:.6f}, 사용량 미확인 예약 상한은 USD {actual['usage_unknown_reservation_upper_usd']:.6f}입니다. 결제 명세서 확인 값은 아닙니다.",
       '', '각 구성 경로에는 공유 선별 호출의 비용이 포함되므로 표의 경로 비용을 더해 전체 실제 지출로 쓰면 안 됩니다.',
       '', '정상 출력만의 점수, 캐시·추론 토큰, 반환 모델, 5,000회 문제 단위 재표집 구간, 첫 회 McNemar, 입력 순서 일관성, 소규모 그룹별 점수는 summary.json에 보존했습니다.',
       '', '## 해석 한계','']
    korean_limits=['정답은 AI가 작성한 합성 속성과 계산식에 근거합니다. 루트 에이전트 독립 검수는 사람 검수가 아닙니다.',
      '후보 설명 구성 틀을 공유합니다. 신뢰구간을 실제 고객 모집단의 구간으로 확장할 수 없습니다.',
      '후보 순서 변화와 모델의 통상 변동이 함께 들어 있습니다. 순서만의 인과 효과를 확정하지 않습니다.',
      '추천 이유의 사실성, 실제 고객 만족과 여행 전체 균형은 채점하지 않았습니다.',
      '여러 구성의 구간을 탐색적으로 함께 제시하며 다중 비교 보정을 적용하지 않았습니다.']
    lines += ['- '+x for x in korean_limits]
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args(argv)
    if not args.run_id or Path(args.run_id).name!=args.run_id:raise ValueError('invalid_run_id')
    current=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
    dataset=ROOT/current['dataset_directory'];run=dataset/'runs'/args.run_id
    metadata=json.loads((run/'metadata.json').read_text(encoding='utf-8'))
    config=metadata['config'];source=dataset/'raw'/config['evaluation_file']
    if metadata['dataset_hash']!=hashlib.sha256(source.read_bytes()).hexdigest():raise ValueError('dataset_hash_mismatch')
    cases=[json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]
    rows=[json.loads(s) for s in (run/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    ledger=[json.loads(s) for s in (dataset/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    metadata['run_id']=args.run_id
    summary=analyze(metadata,cases,rows,ledger)
    destination=Path(args.output_dir)
    destination.mkdir(parents=True,exist_ok=False)
    (destination/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (destination/'summary.md').write_text(render_markdown(summary),encoding='utf-8')
    print(json.dumps({'run_id':args.run_id,'observed_rows':summary['observed_rows'],'scheduled_rows':summary['scheduled_rows'],
                      'complete':summary['complete'],'output_directory':str(destination)},ensure_ascii=False))


if __name__=='__main__':main()
