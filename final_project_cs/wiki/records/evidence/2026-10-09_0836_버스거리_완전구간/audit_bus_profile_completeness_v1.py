from pathlib import Path
from dataclasses import asdict
import hashlib
import importlib.util
import json
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
scratch = Path(__file__).parent
state = json.loads((scratch / 'bus-distance-work-v3.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.bus_profile import BusSegProfile
from app.domains.travel_ops.instances.mobility.engine.paths import cli_processed

base = cli_processed() / 'mobility'
files = [base / p for p in ('bus_route_v1.jsonl', 'bus_stops_v1.jsonl', 'bus_seg_profile_v1.jsonl.gz')]
read = lambda p: [json.loads(s) for s in p.read_text(encoding='utf8').splitlines() if s.strip()]
bus = BusRoutes(read(files[0]), read(files[1]))
record = next(b for b in state['backups'] if b['source'].endswith('/bus_profile.py'))
name = 'bus_profile_before_completeness'
spec = importlib.util.spec_from_file_location(name, root / record['backup'])
before = importlib.util.module_from_spec(spec)
sys.modules[name] = before
spec.loader.exec_module(before)
new = BusSegProfile.load(files[2])
old = before.BusSegProfile(new.index, new.ends, new.arr, new.meta)
counts = {'adjacent_queries': 0, 'equal_adjacent': 0, 'whole_queries': 0, 'equal_whole': 0,
          'valid_adjacent': 0, 'valid_whole': 0}
diff = []
for rid, rows in bus.stops.items():
    for scope, pairs in [('adjacent', zip(rows, rows[1:])), ('whole', [(rows[0], rows[-1])])]:
        for a, b in pairs:
            for q in ('p50', 'p90'):
                args = (rid, rows, a['seq'], b['seq'], 600, lambda t: ('weekday',), q, 5,
                        lambda d: None if d is None else d / 1000 / 20 * 60)
                x, y = asdict(old.walk(*args)), asdict(new.walk(*args))
                counts[scope + '_queries'] += 1
                counts['equal_' + scope] += x == y
                counts['valid_' + scope] += y['minutes'] is not None
                if x != y:
                    diff.append({'route_id': rid, 'start': a['seq'], 'end': b['seq'], 'q': q, 'scope': scope,
                                 'before': x, 'after': y})
got = dict(counts, routes=len(bus.by_id), stop_rows=sum(map(len, bus.stops.values())),
           differences=diff, inputs={p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in files},
           conditions={'depart_min': 600, 'day_types': ['weekday'], 'min_days': 5,
                       'fallback_kmh': 20, 'quantiles': ['p50', 'p90']},
           scope='fixed model replay of stored profiles; not production speed, actual travel or new web validation',
           map_developer_api_calls=0, new_web_routes=0, actual_trips=0)
with (ev / 'existing-profile-audit-v1.json').open('x', encoding='utf8') as f:
    json.dump(got, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps(got, ensure_ascii=False))
if diff:
    sys.exit(1)
