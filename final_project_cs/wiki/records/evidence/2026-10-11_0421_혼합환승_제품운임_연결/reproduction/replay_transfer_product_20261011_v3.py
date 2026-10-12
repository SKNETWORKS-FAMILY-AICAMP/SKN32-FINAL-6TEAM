"""저장 서울 좌표에서 실제 제품 탐색을 다시 실행한다. 외부 통신은 차단한다."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import fields
from datetime import datetime
from pathlib import Path
import hashlib
import json
import socket
import sys

sys.stdout.reconfigure(encoding='utf8')
root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
state = json.loads((Path(__file__).parent / 'transfer-product-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
raw = root / 'datasets/mobility/raw/kakao_golden'
paths = [raw / 'fresh_experiment_100_design.json',
         raw / 'fresh_ours_transit_100_v1.json', raw / 'fresh_web_100_v1.json']
design, previous, web = [json.loads(p.read_text(encoding='utf8')) for p in paths]
refs = {x[0]: x for x in web}
targets = []
for row in previous['rows']:
    obj = row['transit']
    route = obj.get('route', {})
    trace = {x['id']: x for x in obj.get('comparison', {}).get('options', [])}
    if any({x.get('mode', 'subway') for x in item.get('check', {}).get('legs', [])} == {'bus', 'subway'}
           for item in trace.values()):
        targets.append(row['id'])
targets = sorted(targets)[:12]
assert len(targets) == 12
network_attempts = 0
def deny(*args, **kwargs):
    global network_attempts
    network_attempts += 1
    raise RuntimeError('외부 통신을 차단한 오프라인 재생입니다')
socket.socket.connect = deny
socket.socket.connect_ex = deny
from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.plan import Planner
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.verify_time import LegResult, leg_txt
runtime = build_verifier(quiet=True, local_router=True, seoul_key='', gh_url='',
                         data_dir=str(root / 'datasets/mobility/processed'))
print('정적 자료 로딩 완료 · 선택한 서울 12쌍 제품 탐색 시작', flush=True)
inputs = [x for x in design['pairs'] if x['id'] in targets]
def run(pair):
    a = {'key': pair['id'] + 'a', 'name': pair['a'], 'lat': pair['alat'], 'lon': pair['alon']}
    b = {'key': pair['id'] + 'b', 'name': pair['b'], 'lat': pair['blat'], 'lon': pair['blon']}
    planner = Planner(runtime, stage='planning', modes=['bus', 'subway'])
    routes, why = planner.leg(a, b, datetime.fromisoformat('2026-10-08T10:30:00+09:00'), {}, True, pair['id'])
    row = {'id': pair['id'], 'from': a, 'to': b, 'failure': why, 'options': []}
    if not routes:
        return row
    route = routes[0]
    context = planner.departure_context
    row['planned'] = route['planned']
    names = {f.name for f in fields(LegResult)}
    for option in route['options']:
        selected = context['options'][option['id']]
        legs = selected['legs']
        if 'bus' not in O.modes_of(legs) or len(legs) < 2:
            continue
        vehicle = [r for r in selected['leg_results'] if r['depart_min'] is not None]
        assert len(vehicle) == len(legs)
        lr = [LegResult(label=leg_txt(leg), reason='', **{k: val for k, val in result.items() if k in names})
              for leg, result in zip(legs, vehicle)]
        old = O.fare_upper_of(runtime._v, legs, lr)
        current = O.mixed_fare_estimate(runtime._v, legs, lr)
        row['options'].append({'public': option, 'discount_before_sum': old,
                               'discount_estimate': current, 'legs': legs,
                               'leg_results': selected['leg_results'],
                               'product_connected': current is not None and option.get('fare_krw') == int(current)})
    return row
rows = []
checkpoint = ev / 'seoul-product-replay-v3.jsonl'
with checkpoint.open('x', encoding='utf8') as out, ThreadPoolExecutor(max_workers=3) as pool:
    for future in as_completed([pool.submit(run, pair) for pair in inputs]):
        row = future.result()
        rows.append(row)
        out.write(json.dumps(row, ensure_ascii=False) + '\n')
        out.flush()
        print(f"서울 제품 재생 {len(rows)}/12 · {row['id']} · 혼합 후보 {len(row['options'])}", flush=True)
options = [x for row in rows for x in row['options']]
connected = [x for x in options if x['product_connected']]
out = {'created_at': datetime.now().astimezone().isoformat(), 'selected_pairs': len(inputs),
       'completed_pairs': len(rows), 'mixed_options': len(options),
       'discounted_product_options': len(connected),
       'changed_pairs': sum(any(x['product_connected'] for x in row['options']) for row in rows),
       'lower_than_separate_sum': sum(x['discount_estimate'] < x['discount_before_sum'] for x in connected),
       'fallback_options': sum(x['discount_estimate'] is None for x in options),
       'network_attempts': network_attempts, 'limited_api_calls': 0,
       'scope': '기존 개발 표본 좌표의 현재 제품 탐색. 신규 독립 웹 대조·실제 탑승·결제 측정이 아님.',
       'fixed_arrive_at': '2026-10-08T10:30:00+09:00',
       'inputs': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
       'rows': sorted(rows, key=lambda x: x['id'])}
with (ev / 'seoul-product-replay-v3.json').open('x', encoding='utf8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in out.items() if k not in ('rows', 'inputs')}, ensure_ascii=False))
