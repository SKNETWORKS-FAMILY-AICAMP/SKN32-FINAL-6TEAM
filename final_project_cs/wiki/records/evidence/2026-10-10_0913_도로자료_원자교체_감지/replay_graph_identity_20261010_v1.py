from pathlib import Path
from datetime import datetime
import hashlib, importlib.util, json, socket, sys

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT/'final_project_cs'
sys.path.insert(0, str(CS))
sys.stdout.reconfigure(encoding='utf8')
state = json.loads((Path(__file__).parent/'graph-identity-state-20261010-v1.json').read_text(encoding='utf8'))
ev = ROOT/state['evidence']
from app.domains.travel_ops.instances.mobility.engine import turn_restrictions as current
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
backup = state['backups'][0]
assert sha(ROOT/backup['backup']) == backup['sha256']
spec = importlib.util.spec_from_file_location(current.__package__+'._identity_before', ROOT/backup['backup'])
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
new_load = current.load
folder = ROOT/'datasets/mobility/processed/mobility/road_graph_v2'
hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in folder.iterdir() if p.is_file()}
attempts = []
def denied(*args, **kwargs):
    attempts.append(True)
    raise RuntimeError('오프라인 재생: 네트워크 연결 금지')
socket.socket.connect = denied
socket.create_connection = denied
router = GraphRouter(folder)
router.warm(('car',))
loaded_signature = router._graph_signature
conditions = [{'from': [126.9852, 37.5845], 'to': [127.0601, 37.6076]},
              {'from': [126.9780, 37.5665], 'to': [126.9895, 37.5700]}]
rows = []
try:
    for index, condition in enumerate(conditions):
        expected = None
        for variant in ('A', 'B', 'B', 'A'):
            module = old if variant == 'A' else current
            # 비교 대상의 식별자 형식에 맞춰 같은 적재 그래프의 기준값만 맞춘다.
            # 자료 파일은 교체하지 않는다. 원자 교체 검증은 별도 회귀 시험이 담당한다.
            router._graph_signature = module.graph_signature(folder)
            current.load = old.load if variant == 'A' else new_load
            output = router.route(tuple(condition['from']), tuple(condition['to']), profile='car')
            if expected is None:
                expected = output
            assert output == expected, (index, variant)
            encoded = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            row = {'condition': index+1, 'variant': variant,
                   'output_sha256': hashlib.sha256(encoded).hexdigest(),
                   'distance_m': output['paths'][0]['distance'],
                   'applied_relations': output['paths'][0]['turn_restrictions']['applied_relations']}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
finally:
    current.load = new_load
    router._graph_signature = loaded_signature
assert not attempts
assert all(sha(ROOT/name) == value for name, value in hashes.items())
with (ev/'real-data-replay-v1.json').open('x', encoding='utf8') as f:
    json.dump({'created_at': datetime.now().astimezone().isoformat(), 'conditions': conditions,
               'replays': rows, 'matched': len(rows), 'total': len(rows), 'data_hashes': hashes,
               'network_attempts': len(attempts), 'limited_api_calls': 0,
               'limits': '보유 서울 도로자료의 고정 개발 2쌍. 실차·새 독립 웹·HTTP 지연 측정이 아닙니다.'},
              f, ensure_ascii=False, indent=2)
