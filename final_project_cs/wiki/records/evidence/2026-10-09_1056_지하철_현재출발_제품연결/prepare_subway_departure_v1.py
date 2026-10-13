from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
old = cs / 'wiki/records/evidence/2026-10-09_1039_지하철_접근후열차_선택'
proof = json.loads((old / 'verification-proof-v1.json').read_text(encoding='utf8'))
pub = json.loads((old / 'publication-validation-v1.json').read_text(encoding='utf8'))
hashes = {**proof['source_test_data_hashes'], **pub['artifact_hashes']}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(root / rel) == digest for rel, digest in hashes.items())
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
tag = stamp + '_지하철_현재출발_제품연결'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
owned = ['app/composition.py', 'config/guardrails.yaml',
         'app/domains/travel_ops/ports/data_sources/base.py',
         'app/domains/travel_ops/ports/data_sources/seoul_subway.py',
         'app/domains/travel_ops/components/watch/departure_revalidation.py',
         'app/domains/travel_ops/components/watch/trip_reminders.py',
         'app/domains/travel_ops/instances/mobility/engine/runtime.py',
         'app/domains/travel_ops/instances/mobility/engine/verify_time.py',
         'app/domains/travel_ops/instances/mobility/engine/departure_observer.py',
         'wiki/teams/mobility.md']
backups = []
for rel in owned:
    src = cs / rel
    dst = src.parent / '_backup' / tag / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(src, dst)
    backups.append({'source': src.relative_to(root).as_posix(), 'backup': dst.relative_to(root).as_posix(), 'sha256': sha(src)})
state = {'tag': tag, 'owned': owned, 'backups': backups, 'prior_source_test_data_hashes': proof['source_test_data_hashes']}
with (Path(__file__).parent / 'subway-departure-work-v1.json').open('x', encoding='utf8') as f: json.dump(state, f, ensure_ascii=False, indent=2)
with (ev / 'preflight-v1.json').open('x', encoding='utf8') as f: json.dump({'hash_matches': len(hashes), 'backups': backups}, f, ensure_ascii=False, indent=2)
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 지하철 현재 출발 연결의 내부 계약\n\n첫 승차가 지하철이며 공식 노선/역명으로 정확히 대응하는 일반·비순환 경로만 현재 도착 콜백을 호출합니다. 정적 경로의 다음역/종착역을 공식ID로 생성하고, 선택된 열차의 ID·경로·생성시각 기준 도착을 재대조한 뒤 현재 요청에만 승차 분을 전달합니다. 승차 이후 소요는 해당 일반 경로의 역간 모델이며 다른 시간표 열차의 소요를 빌리지 않습니다. 이후 환승/혼잡/출발 안내는 바뀐 시각으로 다시 계산합니다. 미래 구간은 현재 실시간이라고 부르지 않습니다. 실패/오래됨/미대응은 상태 근거를 보존하고 기존 시간표 모델로 재검증하며 모델도 못 계산하면 기존 치명/재계산 경로를 유지합니다. 내부 optional subway_arrival 콜백과 subway_departures 인자를 추가하고 공개 고객JSON/Core계약은 변경하지 않습니다. 지하철 도착 보관 시간은 travel.subway_arrival_cache_seconds 설정으로 통일합니다.\n')
with (cs / 'wiki/records/reports/debugs' / (tag + '.md')).open('x', encoding='utf8') as f:
    f.write('# 지하철 현재 도착의 출발 안내 미연결\n\n## 미해결\n\n출발 관측(departure_observer.py)은 버스만 조회하고 지하철은 시간표 모델만 사용합니다. 지하철 소스 보관은 일반 소스 TTL이므로 현재 승차의 짧은 신선도 정책과 맞지 않습니다. 신규 통제 시험으로 조립→정확 경로→현재 승차→후속 환승→안내 연결을 재현하며 로그를 같은 이름의 evidence에 보존합니다. 일반 비순환의 정확 노선/역명 범위만 이번 단위이고 공식 이름 차이·급행·순환선·실탑승은 남습니다.\n')
print(json.dumps({'tag': tag, 'preflight': len(hashes), 'backups': len(backups)}, ensure_ascii=False))
