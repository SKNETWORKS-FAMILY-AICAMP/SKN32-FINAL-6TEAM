from pathlib import Path
from collections import deque, Counter
import sys, json
from datetime import datetime
p = Path(__file__).parent
workspace = p.parents[1]
sys.path.insert(0, str(workspace/'final_project_cs'))
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
gdir = workspace/'datasets/mobility/processed/mobility/road_graph_v2'
g = GraphRouter(gdir)
g.warm(('car',))
data = json.loads((gdir/'turn_restrictions_v1.json').read_text(encoding='utf8'))
probe = json.loads((p/'car-turn-pinned-v2.json').read_text(encoding='utf8'))
obs = next(o for o in probe['observations'] if o['repeats'][0]['after']['status'] == 'no_path')
only, no = {}, {}
for r in data['rules']:
    target = only if r['value'].startswith('only_') else no
    target.setdefault(r['incoming'], set()).add(r['outgoing'])
def start_node(arc):
    return g.ev[arc >> 1] if arc & 1 else g.eu[arc >> 1]
def end_node(arc):
    return g.eu[arc >> 1] if arc & 1 else g.ev[arc >> 1]
inc, out = obs['incoming'], obs['outgoing']
starts = [arc for arc in (inc, inc ^ 1) if g._allowed('car', arc >> 1)[arc & 1]]
goals = [arc for arc in (out, out ^ 1) if g._allowed('car', arc >> 1)[arc & 1]]
deg, to, arcs, weights = g._adjacency('car')
seen = {(end_node(arc), arc) for arc in starts}
q = deque(seen)
blocked = Counter()
reached = []
while q:
    node, previous = q.popleft()
    for goal in goals:
        if start_node(goal) == node and goal not in no.get(previous, ()) and (previous not in only or goal in only[previous]):
            reached.append((node, previous, goal))
    for idx in range(deg[node], deg[node+1]):
        following = arcs[idx]
        if following in no.get(previous, ()) or (previous in only and following not in only[previous]):
            blocked[(previous, following)] += 1
            continue
        state = (to[idx], following)
        if state not in seen:
            seen.add(state)
            q.append(state)
target_nodes = {start_node(arc) for arc in goals}
result = dict(created_at=datetime.now().astimezone().isoformat(), relation_id=obs['relation_id'],
    starts=starts, goal_arcs=goals, reachable_states=len(seen), reachable_nodes=len({n for n, _ in seen}),
    goal_node_states=[list(s) for s in sorted(seen) if s[0] in target_nodes],
    permitted_goal_entries=reached,
    blocked_transitions=[dict(incoming=a, outgoing=b, occurrences=c,
        rules=[r for r in data['rules'] if r['incoming'] == a]) for (a,b),c in blocked.items()],
    scope='independent unweighted state reachability using current graph and sidecar only; real road topology not confirmed')
with (p/'car-turn-no-path-diagnosis-v1.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result))
