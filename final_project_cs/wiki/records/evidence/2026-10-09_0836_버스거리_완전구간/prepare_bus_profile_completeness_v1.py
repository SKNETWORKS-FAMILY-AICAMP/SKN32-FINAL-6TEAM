from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'bus-distance-work-v2.json').read_text(encoding='utf8'))
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
for rel in ['app/domains/travel_ops/instances/mobility/engine/bus_profile.py', 'wiki/teams/mobility.md', state['debug']]:
    p = cs / rel
    b = p.parent / '_backup' / (stamp + '_버스프로파일_완전구간') / p.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(p, b)
    state['backups'].append({'source': p.relative_to(root).as_posix(), 'backup': b.relative_to(root).as_posix(),
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write('\n\n### 버스 통행시간 자료의 구간 완전성 보완 계약\n\nBusSegProfile.walk도 요청한 양 끝과 중간 순번의 연속성을 확인한다. 중간 행 누락·중복·다른 노선 행으로 생긴 가짜 인접 구간에 통행시간이나 도착 행의 거리 대체를 적용하지 않는다. 유효 프로파일은 거리 칸이 없어도 사용하되 거리 대체를 할 때만 유한 비음수 숫자 거리인지 검사한다. 기점 통과 계산의 같은 순번 0분 계약은 유지한다. 실제 자료 영향·기존 프로파일 시험·현재 출발 연결을 별도 확인한다.\n')
with (cs / state['debug']).open('a', encoding='utf8') as f:
    f.write('\n\n추가 확인: bus_profile.py의 walk도 중간 순번 누락을 실제 인접 구간으로 취급하고 도착 행의 한 구간 거리로 대체할 수 있다. 같은 원인의 별도 계산 경로이므로 함께 수정한다. 유효 프로파일에 거리 누락을 이유로 불필요한 대체를 강제하지 않는다.\n')
with (scratch / 'bus-distance-work-v3.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print('backup records', len(state['backups']))
