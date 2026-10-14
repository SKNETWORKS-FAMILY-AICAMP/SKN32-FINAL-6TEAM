from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
tag = stamp + '_時間帯도보_보행망연결'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
state = {'tag': tag, 'backups': []}
for rel in ['app/domains/travel_ops/instances/mobility/engine/plan_estimate.py', 'wiki/teams/mobility.md']:
    p = cs / rel
    b = p.parent / '_backup' / (stamp + '_시간대도보_보행망연결') / p.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(p, b)
    state['backups'].append({'source': p.relative_to(root).as_posix(),
        'backup': b.relative_to(root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
debug = cs / 'wiki/records/reports/debugs' / (stamp + '_시간대도보_보행망시간_미연결.md')
debug.write_text('''# 시간대별 도보 추정이 보행망을 사용하지 않는 결함

## 미해결

시간대별 추정은 직접 도보의 직선거리만 계산하여 일정 안내와 다른 소요를 제공합니다. 계단·우회·경로 미발견 상태가 이 경로에 전달되지 않습니다.

위치: `app/domains/travel_ops/instances/mobility/engine/plan_estimate.py:307`부터의 직접 도보 분기. 기존 `Planner._walk_path`는 거리와 계단 보정 시간을 반환하나 해당 분기에서는 호출하지 않습니다.

재현: 새 `test_estimate_walk_network_v1.py`에서 같은 합성 보행망을 시간대 추정과 일정 안내에 주입하여 비교합니다. 실제 운행 오차·웹 표본은 이 재현과 별개입니다. 수정 전 실행 로그를 이번 근거 폴더에 보존합니다.

위험: 시간대별 추정 소요가 더 짧거나 길어질 수 있고, 보행망에서 연결하지 못한 직접 경로를 가능으로 안내할 수 있습니다. 연결하지 못했다는 응답은 현실에서 걸을 수 없다는 증거가 아닙니다.
''', encoding='utf8')
state['debug'] = debug.relative_to(root).as_posix()
p = cs / 'wiki/teams/mobility.md'
p.write_text(p.read_text(encoding='utf8') + '\n\n## ' + stamp + ' 시간대별 직접 도보 보행망 연결 계약\n\n시간대별 이동 추정의 직접 도보도 Planner._walk_path의 거리·계단 시간과 경로 미발견 상태를 사용합니다. 직선거리의 현행 1.2km 정책과 최소 1분·분 올림, 시간대 표본 분포의 뜻은 유지합니다. 같은 창에서 직접 경로는 한 번 조회합니다. 응답 walk_basis에 보행망 또는 명시된 직선거리 대체 모델의 근거를 남기며 경로 미발견을 가능한 직접 도보로 채우지 않습니다. 지하철 접근 걷기·환승·대중교통 후보·최단 경로 보장은 이번 단위에서 바꾸지 않습니다. 이 엔진/명령줄의 소비자 API 연결 여부와 실제 보행 정확도는 별도 검증입니다.\n', encoding='utf8')
(scratch / 'estimate-walk-network-work-v1.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps(state, ensure_ascii=False))
