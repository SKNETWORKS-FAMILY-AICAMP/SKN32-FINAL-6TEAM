"""최신 통합 회귀 원본을 보존하고 자기 상태만 갱신한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, shutil
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
run = HERE/'checks/2026-10-12_054657_390668_isolated_integration'
cases = ET.parse(run/'junit.xml').getroot().findall('.//testcase')
assert len(cases) == 229
assert sum(c.find('skipped') is not None for c in cases) == 11
assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
result = json.loads((run/'result.json').read_text())
assert result['exit'] == 0 and result['source_changed'] == [] and result['network_blocks'] == []
assert json.loads((run/'cleanup.json').read_text())['own_cluster_stopped']
now = datetime.now(ZoneInfo('Asia/Seoul'))
backup = HERE/'_backup'/(now.strftime('%Y-%m-%d_%H%M%S')+'_latest_regression')
backup.mkdir(parents=True)
for name in ('status.json','report.md'):
    shutil.copy2(HERE/name, backup/name)
report = ROOT/'final_project_cs/wiki/records/reports'/(now.strftime('%Y-%m-%d_%H%M')+'_privacy-regression-integration.md')
assert not report.exists()
report.write_text('''# 개인정보 파기·여행 계약 통합 회귀

선택한 최신 회귀 229개 중 218통과·11건너뜀·실패0·준비 오류0입니다. 과거 검증 담당이 인계한 실패22개가 모두 이 실행에 포함돼 통과했습니다. 전체 여행 시험의 최신 인수 완료를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 선택 회귀 | 통과·건너뜀 | 218/229 = 95% |
| 인계 실패 재검증 | 통과 | 22/22 = 100% |
| 실행 소스 안정성·DB 종료 | 확인 | 2/2 = 100% |

## 실제 변경

고객 파기 때 OAuth 기록·운영 진단 고객 연결을 지웁니다. 보존 Case의 외래키 때문에 고객 행이 남으면 외부 식별자를 erased:<UUID>로 바꾸고 진단 이벤트의 고객 참조를 비웁니다. 파기 전 SQLite에 대기하던 이벤트도 재전송 시 거부하므로 개인정보 연결을 되살리지 않습니다. 집계 숫자와 보존 Case는 삭제하지 않습니다. 격리 DB의 실제 파기·재전송 시험으로 확인했습니다.

자동 일정 조정 시험은 설문 응답과 자동 변경 동의를 명시했습니다. 미응답 기본 꺼짐 계약은 유지했습니다. 실제 조립에 등록된 식당·이동 제공자를 시험 대역으로 교체하고 방문 시각·종료 구간을 전달했습니다. 플러그인 비활성 상태에서도 읽는 접수 복원 메타데이터를 조회 경계에 반영했습니다. 평가 문구는 여행 예약을 기준으로 검사합니다. 공개 OAuth GET/POST는 서로 다른 operation_id를 선언했습니다.

중형 택시 23:30·5km의 검산 기대값은 10,300원으로 바로잡았습니다. 기존 10,400원은 4,800원에 40%를 곱한 6,720원을 기본요금으로 사용한 결과였습니다. [서울시 공식 요금](https://news.seoul.go.kr/traffic/archives/1659)의 23~02시 기본요금 6,700원과 131m당 140원을 적용하면 6,700+ceil(3,400/131)×140=10,340원이며 100원 단위 규칙에 따라 10,300원입니다. 실제 계산 코드는 이미 이 규칙을 따르므로 바꾸지 않았습니다. [서울시 물가정보](https://sftc.seoul.go.kr/seoul/mulga/main/contents.do?menuNo=200023)와도 대조했습니다. 실제 요금 예측 정확도 전체를 통과로 바꾸는 근거는 아닙니다.

## 원본과 한계

- [JUnit](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_054657_390668_isolated_integration/junit.xml)
- [종료·소스·연결 결과](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_054657_390668_isolated_integration/result.json)
- [전용 PostgreSQL 종료](../../../../program/research/baseline_completion_2026-10-12/tasks/integration/checks/2026-10-12_054657_390668_isolated_integration/cleanup.json)
- [변경 전 백업](../../../_backup/2026-10-12_0544_remaining_integration/)

11개 PGlite 시험은 패키지 전제가 없어 건너뛰었습니다. 별도 PostgreSQL 경쟁·복구8개와 새 식당 정책20개는 통과했습니다. 앞선 176통과·4실패 실행과 변경 중 소스는 보존합니다. 업무 DB·배포·원격 재시작·고객 통지·유료 API는 수행하지 않았습니다. 최신 전체 공통·여행, 자료 전제16개, 초기 분류·라우팅 진단 경계는 후속 확인 대상입니다.

mock 서버 시험(화면 반응): 이번 실행은 화면 시험이 아닙니다.

실서버 확인(서버 응답): 외부 제공처·cs 프로젝트 서버의 실제 응답을 새로 확인하지 않았습니다. 격리 PostgreSQL만 실행했습니다.
''', encoding='utf-8')
state = json.loads((HERE/'status.json').read_text(encoding='utf-8'))
state['updated_at_kst'] = now.isoformat()
state['tests'].append(dict(passed=218,failed=0,skipped=11,total=229,evidence=(run/'junit.xml').relative_to(ROOT).as_posix()))
state['latest_review_report'] = report.relative_to(ROOT).as_posix()
state['backup'] = backup.relative_to(ROOT).as_posix()
state['changed_files'] = sorted(set(state['changed_files']) | {report.relative_to(ROOT).as_posix(),Path(__file__).relative_to(ROOT).as_posix()})
(HERE/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (HERE/'report.md').open('a',encoding='utf-8') as f:
    f.write(f'\n## {now.isoformat()} 개인정보·여행 회귀\n\n218통과·11건너뜀, 인계22실패 모두 재검증 통과. 실행 소스 불변·전용 DB 종료 확인. [{report.name}](../../../../../final_project_cs/wiki/records/reports/{report.name}). 전체 인수는 미완료입니다.\n')
print(report.relative_to(ROOT).as_posix())
