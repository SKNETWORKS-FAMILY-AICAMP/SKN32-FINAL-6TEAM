import sys, importlib.util, json, random, time, statistics, hashlib
from pathlib import Path
import numpy as np
W=Path(__file__).parent
paths=[W/'latest-baseline.py',Path('C:/_proj/busreview1029/final_project_cs/app/domains/travel_ops/instances/mobility/engine/bus_profile.py')]
mods=[]
for i,p in enumerate(paths):
    spec=importlib.util.spec_from_file_location('perf'+str(i),p); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); mods.append(m)
profiles=[m.BusSegProfile.load(W/'valid-synthetic.jsonl.gz') for m in mods]
stops=[dict(seq=i+1,station_id=f'S{i+1}',sect_dist_m=600) for i in range(33)]
rng=random.Random(102904)
args=[(rng.randrange(32),rng.choice(('weekday','holiday')),rng.randrange(24),rng.choice(('p10','p50','p90')),rng.choice((0,5,5,5,30))) for _ in range(4096)]
requests=[(rng.randrange(1,8),rng.randrange(16,34),rng.choice((475.,1079.,1439.,1441.,2879.)),rng.choice(('p10','p50','p90'))) for _ in range(160)]
def cell(p):
    acc=0.; missing=0
    for _ in range(12):
        for a in args:
            v=p.cell(*a)
            if v is None: missing+=1
            else: acc+=v
    return acc,missing
def walk(p):
    out=[]
    for _ in range(4):
        for a,b,dep,q in requests:
            w=p.walk('R',stops,a,b,dep,lambda t:('weekday',) if t<1440 else ('weekday','holiday'),q,5,lambda d:3.)
            out.append(tuple(vars(w).values()))
    return out
result={'python':sys.version,'numpy':np.__version__,'seed':102904,'source_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],'trials_per_workload':30}
for name,fn in [('cell',cell),('mixed_walk',walk)]:
    for _ in range(3):
        for p in profiles: fn(p)
    rows=[]
    orders=[[0,1]]*15+[[1,0]]*15; rng.shuffle(orders)
    for order in orders:
        ts={}; outputs={}
        for i in order:
            start=time.perf_counter(); outputs[i]=fn(profiles[i]); ts[i]=time.perf_counter()-start
        assert outputs[0]==outputs[1]
        rows.append({'order':order,'baseline_s':ts[0],'candidate_s':ts[1]})
    ratios=np.array([1-r['candidate_s']/r['baseline_s'] for r in rows]); boot=np.random.default_rng(102904).choice(ratios,(20000,30),replace=True).mean(axis=1)
    result[name]={'trials':rows,'median_baseline_s':statistics.median(r['baseline_s'] for r in rows),'median_candidate_s':statistics.median(r['candidate_s'] for r in rows),'mean_paired_reduction_pct':float(ratios.mean()*100),'bootstrap_mean_paired_95ci_pct':(np.quantile(boot,[.025,.975])*100).tolist(),'candidate_faster':sum(r['candidate_s']<r['baseline_s'] for r in rows)}
    print(name,{k:v for k,v in result[name].items() if k!='trials'},flush=True)
(W/'performance.json').write_text(json.dumps(result,indent=2),encoding='utf8')
