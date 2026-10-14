from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
import hashlib
import json
import sys
import time

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.ports.data_sources.seoul_subway import select_boardable_arrival

scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-selection-work-v2.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
raw = root / 'datasets/mobility/raw/2026-10-09_1009_지하철응답_빈값오인_public_sample/normalized-v1.json'
data = json.loads(raw.read_text(encoding='utf8'))
checked = datetime.fromisoformat(data['confirmed_at'])
started = time.perf_counter()
rt = build_verifier(data_dir=root / 'datasets/mobility/processed', gh_url='', seoul_key='', quiet=True, local_router=False)
candidates, _, _ = rt._v.candidates('01호선', '서울역', '시청', '평일')
services = {}
for departure, verdict, full in candidates:
    if departure.run is not None or departure.inferred or full or not verdict.path:
        continue
    identifiers = [rt.subway_stations.lookup('01호선', {'서울역': '서울'}.get(station, station)) for station in verdict.path]
    if any(row is None for row in identifiers):
        continue
    ids = [row['station_id'] for row in identifiers]
    if len(set(ids)) != len(ids):
        continue
    services[(ids[1], ids[-1], '일반')] = {'train_status': '일반', 'path_station_ids': ids}
binding = rt.subway_stations.bind({'line': '01호선', 'from': '서울', 'to': '시청'})
assert binding['status'] == 'matched' and services
policy = dict(line_id=binding['line_id'], station_id=binding['station_id'], target_station_id=binding['target_station_id'],
              allowed_services=list(services.values()), now=checked, ready_at=checked,
              max_age_seconds=30, max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2)
historical = select_boardable_arrival(data, **policy)
assert historical['status'] == 'no_boardable_prediction', historical
assert len(historical['excluded']) == len(data['trains']) == 5
stale = select_boardable_arrival(data, **dict(policy, now=checked + timedelta(seconds=30), ready_at=checked + timedelta(seconds=30)))
assert stale['status'] == 'stale'

# 동일 공급 자료 나이·접근 시간을 고정한 A/B/A/B 재생. B는 cache age를 ETA에서 추가 차감하는 잘못된 식.
observations = []
for cache_age in (0, 5, 15):
    provider_age, eta, access = 20, 200, 177
    fixture = {'kind': 'subway_arrival', 'source': 'controlled/replay',
               'confirmed_at': (checked - timedelta(seconds=cache_age)).isoformat(),
               'trains': [{'line_id': binding['line_id'], 'station_id': binding['station_id'],
                           'next_station_id': binding['target_station_id'],
                           'terminal_station_id': binding['target_station_id'],
                           'train_status': '일반', 'train_number': '0123', 'eta_seconds': eta,
                           'eta_status': 'valid', 'arrival_code': '99',
                           'received_at': (checked - timedelta(seconds=provider_age)).isoformat()}]}
    p = dict(policy, allowed_services=[{'train_status': '일반', 'path_station_ids': [binding['station_id'], binding['target_station_id']]}],
             ready_at=checked + timedelta(seconds=access))
    for mode in ('A', 'B', 'A', 'B'):
        if mode == 'A':
            selected = select_boardable_arrival(fixture, **p)
            remaining = selected['remaining_seconds']
            boardable = selected['status'] == 'predicted'
        else:
            remaining = eta - provider_age - cache_age
            boardable = remaining >= access
        observations.append({'cache_age_seconds': cache_age, 'mode': mode,
                             'remaining_seconds': remaining, 'predicted_boardable': boardable})
assert all(row['remaining_seconds'] == 180 for row in observations if row['mode'] == 'A')
result = {'created_at': datetime.now().astimezone().isoformat(),
          'input_path': raw.relative_to(root).as_posix(), 'input_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
          'snapshot_original_confirmed_at': data['confirmed_at'], 'new_live_snapshots': 0, 'audit_only_name_bridge': {'01호선|서울역': '1호선|서울'}, 'production_alias_changed': False,
          'unique_historical_snapshots': 1, 'partial_provider_rows': 5,
          'binding': binding, 'static_service_patterns': len(services), 'historical_selection': historical,
          'historical_exclusion_counts': dict(Counter(x['reason'] for x in historical['excluded'])),
          'stale_replay': stale, 'controlled_abba_runs': observations,
          'elapsed_seconds': time.perf_counter() - started,
          'claim': 'Historical five-row partial response with static route identity, not five independent samples or observed ETA accuracy. ABBA is deterministic controlled arithmetic, not statistical performance.'}
with (ev / 'native-source-replay-v2.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps({'historic_status': historical['status'], 'rows': 5, 'patterns': len(services),
                  'exclusions': result['historical_exclusion_counts'], 'controlled_abba_runs': len(observations)}, ensure_ascii=False))
