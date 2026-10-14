from pathlib import Path
from datetime import datetime
import sys,json,socket
sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parents[2];cs=root/'final_project_cs'
ev=cs/'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단'
sys.path.insert(0,str(cs))
def deny(*a,**k):raise RuntimeError('통신 차단')
socket.socket.connect=deny;socket.socket.connect_ex=deny
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.plan import Planner,service_day
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from tests.unit.travel.mobility.test_plan_v1 import _NT
rt=build_verifier(quiet=True,local_router=True,seoul_key='',gh_url='',data_dir=str(root/'datasets/mobility/processed'))
original=BusRoutes.routes_between
rows=[]
when=datetime.fromisoformat('2026-09-29T15:00:00+09:00');sd,by=service_day(when)
for enabled in (False,True):
    def pairs(self,a,b,c,d,e,include_access=False):return original(self,a,b,c,d,e,enabled and include_access)
    BusRoutes.routes_between=pairs
    p=Planner(rt,modes=['bus']);options=p._bus_direct(_NT[0],_NT[1],when,sd,by,{},True,'rv',p._walk_limit({}))
    items=[]
    for o in options:
        check,verdict=p._recheck_at(o,o['_start'],by,{},True,'rv')
        items.append({'route':o['_route'],'key':o['_key'],'start':o['_start'],'eta':o['eta_min'],
                      'walk':o['_walk_m'],'recheck_verdict':verdict,'recheck':check})
    rows.append({'enabled':enabled,'items':items})
    print(json.dumps({'enabled':enabled,'items':[{k:v for k,v in x.items() if k!='recheck'} for x in items]},ensure_ascii=False),flush=True)
BusRoutes.routes_between=original
with (ev/'revival-diagnosis-v1.json').open('x',encoding='utf8') as f:json.dump(rows,f,ensure_ascii=False,indent=2,default=str)
