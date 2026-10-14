"""독립 DB·신고 화면·문서 검토 결과를 실제 원본과 연결합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT / 'final_project_cs'
now = datetime.now(ZoneInfo('Asia/Seoul'))
stamp = now.strftime('%Y-%m-%d_%H%M%S')
backup = HERE / '_backup' / (stamp + '_review_progress')
def preserve(path):
    dest = backup / path.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
def rewrite(path, text):
    preserve(path)
    path.write_text(text, encoding='utf-8')

run = HERE / 'checks/2026-10-12_061303_591088_isolated_integration'
cases = ET.parse(run/'junit.xml').getroot().findall('.//testcase')
assert len(cases) == 20 and all(not any(c.find(x) is not None for x in ('skipped','error','failure')) for c in cases)
result = json.loads((run/'result.json').read_text())
assert result['exit'] == 0 and result['source_changed'] == result['network_blocks'] == []
assert json.loads((run/'cleanup.json').read_text())['own_cluster_stopped']
unit = json.loads((HERE/'checks/support-unit-2026-10-12_0621.json').read_text(encoding='utf-8'))
screen = json.loads((HERE/'checks/support-screen-2026-10-12_0623.json').read_text(encoding='utf-8'))
assert unit['numPassedTests'] == unit['numTotalTests'] == 6 and unit['success']
assert screen['stats']['expected'] == 5 and screen['stats']['unexpected'] == screen['stats']['skipped'] == 0

report = CS / 'wiki/records/reports/2026-10-12_0626_review-support-db-integration.md'
assert not report.exists()
report.write_text('''# 검토 문서·신고 화면·추가 DB 시험 접합

공통 기본 실행에서 건너뛴 PGlite12개를 기존 로컬 패키지로 다시 실행하고 PostgreSQL8개도 함께 확인했습니다. 결과는20/20입니다. 고객 신고 화면의 상담 답변을 암시하는 제목·메뉴를 문제 신고·건의 기록으로 맞췄으며 과거 안내 이력은 그대로 보여 줍니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 추가 격리 DB 시험 | 통과 | 20/20 = 100% |
| 신고 화면 단위 시험 | 통과 | 6/6 = 100% |
| mock 서버 화면 시험 | 통과 | 5/5 = 100% |
| 문서 Chromium 화면 검사 | 통과 | 4/4 = 100% |

## 실행 원본

- [DB JUnit](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_061303_591088_isolated_integration/junit.xml), [소스·차단 결과](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_061303_591088_isolated_integration/result.json), [정리](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_061303_591088_isolated_integration/cleanup.json)
- [단위 시험 JSON](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/support-unit-2026-10-12_0621.json)
- [화면 시험 JSON](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/support-screen-2026-10-12_0623.json), [스크린샷](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/support-screen-2026-10-12_0623/)
- [문서 화면 원본](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/review-screens-2026-10-11T21-14-46-218Z/render-checks.json), [문서 내용·링크·해시 감사](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/review-audit-2026-10-12_061441.json)

DB 명령은 통합 전용 격리 실행기로 tests/integration/db/test_unattended_operations.py를 선택했습니다. OPS_PGLITE_MODULE은 이미 설치된 로컬0.3.14 패키지를 지정했습니다. 패키지를 새로 받거나 업무 DB를 열지 않았습니다. 원본 공통892통과·12건너뜀 결과는 보존하며 단일 실행904통과라고 바꾸지 않습니다.

웹 명령은 npm run test로 support.test.ts·client.test.ts를, npm run test:live로 support.spec.ts·uiux-sonnet-trip-20261012.spec.ts 중 관련5개를 선택했습니다. 전용 mock 포트·새 빌드 폴더를 사용하고 외부 지도 타일도 mock 응답을 사용했습니다. 첫 단위 실행은 Windows 임시 파일 접근 오류로 화면 모듈을 수집하지 못했으며4통과·모듈 오류1입니다. 작업 폴더 임시 경로의 재실행6/6으로 확인했습니다. 제품 코드 문제로 단정하지 않습니다.

문서2개를1440px·375px에서 렌더링해 넘침·SVG 글자 범위·중복 ID·오류·외부 요청을 검사했습니다. 문서 상단과 흐름 그림2장을 육안으로 확인했습니다. 표와 흐름 그림은 좁은 화면에서 해당 영역 안에서 가로 스크롤합니다. 이것은 고객 제품 화면 검증과 별도입니다.

mock 서버 시험5/5 (화면 반응): 재전송 요청 번호·CSRF·기록 완료·이전 안내·공지·목록 재시도·영어 빈 상태·키보드 초점을 확인했습니다.

실서버 확인 (서버 응답): 안 했음 — x600 서버의 cs 프로젝트 서버·외부 자료·고객 전송은 호출하지 않았습니다. 새 전용 PostgreSQL과 PGlite만 사용했습니다.

## 아직 닫지 않은 문제

여행 전체 실행 중 제품 소스는 바꾸지 않았습니다. 검증 담당의 단독22개 실행에서 발견된 시나리오 초기화4실패는 확장210개 실행에서는 통과했지만 단독 준비 문제는 남습니다. 프로세스 이동 설정 보호를 낮추지 않고 시험의 조립 준비를 맞춘 뒤 재검증합니다. 차단 계정의 API 안내에는 운영자 상담 문구가 남아 있어 전체 실행 종료 후 수정·관련 검증이 필요합니다.

여행 규정12문서130청크는 아직 적재하지 않았습니다. 기존 본문에는 자체72시간 무료 취소·24시간 되돌림·상담원 인계 문장이 있어 현재 확정 계약과의 적합성 확인이 먼저입니다. ARM의 안내11청크는 이것을 대체하지 않습니다. 구글 영업 판정 정책과 별개로 기존 가격 경로에는09-30 사용자 결정이라는 주석과 상한 예외가 있습니다. 원문 결정 연결을 확보하기 전에는 새벽 규칙으로 임의 축소하거나 예산을 늘리지 않습니다.

문서2개는 최종 인수 전 검토본입니다. 최신 여행 전체·실자료·외부 개인 AI 종단·배포 인수는 미완료이며 heartbeat를 종료하지 않습니다.

## 백업

[화면 문구 변경 전](../../../_backup/2026-10-12_061946_support_copy_integration/), [스크린샷 검사 보강 전](../../../_backup/2026-10-12_0623_support_screen_evidence/), [문서 재생성 전 안내서](../../../../program/plan/_backup/2026-10-12_061217_review_documents/), [기준선](../../../../program/baseline/_backup/2026-10-12_061217_review_documents/)에 이전 판을 보존했습니다. 소스 변경의 실제 해시와 현재 관측은 최종 통합 목록에서 다시 대조합니다.
''', encoding='utf-8')

wiki = CS/'wiki/operations/unattended-operations.md'
text = wiki.read_text(encoding='utf-8')
text = text.replace('실제 무료 관측 자료의 대상 장소 충족률, 초기 분류·라우팅 진단, 최신 전체 회귀와 배포 인수는 남아 있으므로', '[최초 분류·라우팅 접합](../records/reports/2026-10-12_0603_initial-diagnostics-integration.md)의 관련 회귀268/268과 [추가 DB·고객 화면](../records/reports/2026-10-12_0626_review-support-db-integration.md)의 DB20/20·화면5/5를 후속 확인했습니다. 실제 무료 관측 자료의 대상 장소 충족률, 최신 전체 회귀와 배포 인수는 남아 있으므로')
rewrite(wiki,text)

guide = ROOT/'program/plan/triPilot_구현계획서_v12.md'
text = guide.read_text(encoding='utf-8').replace('| 최신 여행 전체 시험 | 실행 중 | 분모 집계 중 |','| 최신 여행 전체 시험 | 실행 중 | 분모6,946個 |'.replace('個','개'))
text = text.replace('개발자·QA 운영 화면은 결함과 자료 정책을 확인하는 곳입니다.', '고객의 문제 신고·건의는 서비스 개선 기록이며 개별 상담 답변 대기 절차가 아닙니다. 개발자·QA 운영 화면은 결함과 자료 정책을 확인하는 곳입니다.')
rewrite(guide,text)

baseline = ROOT/'program/baseline/triPilot-baseline-2026-10-12.md'
text = baseline.read_text(encoding='utf-8')
text = text.replace('공통의 건너뜀12개와 선택 회귀의 건너뜀11개는 PGlite 패키지 전제입니다.', '공통의 건너뜀12개와 선택 회귀의 건너뜀11개는 PGlite 패키지 전제입니다. 이후 기존 패키지를 지정한 [추가 실행](../../final_project_cs/wiki/records/reports/2026-10-12_0626_review-support-db-integration.md)에서는 PGlite12개·실제 PostgreSQL8개를20/20 통과했습니다. 기본 실행의 건너뜀을 소급 삭제하지 않습니다.')
text = text.replace('앞선 Windows 비정상 종료2회,', '[독립 검증](../research/baseline_completion_2026-10-12/tasks/verification/runs/2026-10-12_followup_060032/followup-summary.json)의 보안·정책210/210과 관문 연결150/150은 별도 원본입니다. 작은 선택22개 중4개는 시험 초기화 문제로 실패했으며 확장 선택에서는 통과했습니다. 단독 준비 보완 전에는 이를 닫지 않습니다. 앞선 Windows 비정상 종료2회,')
rewrite(baseline,text)

statepath = HERE/'status.json'
state = json.loads(statepath.read_text(encoding='utf-8'))
state['updated_at_kst'] = now.isoformat()
state['tests'].extend([
    dict(passed=20,failed=0,skipped=0,total=20,evidence=(run/'junit.xml').relative_to(ROOT).as_posix()),
    dict(passed=6,failed=0,skipped=0,total=6,evidence=(HERE/'checks/support-unit-2026-10-12_0621.json').relative_to(ROOT).as_posix()),
    dict(passed=5,failed=0,skipped=0,total=5,evidence=(HERE/'checks/support-screen-2026-10-12_0623.json').relative_to(ROOT).as_posix(),scope='mock screen'),
])
state['latest_review_report'] = report.relative_to(ROOT).as_posix()
state['unresolved'].extend(['単独22개 선택의 시나리오 초기화4실패 재검증 필요'.replace('単独','단독'),'차단 계정 API의 상담원 안내 문구 후속 접합'])
state['changed_files'] = sorted(set(state['changed_files']) | {report.relative_to(ROOT).as_posix(),Path(__file__).relative_to(ROOT).as_posix(),baseline.relative_to(ROOT).as_posix(),guide.with_suffix('.html').relative_to(ROOT).as_posix(),baseline.with_suffix('.html').relative_to(ROOT).as_posix()})
rewrite(statepath,json.dumps(state,ensure_ascii=False,indent=2)+'\n')
ownreport = HERE/'report.md'
rewrite(ownreport,ownreport.read_text(encoding='utf-8')+f'\n## {now.isoformat()} 추가 DB·화면·문서 검토\n\nDB20/20, 화면 단위6/6, mock 화면5/5. 문서2개 검토본·HTML 생성, 렌더4/4·링크·본문·해시 확인. 단독 초기화4실패·실자료·여행 전체는 후속 확인. [{report.name}](../../../../../final_project_cs/wiki/records/reports/{report.name}). [백업]({backup.relative_to(HERE).as_posix()}/).\n')
print(json.dumps({'report':report.relative_to(ROOT).as_posix(),'backup':backup.relative_to(ROOT).as_posix()},ensure_ascii=True))
