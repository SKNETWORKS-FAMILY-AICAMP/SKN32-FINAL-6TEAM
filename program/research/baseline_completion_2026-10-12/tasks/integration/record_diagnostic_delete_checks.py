"""완료된 세 실행의 원본 집계를 보존하고 통합 담당의 상태만 갱신한다."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT / 'final_project_cs'
now = datetime.now(ZoneInfo('Asia/Seoul'))
stamp = now.strftime('%Y-%m-%d_%H%M%S_%f')
backup = HERE / '_backup' / (stamp + '_diagnostic_delete_record')
backup.mkdir(parents=True)
for name in ('status.json', 'report.md'):
    shutil.copy2(HERE / name, backup / name)
runs = [('2026-10-12_050552_917634_diagnostic_callback', '215'),
        ('2026-10-12_050924_562803_isolated_integration', '108'),
        ('2026-10-12_051445_838389_isolated_integration', '8')]
tests = []
for name, expected in runs:
    run = HERE / 'checks' / name
    xml = next(run.glob('*.xml'))
    suites = ET.parse(xml).getroot().findall('.//testsuite')
    total = sum(int(s.get('tests', 0)) for s in suites)
    failed = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in suites)
    skipped = sum(int(s.get('skipped', 0)) for s in suites)
    assert total == int(expected) and failed == skipped == 0
    if name.endswith('isolated_integration'):
        assert json.loads((run / 'cleanup.json').read_text())['own_cluster_stopped']
        result = json.loads((run / 'result.json').read_text())
        assert result['exit'] == 0 and not result['source_changed']
    tests.append({'passed': total, 'failed': failed, 'skipped': skipped, 'total': total,
                  'evidence': xml.relative_to(ROOT).as_posix()})

report = CS / 'wiki/records/reports' / (now.strftime('%Y-%m-%d_%H%M') + '_diagnostic-delete-integration.md')
assert not report.exists()
lines = ['# 오류 수집·여행 삭제·PostgreSQL 경쟁 검증', '',
    '오류 수집 콜백을 실행 경계에 연결하고, 여행 삭제 뒤 남던 운영 조회 기록을 정리했습니다. 필수 전체 접합과 최종 기준선은 아직 완료하지 않았습니다.', '',
    '| 할 일 | 상태 | 진행 |', '|---|---|---|',
    '| 오류 수집 선택 시험 | 통과 | 215/215 = 100% |',
    '| 여행 삭제·콜백 격리 시험 | 통과 | 108/108 = 100% |',
    '| 다중 연결 경쟁·복구 | 통과 | 8/8 = 100% |', '',
    '## 변경과 조건', '',
    'Core는 도메인 중립 콜백만 받습니다. 조립부에서 여행 범위를 전달하고 팀 예외·시간 초과·상태 충돌, 여행 분류 계획 실패·자료 실패·재시도를 고정 코드와 UUID로 수집합니다. 독립 저장·내구 대기·수집 저하를 구분하며 예외 원문·고객 본문은 전달하지 않습니다. 초기 메시지 분류·라우팅 단계와 그 밖의 실패 경계는 추가 검토 대상입니다.', '',
    '운영 조회 예산·확인 시각 표는 기존 여행 삭제 경로에 연결했습니다. 미배포 SQL 902 후보에 여행 외래 키와 삭제 연쇄를 추가했습니다. 다른 여행의 기록은 보존하고 진단 사건은 삭제 여행 연결만 해제합니다. 원 담당의 이전 SQL 해시는 이 수정 전 증거이며 최종 해시로 재확인해야 합니다.', '',
    '각 PostgreSQL 실행은 새 전용 DB에 현재 안전 SQL 실행기를 적용하고 실행 종료 뒤 해당 시험 DB 프로세스만 중지했습니다. 업무 DB·외부 통신은 차단했습니다. 동시 CAS와 1회 조회 상한은 서로 다른 연결의 요청 2개로 각각 3회 검증했습니다. DB 커밋 뒤 SQLite 대기 행이 남은 복구는 중복 발생 0건이며, 소유권 확인 뒤 여행을 지운 경쟁에서도 유료 자료 공급 호출은 0회였습니다.', '',
    '## 원본 실행 증거', '']
for test in tests:
    path = ROOT / test['evidence']
    rel = Path(__import__('os').path.relpath(path, report.parent)).as_posix()
    lines.append(f"- [{path.parent.name}]({rel}): {test['passed']}/{test['total']} 통과. 같은 폴더의 실행 결과·전후 소스 목록·정리 결과를 함께 보존합니다.")
lines += ['', '초기 선택 시험 213통과·2실패 및 214통과·1실패는 삭제하지 않았습니다. 기존 시험의 비활성 Activity 조정자 의존을 현재 계약과 대조해 실제 묶음 진입·소유 팀을 검증하도록 정정했습니다.', '',
    '## 백업·남은 범위', '',
    '- [콜백 변경 전](../../../_backup/2026-10-12_050103_diagnostic_callback_integration/)',
    '- [여행 삭제 변경 전](../../../_backup/2026-10-12_050730_operations_trip_delete_integration/)',
    '- [경쟁 시험 변경 전](../../../_backup/2026-10-12_051432_operations_postgres_competition/)', '',
    'Dining 실제 자료 조회 정책 접합·전체 공통/여행 최종 재검증·운영 환경의 볼륨 권한과 재시작·외부 개인 AI 종단 확인은 남아 있습니다. 격리 검증 결과를 실제 환경 반영이나 전체 기능 완료로 확대하지 않습니다. 업무 DB 변경·배포·고객 알림·유료 호출·commit·push·다른 채팅 메시지는 실행하지 않았습니다.', '']
report.write_text('\n'.join(lines), encoding='utf-8')
state = json.loads((HERE / 'status.json').read_text(encoding='utf-8'))
state['updated_at_kst'] = now.isoformat()
state['tests'].extend(tests)
state['latest_review_report'] = report.relative_to(ROOT).as_posix()
state['dependencies_remaining'] = [s.replace('policy/common-errors/PostgreSQL competition pending', 'Dining policy and remaining error boundaries pending; PostgreSQL competition verified') for s in state['dependencies_remaining']]
state['unresolved'] = [s.replace('진단 자동 재전송 1/3 접합 검증; Dining 정책·공통 오류 수집 및 PostgreSQL 경쟁 시험 남음', '자동 재전송·주요 오류 콜백·PostgreSQL 경쟁 시험 검증. Dining 정책·초기 분류/라우팅 오류 경계와 전체 재검증 남음') for s in state['unresolved']]
state['backup'] = backup.relative_to(ROOT).as_posix()
state['changed_files'] = sorted(set(state['changed_files']) | {report.relative_to(ROOT).as_posix(), Path(__file__).relative_to(ROOT).as_posix()})
(HERE / 'status.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
with (HERE / 'report.md').open('a', encoding='utf-8') as f:
    rel = Path(__import__('os').path.relpath(report, HERE)).as_posix()
    f.write(f'\n## {now.isoformat()} 오류 수집·여행 삭제·경쟁 검증\n\n[원본 결과와 범위]({rel}): 선택 콜백 215/215, 격리 삭제·콜백 108/108, 실제 PostgreSQL 다중 연결 경쟁·복구 8/8 통과. 전후 소스 불변·전용 시험 DB 중지를 확인했습니다. Dining 정책과 남은 실패 경계·최종 전체 재검증은 계속 진행합니다.\n')
print(report.relative_to(ROOT).as_posix())
