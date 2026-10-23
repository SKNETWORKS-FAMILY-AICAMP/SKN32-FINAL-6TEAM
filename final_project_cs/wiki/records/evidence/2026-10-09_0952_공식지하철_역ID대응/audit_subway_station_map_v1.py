from pathlib import Path
from datetime import datetime
from collections import Counter
import importlib.util
import json
import socket
import sys

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-station-map-work-v2.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
sys.path.insert(0, str(root / 'final_project_cs'))
from scripts.mobility.build_subway_realtime_stations import canonical_line
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
import httpx

old_path = root / next(x['backup'] for x in state['backups'] if x['source'].endswith('/seoul_subway.py'))
spec = importlib.util.spec_from_file_location('app.domains.travel_ops.ports.data_sources._old_line_subway', old_path)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
data = json.loads((root / 'datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json').read_text(encoding='utf8'))
index = {(x['line'], x['station']): x for x in data['stations']}
coords = json.loads((root / 'datasets/mobility/processed/mobility/station_coords.json').read_text(encoding='utf8'))['stations']
matched, unmatched = [], []
for key, row in coords.items():
    identity = index.get((canonical_line(row['line']), row['station_nm']))
    if identity:
        matched.append({'coordinate_key': key, 'official_station_id': identity['station_id'], 'line_id': identity['line_id'],
                        'official_query_name': identity['query_station']})
    else:
        unmatched.append({'coordinate_key': key, 'line': row['line'], 'station': row['station_nm'],
                          'reason': 'no_exact_line_and_station_match'})
assert len(matched) + len(unmatched) == len(coords) == 793
attempts = []
def no_network(*args, **kwargs):
    attempts.append('blocked')
    raise AssertionError('No network allowed in official-row injected replay')
socket.socket.connect = no_network
socket.create_connection = no_network
by_line = Counter(x['line'] for x in data['stations'])
records = []
for variant, cls in [('before', old.SeoulSubwayArrival), ('after', SeoulSubwayArrival),
                     ('after', SeoulSubwayArrival), ('before', old.SeoulSubwayArrival)]:
    retained = Counter()
    for row in data['stations']:
        payload = {'realtimeArrivalList': [{'subwayId': row['line_id'], 'statnId': row['station_id'], 'barvlDt': '180'}]}
        def transport(url, params):
            return httpx.Response(200, json=payload, request=httpx.Request('GET', url))
        got = cls(service_key='controlled-test-key', transport=transport).arrivals(row['query_station'], line=row['line'])
        if got['trains']:
            assert len(got['trains']) == 1 and got['trains'][0]['station_id'] == row['station_id']
            retained[row['line']] += 1
    records.append({'variant': variant, 'retained': sum(retained.values()), 'by_line': dict(retained)})
assert [x['retained'] for x in records] == [652, 696, 696, 652]
assert not attempts
out = {'created_at': datetime.now().astimezone().isoformat(), 'official_rows': 696, 'official_lines': 19,
       'by_line': dict(by_line), 'coordinate_rows': len(coords), 'exact_matches': len(matched),
       'matched': matched, 'unmatched': unmatched, 'injected_variants': records,
       'homonym_yangpyeong': [x for x in data['stations'] if x['station'] == '양평'],
       'network_attempts': attempts, 'new_route_web_samples': 0, 'actual_arrival_samples': 0,
       'scope': 'official static identity rows injected into public arrivals; not live station service coverage'}
with (ev / 'official-row-replay-and-join-v1.json').open('x', encoding='utf8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps({'rows': 696, 'lines': 19, 'exact_matches': len(matched), 'unmatched': len(unmatched),
                  'retained_abba': [x['retained'] for x in records], 'network_attempts': len(attempts)}, ensure_ascii=False))
