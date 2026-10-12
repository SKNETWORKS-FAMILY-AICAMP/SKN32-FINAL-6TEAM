from pathlib import Path
import sys,os,json,subprocess
sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parents[2];cs=root/'final_project_cs';ev=cs/'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단'
stage=sys.argv[1];base=Path(__file__).parent/f'pytest-bus-access-{stage}'
assert not base.exists();assert not (ev/f'{stage}.log').exists()
paths=[str(p.relative_to(cs)) for p in sorted((cs/'tests/unit/travel/mobility').glob('test_bus*.py'))]
paths += ['tests/unit/travel/mobility/'+n for n in ['test_plan_access_walk.py','test_plan_v1.py','test_review_fixes_plan.py','test_transfer_fare_product_v1.py']]
guard='''import socket,sys,json
from pathlib import Path
calls=[]
def deny(*a,**kw):
    calls.append(1);raise RuntimeError('offline network denied')
socket.socket.connect=deny;socket.socket.connect_ex=deny
from app.domains.travel_ops.instances.mobility.engine import runtime
original=runtime.build_verifier
def offline(**kw):
    kw.setdefault('local_router',True);kw.setdefault('seoul_key','');kw.setdefault('gh_url','')
    return original(**kw)
runtime.build_verifier=offline
'''
if stage=='related-baseline':
    guard+='''from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
original_pairs=BusRoutes.routes_between
def old_pairs(self,a,b,c,d,e,include_access=False):
    return original_pairs(self,a,b,c,d,e,False)
BusRoutes.routes_between=old_pairs
'''
    paths=[p for p in paths if not p.endswith('test_bus_access_pairs_v1.py')]
guard+='''import pytest
code=pytest.main(sys.argv[1:])
Path('''+repr(str(ev/f'{stage}-network.json'))+''').write_text(json.dumps({'network_attempts':len(calls),'limited_api_calls':0}),encoding='utf8')
sys.exit(code)
'''
cmd=[sys.executable,'-c',guard,*paths,'-q','--basetemp='+str(base),'--junitxml='+str(ev/f'{stage}.xml')]
p=subprocess.run(cmd,cwd=cs,env=dict(os.environ,PYTHONIOENCODING='utf8'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8')
with (ev/f'{stage}.log').open('x',encoding='utf8') as f:f.write(p.stdout)
with (ev/f'{stage}-run.json').open('x',encoding='utf8') as f:json.dump({'command':cmd,'exit_code':p.returncode},f,indent=2)
print(p.stdout[-5500:]);sys.exit(p.returncode)
