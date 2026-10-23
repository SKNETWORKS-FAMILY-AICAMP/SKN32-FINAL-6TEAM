"""공통 실패 접합의 실행 근거를 보존하고 통합 상태만 갱신한다."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
run = BASE / sys.argv[1]
meta = json.loads((run / 'run.json').read_text(encoding='utf-8'))
cases = list(ET.parse(run / 'junit.xml').getroot().iter('testcase'))
counts = {'total': len(cases), 'failed': sum(c.find('failure') is not None for c in cases),
          'errors': sum(c.find('error') is not None for c in cases),
          'skipped': sum(c.find('skipped') is not None for c in cases)}
counts['passed'] = counts['total'] - counts['failed'] - counts['errors'] - counts['skipped']
assert counts == {'total': 228, 'failed': 0, 'errors': 0, 'skipped': 0, 'passed': 228}
assert meta['returncode'] == 0 and not meta['changed_during_run'] and not meta['blocked_connections']
now = datetime.now(timezone(timedelta(hours=9)))
stamp = now.strftime('%Y-%m-%d_%H%M%S_%f')
backup = BASE / '_backup' / (stamp + '_common_fix_review')
backup.mkdir(parents=True)
for name in ('integration-table.json', 'integration-table.md', 'report.md', 'status.json'):
    shutil.copy2(BASE / name, backup / name)
legacy_before = json.loads((BASE / 'checks/debug-report-sources-before-2026-10-12.json').read_text(encoding='utf-8'))
legacy_changed = [x['path'] for x in legacy_before['files'] if hashlib.sha256((ROOT / x['path']).read_bytes()).hexdigest() != x['sha256']]
assert not legacy_changed
record = ROOT / 'final_project_cs/wiki/records/reports' / (now.strftime('%Y-%m-%d_%H%M') + '_common-integration-validation.md')
assert not record.exists()


def link(path):
    return Path(os.path.relpath(ROOT / path, record.parent)).as_posix()


run_path = run.relative_to(ROOT).as_posix()
summary = {'recorded_at_kst': now.isoformat(), 'counts': counts, 'run': run_path,
           'original_reports': {'total': len(legacy_before['files']), 'changed': legacy_changed},
           'unverified_annotations': 18, 'source_count': len(meta['source_before']),
           'scope': '선택한 3개 시험 파일. 전체 common/travel 통과 판정 아님',
           'sandbox_attempts': [{'result': 'interrupted_before_completion', 'junit_written': False},
                                {'result': 'interrupted_in_event_loop_setup',
                                 'observed_stack': 'socket.accept -> _fallback_socketpair -> asyncio.ProactorEventLoop -> pytest_asyncio event_loop fixture'}],
           'permissions': '검증 실행기만 자동 승인 검토를 거쳐 확장 실행. 외부/기존 앱 연결·업무 DB 차단, 시험이 바인딩한 루프백만 허용',
           'deployment': 'not_deployed'}
(run / 'integration-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
record.write_text(f'''# 공통 검사 실패 접합 결과 — {now.isoformat()}

과거 보고서 상태 검사와 원격 작업 취소 시험을 보완하고 관련 시험 228개를 통과했습니다. 제품 코드의 마감·취소 정책은 바꾸지 않았고, 과거 결함 18개를 해결로 표시하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 관련 회귀 시험 | 통과 | 228/228 = 100% |
| 원본 보고서 보존 대조 | 동일 | 167/167 = 100% |
| 실행 전후 관련 파일 | 동일 | 172/172 = 100% |
| 전체 여행·최종 관문 | 담당 결과 대기 | 분모 미확정 |

## 문제와 수정

1. 기존 상태 검사는 보고서 전체에서 해결·미해결 제목을 찾아 둘 다 있으면 실패했습니다. 18개에는 발견·후속 상태가 공존하거나 다른 제목을 쓴 사례가 있었습니다. 원문을 다시 쓰지 않고 [현황 주석]({link('final_project_cs/wiki/quality/debug-report-current-status.json')})과 [표시 규칙]({link('final_project_cs/wiki/quality/debug-report-status.md')})을 추가했습니다. 현재 코드·적용 환경의 해결 여부를 새로 검증하지 않아 모두 `unverified`입니다. 새 보고서 누락, 상충 표기, 중복 참조, 원문 해시 변화, 근거 없는 해결 승격을 차단하는 회귀도 추가했습니다.
2. 30ms 취소 시험은 설정 읽기와 동기 조회 스레드 준비도 마감 안에 포함해 원격 작업을 제출하기 전에 끝났습니다. 실행기 준비 뒤 마감을 정하고 즉시 끝나는 비동기 조회를 사용했습니다. 실제 poll 진입·0.5초 이내 반환·정확한 원격 작업 취소를 모두 확인합니다. 제출 전 이미 마감된 경우에는 제출·취소 모두 하지 않는 반대 경계도 추가했습니다. 기존 동기 조회·응답성·취소 예산 시험은 유지했습니다.
3. [품질 입구]({link('final_project_cs/wiki/quality/index.md')})의 옛 61개 요약·29항목 안내와 쇼핑몰 실행 명령을 현재 불변식 자동 집계·여행 평가·시험 지도로 연결했습니다. 해당 수치를 새 통과 수로 바꾸지 않았으며 기존 문서는 백업했습니다.

## 실제 실행과 제한

[최종 실행 원본]({link(run_path + '/run.json')})과 [JUnit]({link(run_path + '/junit.xml')})에 KST 시작·종료, 명령, 228통과·0실패·0오류·0건너뜀, 관련 파일 해시를 보존했습니다. 선택한 파일은 문서 상태 검사, Team 포트, 플러그인 가용성 세 개입니다. 전체 공통·여행 시험을 다시 통과했다고 일반화하지 않습니다.

초기 두 실행은 Windows 내부 소켓 쌍을 만드는 event_loop fixture에서 정체돼 직접 중단했습니다. JUnit 완료본이 없어 통과 수에 더하지 않습니다. 두 번째 실행의 faulthandler 출력에서 `socket.accept` → `_fallback_socketpair` → `ProactorEventLoop` → pytest_asyncio fixture를 직접 확인했습니다. 이후 [제한 검증 실행기]({link('program/research/baseline_completion_2026-10-12/tasks/integration/run_common_fix_checks.py')})를 자동 승인 검토를 거쳐 확장 실행했습니다. 외부 통신·이미 떠 있는 로컬 앱 연결·업무 DB를 막고 시험이 직접 바인딩한 루프백만 허용했습니다. 차단된 접속 시도는 0개입니다.

검사 대상 167개 과거 보고서는 변경 전 SHA-256과 모두 일치합니다. 18개 현황 주석은 기계 판독 상태를 명확히 한 것이며 해당 결함의 현재 해결·배포·실사용 품질을 증명하지 않습니다. 앞 중간 표의 실행 분모 227은 최종 수집 228로 정정합니다.

mock 서버 시험(화면 반응): 안 했음. 주입된 A2A transport와 파일 검사를 실행했습니다.

실서버 확인(서버 응답): 안 했음. 업무 DB·cs 프로젝트 서버·유료 모델·외부 API를 호출하지 않았습니다.

## 변경·백업·후속 작업

변경한 시험은 [상태 검사]({link('final_project_cs/tests/unit/core/test_debug_report_status.py')})와 [Team 포트 시험]({link('final_project_cs/tests/unit/ports/test_team_ports.py')})입니다. 제품 `A2ATeamExecutor`는 변경하지 않았습니다. 문서 상태는 draft로 유지하고 독립 사용자 검토·운영 반영을 주장하지 않습니다.

[시험 변경 전 사본]({link('final_project_cs/tests/_backup/2026-10-12_0437_integration_common_failures/')})·[품질 문서 변경 전 사본]({link('final_project_cs/wiki/quality/_backup/2026-10-12_0440_integration_status/')})·[통합표 변경 전 사본]({link(backup.relative_to(ROOT).as_posix() + '/')})을 보존했습니다. 다른 담당의 status·공용 coordination은 수정하지 않았습니다.

공통 전체 시험은 새 시험·주석 파일을 포함한 최종 소스로 다시 확인해야 합니다. 여행 전체 실행과 인증·실행 계획·운영 접합 결과도 아직 통합 대기입니다. 이 기록으로 v12·최종 기준선 완료를 선언하지 않습니다.
''', encoding='utf-8')
table = json.loads((BASE / 'integration-table.json').read_text(encoding='utf-8'))
for row in table['rows']:
    if row['id'] in ('W10', 'W13', 'W20', 'W22', 'W23', 'W25'):
        row['integration_findings'].append({'id': 'INT-COMMON-001', 'scope': '공통 실패 19건의 검사·시험 접합 및 현재 품질 입구',
            'result': 'focused_pass_full_suite_pending', 'evidence': record.relative_to(ROOT).as_posix(), 'unverified_defects': 18})
table['last_review_at_kst'] = now.isoformat()
(BASE / 'integration-table.json').write_text(json.dumps(table, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
rel_record = Path(os.path.relpath(record, BASE)).as_posix()
for name in ('report.md', 'integration-table.md'):
    text = (BASE / name).read_text(encoding='utf-8')
    text += f'\n\n## 공통 실패 접합 — {now.isoformat()}\n\n[실행 결과와 한계]({rel_record}): 관련 시험 228/228 통과, 과거 보고서 167/167 보존, 실행 전후 관련 파일 172/172 동일. 현황 주석의 18개 결함은 unverified이며 전체 공통·여행 재검증은 대기입니다.\n'
    (BASE / name).write_text(text, encoding='utf-8')
status = json.loads((BASE / 'status.json').read_text(encoding='utf-8'))
status.update(updated_at_kst=now.isoformat(), phase='waiting_dependency', backup=backup.relative_to(ROOT).as_posix(),
              latest_review_report=record.relative_to(ROOT).as_posix())
status['tests'].append({'command': meta['command'], **counts, 'evidence': run_path + '/integration-summary.json'})
status['unresolved'] = [x for x in status['unresolved'] if '공통 시험 실패 19건' not in x]
status['unresolved'].append('공통 검사 실패 접합의 관련 228건 통과. 전체 common·travel 최종 재실행 대기; 과거 결함 18건 현재 해결 여부 unverified')
status['dependencies_remaining'] = []
for key in ('auth', 'orchestration', 'operations', 'wiki', 'verification'):
    p = BASE.parent / key / 'status.json'
    phase = json.loads(p.read_text(encoding='utf-8-sig')).get('phase') if p.exists() else 'status_not_written'
    status['dependencies_remaining'].append(key + ': ' + phase)
status['dependencies_remaining'].append('existing: 관련 결과의 현재 코드·원본 실행 증거 검토')
new_paths = [p.relative_to(ROOT).as_posix() for p in [Path(__file__), BASE/'run_common_fix_checks.py', record, run/'integration-summary.json']]
new_paths += ['final_project_cs/' + p for p in ['tests/unit/core/test_debug_report_status.py', 'tests/unit/ports/test_team_ports.py',
              'wiki/quality/index.md', 'wiki/quality/test-map.md', 'wiki/quality/debug-report-status.md', 'wiki/quality/debug-report-current-status.json']]
status['changed_files'] = sorted(set(status['changed_files'] + new_paths))
(BASE / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps({'report': record.relative_to(ROOT).as_posix(), 'counts': counts, 'legacy_preserved': len(legacy_before['files']),
                  'backup': status['backup']}, ensure_ascii=False))
