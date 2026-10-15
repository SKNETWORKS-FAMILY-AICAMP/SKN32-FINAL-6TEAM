from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
now = datetime.now().astimezone()
tag = now.strftime('%Y-%m-%d_%H%M') + '_공식지하철_역ID대응'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
prior = cs / 'wiki/records/evidence/2026-10-09_0936_지하철_식별정보_보존'
proof = json.loads((prior / 'verification-proof-v1.json').read_text(encoding='utf8'))
validation = json.loads((prior / 'publication-validation-v1.json').read_text(encoding='utf8'))
for name, digest in [*proof['source_test_data_hashes'].items(), *validation['artifact_hashes'].items()]:
    assert sha(root / name) == digest, name
backups = []
for rel in ['final_project_cs/wiki/teams/mobility.md', 'datasets/mobility/REPORT.md', 'datasets/mobility/README.md']:
    src = root / rel
    dst = src.parent / '_backup' / tag / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(src, dst)
    backups.append({'source': rel, 'backup': dst.relative_to(root).as_posix(), 'sha256': sha(src)})
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'''\n\n## {tag} 공식 실시간 지하철 역ID 대응 자료 계약

서울시 OA-12764의 2026-09-02 공개 역정보 파일을 새 원문으로 보존하고 파일에 있는 SUBWAY_ID·STATN_ID·STATN_NM·호선이름을 추출합니다. ID를 기존 역 코드에 접두사를 붙여 생성하지 않습니다. 중복 ID·동일 노선과 역명 중복·잘못된 타입은 추출 실패로 표시하고 원문을 수정하지 않습니다. 기존 역 좌표와의 대응은 숫자 호선의 선행0만 통일한 노선명+정확 역명으로 검사하며 미대응 원문과 목록을 보존합니다. 동명이역·환승역은 노선으로 구별합니다. 파일 존재를 실시간 제공·열차 선택·출발/환승 연결 완료로 보지 않습니다. 기존 기동 자료 명세를 바꾸거나 추출물을 런타임에 자동 연결하지 않습니다.
''')
state = {'tag': tag, 'created_at': now.isoformat(), 'backups': backups,
         'prior_source_test_data_hashes': proof['source_test_data_hashes']}
(Path(__file__).parent / 'subway-station-map-work-v1.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'tag': tag, 'backups': len(backups), 'prior_matches': 229}, ensure_ascii=False))
