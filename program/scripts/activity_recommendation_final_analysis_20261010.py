"""Read-only synthesis of completed, separately preserved research runs."""
from pathlib import Path
from collections import Counter
from statistics import mean
import copy
import json
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'program/scripts/activity_recommendation_retest'))
from analyze import summarize,ci,stability
from providers import CONFIG,save_new,price_usage

DATA=ROOT/CONFIG['dataset_directory']
RAW={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'runs').glob('*/responses/*.json')}
def read_run(name):
    p=DATA/'runs'/name
    finish=json.loads((p/'finish.json').read_text(encoding='utf-8'))
    assert finish['completed']==finish['planned'] and not finish['stop']
    assert finish['source_hashes_unchanged']
    return [json.loads(s) for s in (p/'results.jsonl').read_text(encoding='utf-8').splitlines()]

def primary(rows):return [r for r in rows if r['metrics']['eligible'] and r['eligible_count']>=2]

def summary(rows):
    out=summarize(rows)
    for arm,value in out.items():
        value['ndcg_k']=1 if 'choice' in arm else 3
        items=[r for r in primary(rows) if r['arm']==arm];tokens=Counter();known=0;missing=0
        for r in items:
            for cid in r['call_ids']:
                raw=RAW.get(cid,{});u=raw.get('usage')
                if not u:missing+=1;continue
                lane='jev' if raw.get('model','').startswith('jev') else ('nano' if 'nano' in raw.get('model','') else 'luna')
                known+=price_usage(lane,u);d=u.get('input_tokens_details') or {}
                tokens.update(input_tokens=u['input_tokens'],output_tokens=u['output_tokens'],
                    cache_read_tokens=d.get('cached_tokens',u.get('cached_input_tokens',0)) or 0,
                    cache_write_tokens=d.get('cache_write_tokens',u.get('cache_creation_input_tokens',0)) or 0,
                    reasoning_tokens=(u.get('output_tokens_details') or {}).get('reasoning_tokens',0) or 0)
        value['path_token_usage_all_subcalls']=dict(tokens)
        value['path_usage_unknown_calls']=missing
        value['known_priced_cost_sum_usd']=known
        value['unknown_reserved_cost_sum_usd']=sum(r['cost_usd'] for r in items)-known
        value['known_priced_cost_mean_usd']=known/len(items) if items else None
    return out

def pairs(rows,pair_list):
    by={(r['arm'],r['base_id']):r for r in primary(rows)}
    output=[]
    for left,right,metric in pair_list:
        keys=sorted({k for a,k in by if a==left}&{k for a,k in by if a==right})
        delta=[float(by[left,k]['metrics'][metric])-float(by[right,k]['metrics'][metric]) for k in keys]
        costs=[by[left,k]['cost_usd']-by[right,k]['cost_usd'] for k in keys]
        output.append(dict(left=left,right=right,metric=metric,n=len(keys),difference=mean(delta),ci95=ci(delta),cost_difference_usd=mean(costs),cost_ci95=ci(costs)))
    return output

def main(output_id):
    original=read_run('eval-v1')
    choice=read_run('id-choice-eval-v2')
    features=read_run('features-eval-v1')
    id_rank=read_run('id-rank-diag-v1')
    repeat=read_run('stability-v1')
    feature_repeat=read_run('features-stability-v1')
    canonical=[r for r in original if r['arm']!='jev_choice']+choice+features
    ids={r['base_id'] for r in id_rank}
    diagnostic=id_rank+[r for r in canonical if r['base_id'] in ids and r['arm'] in ('rule','id_only','jev_score','jev_noul_features_code','nano_none','luna_none','luna_low')]
    # Compare corrected Choice repeats with corrected baseline, preserving historical arm labels.
    corrected_choice=copy.deepcopy(choice)
    for r in corrected_choice:r['arm']='jev_choice'
    repeat_base=[r for r in original if r['arm']!='jev_choice']+corrected_choice
    result=dict(main_original=summary(original),canonical=summary(canonical),id_only_diagnostic_10=summary(diagnostic),
        paired=pairs(canonical,[('jev_choice_id_eval','nano_choice','top1'),('jev_choice_id_eval','luna_choice','top1'),
        ('jev_noul_features_code','jev_score','ndcg'),('jev_noul_features_code','luna_none','ndcg'),
        ('jev_noul_features_code','luna_low','ndcg'),('jev_noul_features_code','rule','ndcg'),('luna_none','nano_none','ndcg')]),
        stability_main=stability(repeat_base,repeat),stability_features=stability(features,feature_repeat),
        failures_original=dict(Counter(str((r['arm'],r.get('validation_error'),r.get('error_type'),r.get('http_status'))) for r in original if r['status']!='ok')),
        humans=0,primary_n=27,id_diagnostic_n=10,independent_customers=0,
        limits=['Self-authored synthetic oracle; rule baseline knows generator phrases',
        'Main OpenAI Top3 includes exact quotes; Jev plus code does not generate quotes',
        'Additional arms tested later on reused evaluation cases; exploratory, not unused holdout',
        'Stability repeats are dependent observations, not additional independent quality cases',
        'Observed cache usage; no controlled cold/warm test; web search calls zero'])
    db=sqlite3.connect((DATA/'ledger.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    calls={r['call_id']:dict(r) for r in db.execute('SELECT * FROM calls')};db.close()
    result['stage_costs']=[]
    for directory in sorted((DATA/'runs').iterdir()):
        if not (directory/'finish.json').exists():continue
        rows=read_run(directory.name)
        unique={cid for r in rows for cid in r['call_ids']}
        entries=[calls[cid] for cid in unique]
        result['stage_costs'].append(dict(run=directory.name,rows=len(rows),unique_calls=len(unique),
            known_usd=sum(float(c['actual_usd']) for c in entries if c['usage_known']),
            unknown_reserved_usd=sum(float(c['upper_usd']) for c in entries if not c['usage_known'])))
    common_repeat_ids={r['base_id'] for r in repeat}&{r['base_id'] for r in feature_repeat}
    result['stability_common_base_cases']=len(common_repeat_ids)
    result['stability_common_6']=stability(repeat_base+features,[r for r in repeat+feature_repeat if r['base_id'] in common_repeat_ids])
    # All call IDs, including hierarchical Choice subcalls and shared cascade filter, are reconciled separately.
    result['lane_costs']={lane:dict(calls=sum(c['lane']==lane for c in calls.values()),
        known_usd=sum(float(c['actual_usd']) for c in calls.values() if c['lane']==lane and c['usage_known']),
        unknown_reserved_usd=sum(float(c['upper_usd']) for c in calls.values() if c['lane']==lane and not c['usage_known'])) for lane in ('nano','luna','jev')}
    output=DATA/'analysis'/output_id;output.mkdir(parents=True,exist_ok=False)
    save_new(output/'summary.json',result)
    print(json.dumps({'output':str(output),'canonical_arms':len(result['canonical']),'stage_count':len(result['stage_costs'])}))

if __name__=='__main__':main(sys.argv[1])
