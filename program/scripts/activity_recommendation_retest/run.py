"""Sequential, cost-bounded paid retest. Frozen independent synthetic evaluation."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
from statistics import mean
import sys

from budget import Budget
from fixtures import prepare_case,public_case,rule_rank
from providers import CONFIG,HERE,ROOT,Providers,save_new

DATA=ROOT/CONFIG['dataset_directory']
ARMS=['nano_none','nano_low','luna_none','luna_low','jev_choice','jev_score']

def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]

def append(path,value):
    with Path(path).open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');stream.flush()

def root_metrics(case,answer,choice=False):
    prepared=prepare_case(case);state=prepared['status'];ranking=answer.get('ranking',[])
    if state!='ready':
        valid=answer.get('decision_status')==state and ranking==[]
        return {'eligible':False,'valid':valid,'status_correct':valid,'top1':None,'ndcg':None,'recall':None,'hard_violations':0,'k':0}
    feasible=set(prepared['feasible_ids']);candidates={c['id']:c for c in case['candidates']}
    w=case['weights']
    def value(cid):
        c=candidates[cid]
        return w['taste']*c['oracle_taste']+w['travel']*max(0,1-c['facts']['travel_min']['value']/60)+w['similarity']*c['oracle_similarity']
    ideal=sorted(feasible,key=lambda cid:(-value(cid),cid));k=1 if choice else min(3,len(ideal))
    good=answer.get('status')=='ok' and len(ranking)==k and all(isinstance(cid,str) for cid in ranking) and len(set(ranking))==k and set(ranking)<=feasible
    hard=sum(cid not in feasible for cid in ranking)
    if not good:return {'eligible':True,'valid':False,'status_correct':False,'top1':False,'ndcg':0.0,'recall':0.0,'hard_violations':hard,'k':k}
    dcg=lambda ids:sum(value(cid)/__import__('math').log2(i+2) for i,cid in enumerate(ids))
    best=dcg(ideal[:k]);remaining=k;hits=0;offset=0
    while remaining:
        group=[];group_value=value(ideal[offset])
        while offset<len(ideal) and abs(value(ideal[offset])-group_value)<1e-12:
            group.append(ideal[offset]);offset+=1
        quota=min(remaining,len(group));hits+=min(quota,len(set(ranking)&set(group)));remaining-=quota
    return {'eligible':True,'valid':True,'status_correct':True,'top1':abs(value(ranking[0])-value(ideal[0]))<1e-12,
       'ndcg':dcg(ranking)/best if best else 1.0,'recall':hits/k,
       'hard_violations':hard,'k':k,'regret':value(ideal[0])-value(ranking[0]),'gold_best_ids':[cid for cid in ideal if abs(value(cid)-value(ideal[0]))<1e-12]}

def choose_dev(directory):
    source=rows(Path(directory)/'results.jsonl');selected={}
    for lane in ('nano','luna'):
        values=[]
        for effort in CONFIG['efforts']:
            subset=[r for r in source if r['arm']==lane+'_'+effort and r['metrics']['eligible']]
            values.append((mean(r['metrics']['ndcg'] for r in subset),-mean(r['cost_usd'] for r in subset),effort))
        selected[lane]=max(values)[2]
    return selected

def variant(case,index):
    changed=copy.deepcopy(case);rng=random.Random(CONFIG['seed']+index+971)
    if index%2==0:return changed,'same_input',{}
    mapping={c['id']:f'{rng.getrandbits(96):024x}' for c in changed['candidates']}
    def rename(value):
        if isinstance(value,str):
            for old,new in mapping.items():value=value.replace(old,new)
            return value
        if isinstance(value,dict):return {rename(k):rename(v) for k,v in value.items()}
        if isinstance(value,list):return [rename(v) for v in value]
        return value
    changed=rename(changed);rng.shuffle(changed['candidates'])
    return changed,'renamed_id_and_permutation',{new:old for old,new in mapping.items()}

def run(args):
    data_source=DATA/CONFIG['raw_subdirectory']/('dev.jsonl' if args.stage in ('smoke','dev') else 'eval.jsonl')
    cases=rows(data_source)
    if args.stage=='smoke':cases=[c for c in cases if prepare_case(c)['status']=='ready' and len(c['candidates'])<=16][:1]
    selected={'nano':'none','luna':'none'} if args.stage in ('smoke','dev') else choose_dev(DATA/'runs'/args.dev_run)
    budget=Budget(DATA/'ledger.sqlite',CONFIG['new_budget_usd'],CONFIG['max_paid_calls'],CONFIG['baseline_usd'])
    with budget.run_lock():
        directory=DATA/'runs'/args.run_id;directory.mkdir(parents=True,exist_ok=False)
        providers=Providers(budget,directory)
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
        save_new(directory/'metadata.json',{'stage':args.stage,'config':CONFIG,'source_hashes':source_hashes,
            'dataset_hash':hashlib.sha256(data_source.read_bytes()).hexdigest(),'selected_efforts_from_dev':selected,
            'human_reviews':0,'tools':[],'auto_retries':0,'started_at':datetime.now(timezone.utc).isoformat(),
            'retest_is_synthetic':True,'rule_is_independent_research_baseline':True})
        work=[]
        if args.stage=='stability':
            ready=sorted([c for c in cases if prepare_case(c)['status']=='ready' and len(c['candidates'])<=16],key=lambda c:c['case_id'])[:CONFIG.get('stability_case_count',8)]
            for i,c in enumerate(ready):
                for offset in (0,1):
                    changed,condition,inverse=variant(c,i*2+offset);work.append((changed,condition,inverse))
        else:work=[(c,'main',{}) for c in cases]
        random.Random(CONFIG['seed']).shuffle(work)
        save_new(directory/'schedule.json',[{'case_id':c['case_id'],'condition':condition,'identity_inverse':inverse} for c,condition,inverse in work])
        completed=0;stop=None
        try:
            for index,(case,condition,inverse) in enumerate(work):
                prepared=prepare_case(case);state=prepared['status'];count=prepared['requested_count']
                common={'case_id':case['case_id'],'base_id':case['base_id'],'stratum':case['stratum'],
                   'split':case['split'],'condition':condition,'identity_inverse':inverse,
                   'decision_status':state,'eligible_count':len(prepared.get('feasible_ids',[]))}
                public=public_case(case,prepared.get('feasible_ids',[]))
                arms=list(ARMS)+(['nano_choice','luna_choice'] if args.stage!='dev' else []);random.Random(CONFIG['seed']+index).shuffle(arms)
                scored=None
                for arm in ['rule','id_only']+arms:
                    if state!='ready':
                        result={'status':'ok','decision_status':state,'ranking':[],'cost_usd':0.0,'latency_ms':0.0,'call_ids':[]}
                    elif arm in ('rule','id_only'):
                        ranking=rule_rank(case) if arm=='rule' else sorted(prepared['feasible_ids'])
                        result={'status':'ok','decision_status':'ready','ranking':ranking[:count],'cost_usd':0.0,'latency_ms':0.0,'call_ids':[]}
                    elif arm=='jev_choice':result=providers.choice(public)
                    elif arm in ('nano_choice','luna_choice'):result=providers.pick(arm.split('_')[0],public)
                    elif arm=='jev_score':
                        result=providers.score(public);scored=copy.deepcopy(result)
                        result['ranking']=result.get('ranking',[])[:count]
                    else:
                        lane,effort=arm.split('_');result=providers.rank(lane,public,effort)
                    append(directory/'results.jsonl',{**common,'arm':arm,**result,'metrics':root_metrics(case,result,arm.endswith('_choice'))})
                if args.stage in ('eval','stability'):
                    if state!='ready':
                        result={'status':'ok','decision_status':state,'ranking':[],'cost_usd':0.0,'latency_ms':0.0,'call_ids':[]}
                    elif scored is None or scored['status']!='ok':
                        result={'status':'blocked_by_filter','ranking':[],'cost_usd':0.0 if scored is None else scored['cost_usd'],
                           'latency_ms':0.0 if scored is None else scored['latency_ms'],'call_ids':[] if scored is None else scored['call_ids']}
                    else:
                        raw_ids=scored['ranking'][:CONFIG['shortlist_keep']]
                        protected=set(raw_ids+rule_rank(case)[:2])
                        shortlist=public_case(case,[c['id'] for c in public['candidates'] if c['id'] in protected])
                        result=providers.rank('luna',shortlist,selected['luna'])
                        result['ranker_cost_usd']=result['cost_usd'];result['ranker_latency_ms']=result['latency_ms']
                        result['cost_usd']+=scored['cost_usd'];result['latency_ms']+=scored['latency_ms']
                        result['call_ids']=scored['call_ids']+result['call_ids']
                        gold=root_metrics(case,{'status':'ok','ranking':scored['ranking'][:count]})['gold_best_ids']
                        result.update(raw_shortlist_best_preserved=bool(set(gold)&set(raw_ids)),
                           protected_shortlist_best_preserved=bool(set(gold)&protected),shortlist_count=len(protected))
                    append(directory/'results.jsonl',{**common,'arm':'jev_luna','luna_effort':selected['luna'],**result,'metrics':root_metrics(case,result)})
                completed+=1
                print(json.dumps({'stage':args.stage,'completed':completed,'planned':len(work),'budget':budget.snapshot()},ensure_ascii=True),flush=True)
        except Exception as exc:
            stop=type(exc).__name__
            print(json.dumps({'stopped':stop,'completed':completed,'planned':len(work),'budget':budget.snapshot()}),flush=True)
            raise
        finally:
            save_new(directory/'finish.json',{'completed':completed,'planned':len(work),'stop':stop,'budget':budget.snapshot(),
                'finished_at':datetime.now(timezone.utc).isoformat(),'source_hashes_unchanged':source_hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}})

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=('smoke','dev','eval','stability'),required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--dev-run',default='dev-v1')
    run(parser.parse_args())
