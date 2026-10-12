from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-station-map-work-v1.json').read_text(encoding='utf8'))
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
for rel in ['app/domains/travel_ops/ports/data_sources/seoul_subway.py', 'wiki/teams/mobility.md']:
    src = cs / rel
    dst = src.parent / '_backup' / (stamp + '_지하철누락호선') / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(src, dst)
    state['backups'].append({'source': src.relative_to(root).as_posix(), 'backup': dst.relative_to(root).as_posix(),
                             'sha256': hashlib.sha256(src.read_bytes()).hexdigest()})
debug = cs / 'wiki/records/reports/debugs' / (stamp + '_실시간지하철_세호선_필터누락.md')
debug.write_text('''# 실시간 지하철 세 호선 필터 누락

## 미해결

서울시 2026-09-02 공개 역정보696행의 호선ID를 기존 소스 SUBWAY_ID와 대조하니 경강선1081의12역·서해선1093의21역·신림선1094의11역이 호선 이름으로 변환되지 않습니다. 위치: app/domains/travel_ops/ports/data_sources/seoul_subway.py:30. 현재 sources.arrivals(line=호선명)은 이 행을 걸러 버립니다.

자료 자체로 ID 누락을 확인했으며 실제 운행 응답44건을 받은 결과가 아닙니다. 통제 응답의 공개 arrivals 호출로 수정 전후를 재현합니다. 재현 명령은 같은 근거 폴더 before-v1.run.json에 보존합니다. 영향: 요청 호선의 열차 목록이 빈 것처럼 보임. 실시간 출발/환승 관측은 아직 지하철에 연결되지 않아 잘못된 안내 전송을 단정하지 않습니다. 기존 웹 정확도 지표 정정 근거는 아닙니다.
''', encoding='utf8')
state['debug'] = debug.relative_to(root).as_posix()
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'\n\n## {stamp} 공식 실시간 호선 번호 대응 보강 계약\n\n공식 공개 역정보의 경강선1081·서해선1093·신림선1094를 기존 SUBWAY_ID 이름 표에 추가합니다. 공개 arrivals의 호선 필터가 세 호선을 버리지 않게 하되 미등록 번호는 기존대로 원 번호를 보존합니다. 번호는 공개 파일 값을 쓰고 임의 요율·ETA·역번호를 보정하지 않습니다. 공식 역정보44행으로 주입한 필터 검증과 실제44역 운행 응답은 구별합니다. [발견 기록](../records/reports/debugs/{debug.name}).\n')
newstate = scratch / 'subway-station-map-work-v2.json'
newstate.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'backups': len(state['backups']), 'debug': debug.name}, ensure_ascii=False))
