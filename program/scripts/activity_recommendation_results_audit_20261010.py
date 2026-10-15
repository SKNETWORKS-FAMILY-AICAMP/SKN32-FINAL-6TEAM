"""Read-only independent retest audit; never reads credentials or calls a provider."""
from pathlib import Path
import collections
from decimal import Decimal
import hashlib
import json
import math
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'program/scripts/activity_recommendation_retest'
sys.path.insert(0,str(HERE))
from fixtures import prepare_case
from metrics import evaluate,validate_citations
CONFIG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
DATA=ROOT/CONFIG['dataset_directory']

def read(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]

def dollars(lane,usage,cold=False):
    p=CONFIG['prices'][lane];d=usage.get('input_tokens_details') or {}
    inp=usage['input_tokens'];out=usage['output_tokens']
    cached=d.get('cached_tokens',usage.get('cached_input_tokens',0)) or 0
    writes=d.get('cache_write_tokens',usage.get('cache_creation_input_tokens',0)) or 0
    if cold:cached=writes=0
    return ((inp-cached-writes)*p['input']+cached*p['cached_input']+writes*p['cache_write']+out*p['output'])/1e6

def audit(output_name):
    out=DATA/'analysis'/output_name;out.mkdir(parents=True,exist_ok=False)
    cases={c['base_id']:c for split in ('dev','eval') for c in read(DATA/CONFIG['raw_subdirectory']/(split+'.jsonl'))}
    db=sqlite3.connect((DATA/'ledger.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    calls={c['call_id']:dict(c) for c in db.execute('SELECT * FROM calls')};db.close()
    response_files=list((DATA/'runs').glob('*/responses/*.json'))
    raw={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in response_files}
    errors=[];scored=0;quoted=0;paths=0;stage_results={};scale=collections.defaultdict(list)
    for run in sorted((DATA/'runs').iterdir()):
        if not (run/'results.jsonl').exists():continue
        values=read(run/'results.jsonl');finish=json.loads((run/'finish.json').read_text(encoding='utf-8')) if (run/'finish.json').exists() else None
        stage_results[run.name]={'rows':len(values),'finish':finish,'path_failures':sum(r['status']!='ok' for r in values)}
        for row in values:
            case=cases[row['base_id']];inverse=row.get('identity_inverse',{})
            ids=[inverse.get(cid,cid) for cid in row.get('ranking',[])]
            prepared=prepare_case(case);status=prepared['status'];choice='choice' in row['arm']
            supplied={'status':row.get('decision_status',row.get('status')) if status!='ready' else ('ready' if row['status']=='ok' else row['status']),'ranking':ids}
            expected=evaluate(case,supplied,expected_count=1 if choice and status=='ready' else None)
            actual=row['metrics'];scored+=1
            checks=[actual['valid']==expected['format_valid'],actual['top1']==expected['top1_correct'],
                actual['eligible']==expected['ranking_applicable'],
                row['eligible_count']==len(prepared.get('feasible_ids',[])),
                actual['k']==expected.get('requested_count',0),
                actual['hard_violations']==expected['hard_violations']]
            if status!='ready':checks.append(actual['status_correct']==expected['status_correct'])
            metric_k=expected['metric_k']
            for left,right in [('ndcg',f'ndcg{metric_k}'),('recall',f'recall{metric_k}')]:
                a=actual[left];b=expected[right];checks.append(a is b if a is None or b is None else math.isclose(a,b,abs_tol=1e-10))
            if not all(checks):errors.append({'kind':'metrics','run':run.name,'case':row['case_id'],'arm':row['arm']})
            if row.get('reasons') and row['status']=='ok':
                def restore(s):
                    for new,old in inverse.items():s=s.replace(new,old)
                    return s
                reasons=[{k:restore(v) for k,v in r.items()} for r in row['reasons']]
                quoted+=1
                if not validate_citations(case,{'ranking':ids,'reasons':reasons})['valid']:errors.append({'kind':'quote','run':run.name,'case':row['case_id'],'arm':row['arm']})
            path_cost=sum(float(calls[cid]['actual_usd'] if calls[cid]['usage_known'] else calls[cid]['upper_usd']) for cid in row['call_ids'])
            paths+=1
            if not math.isclose(path_cost,row['cost_usd'],abs_tol=1e-10):errors.append({'kind':'path_cost','run':run.name,'case':row['case_id'],'arm':row['arm']})
            if 'eval' in run.name and actual['eligible'] and row['eligible_count']>=2:
                us=[(calls[cid]['lane'],raw.get(cid,{}).get('usage')) for cid in row['call_ids']]
                cold=sum(dollars(lane,u,True) for lane,u in us if u)
                scale[(run.name,len(case['candidates']),row['arm'])].append({'ndcg':actual['ndcg'],'top1':actual['top1'],'cost':row['cost_usd'],'no_cache_same_tokens':cold})
    raw_checked=0;token_totals=collections.defaultdict(collections.Counter)
    for cid,c in calls.items():
        usage=raw.get(cid,{}).get('usage')
        if usage:
            raw_checked+=1
            actual=dollars(c['lane'],usage)
            if not c['usage_known'] or not math.isclose(actual,float(c['actual_usd']),abs_tol=1e-10):errors.append({'kind':'raw_cost','call_id':cid})
            details=usage.get('input_tokens_details') or {}
            token_totals[c['lane']].update(input=usage['input_tokens'],output=usage['output_tokens'],cache_read=details.get('cached_tokens',usage.get('cached_input_tokens',0)) or 0,
                 cache_write=details.get('cache_write_tokens',usage.get('cache_creation_input_tokens',0)) or 0,
                 reasoning=(usage.get('output_tokens_details') or {}).get('reasoning_tokens',0) or 0)
        elif c['usage_known']:errors.append({'kind':'missing_raw_usage','call_id':cid})
    known=sum((Decimal(c['actual_usd']) for c in calls.values() if c['usage_known']),Decimal(0))
    unknown=sum((Decimal(c['upper_usd']) for c in calls.values() if not c['usage_known']),Decimal(0))
    summary={'stages':stage_results,'score_checks':scored,'quote_checks':quoted,'path_cost_checks':paths,'raw_cost_checks':raw_checked,'errors':errors,
      'reserved_calls':len(calls),'finished_calls':sum(c['finished'] for c in calls.values()),'known_usd':str(known),'unknown_reserved_usd':str(unknown),
      'baseline_usd':CONFIG['baseline_usd'],'cumulative_usd':str(known+unknown+Decimal(str(CONFIG['baseline_usd']))),'token_totals_unique_calls':dict(token_totals),
      'scales':[{'run':key[0],'candidates':key[1],'arm':key[2],'n':len(items),**{field:sum(r[field] for r in items)/len(items) for field in items[0]}} for key,items in sorted(scale.items())],
      'scope':'Independent scorer and raw usage reconciliation; synthetic data; no human or live venue verification',
      'no_cache_scope':'counterfactual repricing with observed token counts fixed; not new cold calls',
      'audit_script_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['score_checks','quote_checks','path_cost_checks','raw_cost_checks','errors','reserved_calls','known_usd','unknown_reserved_usd','cumulative_usd']}))

if __name__=='__main__':audit(sys.argv[1])
