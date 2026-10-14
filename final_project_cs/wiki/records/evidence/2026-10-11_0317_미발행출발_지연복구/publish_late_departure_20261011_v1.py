from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from copy import deepcopy
import difflib
import hashlib
import html
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'final_project_cs'
TAG = '2026-10-11_0317_미발행출발_지연복구'
EV = CS / 'wiki/records/evidence' / TAG
REPORT = CS / 'wiki/records/reports' / (TAG + '.md')
ASSETS = CS / 'wiki/records/reports/assets/2026-10-11_mobility_readiness_v55'
ASSETS.mkdir(parents=True, exist_ok=False)
now = datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
baseline = json.loads((EV/'baseline-v1.json').read_text(encoding='utf-8'))
code = CS/'app/domains/travel_ops/components/watch/trip_reminders.py'
old = code.parent/'_backup'/TAG/code.name
patch = ''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),
    code.read_text(encoding='utf-8').splitlines(True), fromfile='before/trip_reminders.py', tofile='after/trip_reminders.py'))
(EV/'code-change-v1.patch').write_text(patch, encoding='utf-8')
commands = [
    ('legacy-window-v1', [sys.executable, '-m', 'pytest', '-q',
        'tests/scenario/test_trip_reminders.py::test_windows_follow_the_first_item_and_each_move',
        '--basetemp='+str(ROOT/'.tmp/mobility_complete_20261008/pytest_late_legacy'),
        '--junitxml='+str(EV/'legacy-window-v1.xml')]),
    ('lint-v1', [sys.executable, '-m', 'ruff', 'check',
        'app/domains/travel_ops/components/watch/trip_reminders.py',
        'tests/unit/travel/test_late_departure_notice_v1.py'])]
for name, cmd in commands:
    result = subprocess.run(cmd, cwd=CS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**__import__('os').environ, 'PYTHONIOENCODING':'utf-8'})
    with (EV/(name+'.log')).open('xb') as f: f.write(result.stdout)
    with (EV/(name+'-run.json')).open('x', encoding='utf-8') as f:
        json.dump({'command':cmd, 'returncode': result.returncode}, f, indent=2)
    assert result.returncode == 0, (name, result.stdout)
