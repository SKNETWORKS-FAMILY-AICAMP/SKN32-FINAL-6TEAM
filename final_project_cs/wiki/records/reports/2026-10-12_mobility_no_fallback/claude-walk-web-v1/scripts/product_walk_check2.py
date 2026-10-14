"""제품 조립 경로(build_verifier → Planner._walk_path)로 17쌍 직접 도보 — 새 규칙(서울 안: 두 자료 중 검증된 짧은 길) 확인."""
import json, sys
sys.path.insert(0, 'final_project_cs')
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.geo import meters
rt = build_verifier(quiet=True, local_router=True, seoul_key='', gh_url='')
p = Planner(rt, modes=['walk'])
rows = []
w = json.load(open('datasets/mobility/raw/mobility_walk_web_20261012_v3/kakao-walk-observed-v1.json', encoding='utf-8'))
for r in w['rows']:
    rows.append((r['id'], (r['request']['from']['lat'], r['request']['from']['lon']), (r['request']['to']['lat'], r['request']['to']['lon']), r['modes']['SHORTEST']['length_m'], 'dev' if r['id'] == 'W01' else 'frozen'))
od = {x['id']: x for x in json.load(open('datasets/mobility/raw/mobility_walk_web_20261013_v4/od-frozen-v1.json', encoding='utf-8'))['rows']}
for r in json.load(open('datasets/mobility/raw/mobility_walk_web_20261013_v4/kakao-walk-observed-v1.json', encoding='utf-8'))['rows']:
    o = od.get(r['id']) or r
    rows.append((r['id'], tuple(o['from']), tuple(o['to']), r['shortest_m'], 'dev' if r['id'] == 'N01' else 'frozen'))
out = []
for rid, a, b, k, kind in rows:
    A, Bp = {'lat': a[0], 'lon': a[1]}, {'lat': b[0], 'lon': b[1]}
    ev = {}
    d, mins, blocked = p._walk_path(A, Bp, meters(*a, *b), evidence=ev)
    wc = ev.get('walk_candidates') or {}
    row = {'id': rid, 'kind': kind, 'kakao_m': k, 'product_m': d, 'minutes': None if mins is None else round(mins, 2),
           'blocked': blocked, 'reason': ev.get('reason'), 'chosen': wc.get('chosen'), 'source_id': ev.get('source_id'),
           'candidates': wc.get('candidates'), 'diff_pct': None if d is None else round(100 * (d - k) / k, 1)}
    out.append(row)
    print(f"{rid:4} {kind:6} kakao {k:5} | product {d if d is None else round(d,1)} ({row['diff_pct']}%) chosen={row['chosen']} blocked={blocked} {row['reason'] or ''}")
fz = [r for r in out if r['kind'] == 'frozen']
prov = [r for r in fz if r['product_m'] is not None]
print('frozen OD', len(fz), 'provided', len(prov), 'within10', sum(1 for r in prov if abs(r['diff_pct']) <= 10))
json.dump(out, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
