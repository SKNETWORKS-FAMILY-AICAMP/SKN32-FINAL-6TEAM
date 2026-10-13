from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
now = datetime.now().astimezone()
tag = now.strftime('%Y-%m-%d_%H%M') + '_지하철응답_빈값오인'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
prior = cs / 'wiki/records/evidence/2026-10-09_0952_공식지하철_역ID대응'
proof = json.loads((prior / 'verification-proof-v1.json').read_text(encoding='utf8'))
hashes = proof['source_test_data_hashes']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for rel, digest in hashes.items():
    assert sha(root / rel) == digest, rel
state = {'tag': tag, 'created_at': now.isoformat(), 'prior_source_test_data_hashes': hashes, 'backups': []}
for rel in ['app/domains/travel_ops/ports/data_sources/seoul_subway.py', 'wiki/teams/mobility.md',
            'tests/unit/travel/test_subway_identity_v1.py']:
    src = cs / rel
    dst = src.parent / '_backup' / tag / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(src, dst)
    state['backups'].append({'source': src.relative_to(root).as_posix(),
                             'backup': dst.relative_to(root).as_posix(), 'sha256': sha(src)})
debug = cs / 'wiki/records/reports/debugs' / (tag + '.md')
with debug.open('x', encoding='utf8') as f:
    f.write('''# 지하철 도착 목록 누락을 빈 결과로 오인

## 미해결

위치: app/domains/travel_ops/ports/data_sources/seoul_subway.py의 arrivals에서 realtimeArrivalList가 None이면 []로 바꿉니다. _body_error는 공식 INFO-200 여부와 목록 존재를 함께 검사하지 않습니다. 그래서 HTTP200의 {}·INFO-000이지만 목록이 없는 응답·명시 null을 열차가 없는 정상 결과로 반환합니다. 잘못된 목록도 공통 _fetch_json이 먼저 성공 응답으로 보관하므로, 공급자가 회복해도 보관 기간 동안 재사용할 수 있습니다.

서울시 공식 문서는 INFO-000=정상 처리, INFO-200=해당 데이터 없음으로 구분합니다. 재현은 새 통제 HTTP 응답 시험과 실제 ResponseCache를 이용하며 공개 arrivals를 두 번 부릅니다. 명령·원문 출력은 같은 이름의 evidence 폴더에 보존합니다. 실제 서울시 장애 응답을 관측한 횟수가 아니며 실제 열차 선택·출발/환승 적용은 아직 연결되지 않았습니다. 고객 위험은 소스 실패와 실제 열차 없음의 혼동 및 회복된 응답을 읽지 못하는 것입니다. 기존 웹 오차 수치를 바꾸는 근거는 아닙니다.
''')
state['debug'] = debug.relative_to(root).as_posix()
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'''\n\n## {tag} 지하철 정상 빈 결과와 응답 오류 구분 계약

공식 INFO-200만 목록 누락·null을 정상 빈 결과로 인정합니다. 명시적 빈 목록은 기존 호환을 유지합니다. INFO-200과 비어 있지 않은 목록이 함께 온 모순, 다른 응답의 목록 누락·null, 목록이 아닌 값과 dict가 아닌 행은 소스 실패입니다. 신규 HTTP 응답은 보관 전에 검사하고 body_error로 호출 실패를 셉니다. 기존 보관 응답도 공개 arrivals에서 재검사하지만 외부 호출 없이 읽은 오류를 제공처 호출 실패로 세지 않으며 malformed_arrivals로 구분합니다. 반환 성공 형식 v1.1·0초 ETA·식별정보·INFO-200 재사용은 유지합니다. 응답 실패를 실제 열차 없음으로 바꾸지 않습니다. 실시간 열차 선택과 출발/환승 적용은 이 단위의 완료 범위가 아닙니다. [발견 기록](../records/reports/debugs/{debug.name}).
''')
with (scratch / 'subway-envelope-work-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(json.dumps({'tag': tag, 'baseline_hashes': len(hashes), 'backups': len(state['backups'])}, ensure_ascii=False))
