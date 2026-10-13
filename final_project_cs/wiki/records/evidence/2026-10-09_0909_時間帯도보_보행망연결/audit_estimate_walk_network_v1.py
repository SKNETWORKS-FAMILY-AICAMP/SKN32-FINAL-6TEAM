from pathlib import Path
from datetime import datetime
import hashlib
import importlib.util
import json
import socket
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
state = json.loads((Path(__file__).parent / 'estimate-walk-network-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
old_path = root / next(x['backup'] for x in state['backups'] if x['source'].endswith('/engine/plan_estimate.py'))
spec = importlib.util.spec_from_file_location('app.domains.travel_ops.instances.mobility.engine.estimate_before_audit', old_path)
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)
from app.domains.travel_ops.instances.mobility.engine.plan_estimate import Estimator
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from tests.unit.travel.mobility.test_estimate_walk_network_v1 import run_estimate
from tests.unit.travel.mobility.test_review_fixes_plan import PLACES, _rt
from tests.unit.travel.mobility.test_walk_duration_contract_v1 import stair_router
from app.domains.travel_ops.instances.mobility.engine.bike import BikeRouter

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
attempts = []
def blocked(*a, **kw):
    attempts.append('blocked')
    raise RuntimeError('External network is prohibited during local replay')
socket.socket.connect = blocked
socket.create_connection = blocked

controlled = []
for label, result, error in [
        ('短い平地', {'distance_m': 150}, None),
        ('우회 평지', {'distance_m': 650}, None),
        ('경로 미발견', None, {'kind': 'no_path'})]:
    from types import SimpleNamespace
    rt = _rt()
    rt._v.bike_router = SimpleNamespace(available=lambda: True, route=lambda *a: result, last_error=error)
    before = old.Estimator(rt, modes=['walk']).estimate(PLACES[0], PLACES[1], '2026-10-09', '오후', window=(720,740))
    after, _, _ = run_estimate(result, error)
    controlled.append({'case': label, 'before': before.get('eta', {}).get('p50_min'),
                       'after': after.get('eta', {}).get('p50_min'), 'verdict': after['verdict']})
rt = _rt()
rt._v.bike_router = BikeRouter(stair_router())
before = old.Estimator(rt, modes=['walk']).estimate(PLACES[0], PLACES[1], '2026-10-09', '오후', window=(720,740))
after, _, _ = run_estimate(runtime=rt)
controlled.append({'case':'계단', 'before':before['eta']['p50_min'], 'after':after['eta']['p50_min'], 'verdict':after['verdict']})

pairs_path = cs / 'tests/unit/travel/mobility/golden_pairs_v1.json'
pair = next(x for x in json.loads(pairs_path.read_text(encoding='utf8'))['pairs'] if x['id']=='G04')
a = dict(name=pair['a'], lat=pair['alat'], lon=pair['alon'])
b = dict(name=pair['b'], lat=pair['blat'], lon=pair['blon'])
rt = build_verifier(quiet=True, seoul_key='', gh_url='')
planner = Planner(rt, modes=['walk'])
(leg, *_), why = planner.leg(a, b, datetime.fromisoformat('2026-10-09T10:30:00+09:00'), {}, True, 'G04-estimate-audit')
option = next(x for x in leg['options'] if x['id']=='walk')
estimates = []
for name in ('before','after','after','before'):
    estimator = old.Estimator(rt, modes=['walk']) if name=='before' else Estimator(rt, modes=['walk'])
    samples = []
    out = estimator.estimate(a,b,'2026-10-09','오전',window=(600,610),samples=samples)
    estimates.append({'variant':name,'p50_min':out['eta']['p50_min'],'walk_basis':out.get('walk_basis'),
                      'sample_minutes':[x['eta'] for x in samples]})
assert len([x for x in estimates if x['variant']=='after' and x['p50_min']==option['eta_min']])==2
assert not attempts
prior = json.loads((cs/'wiki/records/evidence/2026-10-09_0852_혼합요금_조조경계/verification-proof-v1.json').read_text(encoding='utf8'))
inputs = {k:v for k,v in prior['source_test_data_hashes'].items() if '/road_graph_v2/' in k}
inputs[pairs_path.relative_to(root).as_posix()] = sha(pairs_path)
assert all(sha(root/p)==h for p,h in inputs.items())
record = {'created_at':datetime.now().astimezone().isoformat(), 'inputs':inputs,
          'controlled_cases':controlled,'existing_pair':pair,'replay_order':'ABBA',
          'estimates':estimates,'schedule_option':option,'native_unique_pairs':1,'after_matches':2,
          'network_attempts':len(attempts),'new_web_samples':0,'actual_walks':0,
          'scope':'Stored G04 coordinates on local OSM graph; not new independent accuracy or browser observation.'}
with (ev/'native-replay-v1.json').open('x',encoding='utf8') as f:
    json.dump(record,f,ensure_ascii=False,indent=2)
print(json.dumps({'controlled':controlled,'native':[(x['variant'],x['p50_min']) for x in estimates],
                  'schedule_min':option['eta_min'],'network_attempts':len(attempts)},ensure_ascii=False))
