"""OSM 보행 그래프 · 서울시 도보 그래프 · 「두 자료 중 검증된 짧은 쪽」 규칙을 카카오 웹 최단 도보와 비교(읽기 전용)."""
import json, sys, statistics
sys.path.insert(0, 'final_project_cs')
from pathlib import Path
from app.domains.travel_ops.instances.mobility.engine import paths
paths.configure('datasets/mobility/processed')
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
B = Path('datasets/mobility/processed/mobility')
G = {'osm': GraphRouter.shared(B / 'road_graph_v2'), 'seoul': GraphRouter.shared(B / 'walk_graph_seoul_v2')}
rows = []
w = json.load(open('datasets/mobility/raw/mobility_walk_web_20261012_v3/kakao-walk-observed-v1.json', encoding='utf-8'))
for r in w['rows']:
    rows.append((r['id'], (r['request']['from']['lat'], r['request']['from']['lon']), (r['request']['to']['lat'], r['request']['to']['lon']), r['modes']['SHORTEST']['length_m'], 'dev' if r['id'] == 'W01' else 'frozen_v3'))
od = {x['id']: x for x in json.load(open('datasets/mobility/raw/mobility_walk_web_20261013_v4/od-frozen-v1.json', encoding='utf-8'))['rows']}
for r in json.load(open('datasets/mobility/raw/mobility_walk_web_20261013_v4/kakao-walk-observed-v1.json', encoding='utf-8'))['rows']:
    o = od.get(r['id']) or r
    rows.append((r['id'], tuple(o['from']), tuple(o['to']), r['shortest_m'], 'dev' if r['id'] == 'N01' else 'frozen_v4'))
out = []
for rid, a, b, k, kind in rows:
    res = {}
    for name, g in G.items():
        try:
            p = g.route((a[1], a[0]), (b[1], b[0]), 'foot')['paths'][0]
            res[name] = {'m': p['distance'], 'opt': p['quality']['optimistic'], 'acc': p['quality']['access_max_m'],
                         'stairs_m': round(p['foot_timing']['stairs_m'], 1), 'sec': round(p['foot_timing']['seconds'])}
        except Exception as e:
            res[name] = {'error': str(e)[:60]}
    ok = {n: v for n, v in res.items() if 'm' in v and not v['opt']}
    best = min(ok, key=lambda n: ok[n]['m']) if ok else None
    row = {'id': rid, 'kind': kind, 'kakao_m': k, **{n: v for n, v in res.items()}, 'min_rule': best}
    for n in ('osm', 'seoul'):
        v = res[n]
        row[n + '_pct'] = round(100 * (v['m'] - k) / k, 1) if 'm' in v else None
    row['min_pct'] = round(100 * (ok[best]['m'] - k) / k, 1) if best else None
    out.append(row)
    print(f"{rid:4} {kind:9} kakao {k:5} | osm {res['osm'].get('m','-'):>8} {row['osm_pct']}%{'(낙관)' if res['osm'].get('opt') else ''} | seoul {res['seoul'].get('m','-'):>8} {row['seoul_pct']}%{'(낙관)' if res['seoul'].get('opt') else ''} st{res['seoul'].get('stairs_m','')} | min→{best} {row['min_pct']}%")
def summ(sel, key):
    xs = [r[key] for r in out if sel(r) and r[key] is not None]
    within = sum(1 for x in xs if abs(x) <= 10)
    blocked = sum(1 for r in out if sel(r) and r[key] is None)
    return {'n': len(xs), 'within10': within, 'blocked_or_optimistic_n': blocked,
            'median_abs_pct': round(statistics.median([abs(x) for x in xs]), 1) if xs else None}
summary = {}
for label, sel in (('frozen_all', lambda r: r['kind'] != 'dev'), ('all', lambda r: True)):
    summary[label] = {}
    for key in ('osm_pct', 'seoul_pct', 'min_pct'):
        # 낙관(접근 미검증)은 제품이 막으므로 「제공 가능」에서 뺀다
        if key != 'min_pct':
            n = key[:-4]
            xs = [r for r in out if sel(r)]
            prov = [r for r in xs if 'm' in r[n] and not r[n]['opt']]
            vals = [r[key] for r in prov]
            summary[label][n] = {'od': len(xs), 'provided': len(prov), 'within10_of_provided': sum(1 for v in vals if abs(v) <= 10),
                                 'within10_of_all': sum(1 for v in vals if abs(v) <= 10),
                                 'median_abs_pct_provided': round(statistics.median([abs(v) for v in vals]), 1) if vals else None}
        else:
            xs = [r for r in out if sel(r)]
            vals = [r['min_pct'] for r in xs if r['min_pct'] is not None]
            summary[label]['min_rule'] = {'od': len(xs), 'provided': len(vals), 'within10_of_all': sum(1 for v in vals if abs(v) <= 10),
                                          'median_abs_pct_provided': round(statistics.median([abs(v) for v in vals]), 1) if vals else None}
print(json.dumps(summary, ensure_ascii=False, indent=1))
json.dump({'rows': out, 'summary': summary}, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
