import sys, importlib.util, json, hashlib, random, dataclasses
from pathlib import Path
W=Path(__file__).parent
DATA=Path('C:/_proj/final_workspace/datasets/mobility/processed/mobility/bus_seg_profile_v1.jsonl.gz')
paths=[W/'latest-baseline.py',Path('C:/_proj/busreview1029/final_project_cs/app/domains/travel_ops/instances/mobility/engine/bus_profile.py')]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=digest(DATA); profiles=[]
for i,p in enumerate(paths):
    spec=importlib.util.spec_from_file_location('real'+str(i),p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);profiles.append(m.BusSegProfile.load(DATA))
assert profiles[0].arr.tobytes()==profiles[1].arr.tobytes()
assert profiles[0].index==profiles[1].index and profiles[0].ends==profiles[1].ends and profiles[0].meta==profiles[1].meta
rng=random.Random(102905)
for _ in range(50000):
    args=(rng.randrange(len(profiles[0].arr)),rng.choice(('weekday','holiday')),rng.randrange(24),rng.choice(('n','p10','p50','p90')),rng.choice((0,5,30,31)))
    vals=[p.cell(*args) for p in profiles];assert vals[0]==vals[1]
routes={}
for (rid,seq),i in profiles[0].index.items(): routes.setdefault(rid,[]).append((seq,i))
walks=0
for rid in rng.sample(list(routes),min(120,len(routes))):
    rows=sorted(routes[rid]); start=rng.randrange(len(rows)); rows=rows[start:start+24]
    chain=[]
    for seq,i in rows:
        fid,tid,tseq=profiles[0].ends[i]
        if chain and (chain[-1]['seq']!=seq or chain[-1]['station_id']!=fid): break
        if not chain: chain.append(dict(seq=seq,station_id=fid,sect_dist_m=None))
        chain.append(dict(seq=int(tseq),station_id=tid,sect_dist_m=None))
    if len(chain)<2: continue
    for dep in (475.,1079.,1439.,2879.):
        args=(rid,chain,chain[0]['seq'],chain[-1]['seq'],dep,lambda t:('weekday',) if t<1440 else ('weekday','holiday'),'p50',5,lambda d:None)
        vals=[dataclasses.asdict(p.walk(*args)) for p in profiles];assert vals[0]==vals[1];walks+=1
after=digest(DATA); assert before==after
result={'source_sha256_before':before,'source_sha256_after':after,'arr_shape':profiles[0].arr.shape,'dtype':str(profiles[0].arr.dtype),'array_bytes_identical':True,'metadata_and_endpoints_identical':True,'sampled_cells_passed':50000,'actual_route_walks_passed':walks,'failed':0,'seed':102905,'records_exported':0}
(W/'real-profile.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
