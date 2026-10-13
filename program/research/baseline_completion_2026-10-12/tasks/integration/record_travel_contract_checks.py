"""현재 코드의 여행·인증 접합 재검증 원본을 기록한다."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
now = datetime.now(ZoneInfo('Asia/Seoul'))
backup = HERE / '_backup' / (now.strftime('%Y-%m-%d_%H%M%S') + '_travel_contract_record')
backup.mkdir(parents=True)
for name in ('status.json', 'report.md'):
    shutil.copy2(HERE / name, backup / name)
tests = []
for name, count in [('2026-10-12_052028_565873_isolated_integration', 79),
                    ('2026-10-12_052414_983603_isolated_integration', 113)]:
    run = HERE / 'checks' / name
    suites = ET.parse(run / 'junit.xml').getroot().findall('.//testsuite')
    assert sum(int(s.get('tests', 0)) for s in suites) == count
    assert sum(int(s.get(k, 0)) for s in suites for k in ('failures', 'errors', 'skipped')) == 0
    result = json.loads((run / 'result.json').read_text())
    assert result['exit'] == 0 and not result['source_changed'] and not result['network_blocks']
    assert json.loads((run / 'cleanup.json').read_text())['own_cluster_stopped']
    tests.append(dict(passed=count, failed=0, skipped=0, total=count,
                      evidence=(run / 'junit.xml').relative_to(ROOT).as_posix()))
report = ROOT / 'final_project_cs/wiki/records/reports' / (now.strftime('%Y-%m-%d_%H%M') + '_travel-contract-integration.md')
assert not report.exists()
report.write_text('''# 여행 등록·예약 보존·인증 계약 접합

선택 장소를 등록할 때 앞 항목의 추정 종료 시각이 다시 늘어나 새 이동 시간이 사라지는 결함을 수정했습니다. 예약 사실 보존과 고객 고정은 현재 D-020 계약에 맞게 따로 검증했습니다. 전체 기준선은 아직 미완료입니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 여행 등록·실패 안내 | 통과 | 79/79 = 100% |
| 인증·API·작업 마감 | 통과 | 113/113 = 100% |

자동 조정은 뒤 일정을 미룰 때 이미 이동 계산에 쓴 앞 항목의 추정 종료 시각도 명시적으로 보존합니다. 선택 장소의 검토 화면과 최종 등록 모두 이동 겹침이 없는지 확인했습니다. 최초 재현 22통과·1실패는 보존합니다. 예약 번호·예약 선언은 잃지 않으며 보호 여부는 고객 고정으로 검사합니다. 결과 표지가 없는 재시도 가능한 묶음 실패는 현재 계약에 따라 기존 일정을 유지한다는 안내를 한 번만 기록합니다.

브라우저 회원 쿠키 인증을 기존 CSRF 검사와 함께 FastAPI 의존성으로 선언했습니다. 연결 목록·폐기, 공개 시험 시나리오, 접수 복원 경로를 기존 wiki 계약과 API 표면 관문 목록에서 대조했습니다. 장시간 전체 시험에서 import 시각에 만들어 둔 90초 마감이 먼저 만료되는 시험 자료 결함은 작업을 만드는 현재 시각으로 고쳤으며 제품 마감 제한은 늘리지 않았습니다.

두 실행은 새 격리 PostgreSQL에 현재 SQL을 적용했습니다. 실행 중 소스 변경·외부 통신 차단 시도는 0건이며 각 시험 DB 프로세스 중지를 확인했습니다. 고객 알림은 저장 경로만 검사했고 실제 발송하지 않았습니다. 업무 DB·배포·유료 호출·commit·push는 하지 않았습니다.

## 원본

''' + '\n'.join(f'- [{t["passed"]}건 JUnit](../../../../{t["evidence"]}): 같은 폴더의 result.json·cleanup.json·소스 해시를 함께 확인합니다.' for t in tests) + '''

## 백업과 남은 범위

- [여행 변경 전](../../../_backup/2026-10-12_051702_travel_contract_assertions/)
- [인증·마감 변경 전](../../../_backup/2026-10-12_052358_api_surface_deadline_integration/)

OAuth GET/POST의 중복 operationId 경고 1건은 후속 확인 대상입니다. Dining 정책의 실제 호출 연결·전체 여행 재검증·최종 문서·해시 검토가 남아 있으며, 선택 시험 통과를 전체 완료나 운영 반영으로 확대하지 않습니다.
''', encoding='utf-8')
state = json.loads((HERE / 'status.json').read_text(encoding='utf-8'))
state['updated_at_kst'] = now.isoformat()
state['tests'].extend(tests)
state['latest_review_report'] = report.relative_to(ROOT).as_posix()
state['changed_files'] = sorted(set(state['changed_files']) | {report.relative_to(ROOT).as_posix(), Path(__file__).relative_to(ROOT).as_posix()})
state['backup'] = backup.relative_to(ROOT).as_posix()
(HERE / 'status.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
with (HERE / 'report.md').open('a', encoding='utf-8') as f:
    f.write(f'\n## {now.isoformat()} 여행·인증 접합\n\n여행 79/79, 인증·계약 113/113 통과. 소스 불변·격리 DB 중지를 확인했습니다. 원본: [{report.name}](../../../../../final_project_cs/wiki/records/reports/{report.name}). 전체 검증과 Dining 정책 접합은 미완료입니다.\n')
print(report.relative_to(ROOT).as_posix())
