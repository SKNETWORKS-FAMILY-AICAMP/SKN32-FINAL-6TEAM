from pathlib import Path
import hashlib
import importlib.util
import json
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
scratch = Path(__file__).parent
state = json.loads((scratch / 'bus-distance-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.paths import PROCESSED

name = 'app.domains.travel_ops.instances.mobility.engine.bus_distance_before'
spec = importlib.util.spec_from_file_location(name, root / state['backups'][0]['backup'])
before = importlib.util.module_from_spec(spec)
sys.modules[name] = before
spec.loader.exec_module(before)
rp, sp = (PROCESSED / 'mobility' / p for p in ('bus_route_v1.jsonl', 'bus_stops_v1.jsonl'))
read = lambda p: [json.loads(s) for s in p.read_text(encoding='utf8').splitlines() if s.strip()]
routes, stops = read(rp), read(sp)
old, new = before.BusRoutes(routes, stops), BusRoutes(routes, stops)
adjacent = whole = equal_adjacent = equal_whole = valid_adjacent = valid_whole = 0
zero_segments = 0
differences = []
for rid, rows in new.stops.items():
    for a, b in zip(rows, rows[1:]):
        args = (rid, a['seq'], b['seq'])
        x, y = old.distance_m(*args), new.distance_m(*args)
        adjacent += 1
        equal_adjacent += x == y
        valid_adjacent += y is not None
        zero_segments += y == 0
        if x != y:
            differences.append({'route_id': rid, 'start': a['seq'], 'end': b['seq']})
    args = (rid, rows[0]['seq'], rows[-1]['seq'])
    x, y = old.distance_m(*args), new.distance_m(*args)
    whole += 1
    equal_whole += x == y
    valid_whole += y is not None
    if x != y:
        differences.append({'route_id': rid, 'scope': 'whole'})
assert not differences
got = {'routes': len(routes), 'stop_rows': len(stops), 'adjacent_queries': adjacent,
       'equal_adjacent': equal_adjacent, 'valid_adjacent': valid_adjacent,
       'whole_route_queries': whole, 'equal_whole': equal_whole, 'valid_whole': valid_whole,
       'zero_adjacent_preserved': zero_segments, 'differences': differences,
       'scope': 'existing source distances; not fare-distance, road completeness or actual trip validation',
       'inputs': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (rp, sp)},
       'map_developer_api_calls': 0, 'new_web_routes': 0, 'actual_trips': 0}
with (ev / 'existing-distance-audit-v1.json').open('x', encoding='utf8') as f:
    json.dump(got, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps(got, ensure_ascii=False))
