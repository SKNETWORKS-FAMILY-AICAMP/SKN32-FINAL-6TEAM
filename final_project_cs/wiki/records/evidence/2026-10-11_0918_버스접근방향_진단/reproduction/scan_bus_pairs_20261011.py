from pathlib import Path
import sys,json
sys.stdout.reconfigure(encoding='utf8')
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'final_project_cs'))
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
b=BusRoutes.load(root/'datasets/mobility/processed/mobility/bus_route_v1.jsonl',root/'datasets/mobility/processed/mobility/bus_stops_v1.jsonl')
design=json.loads((root/'datasets/mobility/raw/kakao_golden/fresh_experiment_100_design.json').read_text(encoding='utf8'))
rules=json.loads((root/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json').read_text(encoding='utf8'))
radius=rules['alternatives']['정류장_반경_m']['value']
rows=[]
for p in design['pairs']:
    chosen=b.routes_between(p['alat'],p['alon'],p['blat'],p['blon'],radius)
    invalid=[r for r,x,y,span,da,db in chosen if b.distance_m(r.route_id,x['seq'],y['seq']) is None]
    if not invalid: continue
    a=b.stops_near(p['alat'],p['alon'],radius); z=b.stops_near(p['blat'],p['blon'],radius)
    for r in invalid:
        alternatives=[{'x':x,'y':y,'da':da,'db':db,'distance':b.distance_m(r.route_id,x['seq'],y['seq'])} for da,x in a for db,y in z if x['route_id']==y['route_id']==r.route_id and x['seq']<y['seq'] and b.distance_m(r.route_id,x['seq'],y['seq']) is not None]
        rows.append({'pair':p,'route':r.route_nm,'valid_alternatives':alternatives})
print(json.dumps({'total_pairs':len(design['pairs']),'invalid_routes':len(rows),'recoverable':sum(bool(r['valid_alternatives']) for r in rows)},ensure_ascii=False))
out=root/'final_project_cs/wiki/records/evidence/2026-10-11_0918_버스접근방향_진단/bus-pair-scan-v1.json'
with out.open('x',encoding='utf8') as f: json.dump(rows,f,ensure_ascii=False,indent=2)
