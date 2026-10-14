from pathlib import Path
from datetime import datetime
from statistics import median
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import math
import sys
import time

workspace = Path(__file__).resolve().parents[2]
cs = workspace/'final_project_cs'
sys.path.insert(0, str(cs))
from app.domains.travel_ops.instances.mobility.engine import paths
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter

scratch = workspace/'.tmp/mobility_complete_20261008'
work = json.loads((scratch/'car-turn-work.json').read_text(encoding='utf-8-sig'))
backups = json.loads((cs/work['evidence']/'before-backup.json').read_text(encoding='utf-8-sig'))
source = next(row['backup'] for row in backups if row['file'].endswith('graph_router.py'))
name = 'app.domains.travel_ops.instances.mobility.engine._baseline_graph_router'
spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, source))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
paths.configure(str(workspace/'datasets/mobility/processed'))
graph_dir = workspace/'datasets/mobility/processed/mobility/road_graph_v2'
baseline, current = module.GraphRouter(graph_dir), GraphRouter.default()
t0 = time.perf_counter()
baseline.warm(('car',))
current.warm(('car',))
from app.domains.travel_ops.instances.mobility.engine.turn_restrictions import load
load(current)
load_seconds = time.perf_counter()-t0
data = json.loads((graph_dir/'turn_restrictions_v1.json').read_text(encoding='utf8'))
rules = data['rules']
assert len(rules) == 2487
queries = []
for row in (r for r in rules if r['value'].startswith('no_')):
    def point(code, ending):
        coords = current._geom(code >> 1)[0]
        if code & 1:
            coords = list(reversed(coords))
        segment = coords[-2:] if ending else coords[:2]
        alpha = .6 if ending else .4
        return tuple(segment[0][axis]*(1-alpha)+segment[1][axis]*alpha for axis in (0, 1))
    queries.append((row['relation_id'], point(row['incoming'], True), point(row['outgoing'], False)))
    if len(queries) == 12:
        break

def violations(arcs):
    return [r['relation_id'] for inc, out in zip(arcs, arcs[1:]) for r in rules
            if r['incoming'] == inc and ((r['value'].startswith('no_') and r['outgoing'] == out)
                or (r['value'].startswith('only_') and r['outgoing'] != out))]

observations = []
for rid, start, end in queries:
    repeats = []
    for repeat in range(3):
        pair = {}
        for label, router in [('before', baseline), ('after', current)]:
            t0 = time.perf_counter()
            path = router.route(start, end, profile='car')['paths'][0]
            pair[label] = dict(distance_m=path['distance'], model_seconds=path['time']/1000,
                               query_seconds=time.perf_counter()-t0)
            if label == 'after':
                assert path['turn_restrictions']['applied_relations'] == 2487
                assert violations(path['turn_restrictions']['arc_codes']) == []
        repeats.append(pair)
    current.force_dijkstra = True
    direct = current.route(start, end, profile='car')['paths'][0]
    current.force_dijkstra = False
    astar = current.route(start, end, profile='car')['paths'][0]
    assert math.isclose(direct['turn_restrictions']['search_cost_seconds'],
                        astar['turn_restrictions']['search_cost_seconds'], abs_tol=1e-4)
    observations.append(dict(relation_id=rid, start=start, end=end, repeats=repeats,
                             astar_dijkstra_equal=True, applied_rule_violations=0))
    print(json.dumps({'checked_queries': len(observations), 'total_queries': len(queries)}), flush=True)
result = dict(created_at=datetime.now().astimezone().isoformat(),
              scope='development queries at mapped restriction approaches; not independent web or real driving validation',
              queries=len(observations), repeats_per_pair=3, applied_relations=len(rules),
              source_relations=data['source_relations'], load_seconds=load_seconds,
              developer_api_calls=0, observations=observations,
              median_before_query_seconds=median(x['before']['query_seconds'] for o in observations for x in o['repeats']),
              median_after_query_seconds=median(x['after']['query_seconds'] for o in observations for x in o['repeats']),
              changed_distance_queries=sum(o['repeats'][0]['after']['distance_m'] != o['repeats'][0]['before']['distance_m'] for o in observations))
with (scratch/'car-turn-runtime-probe-v2.json').open('x', encoding='utf8') as out:
    json.dump(result, out, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != 'observations'}, ensure_ascii=True))
