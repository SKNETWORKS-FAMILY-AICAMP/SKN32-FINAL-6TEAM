import sys, importlib.util, json, itertools
from pathlib import Path
from types import SimpleNamespace
W=Path(__file__).parent
CS=Path('C:/_proj/busreview1029/final_project_cs'); sys.path.insert(0,str(CS))
from app.domains.travel_ops.instances.mobility.engine.candidates import ride_estimator
mods=[]
for i,path in enumerate((W/'latest-baseline.py',CS/'app/domains/travel_ops/instances/mobility/engine/bus_profile.py')):
    spec=importlib.util.spec_from_file_location('integrate'+str(i),path); m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);mods.append(m)
stops=[dict(seq=i+1,station_id=f'S{i+1}',sect_dist_m=600) for i in range(33)]
class Bus:
    def __init__(self): self.stops={'R':stops}
count=0
for hour,day,md,speed in itertools.product(range(24),('weekday','holiday'),(0,5,31),(0,20)):
    vs=[SimpleNamespace(bus=Bus(),bus_prof=m.BusSegProfile.load(W/'valid-synthetic.jsonl.gz'),R={},rv=lambda *a:md,bus_speed=lambda *a:(speed,'','',[])) for m in mods]
    fns=[ride_estimator(v,hour,day) for v in vs]
    for a,b in ((0,1),(0,32),(4,19),(20,32)):
        values=[f(SimpleNamespace(route_id='R'),stops[a],stops[b]) for f in fns]
        assert values[0]==values[1],(hour,day,md,speed,a,b,values)
        # Reusing the real candidate cache must retain the same result.
        assert [f(SimpleNamespace(route_id='R'),stops[a],stops[b]) for f in fns]==values
        count+=1
(W/'candidate-integration.json').write_text(json.dumps({'passed':count,'failed':0,'cached_replay_passed':count},indent=2))
print(count,'candidate route estimates + cached replay passed')
