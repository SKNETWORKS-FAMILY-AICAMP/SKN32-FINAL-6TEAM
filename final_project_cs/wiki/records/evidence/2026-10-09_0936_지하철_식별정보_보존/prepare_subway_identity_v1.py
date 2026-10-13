from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
tag = stamp + '_지하철_식별정보_보존'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
prior = cs / 'wiki/records/evidence/2026-10-09_0921_같은최근접역_다른역조합'
proof = json.loads((prior / 'verification-proof-v1.json').read_text(encoding='utf8'))
validation = json.loads((prior / 'publication-validation-v1.json').read_text(encoding='utf8'))
for name, digest in [*proof['source_test_data_hashes'].items(), *validation['artifact_hashes'].items()]:
    assert sha(root / name) == digest, name
backups = []
for rel in ['app/domains/travel_ops/ports/data_sources/seoul_subway.py', 'wiki/teams/mobility.md']:
    src = cs / rel
    dst = src.parent / '_backup' / tag / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(src, dst)
    backups.append({'source': src.relative_to(root).as_posix(), 'backup': dst.relative_to(root).as_posix(), 'sha256': sha(src)})
debug = cs / 'wiki/records/reports/debugs' / (stamp + '_지하철도착_식별정보누락과_숫자변환오류.md')
debug.write_text('''# 지하철 도착정보의 식별정보 누락과 숫자 변환 오류

## 미해결

서울 지하철 도착 소스의 정규화가 승차 역·다음 역·종착역·열차 번호를 버립니다. 공식 명세가 제공하는 식별정보를 잃어 향후 다른 방향 또는 단축 운행 열차를 구별할 근거가 줄어듭니다. 현재 출발 관측은 버스만 연결되어 있어 잘못된 지하철 안내가 실제 전송됐다고 주장하지 않습니다.

위치: app/domains/travel_ops/ports/data_sources/seoul_subway.py:111. `str(seconds).isdigit()` 뒤 `int(seconds)`는 제곱 숫자와 논리값 등에서 실패하거나 오해될 수 있습니다. 통제 응답으로 정규화 결과와 예외를 재현하고 시험 전후 로그를 보존합니다. 운행 중 실제 공급 응답에서 발생한 사례는 아닙니다.

재현: 같은 근거 폴더의 before-v1.run.json 명령으로 신규 시험을 실행합니다. 위험: 향후 열차 선택 근거 손실 또는 도착 조회 실패. 이전 운행 정확도 지표를 바꾸는 증거는 아닙니다.
''', encoding='utf8')
wiki = cs / 'wiki/teams/mobility.md'
with wiki.open('a', encoding='utf8') as f:
    f.write(f'''\n\n## {stamp} 지하철 도착 식별정보 보존 계약

내부 도착 소스 응답 v1.1은 기존 필드를 유지하고 line_id, station_id, previous_station_id, next_station_id, terminal_station_id, terminal_station, train_number, arrival_order를 추가합니다. 원 응답의 문자열 식별정보와 비음수 정수 식별정보를 보존하되 논리값·복합 객체·빈 문자열은 None으로 남기고 임의 ID를 만들지 않습니다. ETA는 비음수 정수 또는 ASCII 숫자 문자열만 받으며 0초는 보존합니다. 잘못된 값은 eta_seconds=None 및 eta_status=invalid로 구분하고 누락은 missing, 정상은 valid로 명시합니다. 도착 정보 전체가 형식에 맞을 때만 기존 열차 목록을 반환하며 잘못된 목록은 소스 실패로 기록합니다. raw 응답·인증키·주소를 추가하지 않습니다. 이번 단위는 열차 선택·실시간 지하철의 출발/환승 시각 적용이 아니며 정확 역ID 대응과 방향·종착·열차 종류 대조는 다음 제품 연결 관문입니다. [발견 기록](../records/reports/debugs/{debug.name}).
''')
state = {'tag': tag, 'created_at': datetime.now().astimezone().isoformat(), 'debug': debug.relative_to(root).as_posix(), 'backups': backups,
         'prior_source_test_data_hashes': proof['source_test_data_hashes'], 'previous_matches': 227}
(Path(__file__).parent / 'subway-identity-work-v1.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'tag': tag, 'backups': len(backups), 'prior_matches': 227}, ensure_ascii=False))