suite = ET.parse(EV/'after-all-v2.xml').getroot().find('testsuite')
assert suite.attrib['tests']=='204' and suite.attrib['failures']=='0' and suite.attrib['errors']=='0'
replay = json.loads((EV/'stored-seoul-late-replay-v1.json').read_text(encoding='utf-8'))
catalog = json.loads((CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v54/readiness-catalog.json').read_text(encoding='utf-8'))
assert len(catalog['features']) == 21
catalog['created_at'] = now
catalog['scope'] = 'ローカル'.replace('ローカル', '로컬') + ' 미발행 출발 안내 지연 복구. 전체 완료/배포/실탑승 확인 아님.'
catalog['latest_validation'] = {'new_tests':18, 'existing_tests':186, 'legacy_window':1,
    'stored_seoul_pair':1, 'limited_api_calls':0, 'independent_accuracy_samples':0}
(ASSETS/'readiness-catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
source_assessment = {'checked_at':now, 'limited_api_calls':0,
    'before': {'shared_usage':'unconfirmed', 'remaining':'unconfirmed', 'reset_at':'unconfirmed'},
    'after': {'shared_usage':'unconfirmed', 'remaining':'unconfirmed', 'reset_at':'unconfirmed'},
    'reservation':'not_acquired_no_limited_API_called', 'reserve_fraction':0.2,
    'network_connection_attempts_replay':replay['blocked_connections'],
    'public_document':'https://gtfs.org/documentation/realtime/feed-entities/trip-updates/',
    'application':'실시간 갱신 누락을 정시/실제 도착으로 단정하지 않는 원칙만 확인. GTFS 변환/지연 전파 구현 아님.',
    'overlap_check':'Python 명령 이름 필터 읽기 전용 조회에서 일치 행 미검출. 다른 이름 작업은 범위 밖.',
    'deployed':False, 'full_completion':False}
(EV/'source-assessment-v1.json').write_text(json.dumps(source_assessment, ensure_ascii=False, indent=2), encoding='utf-8')
debug = CS/'wiki/records/reports/debugs'/(TAG+'.md')
debug_backup = debug.parent/'_backup'/TAG/debug.name
debug_backup.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(debug, debug_backup)
debug.write_text(debug.read_text(encoding='utf-8').replace('## 미해결',
    '## 해결됨 (2026-10-11)\n\n신규18/18·기존186/186·기존 시나리오 창1/1·보유 서울 구간1/1 재생으로 로컬 복구를 확인했습니다. 배포/실탑승 확인은 하지 않았습니다. 현재 경로 재검증을 연결한 안내만 다음 방문 전까지 재시도하며, 이미 발행한 항목은 조회 전에 제외합니다.\n'), encoding='utf-8')
report = '''# 미발행 출발 안내의 지연 복구

예정 이동 종료를 지났어도 다음 일정에 도착할 수 있으면, 현재 경로를 다시 검증해 첫 출발 안내를 발행하도록 수정했습니다. 이미 안내한 이동은 외부 조회 전에 제외합니다. 로컬 수정이며 전체 실사용 완료나 배포 완료가 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 신규 지연 복구 조건 | 통과 | 18/18 = 100% |
| 기존 관련 조건 | 통과 | 186/186 = 100% |
| 기존 안내 창 시나리오 | 통과 | 1/1 = 100% |
| 서울 보유 응답 고정 구간 | 통과 | 1/1 = 100% |
| 전체 기능 상태 분류 | 집계 | 21/21 = 100% |

전체 기능은 조건부 사용3·개선 필요9·추가 검증9입니다. 마지막 행은 분류 개수이며 완료율이 아닙니다. 이번 분모는 실행한 회귀 조건/시나리오/개발 고정 구간 수입니다. 실제 탑승·현재 운행·결제·새 독립 정확도 표본은 0건입니다.

## 달라진 행동과 원인

예를 들어 계획 이동이10:01에 끝나도록 저장됐지만 첫 조회가 실패했고10:02에 복구됐다면, 이전 안내 기능은 후보에서 이미 제외했습니다. 감시 기능은 다음 방문10:30 전까지 같은 이동을 계속 확인했으므로 두 기능의 창이 달랐습니다. 이제 현재 재검증기가 연결된 경우에만 다음 방문 전까지 후보로 두고, 도착 가능성·여유·경로·현재 동행을 다시 확인한 결과로 안내합니다. 너무 늦으면 보류하며 실패 응답을 과거 안내로 바꾸지 않습니다.

다음 방문은 전체 항목의 순서에서 찾아 자정을 넘겨도 연결합니다. 재검증이 없는 기존 동작은 이동 종료 창을 유지합니다. 다음 방문이 없거나 시작 시각이 지났으면 확장 후보에서 제외합니다. 저장 일정 원본·중복 키·저장 전후 근거 검사·저장 경합 검사는 유지했습니다. 실제 현재 위치/탑승을 받는 기능을 추가한 것은 아닙니다.

## 실행 근거와 제한

수정 전18실패에는 새 선택 인자가 없는 계약 실패와 실제 발행 누락 재현이 함께 포함됩니다. 수정 후 첫 실행은13통과·5실패였습니다. 시험 입력의 동행1명과 저장 경로의 동행 정보없음이 달라 재검증기가 정확히 보류했고, 자정에는 하루 시작 안내도 후보가 되어 시험 연결의 DB 대역에 없는 메서드를 요구했습니다. 시험을 동일 동행 입력으로 맞추고 하루 변경 건수 조회를 통제하여18/18을 확인했습니다. 제품의 동행 검사를 완화하지 않았습니다.

기존 관련 시험 첫 실행은201통과·3준비오류였습니다. 기본 pytest 임시 경로 쓰기가 실패하여 작업 폴더 안의 새로운 전용 임시 경로를 지정한 뒤204/204가 통과했습니다. 기존 시나리오 창1/1도 별도 통과했습니다. Ruff2파일 통과입니다. pytest 종료 후 pyreadline3 소멸자 경고는 남았으며 최종 pytest 종료코드0·실패0·오류0입니다.

보유 서울 응답을 실제 이전 수신 종료 시각2026-10-09 12:55:19.344356+09:00으로 재생했습니다. 저장 이동 종료를 그1분 전으로 둔 개발 조건에서, 실제 구성기→팀 연결→현재 경로 검증→출발 안내→메모리 발행 대역까지 연결했습니다. 첫 발행1회·다음 반복 중복 제외1회·보유 응답 읽기1회·네트워크 시도0회입니다. 12:56 출발,12:59 공덕 승차(원 예측12:59:26),13:15 종로3가 환승 예상,13:19 최종 도착 예상이 포함됩니다. 임의로 고정한 노선/접근도보를 사용하는 개발 재생이며 추천 경로·좌표 출입점 정렬·독립 정확도 검증이 아닙니다. 원 응답/생성시각은 바꾸지 않았습니다. 실제 DB 저장 및 바깥 메시지 배달은 하지 않았습니다.

mock 서버 시험(화면 반응): 안 했음. 위 시험은 Python 통제 입력과 메모리 발행 대역입니다.

실서버 확인(서버 응답): 안 했음 — cs 프로젝트 서버 HTTP 요청·운영 배포를 하지 않았습니다.

[GTFS 공식 Trip Updates](https://gtfs.org/documentation/realtime/feed-entities/trip-updates/)는 실시간 갱신이 없다고 정시 운행을 가정하지 않도록 설명합니다. 관측과 시간표 예상의 구분 전제만 재확인했습니다. 서울 응답을 GTFS로 간주하거나 다른 환승 열차에 지연을 일괄 전파하지 않았습니다. 알고리즘 변경이나 논문 성능 주장은 추가하지 않았습니다.

## 파일·백업·남은 작업

제품 변경은 [출발 안내 계산/반복](../../../app/domains/travel_ops/components/watch/trip_reminders.py), 새 검증은 [지연 복구 시험](../../../tests/unit/travel/test_late_departure_notice_v1.py)입니다. 선택 인자 계약은 wiki에 코드보다 먼저 적었습니다. [코드 변경 비교](../evidence/TAG/code-change-v1.patch)·[최종204건 로그](../evidence/TAG/after-all-v2.log)·[기존 창 로그](../evidence/TAG/legacy-window-v1.log)·[서울 재생 원문](../evidence/TAG/stored-seoul-late-replay-v1.json)·[결함 기록](debugs/TAG.md)을 보존했습니다. 실패 실행 로그와 각 실행 명령도 같은 검증 폴더에 있습니다.

[출발 안내 원본 백업](../../../app/domains/travel_ops/components/watch/_backup/TAG/trip_reminders.py)·[wiki 원본 백업](../../teams/_backup/TAG/mobility.md)·[legacy 원본](../../../legacy/TAG/app/)을 수정 전에 복사했습니다. 시험 입력·실행기·결함 기록·최종 wiki 갱신 전 판도 각각 백업했습니다. 이전461해시 중 이번 허용수정2파일 외459/459가 일치합니다. 다른 이름으로 실행되는 작업은 확인 범위 밖이므로 모든 작업자 부재를 단정하지 않습니다.

제한 API 추가 호출0회입니다. 공급자/프로젝트/키별 공유 누적량·잔여량·갱신 시각은 조회 전후 미확인입니다. 원자 예산을 확보할 수 없어 해당 API를 호출하지 않았습니다. 일일20% 예비 규칙·월 비용 상한·운영 설정·예약 주기·알림 정책을 변경하지 않았습니다. 커밋·푸시·배포·외부 메시지·결제는 하지 않았습니다.

남은 일은 실제 위치/탑승 상태를 받은 여행 중 재탐색, 급행/순환선·대체 소스·막차 범위, 운임 누락과 새 도보 웹 대조입니다. 이번에 완료한 것은 첫 안내의 누락 창 복구이며 전체21개 기능은 미완료입니다. [상태 시각화v55](assets/2026-10-11_mobility_readiness_v55/mobility-readiness.html)·[해시 근거](../evidence/TAG/final-integrity-v1.json).
'''.replace('TAG', TAG)
with REPORT.open('x', encoding='utf-8') as f: f.write(report)
rows = ''.join('<tr><td>'+html.escape(f['name'])+'</td><td>'+html.escape(f['status'])+'</td><td>'+html.escape(f['need'])+'</td></tr>' for f in catalog['features'])
visual = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>이동 기능 검증 v55</title><style>body{font:16px/1.6 system-ui;max-width:1050px;margin:32px auto;padding:0 16px;color:#192e3b;background:#f7f9fa}h1{font-size:26px}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #d5dfe3}pre{white-space:pre-wrap;background:#e9f0f4;padding:18px}a{color:#065e9c}</style><h1>늦어진 첫 출발 안내 복구</h1><p>신규18/18 · 기존186/186 · 기존 안내 창1/1 · 서울 보유 응답1/1. 로컬 검증이며 현재 운행·실탑승·배포 확인이 아닙니다.</p><p>조건부 사용3 · 개선 필요9 · 추가 검증9. 전체 완료율이 아닙니다.</p><table><tr><th>상황</th><th>이전</th><th>수정 후</th></tr><tr><td>이동 종료 후 첫 안내 복구</td><td>후보 제외</td><td>다음 방문 전까지 현재 경로 재검증</td></tr><tr><td>도착 불가·조회 실패</td><td>후보 제외로 드러나지 않음</td><td>보류·치명 결과 표시, 안내 미발행</td></tr><tr><td>이미 안내한 이동</td><td>중복 제외</td><td>외부 조회 전 중복 제외 유지</td></tr></table><h2>이전 서울 응답 재생 결과</h2><pre>NOTICE</pre><p><a href="../../TAG.md">작업 보고서</a> · <a href="../../../evidence/TAG/after-all-v2.log">204건 로그</a> · <a href="../../../evidence/TAG/stored-seoul-late-replay-v1.json">재생 근거</a></p><h2>전체21개 기능</h2><table><tr><th>기능</th><th>분류</th><th>남은 근거</th></tr>ROWS</table></html>'''.replace('NOTICE',html.escape(replay['payload']['text'])).replace('TAG',TAG).replace('ROWS',rows)
(ASSETS/'mobility-readiness.html').write_text(visual, encoding='utf-8')
wiki = CS/'wiki/teams/mobility.md'
wb = wiki.parent/'_backup'/(TAG+'_결과발행전')/wiki.name
wb.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(wiki, wb)
with wiki.open('a', encoding='utf-8') as f:
    f.write(f'\n\n## 2026-10-11 미발행 출발 안내 지연 복구 결과\n\n예정 이동 종료 뒤 첫 안내가 누락되던 창을 현재 재검증 연결 시 다음 방문 전까지 복구했습니다. 신규18/18·기존186/186·기존 창1/1·보유서울1쌍(첫발행1·중복제외1)·Ruff2파일. 다음 방문 날짜 경계/도착불가/실패후복구/중복/저장근거 검사 포함. 제한API0·실탑승/현재운행/DB저장/배포확인0·21분류3/9/9유지·전체미완료. [보고서](../records/reports/{TAG}.md)·[시각화v55](../records/reports/assets/2026-10-11_mobility_readiness_v55/mobility-readiness.html)·[검증](../records/evidence/{TAG}/).\n')
shutil.copy2(__file__, EV/Path(__file__).name)
allowed = [code.relative_to(ROOT).as_posix(), wiki.relative_to(ROOT).as_posix()]
preserved = [p for p,d in baseline['hashes'].items() if p not in allowed and hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==d]
assert len(preserved)==459
hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in baseline['hashes']}
for p in [*EV.iterdir(), *ASSETS.iterdir(), REPORT, debug, CS/'tests/unit/travel/test_late_departure_notice_v1.py']:
    if p.is_file(): hashes[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
backups = deepcopy(baseline['backups'])
extra = [debug_backup, wb,
 CS/'tests/unit/travel/_backup/2026-10-11_0320_시험입력정정/test_late_departure_notice_v1.py',
 ROOT/'.tmp/mobility_complete_20261008/_backup/2026-10-11_0320_시험입력정정/run_late_departure_20261011_v1.py',
 ROOT/'.tmp/mobility_complete_20261008/_backup/2026-10-11_0323_pytest임시경로/run_late_departure_20261011_v1.py']
for p in extra:
    backups.append({'backup':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
manifest = {'created_at':now, 'source_test_data_hashes':hashes, 'artifact_hashes':{}, 'backups':backups,
    'allowed_changes':allowed, 'unchanged_baseline_files':len(preserved), 'full_feature_completion':False,'deployed':False}
with (EV/'final-integrity-v1.json').open('x', encoding='utf-8') as f:
    json.dump(manifest,f,ensure_ascii=False,indent=2)
print(json.dumps({'hashes':len(hashes),'preserved_baseline':len(preserved),'backups':len(backups),'tests':204,'legacy':1},ensure_ascii=False))
