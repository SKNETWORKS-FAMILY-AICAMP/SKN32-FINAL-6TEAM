from pathlib import Path
from datetime import datetime
import hashlib
import importlib.util
import json
import socket
import sys

root = Path(__file__).resolve().parents[2]
cs = root/'final_project_cs'
sys.path.insert(0,str(cs))
scratch = Path(__file__).parent
state = json.loads((scratch/'shared-nearest-station-work-v1.json').read_text(encoding='utf8'))
ev = cs/'wiki/records/evidence'/state['tag']
old_path = root/next(x['backup'] for x in state['backups'] if x['source'].endswith('/engine/plan.py'))
spec = importlib.util.spec_from_file_location('app.domains.travel_ops.instances.mobility.engine.plan_before_shared',old_path)
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.geo import same_station
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier

attempts = []
def block(*a,**kw):
    attempts.append('blocked')
    raise RuntimeError('Network prohibited during local path replay')
socket.socket.connect = block
socket.create_connection = block
rt = build_verifier(quiet=True,seoul_key='',gh_url='')
pl = Planner(rt,modes=['subway'])
pairs_path = cs/'tests/unit/travel/mobility/golden_pairs_v1.json'
pairs = json.loads(pairs_path.read_text(encoding='utf8'))['pairs']
wl = pl._walk_limit({})
shortlisted = []
for pair in pairs:
    a = dict(key=pair['id']+'-a',name=pair['a'],lat=pair['alat'],lon=pair['alon'])
    b = dict(key=pair['id']+'-b',name=pair['b'],lat=pair['blat'],lon=pair['blon'])
    sa = rt._v.sc.stations_near(a['lat'],a['lon'],wl)
    sb = rt._v.sc.stations_near(b['lat'],b['lon'],wl)
    if not sa or not sb:
        continue
    x,y = sa[0][1],sb[0][1]
    xl = rt._v.sc.group_lines(x) if rt._v.sc.is_ambiguous(x['station_nm']) else None
    yl = rt._v.sc.group_lines(y) if rt._v.sc.is_ambiguous(y['station_nm']) else None
    if same_station(x['station_nm'],xl,y['station_nm'],yl):
        shortlisted.append((pair,a,b))
shortlisted.sort(key=lambda p:p[0]['straight_m'],reverse=True)
records = []
for pair,a,b in shortlisted:
    sa,sb,new_pairs = pl._station_pairs(a,b,wl)
    old_pl = old.Planner(rt,modes=['subway'])
    old_sa,old_sb,old_pairs = old_pl._station_pairs(a,b,wl)
    assert sa==old_sa and sb==old_sb
    record = {'id':pair['id'],'a':a,'b':b,'straight_m':pair['straight_m'],
              'before_pairs':len(old_pairs),'after_pairs':len(new_pairs),
              'pairs':[[x[2][0],x[3][0]] for x in new_pairs]}
    records.append(record)

replays = []
for record in [x for x in records if x['after_pairs']][:3]:
    result = {'id':record['id'],'variants':[]}
    for name in ('before','after','after','before'):
        planner = old.Planner(rt,modes=['subway']) if name=='before' else Planner(rt,modes=['subway'])
        got,why = planner.leg(record['a'],record['b'],datetime.fromisoformat('2026-10-09T10:30:00+09:00'),
                             {},True,'shared-native-'+record['id'],
                             not_before_dt=datetime.fromisoformat('2026-10-09T09:00:00+09:00'))
        result['variants'].append({'variant':name,'available':got is not None,
            'route':got[0] if got else None,'why':why,'start_min':got[1] if got else None})
    replays.append(result)
assert not attempts
sha = lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior_state = json.loads((scratch/'estimate-walk-network-work-v1.json').read_text(encoding='utf8'))
prior = json.loads((cs/'wiki/records/evidence'/prior_state['tag']/'verification-proof-v1.json').read_text(encoding='utf8'))
inputs = {k:v for k,v in prior['source_test_data_hashes'].items() if k.startswith('datasets/')}
inputs[pairs_path.relative_to(root).as_posix()] = sha(pairs_path)
assert all(sha(root/p)==h for p,h in inputs.items())
out = {'created_at':datetime.now().astimezone().isoformat(),'inputs':inputs,'stored_pairs':len(pairs),
       'same_first_station_pairs':len(records),'opened_pairs':sum(x['after_pairs']>0 for x in records),
       'pair_records':records,'replay_order':'ABBA','replays':replays,
       'network_attempts':len(attempts),'new_web_samples':0,'actual_trips':0,
       'scope':'Stored development coordinates and local timetable replay, not independent route accuracy.'}
with (ev/'native-path-replay-v1.json').open('x',encoding='utf8') as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps({'stored':len(pairs),'same_first':len(records),'opened':out['opened_pairs'],
    'records':[{k:x[k] for k in ['id','before_pairs','after_pairs']} for x in records],
    'replays':[(x['id'],[(v['variant'],v['available']) for v in x['variants']]) for x in replays]},ensure_ascii=False))
