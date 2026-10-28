import sys, importlib.util, hashlib, json, gzip, dataclasses, itertools, warnings, time, random, statistics, struct
from pathlib import Path
import numpy as np
OUT=Path(__file__).parent
CS=Path('C:/_proj/busreview1029/final_project_cs')
REL=Path('app/domains/travel_ops/instances/mobility/engine/bus_profile.py')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m
src=(CS/REL).read_bytes()
assert src.count(b'np.isnan(v) else float(v)')==1
(OUT/'latest-baseline.py').write_bytes(src)
candidate=src.replace(b'np.isnan(v) else float(v)',b'math.isnan(v) else float(v)')
(CS/REL).write_bytes(candidate)
mods=[load('review_base',OUT/'latest-baseline.py'),load('review_candidate',CS/REL)]
def outcome(fn):
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter('always')
        try:
            v=fn()
            if dataclasses.is_dataclass(v): v=dataclasses.asdict(v)
            elif isinstance(v,float): v=('float',struct.pack('!d',v).hex())
            result=('return',v)
        except Exception as e: result=('error',type(e).__name__,str(e))
        return result,[(type(w.message).__name__,str(w.message)) for w in ws]
rng=np.random.default_rng(102903)
# Valid loader fixture: quantiles are ordered, missing hours have n=0.
records=[]
for i in range(32):
    rec=dict(route_id='R',from_seq=i+1,to_seq=i+2,from_id=f'S{i+1}',to_id=f'S{i+2}')
    for day in ('weekday','holiday'):
        qs=np.sort(rng.uniform(10,480,(3,24)),axis=0)
        n=rng.choice([0,4,5,30],24)
        rec[day]={'n':n.tolist(),**{q:[float(qs[j,h]) if n[h] else None for h in range(24)] for j,q in enumerate(('p10','p50','p90'))}}
    records.append(rec)
fixture=OUT/'valid-synthetic.jsonl.gz'
with gzip.open(fixture,'wt',encoding='utf8') as f:
    for rec in [{'_meta':True,'source_id':'synthetic-review','built_at':'2026-10-29'},*records]: f.write(json.dumps(rec)+'\n')
profiles=[m.BusSegProfile.load(fixture) for m in mods]
assert profiles[0].arr.dtype==np.float32
assert profiles[0].arr.tobytes()==profiles[1].arr.tobytes()
counts={'loaded_cells':0,'float32_bits':0,'walks':0,'helpers':0}; mismatches=[]
def compare(label,fn):
    a,b=[outcome(lambda:fn(p,m)) for p,m in zip(profiles,mods)]
    if a!=b: mismatches.append((label,str(a),str(b)))
    counts[label]+=1
for args in itertools.product(range(32),('weekday','holiday'),range(24),('n','p10','p50','p90'),(0,5,31)):
    compare('loaded_cells',lambda p,m:p.cell(*args))
# Random IEEE float32 bit patterns, including signed zero, subnormals and sNaN.
bits=np.r_[rng.integers(0,2**32,10000,dtype=np.uint32),np.array([0,0x80000000,1,0x7f800000,0xff800000,0x7fc00000,0x7f800001],dtype=np.uint32)]
for bit in bits:
    arr=np.full((1,2,4,24),30,dtype=np.float32); arr[0,0,2,0]=np.array([bit],dtype=np.uint32).view(np.float32)[0]
    old=profiles; profiles=[m.BusSegProfile({}, {},arr.copy(),{}) for m in mods]
    compare('float32_bits',lambda p,m:p.cell(0,'weekday',0,'p50',5)); profiles=old
stops=[dict(seq=i+1,station_id=f'S{i+1}',sect_dist_m=600) for i in range(33)]
for trial in range(1500):
    a=int(rng.integers(1,30)); b=int(rng.integers(a,34)); dep=float(rng.choice([0,59.9,1079,1439,1440,2879,2880])); q=random.Random(trial).choice(['p10','p50','p90'])
    dts=lambda t:('weekday',) if t<1440 else ('weekday','holiday')
    compare('walks',lambda p,m:p.walk('R',stops,a,b,dep,dts,q,5,lambda d:3.0))
    for name in ('board_caps','last_pass_early'):
        compare('helpers',lambda p,m:getattr(m,name)(p,'R',stops,a,dep,dts,5))
result={'counts':counts,'mismatches':mismatches,'python':sys.version,'numpy':np.__version__,'baseline_sha256':hashlib.sha256(src).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest()}
(OUT/'semantics.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2)); assert not mismatches
