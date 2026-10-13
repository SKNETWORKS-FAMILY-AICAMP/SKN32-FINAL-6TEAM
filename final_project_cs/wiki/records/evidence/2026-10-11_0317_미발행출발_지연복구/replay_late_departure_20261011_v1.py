"""이전 실제 서울 응답을 당시 시각에 재생한다. 현재 운행 조회 아님."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import hashlib
import json
import shutil
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'final_project_cs'
sys.path.insert(0, str(CS))
sys.stdout.reconfigure(encoding='utf-8')
EV = CS / 'wiki/records/evidence/2026-10-11_0317_미발행출발_지연복구'
RAW = ROOT / 'datasets/mobility/raw/2026-10-09_1248_지하철_방면과_인접역ID_대조'
body = json.loads((RAW / 'response-1-v1.json').read_text(encoding='utf-8'))
acq = json.loads((RAW / 'acquisition-v1.json').read_text(encoding='utf-8'))
now = datetime.fromisoformat(acq['requests'][0]['finished_at'])
connections = []

def denied(*args, **kwargs):
    connections.append(True)
    raise RuntimeError('보유 자료 재생: 네트워크 연결 금지')

socket.socket.connect = denied
socket.create_connection = denied
from app import composition
from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine import runtime
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.instances.mobility.engine.subway_identity import boarding_identity
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival
from app.domains.travel_ops.components.watch import trip_reminders as notices
from app.domains.travel_ops.components.itinerary.itinerary import Item

rt = runtime.build_verifier(quiet=True, local_router=True, seoul_key='', gh_url='',
    data_dir=str(ROOT / 'datasets/mobility/processed'))
wiring._STATE.update(mode='enabled', kw={})
wiring.engine_runtime.get_verifier = lambda **kw: rt
queries = []

class ReplaySource(SeoulSubwayArrival):
    def _fetch_json(self, url, params):
        self._fetch_state.fetched_at = now
        self._fetch_state.from_cache = True
        queries.append('stored_response')
        return deepcopy(body)

source = ReplaySource(service_key='offline-replay', now=lambda: now)
policy = {'travel.bus_arrival_cache_seconds': 30, 'travel.subway_arrival_cache_seconds': 30,
    'mobility.departure_observation.max_provider_age_seconds': 90,
    'mobility.departure_observation.max_provider_clock_ahead_seconds': 2}
observer = composition.build_mobility_departure_observer(SimpleNamespace(mobility_data_dir='offline'),
    SimpleNamespace(subway_arrival=source), guardrails=policy)
legs = [{'mode': 'subway', 'line': '05호선', 'from': '공덕', 'to': '종로3가'},
        {'mode': 'subway', 'line': '03호선', 'from': '종로3가', 'to': '안국'}]
origin = {'lat': 37.544005, 'lon': 126.951058}
destination = {'lat': 37.576562, 'lon': 126.98547}
context = {'schema_version': 1, 'timing_unit': 'model_minutes', 'from_place': origin,
    'to_place': destination, 'basis': input_basis(rt), 'party': {}, 'first_visit': False,
    'options': {'p': {'option_id': 'p', 'legs': legs, 'subway_identity': boarding_identity(rt, legs),
        'check': {'legs': deepcopy(legs), 'walk_place_in': 1, 'walk_stop_in': 1,
                  'walk_stop_out': 1, 'walk_place_out': 1}}}}
def place(coords, name):
    return dict(latitude=coords['lat'], longitude=coords['lon'], name=name)

before = Item(uuid4(), 0, 'activity', '공덕 방문', None, now-timedelta(hours=1), now-timedelta(minutes=3),
    place=place(origin, '공덕'))
move = Item(uuid4(), 1, 'mobility', '공덕 → 안국', None, now-timedelta(minutes=3), now-timedelta(minutes=1),
    detail={'departure_context': context, 'route_def': {'planned': 'p', 'options': [
        {'id': 'p', 'label': '05호선 → 03호선', 'uses': ['05호선', '03호선'], 'eta_min': 999}]}})
after = Item(uuid4(), 2, 'activity', '안국 방문', None, now+timedelta(hours=1), now+timedelta(hours=2),
    place=place(destination, '안국'))
items, trip_id, payloads = [before, move, after], uuid4(), {}
trip = {'version': 1, 'locale': 'ko', 'party_size': None, 'constraints': {'first_visit': False}}
original = deepcopy(items)
notices.PendingStore.list = lambda *a, **kw: []
class Connection:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def transaction(self): return nullcontext()
def enqueue(conn, *, key, payload, **kw):
    if key in payloads: return False
    payloads[key] = deepcopy(payload)
    return True
store = SimpleNamespace(tenant_id='offline_late_replay', active_trip_ids=lambda *a: [trip_id],
    latest=lambda *a: (trip, items), message_exists=lambda conn, **kw: kw['key'] in payloads,
    enqueue_message=enqueue)
runner = notices.TripReminders(store=store, connection_factory=Connection, clock=lambda: now,
    route_events=SimpleNamespace(affecting=lambda targets: {}), rules=notices.ReminderRules(),
    departure_observer=observer)
first = runner.tick()
again = runner.tick()
[payload] = payloads.values()
out = {'scope': '개발 고정 구간·이전 응답 당시 시각 재생. 현재 운행/독립 정확도/실탑승/DB 저장 확인 아님.',
    'replay_clock': now.isoformat(), 'saved_move_ends_at': move.ends_at.isoformat(),
    'first': vars(first), 'again': vars(again), 'payload': payload, 'stored_response_reads': len(queries),
    'blocked_connections': len(connections), 'limited_api_calls': 0, 'input_items_preserved': items == original,
    'source_hashes': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (RAW/'response-1-v1.json', RAW/'acquisition-v1.json')}}
with (EV/'stored-seoul-late-replay-v1.json').open('x', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2, default=str)
shutil.copy2(__file__, EV / Path(__file__).name)
assert len(first.sent) == 1 and not first.fatal and not first.held, first
assert again.already == 1 and not again.sent
assert payload['departure_observation']['status'] == 'realtime'
assert '12:59 공덕 승차' in payload['text'] and '13:15 종로3가 환승' in payload['text']
assert items == original and len(queries) == 1 and not connections
print(json.dumps({'first_sent': len(first.sent), 'again_already': again.already,
    'network_connections': len(connections), 'notice': payload['text']}, ensure_ascii=False, indent=2))
