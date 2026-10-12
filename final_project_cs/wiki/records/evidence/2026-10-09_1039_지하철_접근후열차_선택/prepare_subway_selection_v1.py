from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
previous = cs / 'wiki/records/evidence/2026-10-09_1023_계획지하철_공식ID연결'
proof = json.loads((previous / 'verification-proof-v1.json').read_text(encoding='utf8'))
publication = json.loads((previous / 'publication-validation-v1.json').read_text(encoding='utf8'))
hashes = {**proof['source_test_data_hashes'], **publication['artifact_hashes']}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
changed = [rel for rel, digest in hashes.items() if sha(root / rel) != digest]
assert not changed, changed
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
tag = stamp + '_지하철_접근후열차_선택'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
source = cs / 'app/domains/travel_ops/ports/data_sources/seoul_subway.py'
backup = source.parent / '_backup' / tag / source.name
backup.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(source, backup)
state = {'tag': tag, 'prior_source_test_data_hashes': proof['source_test_data_hashes'],
         'backups': [{'source': source.relative_to(root).as_posix(), 'backup': backup.relative_to(root).as_posix(),
                      'sha256': sha(source)}], 'preflight_hash_matches': len(hashes)}
with (ev / 'preflight-v1.json').open('x', encoding='utf8') as f: json.dump(state, f, ensure_ascii=False, indent=2)
with (Path(__file__).parent / 'subway-selection-work-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
debug = cs / 'wiki/records/reports/debugs' / (tag + '.md')
with debug.open('x', encoding='utf8') as f:
    f.write('# 지하철 접근 이후 열차 선택 미연결\n\n## 미해결\n\n'
            '발견 위치: app/domains/travel_ops/ports/data_sources/seoul_subway.py:144 arrivals. '
            '정규화는 있으나 접근 이후 열차 선택과 recptnDt 기준 도착시각 계산을 제공하지 않습니다. '
            '현재 제품은 시간표 모델만 쓰며 실시간 지하철을 소비한다고 보고하면 안 됩니다.\n\n'
            '이번 최소 단위는 공식 호선/역/다음역/종착역과 명시된 일반열차 경로를 대조하는 선택기 및 소스 어댑터입니다. '
            '제품 출발/환승 시간 대체, 급행·순환선의 실시간 연결은 후속 단위입니다. '
            '회귀 재현 명령과 전후 출력은 같은 이름의 evidence 폴더에 보존합니다. '
            '실제 ETA 정확도와 탑승 가능성은 이 시험으로 보장하지 않습니다.\n')
print(json.dumps({'tag': tag, 'hash_matches': len(hashes), 'backups': 1}, ensure_ascii=False))
