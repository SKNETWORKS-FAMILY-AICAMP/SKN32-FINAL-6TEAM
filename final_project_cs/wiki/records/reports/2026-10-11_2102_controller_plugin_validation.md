# Controller의 담당 실행 관문·재개 검증

로컬 코드에서 꺼진 담당 업무의 재개 입력·토큰·업무 상태를 보존하고, 실행을 시작한 뒤 원격 연결이 실패한 업무는 같은 요청으로 다시 실행하도록 보완했습니다. 운영 배포 완료를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 여행 재개·플러그인 불가·승인 회귀 | 로컬 DB 통과 | 44/44 = 100% |
| 담당 파일 린트 | 통과 | 7/7 = 100% |
| 운영 환경 반영 | 미실행 | 0/1 = 0% |

## 변경

- [Controller](../../../app/application/controller.py): 기존 담당 관문 뒤 읽기 전용 재배분, 최종 담당·기능 관문 뒤 `resume_prepare`, 그 뒤 입력 전이를 기록합니다. 재배분 함수에는 저장하지 않은 예상 재개 상태를 제공합니다. 꺼진 담당이면 유효한 토큰 만료 처리도 업무 상태를 바꾸지 않습니다.
- [대화 연결](../../../app/domains/travel_ops/components/conversation/case_dispatch.py): 후보 확보를 재배분 함수에서 분리해 최종 실행 관문 뒤로 옮겼습니다. 첫 담당 지정도 관문을 통과한 뒤 기록합니다.
- [Case API](../../../app/presentation/api/cases.py): 분류 뒤 확인된 담당 불가를 503과 case_id로 반환합니다. 같은 요청은 재활성화 뒤 실행 기록이 없는 routing 업무를 재접수할 수 있습니다. Case 조회는 기존 업무 상태와 별도로 현재 실행 불가 이유를 표시합니다.
- [공통 오류](../../../app/presentation/errors.py): 공개 코드 `team_unavailable`과 Team·이유를 유지하며 재시도 안내는 `remote_unavailable`에만 허용합니다.

원격 실행이 시작된 뒤 장애가 생기면 이미 기록한 입력을 없애지 않습니다. 실패한 실행 기록을 남기고, 같은 event의 입력이 이미 반영되어 있고 업무가 running이며 활성 실행이 없을 때 실행만 재시도합니다. 입력 전이·입력 이력·토큰 소비는 반복하지 않습니다. 재시도 경합은 기존 활성 실행 유일성 관문이 막으며 현재 상태를 반환합니다. 완료된 요청은 기존 멱등 응답을 유지합니다.

## 실제 검증

시험은 로컬 개발 DB의 고유 시험 테넌트를 만들고 종료 시 정리했습니다. 최초 샌드박스 실행은 DB 연결 권한 오류로 19개가 준비 단계에서 실패했습니다. 샌드박스 외부 실행 승인 뒤 실제 DB로 확인했습니다. mock 서버 시험은 이 작업에서 실행하지 않았습니다.

- [주 회귀 원문](../evidence/2026-10-11_1936_team_plugin_implementation/controller-regression-final.log): `tests/integration/controller/test_conversation_resume.py`, `test_plugin_unavailable.py`, `test_travel_approval_proposal_reaches_waiting.py` 43/43 통과.
- [후속 원문](../evidence/2026-10-11_1936_team_plugin_implementation/controller-retry-followup.log): 추가된 만료 토큰 보존 1개와 재시도·동시 답변·기존 만료 회귀를 포함한 16/16 통과. 앞 시험과 겹친 15개를 다시 전체 분모에 더하지 않았습니다. 두 실행에서 검증한 서로 다른 시험은 44개입니다.
- [신규 시험](../../../tests/integration/controller/test_plugin_unavailable.py) 14개: disabled/not_installed/load_failed × 토큰/고객 인증 재개 6개, 꺼진 최종 담당 1개, 꺼진 담당의 토큰 만료 1개, 후보 준비 순서 1개, 최초 웹 담당 관문 1개, 꺼진 팀 자동 라우팅 1개, 원격 실패 후 동일 요청 재시도 1개, 503·조회 표시 1개, 접수 후 재활성화 재시도 1개.
- 린트 명령: `python -m ruff check app/application/controller.py app/domains/travel_ops/components/conversation/case_dispatch.py app/domains/travel_ops/entry/trip_api.py app/presentation/api/cases.py app/presentation/errors.py tests/integration/controller/test_plugin_unavailable.py tests/integration/controller/test_conversation_resume.py` → `All checks passed!`

검증한 보존 항목은 Case 행·state_json·업무 이벤트·agent_runs와 Team 호출 횟수입니다. 후보 준비 콜백을 호출하지 않는다는 시험은 있으나 실제 모든 외부 자료 확보 경로가 쓰기 없이 중단됨을 증명하는 범위로 확대해 해석하지 않습니다. 실제 운영 API 호출·실제 원격 A2A 장애·운영 배포는 이 담당 범위에서 확인하지 않았습니다. SSE와 조립 판 고정·계산 연결 검증은 통합 담당 결과와 함께 판단해야 합니다.

## 보존과 참조

변경 전 원본은 [legacy 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_1936/)에 있으며 기존 여행 재개 시험도 같은 구조로 추가 보존했습니다. 커밋·푸시·배포는 하지 않았습니다.

- [실행 가용성 계약](../../teams/team-contract/plugin-availability.md)
- [수명 관리 계획](../../teams/team-plugin-lifecycle.md)
- [Sonnet 독립 검토 원문](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-review-attempt2.json)
