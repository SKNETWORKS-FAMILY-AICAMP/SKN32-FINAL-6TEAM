import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / 'final_project_cs'
TAG = '2026-10-11_0317_未발행출발_지연복구'.replace('未', '미')
EV = REPO / 'wiki/records/evidence' / TAG
EV.mkdir(parents=True, exist_ok=False)
old = REPO / 'wiki/records/evidence/2026-10-10_2120_출발안내_탑승환승시각_연결/final-integrity-v1.json'
manifest = json.loads(old.read_text(encoding='utf-8'))
hashes = {**manifest['source_test_data_hashes'], **manifest['artifact_hashes']}
bad = [key for key, digest in hashes.items() if hashlib.sha256((ROOT / key).read_bytes()).hexdigest() != digest]
assert not bad, bad
backups = []
for rel in ('app/domains/travel_ops/components/watch/trip_reminders.py', 'wiki/teams/mobility.md'):
    source = REPO / rel
    dest = source.parent / '_backup' / TAG / source.name
    dest.parent.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source, dest)
    backups.append({'original': source.relative_to(ROOT).as_posix(), 'backup': dest.relative_to(ROOT).as_posix(),
                    'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    if rel.endswith('.py'):
        legacy = REPO / 'legacy' / TAG / rel
        legacy.parent.mkdir(parents=True, exist_ok=False)
        shutil.copy2(source, legacy)
        backups.append({'original': source.relative_to(ROOT).as_posix(), 'backup': legacy.relative_to(ROOT).as_posix(),
                        'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
(EV / 'baseline-v1.json').write_text(json.dumps({'checked': len(hashes), 'hashes': hashes, 'mismatches': bad,
    'backups': backups, 'limited_api_calls': 0, 'shared_usage': 'unconfirmed', 'daily_remaining': 'unconfirmed',
    'reset_at': 'unconfirmed', 'reservation': 'not_attempted_no_api_call'}, ensure_ascii=False, indent=2), encoding='utf-8')
debug = REPO / 'wiki/records/reports/debugs' / (TAG + '.md')
debug.write_text('''# 未発行の出発案内が予定移動終了後に欠落する問題
## 미해결

출발 안내가 발행되지 않은 이동은 감시 기능에서 다음 방문 시작 전까지 선택되지만, 안내 기능은 저장된 이동 종료 시각에 창을 닫습니다. 현재 시각 재검증으로 아직 도착 가능한 경우에도 안내가 누락될 수 있습니다.

- 위치: `app/domains/travel_ops/components/watch/trip_reminders.py`의 `plan_reminders`, `TripReminders.tick`.
- 비교: `TripStore.pending_departures`는 다음 방문 시작을 종료 경계로 씁니다.
- 재현: 신규 `tests/unit/travel/test_late_departure_notice_v1.py` 실행 로그를 같은 이름 evidence에 보존합니다.
- 고객 영향: 첫 안내 조회 실패 뒤 복구됐어도 출발 안내를 받지 못할 수 있습니다. 실제 고객 사고 측정은 아닙니다.
- 적용: 현재 재검증기가 연결된 안내만 다음 방문까지 재시도합니다. 이미 발행한 항목은 기존 사전 확인과 UNIQUE를 유지합니다. 실제 위치/탑승을 추정하지 않습니다.
- 이전 186/186은 기존 시험 범위에서 유효하며 이번 누락 창을 검증하지 않았습니다.
'''.replace('未発行の出発案内が予定移動終了後に欠落する問題', '미발행 출발 안내가 예정 이동 종료 후 누락되는 문제'), encoding='utf-8')
wiki = REPO / 'wiki/teams/mobility.md'
with wiki.open('a', encoding='utf-8') as f:
    f.write('''

## 2026-10-11 미발행 출발 안내 재시도 창 계약

현재 출발 재검증기가 연결된 TripReminders는 plan_reminders의 선택 인자 revalidate_departures=True를 사용합니다. 안내 후보 창은 계획 출발 시각 이상부터 순서상 다음 비이동 일정의 시작 시각 미만까지입니다. 다음 일정은 날짜 경계를 넘어 전체 항목의 seq 순서로 찾습니다. 저장된 이동 종료가 지났다는 이유만으로 미발행 안내를 제외하지 않습니다. 후보 선택은 발행 허가가 아니며, 이미 발행한 키는 외부 조회 전 제외하고 현재 경로/여유/마감 재검증에서 성공한 안내만 기존 저장 경합 검사와 UNIQUE를 거쳐 발행합니다. 재검증기가 없으면 기존 이동 종료 창을 유지합니다. 다음 일정이 없거나 마감이 지났으면 확장 후보에서 제외합니다. 여행 재난 정지·현재 동행·근거 변경 검사는 유지하며 실제 위치/탑승 상태를 추정하지 않습니다.
''')
shutil.copy2(__file__, EV / Path(__file__).name)
print(json.dumps({'baseline_match': len(hashes), 'backups': len(backups), 'evidence': str(EV)}, ensure_ascii=False))
