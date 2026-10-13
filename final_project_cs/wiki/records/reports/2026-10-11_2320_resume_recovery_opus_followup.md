# 재개 입력 저장 직후 중단 — Opus 후속 보완

답변 저장과 실행 시작 사이에 작업이 끊기면 같은 요청을 다시 보내도 진행되지 않는 문제를 단위 시험으로 재현하고 수정했습니다. 명시적 만료 토큰을 자동으로 실행하는 정책 변경은 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| DB 없는 신규 단위·HTTP 시험 | 통과 | 10/10 = 100% |
| 관련 회귀 포함 | 통과 | 70/70 = 100% |
| 수정 파일 린트 | 통과 | 2/2 = 100% |
| 이번 변경의 실제 DB 시험 | 미실행 | 0/1 = 0% |

## 범위와 판단

[Opus 후보 읽기 감사](2026-10-11_2313_plugin_v5_opus_readonly_audit.md)의 7개 지적을 모두 실행 확정으로 처리하지 않았습니다. 부모와 정한 이 작업의 분모는 두 경계입니다. ① VALID_INPUT 커밋 뒤 RESUMING에서 중단된 요청의 복구, ② 명시적 토큰 만료의 자동 진행 금지와 호출부의 원인 식별입니다. 대기 업무가 무관한 질문을 가져가는 문제·초기 실패 duplicate 응답은 부모, 감시 업무의 재시도는 다른 담당이 맡습니다.

현재 구현과 분리 후보 v5는 동일하게, 이미 저장한 event를 찾았을 때 RUNNING만 재실행 대상으로 취급했습니다. 운영 기준 사본은 VALID_INPUT과 RESUMED를 같은 트랜잭션에서 반영하므로 이번과 같은 RESUMING 틈이 없습니다. 현재 구현에서 첫 `run_case` 진입을 중단시키자 답변·토큰·event는 저장되고 상태는 RESUMING인데, 동일 답변 재전송은 실행 없이 그 상태만 반환했습니다. 이는 정상적인 만료 정책과 별개의 복구 결함입니다.

명시적 토큰의 TTL 만료는 WAIT_EXPIRED를 기록하고 자동 실행하지 않는 기존 계약을 유지합니다. 이전에는 호출부가 이 경우를 모든 ControllerError와 같은 종류로만 받았습니다. 만료만 구분할 수 있는 예외를 추가하되 기존 HTTP 오류 코드와 ControllerError 호환성을 유지했습니다. 모든 ControllerError를 401로 옮기는 기존 광범위 매핑의 재설계는 이 작업에 포함하지 않았습니다.

## 최소 수정

- [Controller](../../../app/application/controller.py): 저장된 동일 event의 재실행 조건을 RUNNING 또는 RESUMING으로 넓혔습니다. 활성 run 확인과 담당 Team 관문을 유지하고, 행 잠금을 푼 뒤 기존 실행 입구로 이어갑니다. VALID_INPUT·답변 이력·토큰은 다시 기록하지 않습니다.
- 같은 파일의 `ResumeExpiredError(ControllerError, ResumeTokenExpired)`는 유효 토큰 TTL 만료만 나타냅니다. 기존 `except ControllerError`와 새 `except ResumeTokenExpired` 양쪽에서 잡힙니다. 다른 토큰 오류를 만료라고 부르지 않습니다.
- [가용성 계약](../../teams/team-contract/plugin-availability.md)에 중단 복구·활성 실행 경합·만료 예외의 경계를 먼저 보완했습니다. 일반 Case의 동적 교차 Team 계산은 실행 중 확인될 수 있다는 앞선 정정도 유지합니다.

담당 Team 비활성이면 재시도를 막고 기존 저장 상태를 보존합니다. 토큰이 만료된 경우에도 비활성 담당 관문을 먼저 거절하는 기존 보호 경계는 바꾸지 않았습니다. 도메인 접수 입구가 자동 선택한 대기 업무의 만료 뒤 새 문장을 처리하는 정책은 Controller에서 임의로 구현하지 않았습니다.

## 시험과 한계

[신규 시험](../../../tests/unit/core/test_controller_resume_recovery.py)은 실제 CaseService의 토큰·event 검증, 실제 Registry의 Team 관문, 실제 Case 리듀서를 사용합니다. SQL 연결은 메모리 대역이며 `run_case` 시작 전 중단과 적용 결과는 시험 함수로 주입합니다. 따라서 이 10건을 실제 DB나 실제 Team 종단 실행 증거라고 부르지 않습니다.

수정 전에는 신규 6건 중 4건이 실패했고, 수정 직후 6/6이 통과했습니다. 이후 토큰 HTTP 호환·비활성 담당·다른 본문 request_id 충돌을 추가하여 신규 10건을 포함한 관련 70건이 3.71초에 통과했습니다. 명령은 다음과 같습니다.

```powershell
python -m pytest tests/unit/core/test_controller_resume_recovery.py tests/unit/core/test_plugin_availability.py tests/unit/core/test_case_reducer.py tests/unit/test_applied_action_answer.py -q
python -m ruff check app/application/controller.py tests/unit/core/test_controller_resume_recovery.py
```

확인한 조건은 답변·VALID_INPUT 1회, RESUMED 1회, 완료 뒤 재전송의 추가 적용 0회, 활성 run 존재 시 추가 실행 0회, 비활성 담당의 기존 입력 보존, ActiveRunError 경합의 진행 상태 반환, 명시적 잘못된/만료 토큰의 401 `invalid_resume_token`, 만료 입력 미적용입니다. 고객 DB·외부 서비스는 사용하지 않았습니다. 부모가 기존 전체 E2E를 실행하는 동안 DB 시험을 추가하지 말라고 정한 범위를 지켰습니다.

- mock 서버 시험: 실행하지 않음. 메모리 연결 대역을 쓰는 단위 시험과 프로세스 안의 FastAPI TestClient HTTP 시험입니다.
- 실서버 확인: 이번 보완으로 로컬 개발 서버 또는 x600 서버의 cs 프로젝트 서버를 호출하지 않았습니다.

## 근거와 백업

- [수정 전 실패 로그](../evidence/2026-10-11_1936_team_plugin_implementation/resume-recovery-unit-before-v1.log), [최소 수정 뒤 6건](../evidence/2026-10-11_1936_team_plugin_implementation/resume-recovery-unit-after-v1.log), [최종 70건](../evidence/2026-10-11_1936_team_plugin_implementation/resume-recovery-regression-v1.log)
- [Controller·계약·시험의 수정 전 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_231804_resume_recovery/)

후보 v5는 이 후속 수정으로 덮어쓰지 않았습니다. 후보 이식은 담당에게 정확한 세 변경 구간과 신규 시험을 전달했습니다. 운영 반영·커밋·푸시는 하지 않았습니다.
