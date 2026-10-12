from pathlib import Path
from datetime import datetime
import json
import socket
import time

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
state = json.loads((Path(__file__).parent / 'walk-evaluation-work-v1.json').read_text(encoding='utf8'))
evidence = cs / 'wiki/records/evidence' / state['tag']
from scripts.mobility import compare_kakao_golden as comparison
from app.domains.travel_ops.instances.mobility.engine import runtime as engine

build = engine.build_verifier
def offline_build(**kwargs):
    return build(**dict(kwargs, seoul_key='', gh_url=''))
engine.build_verifier = offline_build
network_attempts = []
def forbidden_connect(*args, **kwargs):
    network_attempts.append('blocked')
    raise RuntimeError('network calls prohibited during local replay')
socket.socket.connect = forbidden_connect
socket.create_connection = forbidden_connect
started = datetime.now().astimezone()
clock = time.monotonic()
got = comparison.run(datetime.fromisoformat('2026-10-09T10:30:00+09:00'), only={'G04'})
assert not network_attempts, network_attempts
assert len(got['rows']) == 1
out = root / 'datasets/mobility/raw/kakao_golden' / (state['tag'] + '_G04_product_v2.json')
with out.open('x', encoding='utf8') as handle:
    json.dump(got, handle, ensure_ascii=False, indent=2)
record = {'started_at': started.isoformat(), 'ended_at': datetime.now().astimezone().isoformat(),
          'elapsed_seconds': time.monotonic()-clock, 'network_attempts': len(network_attempts),
          'map_developer_api_calls': 0, 'actual_trips': 0, 'row': got['rows'][0],
          'summary': got['summary'], 'raw': out.relative_to(root).as_posix()}
with (evidence / 'actual-replay-v2.json').open('x', encoding='utf8') as handle:
    json.dump(record, handle, ensure_ascii=False, indent=2)
print(json.dumps(record, ensure_ascii=False))
