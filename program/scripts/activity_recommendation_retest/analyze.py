"""Read saved rows and SQLite costs. No credentials or paid calls."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import random
from statistics import mean
import sys
from budget import Budget
from providers import CONFIG,ROOT,save_new,price_usage

DATA=ROOT/CONFIG['dataset_directory']

def read(path):return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]

def percentile(values,p):
    if not values:return None
    values=sorted(values);at=(len(values)-1)*p;low=int(at);high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(at-low)

def ci(values,seed=20261010):
    if not values:return None
    rng=random.Random(seed);n=len(values)
    samples=[mean(rng.choices(values,k=n)) for _ in range(CONFIG['bootstrap_samples'])]
    return [percentile(samples,.025),percentile(samples,.975)]

def summarize(rows):
    grouped=defaultdict(list)
    for row in rows:grouped[row['arm']].append(row)
    result={}
    for arm,items in grouped.items():
        primary=[r for r in items if r['metrics']['eligible'] and r['eligible_count']>=2]
        token_usage=Counter();unknown=0
        for r in primary:
            calls=r.get('subcalls',[r])
            for call in calls:
                usage=call.get('usage')
                if usage:
                    details=usage.get('input_tokens_details') or {}
                    token_usage.update(input_tokens=usage['input_tokens'],output_tokens=usage['output_tokens'],
                      cache_read_tokens=details.get('cached_tokens',usage.get('cached_input_tokens',0)) or 0,
                      cache_write_tokens=details.get('cache_write_tokens',usage.get('cache_creation_input_tokens',0)) or 0,
                      reasoning_tokens=(usage.get('output_tokens_details') or {}).get('reasoning_tokens',0) or 0)
                elif call.get('call_ids'):unknown+=1
        result[arm]={'planned_rows_observed':len(items),'primary_nontrivial_cases':len(primary),
          'valid_primary':sum(r['metrics']['valid'] for r in primary),'valid_all':sum(r['metrics']['valid'] for r in items),
          'top1_hits':sum(r['metrics']['top1'] for r in primary),'top1_mean':mean(r['metrics']['top1'] for r in primary) if primary else None,
          'top1_ci95':ci([int(r['metrics']['top1']) for r in primary]),
          'ndcg_k':1 if arm.endswith('_choice') else 3,
          'ndcg_mean':mean(r['metrics']['ndcg'] for r in primary) if primary else None,
          'ndcg_ci95':ci([r['metrics']['ndcg'] for r in primary]),
          'recall_mean':mean(r['metrics']['recall'] for r in primary) if primary else None,
          'cost_mean_usd':mean(r['cost_usd'] for r in primary) if primary else None,
          'cost_ci95_usd':ci([r['cost_usd'] for r in primary]),
          'latency_p50_seconds':percentile([r['latency_ms']/1000 for r in primary],.5),
          'latency_p95_seconds':percentile([r['latency_ms']/1000 for r in primary],.95),
          'hard_violations':sum(r['metrics']['hard_violations'] for r in items),
          'statuses':dict(Counter(r['status'] for r in items)),
          'invalid_primary_cases':[r['case_id'] for r in primary if not r['metrics']['valid']],
          'token_usage_direct_recorded':dict(token_usage),'usage_unknown_direct_rows':unknown,
          'reported_models':dict(Counter(r.get('model','code') for r in items)),
          'cost_scope':'per path; shared Jev filter cost appears in both direct score and cascade; do not sum path totals'}
    return result

def comparisons(rows,selection):
    arm_rows=defaultdict(dict)
    for r in rows:
        if r['metrics']['eligible'] and r['eligible_count']>=2:arm_rows[r['arm']][r['base_id']]=r
    pairs=[('jev_choice','nano_choice','top1'),('jev_choice','luna_choice','top1'),
           ('jev_score','nano_'+selection['nano'],'ndcg'),('jev_score','luna_'+selection['luna'],'ndcg'),
           ('jev_luna','luna_'+selection['luna'],'ndcg'),('luna_'+selection['luna'],'nano_'+selection['nano'],'ndcg')]
    answer=[]
    for left,right,metric in pairs:
        keys=sorted(set(arm_rows[left])&set(arm_rows[right]))
        if not keys:continue
        differences=[float(arm_rows[left][key]['metrics'][metric])-float(arm_rows[right][key]['metrics'][metric]) for key in keys]
        cost=[arm_rows[left][key]['cost_usd']-arm_rows[right][key]['cost_usd'] for key in keys]
        answer.append({'left':left,'right':right,'metric':metric,'paired_base_cases':len(keys),
          'difference_mean':mean(differences),'difference_ci95':ci(differences),
          'cost_difference_mean_usd':mean(cost),'cost_difference_ci95_usd':ci(cost),
          'population_scope':'new synthetic scenarios; not real customer population; comparisons exploratory'})
    return answer

def stability(main,variants):
    baseline={(r['base_id'],r['arm']):r for r in main};grouped=defaultdict(list)
    for r in variants:
        old=baseline.get((r['base_id'],r['arm']))
        if old is None:continue
        inverse=r.get('identity_inverse',{})
        ids=[inverse.get(cid,cid) for cid in r.get('ranking',[])]
        valid=r['metrics']['valid'] and old['metrics']['valid']
        grouped[(r['condition'],r['arm'])].append({'valid':valid,'top1_same':valid and ids[:1]==old.get('ranking',[])[:1],
          'topk_set_same':valid and set(ids)==set(old.get('ranking',[])),'quality_delta':r['metrics']['ndcg']-old['metrics']['ndcg']})
    return [{'condition':condition,'arm':arm,'pairs':len(items),'valid_pairs':sum(r['valid'] for r in items),
       'top1_same':sum(r['top1_same'] for r in items),'topk_set_same':sum(r['topk_set_same'] for r in items),
       'quality_delta_mean':mean(r['quality_delta'] for r in items),
       'scope':'same base cases; not additional independent quality samples'} for (condition,arm),items in grouped.items()]

def run(args):
    output=DATA/'analysis'/args.output_id;output.mkdir(parents=True,exist_ok=False)
    main=read(DATA/'runs'/args.eval_run/'results.jsonl')
    metadata=json.loads((DATA/'runs'/args.eval_run/'metadata.json').read_text(encoding='utf-8'))
    budget=Budget(DATA/'ledger.sqlite',CONFIG['new_budget_usd'],CONFIG['max_paid_calls'],CONFIG['baseline_usd']).snapshot()
    result={'main':summarize(main),'paired_comparisons':comparisons(main,metadata['selected_efforts_from_dev']),
      'selected_efforts_from_dev':metadata['selected_efforts_from_dev'],'budget':budget,'human_review_count':0,
      'sources_checked_at':CONFIG['price_checked_at'],'data_origin':'new self-authored synthetic; not human validated',
      'hypothesis':'Choice-only decision versus one-ID OpenAI decision; Score+code top3 versus OpenAI top3; conditional cascade',
      'cache_scope':'observed billed read/write usage; not controlled cold/warm experiment',
      'semantic_factuality_verified':False,'citation_scope':'source quote existence and candidate reference only',
      'primary_excludes_code_only_status_and_single_candidate':True}
    if args.stability_run:result['stability']=stability(main,read(DATA/'runs'/args.stability_run/'results.jsonl'))
    jev_luna=[r for r in main if r['arm']=='jev_luna' and 'raw_shortlist_best_preserved' in r]
    result['shortlist']={'measured_cases':len(jev_luna),'raw_best_preserved':sum(r['raw_shortlist_best_preserved'] for r in jev_luna),
      'protected_best_preserved':sum(r['protected_shortlist_best_preserved'] for r in jev_luna)}
    save_new(output/'summary.json',result)
    print(json.dumps({'output':str(output.relative_to(ROOT)),'budget':budget,
        'rows':len(main),'arms':len(result['main']),'human_review_count':0},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--eval-run',required=True);p.add_argument('--stability-run');p.add_argument('--output-id',required=True);run(p.parse_args())
