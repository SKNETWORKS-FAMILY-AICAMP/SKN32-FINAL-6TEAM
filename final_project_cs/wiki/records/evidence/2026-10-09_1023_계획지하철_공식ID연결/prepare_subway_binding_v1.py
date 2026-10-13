from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
now = datetime.now().astimezone()
tag = now.strftime('%Y-%m-%d_%H%M') + '_계획지하철_공식ID연결'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
prior = cs / 'wiki/records/evidence/2026-10-09_1009_지하철응답_빈값오인'
proof = json.loads((prior / 'verification-proof-v1.json').read_text(encoding='utf8'))
publication = json.loads((prior / 'publication-validation-v2.json').read_text(encoding='utf8'))
hashes = proof['source_test_data_hashes']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for rel, digest in {**hashes, **publication['artifact_hashes']}.items(): assert sha(root / rel) == digest, rel
state = {'tag': tag, 'created_at': now.isoformat(), 'prior_source_test_data_hashes': hashes, 'backups': []}
files = ['app/domains/travel_ops/instances/mobility/engine/runtime.py',
         'app/domains/travel_ops/instances/mobility/engine/datacheck.py',
         'app/domains/travel_ops/instances/mobility/engine/departure_context.py',
         'app/domains/travel_ops/instances/mobility/engine/departure_observer.py',
         'app/domains/travel_ops/instances/mobility/wiring.py', 'wiki/teams/mobility.md']
for rel in files:
    src = cs / rel
    dst = src.parent / '_backup' / tag / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(src, dst)
    state['backups'].append({'source': src.relative_to(root).as_posix(), 'backup': dst.relative_to(root).as_posix(), 'sha256': sha(src)})
debug = cs / 'wiki/records/reports/debugs' / (tag + '.md')
with debug.open('x', encoding='utf8') as f:
    f.write('''# 計画した地鐵의 공식 역ID가 출발 문맥과 연결되지 않음

## 미해결

위치: engine/departure_context.py의 capture·input_basis와 engine/runtime.py의 default_paths·changed_sources. 공식 역ID696행을 확보했지만 런타임은 파일을 읽지 않고, 저장 출발 문맥에는 계획한 승차/하차역의 공식 ID가 없습니다. 역명만으로 실시간 열차를 붙이면 동명이역과 다른 호선이 섞일 수 있습니다. 현재 지하철 도착 소스는 구성만 되어 있고 출발 관측/안내에서 호출하지 않으므로, 이미 잘못된 안내가 발송됐다고 주장하지 않습니다.

신규 통제 시험으로 정확 노선·역명 대응, 자료 변조/누락, 저장 문맥의 ID 변경을 재현합니다. 실제 ID를 생성하거나 넓은 이름 추정을 하지 않고 공식 파일의 값을 사용합니다. 공식 파일 적재·해시 추적·내부 문맥 연결·저장 전 버전 대조를 최소 단위로 구현하며, 열차 종류/방향/종착 선택과 실시간 시각 대체는 다음 단위입니다. 기존 비교 정확도 수치를 바꾸지 않습니다. 재현 명령과 원문은 같은 이름의 evidence 폴더에 보존합니다.
'''.replace('計画した地鐵', '계획한 지하철'))
state['debug'] = debug.relative_to(root).as_posix()
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'''\n\n## {tag} 계획 지하철의 공식 역ID 연결 계약

공식 추출 파일 subway_realtime_stations_20260902_v1.json을 런타임의 선택 입력으로 읽습니다. 파일이 없으면 기존 시간표 계산은 유지하되 지하철 공식 ID 연결은 unavailable로 명시합니다. 파일이 있으면 잘못된 스키마·타입·중복 ID·중복 노선/역명·건수 불일치를 적재 실패로 처리합니다. 노선명은 숫자1~9호선의 선행0만 통일하고 역명은 정확히 대조하며 임의 별칭이나 ID 접두를 만들지 않습니다. 첫 지하철 구간의 승차역·하차역 ID와 공식 조회명을 내부 출발 문맥에 복사하고 공식 파일의 내용 해시를 입력 판에 넣습니다. 파일 생성/삭제/내용 교체는 같은 수정시각에서도 다시 적재하게 하며 구성 중 변경은 실패입니다. 출발 관측은 현재 런타임의 연결 결과와 저장 연결이 다르면 재계산을 요구합니다. 저장 직전 판 검사도 현재 파일 내용에 맞는지 확인합니다. 공식 연결이 실제 운행 응답·열차 선택·실시간 출발/환승 완료를 뜻하지 않습니다. 기존 수동 런타임과 버스 문맥은 호환을 유지합니다. [발견 기록](../records/reports/debugs/{debug.name}).
''')
with (scratch / 'subway-binding-work-v1.json').open('x', encoding='utf8') as f: json.dump(state, f, ensure_ascii=False, indent=2)
print(json.dumps({'tag': tag, 'prior_hash_matches': len(hashes) + len(publication['artifact_hashes']), 'backups': len(state['backups'])}, ensure_ascii=False))
