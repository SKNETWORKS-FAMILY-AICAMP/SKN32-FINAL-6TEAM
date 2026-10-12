from pathlib import Path
from datetime import datetime, timedelta
from copy import deepcopy
from collections import Counter
import hashlib
import importlib.util
import json
import sys
import urllib.parse
import time

import httpx

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.subway_identity import SubwayStationIndex
from app.domains.travel_ops.instances.mobility.engine.subway_departure import boarding_services
from app.domains.travel_ops.instances.mobility.engine.departure_observer import observe
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from app.domains.travel_ops.ports.data_sources.subway_boarding import select_boardable_arrival

scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-primary-work-v2.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, d):
    with p.open('x', encoding='utf8') as f: json.dump(d, f, ensure_ascii=False, indent=2, allow_nan=False)

original = root / next(x['backup'] for x in state['backups'] if x['source'].endswith('/subway_identity.py'))
spec = importlib.util.spec_from_file_location('old_station_identity', original)
old_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old_module)
index_path = root / 'datasets/mobility/processed/mobility/subway_realtime_stations_20260902_v1.json'
coords_path = index_path.parent / 'station_coords.json'
payload = json.loads(index_path.read_text(encoding='utf8'))
coords = json.loads(coords_path.read_text(encoding='utf8'))['stations']
before_index = old_module.SubwayStationIndex(payload, content_sha256=sha(index_path))
after_index = SubwayStationIndex(payload, content_sha256=sha(index_path))
matches, remaining = [], []
for key, row in coords.items():
    before, after = [ix.lookup(row['line'], row['station_nm']) for ix in (before_index, after_index)]
    record = {'station_key': key, 'before': before, 'after': after}
    (matches if after else remaining).append(record)
before_count = sum(before_index.lookup(row['line'], row['station_nm']) is not None for row in coords.values())
added = [row for row in matches if row['before'] is None]
processed = root / 'datasets/mobility/processed' / (state['tag'] + '_audit')
processed.mkdir(exist_ok=False)
save(processed / 'station-crosswalk-v1.json', {'created_at': datetime.now().astimezone().isoformat(), 'source': '서울특별시 OA-12764 공개 역정보 2026-09-02; 주역명 의미 서울시 2021-05-20 안내', 'license': '공공누리 제1유형, 출처: 서울특별시', 'input_hashes': {index_path.relative_to(root).as_posix(): sha(index_path), coords_path.relative_to(root).as_posix(): sha(coords_path)}, 'total': len(coords), 'before_matches': before_count, 'after_matches': len(matches), 'added_matches': added, 'remaining': remaining, 'alias_conflicts': [{'key': list(key), 'ids': ids} for key, ids in after_index._primary_conflicts.items()], 'claim': '보유 정적 역자료 대응 감사이며 실제 서비스 제공/ETA 정확도 검증 아님. 운영에서 이 감사 파일을 별도 적재하지 않음.'})
start = time.perf_counter()
rt = build_verifier(data_dir=root / 'datasets/mobility/processed', gh_url='', seoul_key='', quiet=True, local_router=False)
leg = {'mode': 'subway', 'line': '05호선', 'from': '양평', 'to': '영등포구청'}
rt.subway_stations = before_index
old_binding, old_services = boarding_services(rt, leg)
rt.subway_stations = after_index
binding, services = boarding_services(rt, leg)
assert len(old_services) == 21 and len(services) > len(old_services)
assert all(any(s['terminal'] == name for s in services) for name in ('하남검단산', '마천'))
now = datetime.fromisoformat('2026-10-09T11:00:00+09:00')
origin, destination = {'lat': 37.5245, 'lon': 126.886}, {'lat': 37.5249, 'lon': 126.896}
context = {'schema_version': 1, 'timing_unit': 'model_minutes', 'from_place': origin, 'to_place': destination,
           'basis': input_basis(rt), 'party': {}, 'first_visit': False, 'options': {'p': {'option_id': 'p',
           'legs': [leg], 'subway_identity': binding, 'check': {'legs': [deepcopy(leg)], 'walk_place_in': 4,
           'walk_stop_in': 2, 'walk_stop_out': 1, 'walk_place_out': 1}}}}
controlled = []
for terminal in ('하남검단산', '마천'):
    def current(station, **kw):
        service = next(s for s in services if s['terminal'] == terminal)
        ids = service['path_station_ids']
        snap = {'kind': 'subway_arrival', 'source': 'controlled/official-name-route', 'confirmed_at': now.isoformat(), 'trains': [{'line_id': binding['line_id'], 'station_id': ids[0], 'next_station_id': ids[1], 'terminal_station_id': ids[-1], 'train_number': '0501', 'train_status': '일반', 'eta_seconds': 540, 'eta_status': 'valid', 'arrival_code': '99', 'received_at': now.isoformat()}]}
        return select_boardable_arrival(snap, max_age_seconds=30, max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2, **kw)
    for repeat in range(2):
        got = observe(rt, context, 'p', now=now, deadline=now + timedelta(hours=1), origin=origin, destination=destination, subway_arrival=current)
        assert got['status'] == 'realtime' and got['leg_results'][0]['depart_min'] == 669, got
        controlled.append({'terminal': terminal, 'repeat': repeat, 'result': got})
