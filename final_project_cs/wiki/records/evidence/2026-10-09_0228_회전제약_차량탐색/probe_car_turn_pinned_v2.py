from pathlib import Path
from datetime import datetime
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import math
import sys
import time

workspace = Path(__file__).resolve().parents[2]
cs = workspace/'final_project_cs'
scratch = workspace/'.tmp/mobility_complete_20261008'
sys.path.insert(0, str(cs))
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, _Snap
from app.domains.travel_ops.instances.mobility.engine.car import RouterDown

work = json.loads((scratch/'car-turn-work.json').read_text(encoding='utf-8-sig'))
backups = json.loads((cs/work['evidence']/'before-backup.json').read_text(encoding='utf-8-sig'))
source = next(row['backup'] for row in backups if row['file'].endswith('graph_router.py'))
name = 'app.domains.travel_ops.instances.mobility.engine._baseline_graph_router'
spec = importlib.util.spec_from_loader(name, SourceFileLoader(name, source))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
directory = workspace/'datasets/mobility/processed/mobility/road_graph_v2'
baseline, current = module.GraphRouter(directory), GraphRouter(directory)
for router in (baseline, current):
    router.warm(('car',))
data = json.loads((directory/'turn_restrictions_v1.json').read_text(encoding='utf8'))
observations = []


def snap(arc, incoming):
    edge = arc >> 1
    coords, cum, segments = current._geom(edge)
    distance = cum[-1]*(.6 if incoming else .4)
    if arc & 1:
        distance = cum[-1]-distance
    index = next(i for i in range(len(segments)) if cum[i+1] >= distance and segments[i] > 0)
    alpha = (distance-cum[index])/segments[index]
    point = tuple(coords[index][axis]*(1-alpha)+coords[index+1][axis]*alpha for axis in (0, 1))
    return _Snap(edge, distance, 0.0, point, (index, alpha))


for row in (r for r in data['rules'] if r['value'].startswith('no_')):
    if not all(current._snappable('car', code >> 1) for code in (row['incoming'], row['outgoing'])):
        continue
    start, end = snap(row['incoming'], True), snap(row['outgoing'], False)
    for router in (baseline, current):
        router._snap_many = lambda profile, lng, lat: [start if (lng, lat) == start.pt else end]
    captured = []
    response = baseline._response
    def capture(parts, *args):
        captured[:] = [edge for edge, points in parts if len(points) >= 2 and points[0] != points[-1]]
        return response(parts, *args)
    baseline._response = capture
    repetitions = []
    for repeat in range(3):
        pair = {}
        for label, router in [('before', baseline), ('after', current)]:
            at = time.perf_counter()
            try:
                path = router.route(start.pt, end.pt, profile='car')['paths'][0]
            except RouterDown as exc:
                if not str(exc).startswith('no_path:'):
                    raise
                pair[label] = dict(status='no_path', query_seconds=time.perf_counter()-at)
                continue
            pair[label] = dict(status='routed', distance_m=path['distance'], model_seconds=path['time']/1000,
                               query_seconds=time.perf_counter()-at)
            if label == 'before':
                pair[label]['target_transition_used'] = any(
                    (a, b) == (row['incoming'] >> 1, row['outgoing'] >> 1) for a, b in zip(captured, captured[1:]))
            else:
                codes = path['turn_restrictions']['arc_codes']
                assert not any(r['incoming'] == inc and
                    ((r['value'].startswith('no_') and r['outgoing'] == out) or
                     (r['value'].startswith('only_') and r['outgoing'] != out))
                    for inc, out in zip(codes, codes[1:]) for r in data['rules'])
        repetitions.append(pair)
    baseline._response = response
    reference = {}
    for label, flag in [('dijkstra', True), ('astar', False)]:
        current.force_dijkstra = flag
        try:
            path = current.route(start.pt, end.pt, profile='car')['paths'][0]
            reference[label] = dict(status='routed', cost=path['turn_restrictions']['search_cost_seconds'])
        except RouterDown as exc:
            if not str(exc).startswith('no_path:'):
                raise
            reference[label] = dict(status='no_path')
    assert reference['astar']['status'] == reference['dijkstra']['status']
    if reference['astar']['status'] == 'routed':
        assert math.isclose(reference['astar']['cost'], reference['dijkstra']['cost'], abs_tol=1e-4)
    observations.append(dict(relation_id=row['relation_id'], incoming=row['incoming'], outgoing=row['outgoing'],
                             start=start.pt, end=end.pt, repeats=repetitions,
                             applied_rule_violations=0, astar_dijkstra_equal=True, reference=reference))
    print(json.dumps({'checked_queries': len(observations), 'target_queries': 12}), flush=True)
    if len(observations) == 12:
        break
result = dict(created_at=datetime.now().astimezone().isoformat(),
              scope='development: incoming and final edge fixed explicitly; public snap selection and real driving are not measured',
              queries=len(observations), repeats_per_query=3, developer_api_calls=0,
              baseline_target_transition_used=sum(o['repeats'][0]['before'].get('target_transition_used', False) for o in observations),
              after_applied_rule_violations=0,
              routed_queries=sum(o['repeats'][0]['after']['status'] == 'routed' for o in observations),
              no_path_queries=sum(o['repeats'][0]['after']['status'] == 'no_path' for o in observations),
              changed_distance_queries=sum(o['repeats'][0]['before'].get('distance_m') != o['repeats'][0]['after'].get('distance_m') for o in observations if o['repeats'][0]['after']['status'] == 'routed'),
              observations=observations)
with (scratch/'car-turn-pinned-v2.json').open('x', encoding='utf8') as out:
    json.dump(result, out, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != 'observations'}))
