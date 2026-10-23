from pathlib import Path
from datetime import datetime
import importlib.util
import json
import sys
import socket

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-identity-work-v1.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
sys.path.insert(0, str(root / 'final_project_cs'))
import httpx
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival

old_file = root / state['backups'][0]['backup']
spec = importlib.util.spec_from_file_location('app.domains.travel_ops.ports.data_sources._audit_old_subway', old_file)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
attempts = []
def no_network(*args, **kwargs):
    attempts.append('blocked')
    raise AssertionError('External network prohibited for controlled source replay')
socket.socket.connect = no_network
socket.create_connection = no_network
row = {'subwayId': '1002', 'statnId': '1002000222', 'statnFid': '1002000221',
       'statnTid': '1002000223', 'bstatnId': '1002000211', 'bstatnNm': '성수',
       'btrainNo': '0021', 'ordkey': '00000001', 'barvlDt': '180',
       'updnLine': '내선', 'btrainSttus': '일반', 'recptnDt': '2026-10-09 09:30:00'}
records = []
for variant, cls in [('before', old.SeoulSubwayArrival), ('after', SeoulSubwayArrival),
                     ('after', SeoulSubwayArrival), ('before', old.SeoulSubwayArrival)]:
    for case, seconds in [('valid', '180'), ('invalid_superscript', '\u00b2')]:
        payload = {'realtimeArrivalList': [{**row, 'barvlDt': seconds}]}
        def transport(url, params):
            return httpx.Response(200, json=payload, request=httpx.Request('GET', url))
        src = cls(service_key='controlled-test-key', transport=transport,
                  now=lambda: datetime.fromisoformat('2026-10-09T09:30:05+09:00'))
        try:
            result = src.arrivals('강남')['trains'][0]
            records.append({'variant': variant, 'case': case, 'outcome': 'normalized', 'train': result})
        except ValueError as exc:
            records.append({'variant': variant, 'case': case, 'outcome': 'ValueError', 'error': str(exc)})
valid = [x for x in records if x['case'] == 'valid']
old_train = valid[0]['train']
new_train = valid[1]['train']
assert all(new_train[key] == val for key, val in old_train.items())
assert 'station_id' not in old_train and new_train['station_id'] == row['statnId']
invalid = [x for x in records if x['case'] == 'invalid_superscript']
assert [x['outcome'] for x in invalid] == ['ValueError', 'normalized', 'normalized', 'ValueError']
assert all(x['train']['eta_status'] == 'invalid' and x['train']['eta_seconds'] is None
           for x in invalid if x['variant'] == 'after')
assert not attempts
with (ev / 'controlled-replay-v1.json').open('x', encoding='utf8') as f:
    json.dump({'created_at': datetime.now().astimezone().isoformat(), 'injected_cases': 2,
               'records': records, 'old_fields_preserved': len(old_train), 'network_attempts': attempts,
               'new_external_samples': 0, 'actual_trips': 0}, f, ensure_ascii=False, indent=2)
print(json.dumps({'replays': len(records), 'old_fields_preserved': len(old_train), 'after_invalid_handled': 2,
                  'network_attempts': len(attempts)}, ensure_ascii=False))
