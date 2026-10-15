import datetime as dt, json, socket, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'final_project_cs'))
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('offline'))
from app.domains.travel_ops.instances.mobility.engine import paths
paths.configure(ROOT / 'datasets/mobility/processed', source='product_check_offline')
from app.domains.travel_ops.instances.mobility.engine.car import CarGraph, CarService
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
BASE = ROOT / 'final_project_cs/app/domains/travel_ops/instances/mobility/engine'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
svc = CarService(CarGraph.load(ROOT / 'datasets/mobility/processed/mobility/graph', read(BASE / 'rules/holidays_2026_2027.json')['holidays']),
                 GraphRouter.default(), read(BASE / 'rules/rules_v0.3.json'))
proto = {r['id']: r for r in read(sys.argv[1])['rows']}
obs = {r['id']: r for r in read(ROOT / 'datasets/mobility/raw/taxi_web_20261013_v1/kakao-car-observed-v1.json')['rows']}
same = 0
for o in read(ROOT / 'datasets/mobility/raw/taxi_web_20261013_v1/od-frozen-v1.json')['rows']:
    depart = dt.datetime.fromisoformat(obs[o['id']]['at'].replace('Z', '+00:00'))
    g = svc.leg((o['from'][1], o['from'][0]), (o['to'][1], o['to'][0]), depart, taxi=True)
    p = proto[o['id']]['td']
    ok = g['meter_won'] == p['meter'] and abs(g['distance_m'] / 1000 - p['km']) < 0.01
    same += ok
    print(o['id'], g['meter_won'], round(g['distance_m']), g['routing_evidence'].get('route_cost'), 'same' if ok else 'DIFF')
print('same', same, '/ 12')
