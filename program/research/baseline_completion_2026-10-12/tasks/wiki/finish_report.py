"""실행 결과 파일을 읽어 담당 보고서·상태·인계 목록을 기록한다."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
now = datetime.now(timezone(timedelta(hours=9)))


def write(path, text):
    if path.exists():
        backup = path.parent/'_backup'/(now.strftime('%Y-%m-%d_%H%M%S_%f')+'_final-report')/path.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    path.write_text(text, encoding='utf-8')


check = json.loads((OUT/'check-handoff.json').read_text(encoding='utf-8'))
inventory = json.loads((ROOT/'wiki/governance/implementation-inventory.generated.json').read_text(encoding='utf-8'))
backups = json.loads((OUT/'backups.json').read_text(encoding='utf-8'))
owned = [r['path'] for r in backups] + [
    'final_project_cs/wiki/data/migration-inventory.generated.md',
    'wiki/governance/implementation-inventory.generated.md',
    'wiki/governance/implementation-inventory.generated.json',
    'wiki/records/reports/2026-10-12_review-policy-before-followup.md',
    'wiki/records/reports/2026-10-12_evidence-grades-before-followup.md',
]
manifest = [{'path': name, 'sha256': hashlib.sha256((ROOT/name).read_bytes()).hexdigest()} for name in owned]
write(OUT/'changed-files.json', json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
tests = []
commands = [
    ('governance-tests-final.xml', '워크스페이스 루트', 'python -m pytest program/scripts/tests/test_wiki_governance.py -q --basetemp=program/research/baseline_completion_2026-10-12/tasks/wiki/_test_tmp_3 --junitxml=program/research/baseline_completion_2026-10-12/tasks/wiki/governance-tests-final.xml --tb=short'),
    ('cs-tests.xml', 'final_project_cs', 'python -m pytest tests/contract/test_team_layout.py tests/architecture/test_travel_ops_cells.py tests/architecture/test_state_diagram_matches_code.py -q --basetemp=../program/research/baseline_completion_2026-10-12/tasks/wiki/_cs_test_tmp_2 --tb=short --junitxml=../program/research/baseline_completion_2026-10-12/tasks/wiki/cs-tests.xml'),
]
for filename, cwd, command in commands:
    suite = ET.parse(OUT/filename).getroot().find('testsuite')
    failed = int(suite.attrib['failures'])+int(suite.attrib['errors'])
    skipped = int(suite.attrib['skipped'])
    tests.append({'command': command, 'cwd': cwd, 'passed': int(suite.attrib['tests'])-failed-skipped,
        'failed': failed, 'skipped': skipped, 'evidence': (OUT/filename).relative_to(ROOT).as_posix(),
        'junit_timestamp': suite.attrib['timestamp'],
        'output_written_at_kst': datetime.fromtimestamp((OUT/filename).stat().st_mtime, timezone(timedelta(hours=9))).isoformat()})
tests.append({'command': 'python program/scripts/check_wiki.py --include-records --json-output program/research/baseline_completion_2026-10-12/tasks/wiki/check-handoff.json',
    'passed': int(check['total_violations'] == 0), 'failed': int(check['total_violations'] > 0), 'skipped': 0,
    'violations': check['total_violations'], 'evidence': (OUT/'check-handoff.json').relative_to(ROOT).as_posix()})
tests.append({'command':'python program/scripts/build_wiki_catalogs.py --check', 'passed':1, 'failed':0, 'skipped':0,
    'evidence': 'program/research/baseline_completion_2026-10-12/tasks/wiki/reproducibility.json'})
write(OUT/'tests.json', json.dumps(tests, ensure_ascii=False, indent=2)+'\n')
handoff = {
    'captured_at_kst': now.isoformat(),
    'full_wiki_violations': {k:v for k,v in check['problems'].items() if v},
    'state_field_warnings': check['warnings'].get('상태 필드 확인 필요', []),
    'unapplied_documents': [{'path':r['path'],'missing_fields':r['missing_fields']} for r in inventory['documents'] if r['missing_fields']],
    'feature_results_pending': ['auth','orchestration','operations','existing:Mobility','verification','integration'],
    'required_integration_actions': [
        '작성 중 상태 in-progress/in_progress를 실제 범위 확인 후 기존 planned/partial/implemented/unverified 중 해당 값으로 정규화',
        '분류 실행 계획의 담당 보고서 링크 생성·확인, 이동 신규 페이지 머리말 보완',
        '각 기능 결과를 해당 wiki 본문 환경·실행 시각·근거에 연결; 확인하지 않은 배포는 unverified 유지',
        '전체 위키 검사 재실행 후 자동 목록 재생성·--check 확인',
        'findings-v2.json 해시가 바뀌었으므로 parent가 관리하는 review_status와 기준선 입력 해시를 통합 때 갱신',
        '저장소 log에는 이번 보고서 링크와 실제 최종 통합 결과 기록; v12·최종 베이스라인은 integration 담당 작성',
    ],
}
write(OUT/'handoff.json', json.dumps(handoff, ensure_ascii=False, indent=2)+'\n')

scope = check['scope']
rows = inventory['documents']
missing = sum(bool(r['missing_fields']) for r in rows)
types = Counter(r['type'] for r in rows)
spec = importlib.util.spec_from_file_location('catalog_counts',ROOT/'program/scripts/build_wiki_catalogs.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
catalog = build.catalog_rows((ROOT/'final_project_cs/wiki/quality/invariants.md').read_text(encoding='utf-8'))
counts = Counter(kind for _,kind in catalog)
report = f'''# 위키 상태 표시·작성 기준 후속 결과

담당 문서·검사 도구 수정과 관련 시험은 완료했습니다. 전체 위키 검사에는 병렬 작업 문서의 위반 {check['total_violations']}건이 남아 있어 통합 때 재검사가 필요합니다. 제품 전체 인수·운영 반영 완료를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 담당 항목 결과·인계 | 통합 검토 요청 | 5/5 = 100% |
| 검사 도구·관련 구조 시험 | 통과 | 24/24 = 100% |
| 전체 위키 수집·검사 실행 | 위반 있음 | {len(check['checked_documents'])}/{len(check['checked_documents'])} = 100% |
| 상태 필드 적용 목록 수집 | 완료 | {len(rows)}/{len(rows)} = 100% |

확인 시각(KST): {now.isoformat()}. 위 비율은 각각 담당 항목, 이번 실행 시험, 검사 실행 문서, 상태 적용 대상 목록의 분모입니다. 목록 수집 완료는 필드 전환·기능 검증 완료가 아닙니다.

## 실제 변경·근거

| 항목 | 결과 | 근거 |
|---|---|---|
| W16 | 기존 README 이름·소개 배치 유지. 기능 책임과 디렉토리 경계 구분, 인증·DB 상시 전담 미확정 유지 | [역할](../../../../../wiki/delivery/roles.md), [코드 위치](../../../../../final_project_cs/wiki/teams/code-layout.md), [로컬 링크 51/51](owned-paths.json), [구조 시험](cs-tests.xml) |
| W20 | 상태 값·시각 형식 검사, 현재 주요 결정·계약과 개정 대상 전체 목록 생성. SQL 과거 예시 정정 | [상태 안내](../../../../../wiki/governance/implementation-state.md), [자동 목록](../../../../../wiki/governance/implementation-inventory.generated.md), [기계용 목록](../../../../../wiki/governance/implementation-inventory.generated.json) |
| W22 | 현재·생성·기록·백업·이관 범위 구분 유지. 시험 백업의 옛 표식 제외, 머리말 없는 문서도 도메인 미표시 분모에 포함 | [검사기](../../../../../program/scripts/check_wiki.py), [회귀 시험](governance-tests-final.xml) |
| W23 | cs 정의 카탈로그와 검사 문서 전체 인용 집계를 분리. SQL 목록은 현재 실행기 입력으로 재생성 | [cs 자동 집계](../../../../../final_project_cs/wiki/quality/invariant-summary.generated.md), [SQL 목록](../../../../../final_project_cs/wiki/data/migration-inventory.generated.md) |
| W25 | 현재 규칙 먼저, 8~9월 사고·미결정은 새 보존 기록으로 연결. findings 과거 검토와 현재 확인 구분 | [리뷰 정책](../../../../../wiki/governance/review-policy.md), [근거 등급](../../../../../wiki/governance/evidence-grades.md), [선택 보존 확인](findings-preservation.json) |

### 병합 분류

| 대상 | 분류 | 기존 내용·현재 확인 | 처리 |
|---|---|---|---|
| 상태 검사·대상 목록 | 보완 | 필드 안내만 있고 새 필드 검사·전체 적용 목록 미구현 | 선택 필드는 선택으로 유지하고 형식 검사·미적용 목록 추가 |
| 역할·경로 안내 | 중복·보완 | 인명 배정은 이미 미확정이며 README 참고 배치와 기능 책임이 혼동될 수 있음 | 새 인명 배정 없이 정본 관계·이번 경로 증거 연결 |
| SQL 환경 예시 | 모순·해소 근거 확보 | 옛 DB 표·배포 제외 규칙 서술과 2026-10-12 실행 기록이 다름 | 요청에 따라 과거 시점·원문 보존, 현재 실측 기록으로 정정 |
| v11 우선·과거 도구 상태 문장 | 모순·후속 결정 명확 | 당시 계획·사고 설명이 현재 규칙처럼 노출 | 현재 wiki 우선 규칙 적용, 전체 옛 본문을 보존 기록으로 연결 |
| 기능별 상태 필드·본문 | 미확인·담당 대기 | 다른 담당의 구현·시험 진행 중 | 직접 덮어쓰지 않고 인계 목록에 기록 |

새 결정·담당 배정·기능 계약을 발명하지 않았고, 이미 확정한 사용자 선택을 재승인 대기로 되돌리지 않았습니다. `§` 참조·에이전트 팀 집합·완료 기준 수는 이번 변경에서 새 수치를 복사하지 않았습니다. 옛 DoD 숫자의 소유를 현재 완료 기준 문서에 연결했습니다. 전체 wiki 본문 의미 검토·현재 기능 전량 대조를 완료했다고 주장하지 않습니다.

## 범위·숫자 구분

- 전체 검사: 현재 {scope['current_documents']}개 + 생성 {scope['generated_documents']}개 = {len(check['checked_documents'])}개. 기록 {scope['record_documents']}개는 본문 규칙 제외, 요청한 기록 링크 통계 {len(check['record_broken_links'])}곳. 백업 디렉토리 {scope['excluded_backup_directories']}개·이관/숨김 디렉토리 {scope['excluded_staging_directories']}개 제외. 디렉토리 수는 하위 파일 수가 아닙니다.
- 상태 적용 대상: 허브·cs의 현재 decision {types['decision']}개, contract {types['contract']}개와 W01~W25의 나머지 현재 wiki 대상 {len(rows)-types['decision']-types['contract']}개, 합계 {len(rows)}개. 필드 일부 미적용 {missing}개는 [전체 미적용 목록](handoff.json)에 있으며 구현·배포는 추정하지 않습니다. deprecated·생성·기록·백업·이관·sample은 적용 목록에서 제외합니다.
- cs 정의 카탈로그: {len(catalog)}개(automated {counts['automated']}, review {counts['review']}). 전체 검사 문서의 인용 고유 ID {len(check['invariant_references']['unique_ids'])}개, automated 연결 행 {check['invariant_references']['automated_link_rows']}개, 현재 시험 코드 표식 {len(check['invariant_references']['current_test_marker_ids'])}개와 분모가 다릅니다. 어느 수도 이번 시험 통과 수가 아닙니다.

## 실행·성공·실패·건너뜀

정확한 명령·작업 폴더·JUnit 기록 시각·성공/실패/건너뜀은 [tests.json](tests.json)을 확인합니다.

| 실행 | 성공 | 실패/오류 | 건너뜀 | 근거 |
|---|---:|---:|---:|---|
| 상태 형식·범위·백업 제외·인용 목록 회귀 | 12 | 0 | 0 | [JUnit](governance-tests-final.xml) |
| 에이전트 팀 등록·의존 방향·코드 전이도 | 12 | 0 | 0 | [JUnit](cs-tests.xml) |
| 전체 wiki 검사 명령 | 0 | 1 | 0 | [전체 결과](check-handoff.json), 위반 {check['total_violations']}건 |
| 자동 생성물 일치·재현 | 1 | 0 | 0 | [재현 기록](reproducibility.json) |
| 문서 안내의 로컬 링크 대상 | 51 | 0 | 0 | [경로 확인](owned-paths.json) |
| 흐름도 정적 구조 검사 | 1 | 0 | 0 | [흐름도](state-recording.html), diagram-design self_check.py 종료 0 |

초기 기본 pytest 실행은 OS 임시 폴더 생성 권한 오류로 1개 통과·2개 setup 오류였습니다. 이후 작업 폴더 안의 격리 임시 경로에서 재실행했습니다. 최종 실행의 경고는 기존 코드의 escape 문법 경고 1개와 종료 시 pyreadline3 콘솔 정리 메시지이며 시험 종료 코드는 0입니다. 브라우저 미리보기는 30초 시간 초과로 화면 확인을 마치지 못했습니다. 그림의 정적 검사 통과와 화면 확인을 구분합니다.

mock 서버 시험 (화면 반응): 안 했음 — 이번 범위는 문서·검사 도구와 구조 시험입니다.

실서버 확인 (서버 응답): 안 했음 — 로컬 개발 DB·x600 서버의 cs 프로젝트에 새 조회·변경·재시작을 하지 않았습니다. SQL 상태는 기존 실측 파일을 읽어 대조했습니다.

## 통합 때 처리할 것

현재 전체 검사 위반과 담당 적용 목록은 [handoff.json](handoff.json)에 정확한 경로로 기록했습니다. 다른 담당의 문서 상태를 임의로 바꾸지 않았습니다. 기능 결과가 준비되면 본문 환경별 표와 시각·근거를 갱신하고 전체 위키 검사·생성을 다시 실행해야 합니다.

현재 기본 검사는 실패 상태입니다. 이 보고서의 통합 검토 요청은 담당 범위의 변경·증거가 준비됐다는 뜻이며, 전체 위키 관문 통과·제품 릴리스 승인·최종 베이스라인 동결이 아닙니다. v12·최종 베이스라인은 integration 담당이 작성합니다. 공용 coordination·review_status·다른 담당 status는 수정하지 않았습니다.

## 외부 근거 재확인

[외부, 2026-10-12 확인] [NASA Systems Engineering Handbook 부록](https://www.nasa.gov/reference/system-engineering-handbook-appendix/)은 책임·권한 배정의 예로 RACI를 제시합니다. [GitHub CODEOWNERS 문서](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)는 파일 경로별 담당과 쓰기 권한·필수 검토 설정을 구분합니다. 프로젝트 인명 배정·최초 발명자·표준 인증·실제 강제 검토 적용을 이 자료로 추정하지 않았습니다. OKF/OpenWiki 기반의 기존 프로젝트 규격을 유지했습니다.

## 변경 해시·백업

문서·도구·생성물의 실제 변경 목록과 현재 SHA-256은 [changed-files.json](changed-files.json), 기존 12개 파일의 변경 전 해시·백업 위치는 [backups.json](backups.json)에 있습니다. findings 추가 백업·선택 보존·전후 해시는 [findings-preservation.json](findings-preservation.json)에 있습니다. 생성물은 생성기가 변경 직전 사본을 각 문서 폴더의 `_backup`에 자동 저장했습니다. 보고서와 상태 파일도 덮기 전 사본을 [담당 백업 폴더](_backup/)에 보존했습니다.

과거 본문은 [리뷰 정책 원문](../../../../../wiki/records/reports/2026-10-12_review-policy-before-followup.md)·[근거 등급 원문](../../../../../wiki/records/reports/2026-10-12_evidence-grades-before-followup.md)에 새로 보존했으며 기존 records·legacy는 수정하지 않았습니다. 이 산출물·코드는 미커밋 작업 트리 기준입니다. 커밋·푸시·원격 배포·업무 DB 변경·고객 알림·유료 호출은 실행하지 않았습니다.
'''
write(OUT/'report.md', report)
dependencies = ['auth','orchestration','operations','existing:Mobility','integration']
status = {
    'phase':'ready_for_integration', 'updated_at_kst':now.isoformat(),
    'w_ids':['W16','W20','W22','W23','W25'],
    'changed_files':owned+[p.relative_to(ROOT).as_posix() for p in OUT.iterdir() if p.is_file() and p.name != 'task.md'],
    'tests':tests, 'report':(OUT/'report.md').relative_to(ROOT).as_posix(),
    'dependencies_remaining':dependencies,
    'unresolved':[
        f'전체 wiki 기본 검사는 {check["total_violations"]}건으로 실패. 정확한 다른 담당 문서 경로는 handoff.json 참조',
        f'현재 적용 대상 {len(rows)}개 중 {missing}개 상태 필드 일부 미적용. 기능별 결과와 환경 증거 확인 후 담당자가 반영',
        '브라우저 미리보기 시간 초과; 흐름도 정적 검사만 완료',
    ],
    'deployment':'not_deployed',
    'ready_reason':'담당 문서·검사·생성기 구현, 회귀 12/12·구조 12/12·경로 51/51 및 생성 재현 증거 준비. 전체 wiki 실패와 기능별 미확인은 숨기지 않고 통합 접합부로 인계. 전체 제품 완료·관문 통과 선언 아님',
}
write(OUT/'status.json',json.dumps(status,ensure_ascii=False,indent=2)+'\n')
print('보고서·상태·인계 목록 기록 완료')
