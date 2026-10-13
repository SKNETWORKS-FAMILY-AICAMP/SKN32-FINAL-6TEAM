from pathlib import Path
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
import sys
import httpx

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from app.domains.travel_ops.ports.data_sources.cache import ResponseCache

scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-envelope-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
old_path = root / next(x['backup'] for x in state['backups'] if x['source'].endswith('/seoul_subway.py'))
spec = importlib.util.spec_from_file_location('app.domains.travel_ops.ports.data_sources._before_envelope_v36', old_path)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
sample = json.loads((ev / 'public-sample-check-v1.json').read_text(encoding='utf8'))
payload = json.loads((root / sample['raw_path']).read_text(encoding='utf8'))
scenarios = {'missing_then_recovered': [{}, payload],
             'malformed_then_recovered': [{'realtimeArrivalList': [None]}, payload],
             'valid_then_reused': [payload],
             'empty_then_reused': [{'code': 'INFO-200'}]}
traces = []
for scenario, sequence in scenarios.items():
    for variant, cls in [('before', old.SeoulSubwayArrival), ('after', SeoulSubwayArrival),
                         ('after', SeoulSubwayArrival), ('before', old.SeoulSubwayArrival)]:
        responses = iter(deepcopy(sequence))
        calls = []
        def transport(url, params):
            calls.append(True)
            return httpx.Response(200, json=next(responses), request=httpx.Request('GET', url))
        cache = ResponseCache(ttl_seconds=300, clock=lambda: 0)
        src = cls(service_key='controlled-replay-key', transport=transport, cache=cache)
        results = [src.arrivals('\uC11C\uC6B8'), src.arrivals('\uC11C\uC6B8')]
        traces.append({'scenario': scenario, 'variant': variant, 'http_transport_calls': len(calls),
                       'cache_stores': cache.stores, 'misses': dict(src.misses),
                       'train_counts': [len(r['trains']) if r is not None else None for r in results]})
        if variant == 'after' and scenario.endswith('recovered'):
            assert traces[-1]['train_counts'] == [None, 5] and len(calls) == 2
        if scenario == 'valid_then_reused':
            assert traces[-1]['train_counts'] == [5, 5] and len(calls) == 1
        if scenario == 'empty_then_reused':
            assert traces[-1]['train_counts'] == [0, 0] and len(calls) == 1
provider = payload.get('errorMessage', payload)
result = {'created_at': datetime.now().astimezone().isoformat(), 'traces': traces,
          'scenario_count': len(scenarios), 'runs': len(traces), 'order': 'ABBA',
          'actual_provider_snapshots': 1, 'actual_provider_rows': len(payload['realtimeArrivalList']),
          'provider_total': provider.get('total'), 'sample_is_complete_station_response': False,
          'source_generated_at': [r.get('recptnDt') for r in payload['realtimeArrivalList']],
          'claim': 'Controlled replay of one public sample snapshot. Recovery and cache semantics, not independent accuracy or measured boarding.'}
with (ev / 'cache-recovery-abba-v1.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps({'scenarios': len(scenarios), 'runs': len(traces), 'actual_snapshots': 1,
                  'actual_rows': 5, 'provider_total': provider.get('total')}, ensure_ascii=False))
