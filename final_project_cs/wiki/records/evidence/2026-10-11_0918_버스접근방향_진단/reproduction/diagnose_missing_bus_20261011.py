from pathlib import Path
from datetime import datetime
import sys, json, hashlib, socket
sys.stdout.reconfigure(encoding='utf8')
root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
ev = cs / 'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단'
ev.mkdir(exist_ok=False)
manifest = json.loads((cs / 'wiki/records/evidence/2026-10-11_0421_혼합환승_제품운임_연결/final-integrity-v1.json').read_text(encoding='utf8'))
audit = {}
for key in ('source_test_data_hashes', 'artifact_hashes'):
    rows = manifest.get(key, {})
    changes = []
    for name, expected in rows.items():
        path = root / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if actual != expected: changes.append({'path': name, 'expected': expected, 'actual': actual})
    audit[key] = {'total': len(rows), 'matched': len(rows)-len(changes), 'changes': changes}
(ev / 'integrity-start.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps(audit, ensure_ascii=False), flush=True)
sys.path.insert(0, str(cs))
attempts = []
def deny(*args, **kw):
    attempts.append(1)
    raise RuntimeError('오프라인 진단: 외부 통신 차단')
socket.socket.connect = deny
socket.socket.connect_ex = deny
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.plan import Planner, service_day
rt = build_verifier(quiet=True, local_router=True, seoul_key='', gh_url='', data_dir=str(root/'datasets/mobility/processed'))
print('정적 자료 로딩 완료', flush=True)
a = {'key':'ns','name':'남산타워','lat':37.5512,'lon':126.9882}
b = {'key':'it','name':'이태원','lat':37.5345,'lon':126.9946}
when = datetime.fromisoformat('2026-09-29T15:00:00+09:00')
rows = []
for reverse in (False, True):
    aa, bb = (b,a) if reverse else (a,b)
    p = Planner(rt, modes=['bus','subway','walk'])
    got, why = p.leg(aa, bb, when, {}, True, 'diagnose')
    radius = p.v.rv('alternatives','정류장_반경_m')
    raw = []
    for r,x,y,span,da,db in p.v.bus.routes_between(aa['lat'],aa['lon'],bb['lat'],bb['lon'],radius):
        if str(r.route_nm) == '405':
            raw.append({'route':str(r), 'x':x,'y':y,'span':span,'da':da,'db':db,
                        'in_eff':p._stop_walk(aa,x,da),'out_eff':p._stop_walk(bb,y,db)})
    row = {'reverse':reverse,'result':got,'why':why,'direct_405':raw,'trace':p.trace,'walk_capped':getattr(p,'walk_capped',[])}
    rows.append(row)
    print('방향', reverse, '405 정류장쌍',len(raw), '결과',str(got)[:1500], flush=True)
(ev/'diagnosis-v1.json').write_text(json.dumps({'rows':rows,'network_attempts':len(attempts)}, ensure_ascii=False, indent=2, default=str),encoding='utf8')
