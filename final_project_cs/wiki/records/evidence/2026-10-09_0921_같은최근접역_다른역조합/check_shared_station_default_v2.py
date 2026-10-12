from pathlib import Path
from datetime import date, datetime
import importlib.util
import json
import socket
import sys

root = Path(__file__).resolve().parents[2]
cs = root/'final_project_cs'
sys.path.insert(0,str(cs))
state = json.loads((Path(__file__).parent/'shared-nearest-station-work-v1.json').read_text(encoding='utf8'))
ev = cs/'wiki/records/evidence'/state['tag']
audit = json.loads((ev/'native-path-replay-v1.json').read_text(encoding='utf8'))
old_path = root/next(x['backup'] for x in state['backups'] if x['source'].endswith('/engine/plan.py'))
spec = importlib.util.spec_from_file_location('app.domains.travel_ops.instances.mobility.engine.plan_before_default',old_path)
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
attempts = []
def block(*a,**kw):
    attempts.append('blocked')
    raise RuntimeError('Network is prohibited during local replay')
socket.socket.connect = block
socket.create_connection = block
rt = build_verifier(quiet=True,seoul_key='',gh_url='')
record = next(x for x in audit['pair_records'] if x['id']=='G04')
default = []
for name,cls in [('before',old.Planner),('after',Planner)]:
    planner = cls(rt,modes=['subway','walk'])
    got,why = planner.leg(record['a'],record['b'],datetime.fromisoformat('2026-10-09T10:30:00+09:00'),
                         {},True,'default-G04',not_before_dt=datetime.fromisoformat('2026-10-09T09:00:00+09:00'))
    assert got is not None,why
    planned = next(x for x in got[0]['options'] if x['id']==got[0]['planned'])
    default.append({'variant':name,'planned':planned,'options':got[0]['options']})
assert all(x['planned']['id']=='walk' and x['planned']['eta_min']==8 for x in default)
earliest = []
for name,cls in [('before',old.Planner),('after',Planner)]:
    planner = cls(rt,modes=['subway'])
    got,why = planner.earliest(record['a'],record['b'],datetime.fromisoformat('2026-10-09T09:00:00+09:00'),
                              {},True,'earliest-G04')
    earliest.append({'variant':name,'available':got is not None,'result':got,'why':why})
assert earliest[0]['available'] is False and earliest[1]['available'] is True
assert not attempts
with (ev/'native-default-and-earliest-v2.json').open('x',encoding='utf8') as f:
    json.dump({'created_at':datetime.now().astimezone().isoformat(),'native_unique_pairs':1,
               'default':default,'earliest':earliest,'network_attempts':len(attempts),
               'scope':'Same existing G04 model replay; no new web or actual trip measurement.'},
              f,ensure_ascii=False,indent=2,default=lambda value: value.isoformat() if isinstance(value,(date,datetime)) else (_ for _ in ()).throw(TypeError(type(value).__name__)))
print(json.dumps({'default':[(x['variant'],x['planned']['id'],x['planned']['eta_min']) for x in default],
                  'earliest':[(x['variant'],x['available']) for x in earliest]},ensure_ascii=False))
