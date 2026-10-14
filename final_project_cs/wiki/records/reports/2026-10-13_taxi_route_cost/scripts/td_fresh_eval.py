"""시험용(제품 코드 안 바꿈): 자동차 길 선택 비용을 TOPIS 시간대 속도로 바꾸면 카카오 공개 비교 193쌍의 거리·요금 오차가 어떻게 되나.

비용 규칙 = CarGraph.compute 의 속도 규칙 그대로(TOPIS 링크 → 도로급 계수 → 골목 정적 속도), 출발 시각의 요일형·시각 하나로 고정.
사용: python td_route_proto.py <split: training|validation|all> <out.json>
"""
import datetime as dt, gzip, json, socket, sys, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'final_project_cs'))
def blocked(*a, **k): raise RuntimeError('offline')
socket.socket.connect = blocked; socket.create_connection = blocked
from app.domains.travel_ops.instances.mobility.engine import paths
paths.configure(ROOT / 'datasets/mobility/processed', source='td_proto_offline')
from app.domains.travel_ops.instances.mobility.engine import car as C
from app.domains.travel_ops.instances.mobility.engine.car import CarGraph, CarService, CLASS_MAP, DEFAULT_KMH
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter

BASE = ROOT / 'final_project_cs/app/domains/travel_ops/instances/mobility/engine'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
rules = read(BASE / 'rules/rules_v0.3.json')
graph = CarGraph.load(ROOT / 'datasets/mobility/processed/mobility/graph', read(BASE / 'rules/holidays_2026_2027.json')['holidays'])
router = GraphRouter.default(); router._load()
pred = read(ROOT / 'datasets/mobility/raw/taxi_stop_model_20261012_v2/current-predictions-v1.json')
pairs = {p['id']: p for p in read(ROOT / 'final_project_cs/tests/unit/travel/mobility/golden_pairs_v1.json')['pairs']}

# 간선 → (lf, lb)
lk = {}
for l in gzip.open(ROOT / 'datasets/mobility/processed/mobility/car_edge_link_v1/edge_link.jsonl.gz', 'rt'):
    r = json.loads(l); lk[(r['u'], r['v'], r['way'])] = (r['lf'], r['lb'])
# router 간선 index → (lf, lb): router 는 노드 id 를 내부 번호로 바꿨으므로 원 id 를 되찾는다
inv = {v: k for k, v in router.nid.items()}
elink = [lk.get((inv[router.eu[e]], inv[router.ev[e]], router.eway[e]), (None, None)) for e in range(len(router.eu))]

def speed(link, hw, dtp, h):
    v = graph.prof.get((link, dtp, h)) if link else None
    if v is not None: return v
    if hw in CLASS_MAP: return graph.cf[CLASS_MAP[hw]]['mean_kmh'][dtp][h]
    return DEFAULT_KMH.get(hw, 20)

orig_cost = GraphRouter._cost
state = {'bucket': None}
def td_cost(self, profile, e, _dir=0):
    if profile != 'car' or state['bucket'] is None: return orig_cost(self, profile, e)
    dtp, h = state['bucket']
    hw = self.hw_name[self.ehw[e]]
    lf, lb = elink[e]
    v = min(speed(lf, hw, dtp, h), speed(lb, hw, dtp, h)) if (lf and lb) else speed(lf or lb, hw, dtp, h)
    return self.elen[e] / (v / 3.6)

def set_bucket(b):
    if state['bucket'] != b:
        state['bucket'] = b
        router._adj.pop('car', None)


obs = {r['id']: r for r in read(ROOT / 'datasets/mobility/raw/taxi_web_20261013_v1/kakao-car-observed-v1.json')['rows']}
od = read(ROOT / 'datasets/mobility/raw/taxi_web_20261013_v1/od-frozen-v1.json')['rows']
svc = CarService(graph, router, rules)
res = []
for o in od:
    k = obs[o['id']]
    depart = dt.datetime.fromisoformat(k['at'].replace('Z', '+00:00')).astimezone(dt.timezone(dt.timedelta(hours=9)))
    a, b = (o['from'][1], o['from'][0]), (o['to'][1], o['to'][0])
    row = {'id': o['id'], 'kakao_km': k['km'], 'kakao_min': k['min'], 'kakao_taxi': k['taxi']}
    for name, td in (('static', False), ('td', True)):
        GraphRouter._cost = td_cost if td else orig_cost
        router._adj.pop('car', None); state['bucket'] = (graph.daytype(depart), depart.hour) if td else None
        g = svc.leg(a, b, depart, taxi=True)
        row[name] = {'km': round(g['distance_m'] / 1000, 2), 'min': round(g['topis_time_s'] / 60, 1), 'meter': g['meter_won'], 'slow_s': g['slow_s'],
                     'err': g['meter_won'] - k['taxi']}
    res.append(row); print(json.dumps(row, ensure_ascii=False))
def summ(n):
    er = [r[n]['err'] for r in res]
    return {'n': len(er), 'mae': round(sum(map(abs, er)) / len(er)), 'med_err': st.median(er), 'under': sum(e < 0 for e in er),
            'within_1000': sum(abs(e) <= 1000 for e in er), 'km_ratio_med': round(st.median(r[n]['km'] / r['kakao_km'] for r in res), 3),
            'min_ratio_med': round(st.median(r[n]['min'] / r['kakao_min'] for r in res), 3)}
s = {'static': summ('static'), 'td': summ('td')}
print(json.dumps(s, ensure_ascii=False))
json.dump({'summary': s, 'rows': res}, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