assert controlled[0]['result'] == controlled[1]['result'] and controlled[2]['result'] == controlled[3]['result']

# 인증키 없는 공개 sample 두 번. 지도 개발자 API를 호출하지 않는다.
raw_dir = root / 'datasets/mobility/raw' / (state['tag'] + '_public_sample')
raw_dir.mkdir(exist_ok=False)
live = []
for i, station in enumerate(('양평', '군자(능동)'), start=1):
    url = 'http://swopenapi.seoul.go.kr/api/subway/sample/json/realtimeStationArrival/0/5/' + urllib.parse.quote(station, safe='')
    started_at = datetime.now().astimezone()
    try:
        response = httpx.get(url, timeout=20, follow_redirects=True)
        finished = datetime.now().astimezone()
        raw = raw_dir / f'response-{i}-v1.json'
        with raw.open('xb') as f: f.write(response.content)
        src = SeoulSubwayArrival(service_key='sample', transport=lambda url, params: response, now=lambda: finished)
        normalized = src.arrivals(station)
        if normalized is not None: save(raw_dir / f'normalized-{i}-v1.json', normalized)
        entry = {'station': station, 'started_at': started_at.isoformat(), 'finished_at': finished.isoformat(), 'url': url,
                 'http_status': response.status_code, 'raw_path': raw.relative_to(root).as_posix(), 'raw_sha256': sha(raw),
                 'response_code': response.json().get('errorMessage', {}).get('code'), 'normalized_rows': len(normalized['trains']) if normalized else None, 'misses': dict(src.misses),
                 'claim': '한 시각의 최대5행 공개 부분응답. 전체 서비스 제공/실제 도착/탑승/독립 웹 경로 성능 아님.'}
        if normalized and station == '양평':
            selections = []
            for label, group in [('before', old_services), ('after', services)]:
                id_keys = {(s['path_station_ids'][1], s['path_station_ids'][-1], '일반') for s in group}
                id_covered = sum(t['line_id'] == binding['line_id'] and t['station_id'] == binding['station_id'] and (t['next_station_id'], t['terminal_station_id'], t['train_status']) in id_keys for t in normalized['trains'])
                result = select_boardable_arrival(normalized, line_id=binding['line_id'], station_id=binding['station_id'], target_station_id=binding['target_station_id'], allowed_services=[{'train_status': s['train_status'], 'path_station_ids': s['path_station_ids']} for s in group], now=finished, ready_at=finished + timedelta(minutes=6), max_age_seconds=30, max_provider_age_seconds=90, max_provider_clock_ahead_seconds=2)
                selections.append({'mode': label, 'identifier_covered_rows': id_covered, 'result': result})
            entry['selections'] = selections
        live.append(entry)
    except Exception as error:
        live.append({'station': station, 'started_at': started_at.isoformat(), 'failure_type': type(error).__name__, 'claim': '네트워크/입력 처리 실패. 실패를 열차 없음으로 해석하지 않음.'})
save(raw_dir / 'acquisition-v1.json', {'created_at': datetime.now().astimezone().isoformat(), 'source': '서울특별시 OA-12764 공개 sample', 'license': '공공누리 제1유형, 출처: 서울특별시', 'requests': live, 'public_requests_attempted': 2, 'map_developer_api_calls': 0, 'actual_boarding_payment': 0})
save(ev / 'native-primary-audit-v1.json', {'created_at': datetime.now().astimezone().isoformat(), 'coord_rows': len(coords), 'before_matches': before_count, 'after_matches': len(matches), 'added_matches': len(added), 'remaining': len(remaining), 'alias_count': len(after_index._by_primary_name), 'alias_conflicts': len(after_index._primary_conflicts), 'line5_names_before_missing': 8, 'line5_names_after_missing': sum(after_index.lookup('05호선', name) is None for name in rt._v.lo.stations('05호선')), 'old_service_patterns': len(old_services), 'new_service_patterns': len(services), 'terminal_restored': ['하남검단산', '마천'], 'controlled_runs': controlled, 'live_requests': live, 'processed_path': processed.relative_to(root).as_posix(), 'raw_path': raw_dir.relative_to(root).as_posix(), 'elapsed_seconds': time.perf_counter() - start, 'claim': '정적 대응 전후 및 두 종착×같은 통제입력2회. 공개 부분응답은 실제 도착 정확도/독립 경로 표본이 아님.'})
print(json.dumps({'matches': [before_count, len(matches), len(coords)], 'patterns': [len(old_services), len(services)], 'controlled': len(controlled), 'live': [{k: x.get(k) for k in ('station', 'http_status', 'response_code', 'normalized_rows', 'failure_type')} for x in live]}, ensure_ascii=False))
