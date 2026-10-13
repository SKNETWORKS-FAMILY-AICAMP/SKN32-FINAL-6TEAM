from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
tag = stamp + '_같은최근접역_다른역조합'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
state = {'tag':tag,'backups':[]}
for rel in ['app/domains/travel_ops/instances/mobility/engine/plan.py',
            'tests/unit/travel/mobility/test_station_fallback_v1.py', 'wiki/teams/mobility.md']:
    p = cs / rel
    b = p.parent / '_backup' / tag / p.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(p,b)
    state['backups'].append({'source':p.relative_to(root).as_posix(),
        'backup':b.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
debug = cs / 'wiki/records/reports/debugs' / (stamp + '_최근접역이_같을때_전체역조합_제외.md')
debug.write_text('''# 가장 가까운 역이 같으면 다른 역 조합도 제외하는 결함

## 미해결

위치: `app/domains/travel_ops/instances/mobility/engine/plan.py:1141`의 `_station_pairs`. 양쪽 첫 역이 같으면 나머지 후보 역을 보기 전에 빈 목록을 반환합니다. 기존 단위 시험은 이 제약을 사각지대로 기록하며 유지하고 있었습니다.

재현: `test_shared_nearest_station_v1.py`의 같은 최근접역·서로 다른 두번째 역 목록과 공개 Planner.leg 호출을 수정 전에 실행합니다. 유효 경로의 시간표 판정은 그대로 두며 새 비교 좌표나 웹 경로가 있다고 가정하지 않습니다.

위험: 직접 도보를 제외한 수단이나 도보 범위 밖인 두 장소에서 허용 범위의 다른 역을 이용하는 경로가 탐색 전에 사라집니다. 기존200쌍은 대중교통 결과200개가 있어 이 결함으로 기존 제공수가 줄었다고 단정하지 않습니다.

범위: 같은 물리적 역끼리의 빈 승차 구간만 제외하고 다른 물리적 역 조합은 기존 순서·상한·시간표 판정으로 확인합니다. 모든 경로를 탐색하는 최적성 보장이나 실제 탑승 정확도는 별개입니다.
''', encoding='utf8')
state['debug'] = debug.relative_to(root).as_posix()
wiki = cs / 'wiki/teams/mobility.md'
wiki.write_text(wiki.read_text(encoding='utf8') + f'\n\n## {stamp} 같은 최근접역의 다른 역 조합 탐색 계약\n\n두 장소의 첫 역이 같아도 다른 물리적 역 조합을 기존 후보 상한·도보 정책 안에서 열거합니다. 동일 물리적 역끼리의 승하차 없는 조합만 제외하고 동명이역의 노선군은 기존 same_station 규칙으로 구별합니다. 조합 정렬·첫 성립 조합 중단·사고 역 제외·운행/도착/앞 일정 끝 판정은 그대로 사용합니다. leg와earliest가 공유하는 목록에 적용하고 모든 가능한 경로 또는 전체 최소 소요를 보장한 것으로 쓰지 않습니다. 기존 사각지대 유지 시험은 새 계약에 맞춰 수정 전판을 보존하고 바꿉니다.\n', encoding='utf8')
(scratch/'shared-nearest-station-work-v1.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(state,ensure_ascii=False))
