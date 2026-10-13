"""식당 정책 접합의 실제 JUnit·정리·소스 증거를 기록한다."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
run = HERE / 'checks/2026-10-12_054119_690586_isolated_integration'
cases = ET.parse(run / 'junit.xml').getroot().findall('.//testcase')
assert len(cases) == 124
assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
skipped = sum(c.find('skipped') is not None for c in cases)
assert skipped == 11
new = [c for c in cases if 'test_place_status_policy' in c.get('classname', '')]
assert len(new) == 20 and not any(c.find('skipped') is not None for c in new)
assert json.loads((run / 'result.json').read_text())['source_changed'] == []
assert json.loads((run / 'cleanup.json').read_text())['own_cluster_stopped']
now = datetime.now(ZoneInfo('Asia/Seoul'))
backup = HERE / '_backup' / (now.strftime('%Y-%m-%d_%H%M%S') + '_place_status_record')
backup.mkdir(parents=True)
for file in ('status.json', 'report.md'):
    shutil.copy2(HERE / file, backup / file)
report = ROOT / 'final_project_cs/wiki/records/reports' / (now.strftime('%Y-%m-%d_%H%M') + '_place-status-integration.md')
assert not report.exists()
report.write_text('''# 무료 휴무 관측·새벽 조회 정책의 실제 호출 연결

새벽 점검·낮 감시·Team의 재점검에 장소 상태 정책을 연결했습니다. 실제 장소 자료 확보나 운영 반영을 완료한 결과는 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 정책 인수 | 통과 | 20/20 = 100% |
| 전체 선택 실행 | 통과·건너뜀 | 113/124 통과 = 91% |
| 환경 전제 부족 | 건너뜀 | 11/124 = 9% |

## 실제 경로와 확인

작업 일꾼의 새벽 조립에서 운영 정책을 호출합니다. 무료 판정은 Dining 팀이 조립에 등록한 읽기 제공자를 통해 운영 허용 출처의 성공한 휴무 관측만 읽습니다. 방문 시작이 같은 기록이며 방문 종료까지 유효해야 합니다. 시간표나 예전 확인 시각을 실제 개점 관측으로 바꾸지 않습니다. 숙소에서 먹는 조식도 장소 종류가 아니라 실제 식사 일정으로 점검합니다.

낮 감시는 tenant·고객·여행 범위를 확인하고 저장된 확인 간격을 원자적으로 확보합니다. 간격 미충족은 점검 건너뜀이며 정상 영업 판정이 아닙니다. 무료 관측을 확보하지 못하면 기존 일정을 유지한다는 안내와 오류를 기록하고 다음 확인 회차에 재시도합니다. Team 도구는 같은 관측을 다시 확인하며 낮 구글 조회는 0회입니다. 이미 정책에서 수집한 오류를 감시 콜백에서 다시 세지 않습니다.

새벽은 무료 판정 우선이며 운영 정책 기본 유료 꺼짐·하루와 여행 상한·03~08시 구글 창을 지킵니다. 요청 전용 공급 사본이 첫 HTTP의 기존 공용 예산을 예약하고 첫 HTTP가 그 허가를 소비합니다. 검색 뒤 상세 HTTP는 별도 한 칸입니다. 이름·좌표 짝 불일치는 별도 place_unmatched 결함 한 번으로 남고 상세 요청은 하지 않습니다. 공유 공급 객체에 고객 범위를 저장하지 않습니다.

## 실행 근거

- [JUnit](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_054119_690586_isolated_integration/junit.xml)
- [전후 소스·종료 결과](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_054119_690586_isolated_integration/result.json)
- [전용 DB 프로세스 정리](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_054119_690586_isolated_integration/cleanup.json)
- [변경 전 백업](../../../_backup/2026-10-12_053150_place_status_policy_integration/)

실행 중 소스 변경은 0건입니다. 새 전용 PostgreSQL과 합성 여행을 사용했으며 외부·업무 DB 연결을 차단했습니다. HTTP는 응답 대역입니다. 11개 기존 PGlite 시험은 패키지 전제가 없어 건너뛰었으며 PostgreSQL 경쟁·복구 8건은 별도로 실행했습니다. 최초 58통과·8실패·정리 오류5, 후속 102통과·2실패·정리 오류5 및 18통과·1실패는 보존합니다. 감사 기록은 append-only이므로 삭제하거나 트리거를 끄지 않고 전용 시험 DB에 보존했습니다.

## 남은 범위

무료 관측 자료를 읽는 접합과 검증 불가 처리는 구현했습니다. 실제 대상 장소들의 최신 운영 관측 자료가 모두 확보됐다는 근거는 없습니다. 운영 환경 배포·볼륨 권한·실제 고객 통지·유료 호출도 수행하지 않았습니다. 기존 구글 가격 비교의 별도 결정과 호출 경계는 최종 계약 대조 대상입니다. 이 실행 후 파기 고객 재전송 거부와 Team 읽기의 종료 구간 전달을 보강했으므로 해당 변경과 전체 공통·여행은 최신 코드에서 다시 검증해야 합니다.

mock 서버 시험(화면 반응): 이번 실행은 화면 시험을 수행하지 않았습니다.

실서버 확인(서버 응답): 외부 제공처·cs 프로젝트 서버의 실제 응답은 새로 확인하지 않았습니다. 격리 PostgreSQL 실행만 확인했습니다.
''', encoding='utf-8')
state = json.loads((HERE / 'status.json').read_text(encoding='utf-8'))
state['updated_at_kst'] = now.isoformat()
state['tests'].append(dict(passed=113, failed=0, skipped=11, total=124,
                          evidence=(run/'junit.xml').relative_to(ROOT).as_posix()))
state['latest_review_report'] = report.relative_to(ROOT).as_posix()
state['changed_files'] = sorted(set(state['changed_files']) | {report.relative_to(ROOT).as_posix(), Path(__file__).relative_to(ROOT).as_posix()})
state['dependencies_remaining'] = [s.replace('Dining policy and remaining error boundaries pending; PostgreSQL competition verified',
    'Dining call policy integrated; latest regressions, free observation coverage and remaining error boundaries pending') for s in state['dependencies_remaining']]
state['backup'] = backup.relative_to(ROOT).as_posix()
(HERE/'status.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
with (HERE/'report.md').open('a', encoding='utf-8') as f:
    f.write(f'\n## {now.isoformat()} 食堂 정책 연결\n\n새 인수 20/20, 선택 실행 113통과·11건너뜀(총124). 실행 중 소스 불변·전용 DB 중지 확인. [{report.name}](../../../../../final_project_cs/wiki/records/reports/{report.name}). 실제 관측 자료 확보·운영 반영·최종 전체 회귀는 미완료입니다.\n'.replace('食堂','식당'))
print(report.relative_to(ROOT).as_posix())
