from pathlib import Path
from dataclasses import asdict
import collections
import hashlib
import importlib.util
import json
import sys
from types import SimpleNamespace

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
scratch = Path(__file__).parent
state = json.loads((scratch / 'fare-discount-upper-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.bus import BusRoutes
from app.domains.travel_ops.instances.mobility.engine.guardrails import resolve
from app.domains.travel_ops.instances.mobility.engine.paths import cli_processed, RULES_DIR
from app.domains.travel_ops.instances.mobility.engine.verify_time import LegResult, leg_txt
from tests.unit.travel.mobility.test_mixed_fare_upper_v1 import fixture, rides

b = next(x for x in state['backups'] if x['source'].endswith('/options.py'))
name = 'app.domains.travel_ops.instances.mobility.engine.options_before_discount_audit'
spec = importlib.util.spec_from_file_location(name, root / b['backup'])
before = importlib.util.module_from_spec(spec)
sys.modules[name] = before
spec.loader.exec_module(before)
rp = cli_processed() / 'mobility/bus_route_v1.jsonl'
rule_path = RULES_DIR / 'rules_v0.3.json'
routes = [json.loads(s) for s in rp.read_text(encoding='utf8').splitlines() if s.strip()]
rules = resolve(json.loads(rule_path.read_text(encoding='utf8')))
v = SimpleNamespace(bus=BusRoutes(routes, []), R=rules)
types = collections.Counter()
supported = old_defined = newly_available = unsupported = 0
bad = []
for route in v.bus.by_id.values():
    types[str(route.route_type_nm)] += 1
    leg = {'mode': 'bus', 'route': route.route_nm, 'route_id': route.route_id,
           'from': '감사 승차', 'to': '감사 하차'}
    lr = [LegResult(1, leg_txt(leg), 'feasible', '', depart_min=385, arrive_min=395, wait_min=5)]
    old = before.bus_fare(v, [leg], lr)
    new = O.bus_fare_upper(v, [leg], lr)
    known = route.route_type_nm in rules['fare']['bus']['by_type']['value']
    supported += known
    unsupported += not known
    old_defined += old is not None
    newly_available += old is None and new is not None
    if known and new != rules['fare']['bus']['by_type']['value'][route.route_type_nm]:
        bad.append(route.route_id)
    elif not known and new is not None:
        bad.append(route.route_id)
mixed = []
for first in (375, 385, 700):
    for rail_first in (False, True):
        mv, bus, rail = fixture()
        legs = [rail, bus] if rail_first else [bus, rail]
        results = rides(legs)
        for i, lr in enumerate(results):
            lr.depart_min = first + i * 10
            lr.arrive_min = lr.depart_min + 8
        mixed.append({'first_board_min': first, 'rail_first': rail_first,
                      'before': before.fare_upper_of(mv, legs, results),
                      'after': O.fare_upper_of(mv, legs, results)})
assert not bad and all(r['after'] == 3150 for r in mixed)
got = {'stored_routes': len(routes), 'route_types': dict(types), 'supported_routes': supported,
       'unsupported_routes': unsupported, 'old_single_fare_defined': old_defined,
       'new_bus_upper_defined': supported, 'boundary_new_upper_defined': newly_available,
       'mismatches': bad, 'controlled_mixed_cases': mixed,
       'conditions': {'board_min': 385, 'alight_min': 395, 'wait_min': 5,
                      'term_min': 'stored route term', 'card_fare_scope': 'adult ordinary type fare'},
       'scope': 'stored route type lookup with synthetic clocks; not real routes, charging or independent validation',
       'inputs': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (rp, rule_path)}, 'new_web_routes': 0, 'map_developer_api_calls': 0,
       'actual_trips_or_payments': 0}
with (ev / 'existing-route-rate-audit-v1.json').open('x', encoding='utf8') as f:
    json.dump(got, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps(got, ensure_ascii=False))
