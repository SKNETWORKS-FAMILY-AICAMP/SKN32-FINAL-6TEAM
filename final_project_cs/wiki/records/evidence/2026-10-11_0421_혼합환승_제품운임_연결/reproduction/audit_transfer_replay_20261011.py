"""제품 재생의 환승 보행 행을 승차 행과 구분하여 운임을 대조한다."""
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
tag = '2026-10-11_0421_혼합환승_제품운임_연결'
ev = cs / 'wiki/records/evidence' / tag
source = ev / 'seoul-product-replay-v1.json'
data = json.loads(source.read_text(encoding='utf8'))
network_attempts = 0
def deny(*args, **kwargs):
    global network_attempts
    network_attempts += 1
    raise RuntimeError('오프라인 계산의 외부 통신을 차단했습니다')
socket.socket.connect = deny
socket.socket.connect_ex = deny
from app.domains.travel_ops.instances.mobility.engine import options as O
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine.verify_time import LegResult, leg_txt
rt = build_verifier(quiet=True, local_router=True, seoul_key='', gh_url='',
                    data_dir=str(root / 'datasets/mobility/processed'))
names = {f.name for f in fields(LegResult)}
for row in data['rows']:
    for option in row['options']:
        # capture()에는 환승 보행 결과도 포함된다. 승차 결과만 시각을 가진다.
        vehicle = [r for r in option['leg_results'] if r['depart_min'] is not None]
        legs = option['legs']
        assert len(vehicle) == len(legs)
        lr = [LegResult(label=leg_txt(leg), reason='', **{k: val for k, val in r.items() if k in names})
              for leg, r in zip(legs, vehicle)]
        old = O.fare_upper_of(rt._v, legs, lr)
        new = O.mixed_fare_estimate(rt._v, legs, lr)
        option['discount_before_sum'] = old
        option['discount_estimate'] = new
        option['product_connected'] = new is not None and option['public'].get('fare_krw') == int(new)
        if new is not None:
            assert option['product_connected']
            assert '1인 1카드' in option['public']['label'] and '승하차 태그' in option['public']['label']
        else:
            assert option['public'].get('fare_krw') == old
options = [o for r in data['rows'] for o in r['options']]
connected = [o for o in options if o['product_connected']]
data.update({'created_at': datetime.now().astimezone().isoformat(),
             'discounted_product_options': len(connected),
             'changed_pairs': sum(any(o['product_connected'] for o in r['options']) for r in data['rows']),
             'lower_than_separate_sum': sum(o['discount_estimate'] < o['discount_before_sum'] for o in connected),
             'fallback_options': sum(o['discount_estimate'] is None for o in options),
             'network_attempts': network_attempts,
             'audit_correction': 'v1은 환승 보행 행을 승차 행에 zip하여 재계산 집계를 0건으로 잘못 냈다. 제품 응답 금액/label은 정상이며 이 파일에서 실제 승차 시각 행만 사용해 정정했다.',
             'source_replay_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
with (ev / 'seoul-product-replay-v2.json').open('x', encoding='utf8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in data.items() if k not in ('rows', 'inputs')}, ensure_ascii=False))
