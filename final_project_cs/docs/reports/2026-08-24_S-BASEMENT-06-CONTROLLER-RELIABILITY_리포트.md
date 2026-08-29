# S-BASEMENT-06-CONTROLLER-RELIABILITY — WAIT_EXPIRED commit 누락 + 데드라인 강제

★Codex 자체 리포트(전체 스위트 "364 passed, 3 failed, 11 errors")는
샌드박스 환경 문제(OpenAI 임베딩 외부 네트워크 차단, pytest tmp 디렉터리
접근 거부)로 수치가 부정확해 Claude 가 실 환경에서 직접 재실행한 아래
결과로 교체한다 — `CLAUDE.md` 의 "Codex 자체보고 신뢰 금지" 원칙.

## 변경 내용

- `app/application/controller.py`
  - `resume()`의 `ResumeTokenError` 처리 분기에서 WAIT_EXPIRED escalation
    전이 직후 명시적 `conn.commit()`을 추가했다. `conn.transaction()`은
    서브트랜잭션(savepoint)이라 그 블록을 정상적으로 빠져나가도 바깥
    연결 자체는 commit 되지 않는다 — 그 직후 `raise ControllerError`가
    나가면서 바깥 `with self.connection_factory() as conn:`이 예외를 보고
    전체를 rollback하면 이 escalation도 함께 사라지던 결함이었다.
  - 같은 지점을 `except InvalidTransition:`으로 감싸, 이미 `resolved`
    같은 종단 상태인 Case에 stale 토큰으로 재시도해 WAIT_EXPIRED 전이가
    거부될 때 크래시 대신 `logger.warning(...)`으로 남기고 원래
    `ResumeTokenError` 기반 `ControllerError`를 그대로 전달한다.
  - 정상 토큰 경로(`VALID_INPUT`→`RESUMED`)도 같은 방식으로 감쌌다 —
    토큰 검증을 통과한 뒤에도 다른 경로가 먼저 같은 Case를 전이시켜
    경합이 나면(`InvalidTransition`), savepoint를 롤백하고 "stale resume
    transition ignored"를 로그로 남긴 뒤 승자의 최신 상태를
    `{"stale": True, "status": ..., "version": ...}`로 반환한다 — 크래시
    없이, 조용히 무시하지도 않는다.
  - `response_review`/`_maybe_review()`는 수정하지 않았다(diff로 직접
    확인).
- `app/core/remote_team/a2a_executor.py`
  - 원격 `submit()`/`poll()` 각 호출을 `_call_within_deadline()`으로 감싸,
    `deadline_at - now()`만큼의 `asyncio.wait_for()` 타임아웃을 건다.
    이미 데드라인이 지났으면 호출 자체를 하지 않고 즉시 `None`을 반환한다.
  - 타임아웃(`None` 반환) 시 `_cancel_best_effort()`로 원격에 취소를
    시도하고(실패해도 무시), `remote_deadline_exceeded`로 실패 처리한다.
    루프 반복 사이의 기존 데드라인 검사는 그대로 유지된다.
- 신규 테스트 (`tests/integration/controller/test_controller_integration.py`,
  `tests/unit/ports/test_team_ports.py`)
  - `test_expired_resume_escalation_survives_outer_rollback`: 만료 토큰
    재시도 후 바깥에서 `ControllerError`가 나가도 Case가 `escalated`로
    실제 커밋돼 있는지 확인한다.
  - `test_stale_resume_on_resolved_case_is_handled_without_invalid_transition`:
    이미 `resolved`인 Case에 stale 토큰 재시도해도 크래시 없이 로그만
    남고 상태가 그대로인지 확인한다.
  - `test_valid_resume_race_invalid_transition_is_logged_and_ignored`:
    `_transition_with_retry`를 monkeypatch로 `InvalidTransition`이 나게
    만들어 정상 토큰 경로의 경합도 크래시 없이 `stale: True`를 반환하고
    로그가 남는지 확인한다.
  - `test_a2a_submit_timeout_is_bounded_by_task_deadline`: `submit()`이
    10초 sleep(hang)하는 mock에 30ms 데드라인을 줘도 0.5초 안에
    `remote_deadline_exceeded`로 끝나는지 확인한다.
  - `test_a2a_poll_timeout_is_bounded_and_best_effort_cancels_remote`:
    `poll()`이 hang해도 같은 방식으로 타임아웃되고 `cancel()`이 실제로
    호출되는지 확인한다.

`final_project_sample/`은 읽기만 했으며 수정하지 않았다.

## 검증 결과 (Claude 실 환경 직접 재실행)

### 대상 테스트

```text
python -m pytest -q tests/unit/ports/test_team_ports.py \
  tests/integration/controller/test_controller_integration.py \
  tests/integration/a2a
34 passed in 6.32s
```

### 전체 비-live 테스트

```text
python -m pytest -q -m "not live"
378 passed, 3 deselected, 18 warnings in 41.74s
```

실패·에러 0건. Codex가 보고한 "3 failed, 11 errors"는 이 작업의 코드
변경과 무관한 실행 환경 문제(외부 네트워크 차단·tmp 권한)였음을 실 환경
재실행으로 확인했다.

## 종합 — 6개 basement 이식 계약 전체 최종 확인

S-BASEMENT-01~06 모두 코드 적용 완료. 마이그레이션 003/004/005 번호
충돌 없음, 2회 재실행 idempotent 확인. 전체 비-live 스위트 최종
**378 passed, 0 failed** (작업 시작 전 기준 359 passed 대비 +19).

## 부록 — 재발송 경위

이 계약은 최초 dispatch가 sample 경로 혼동(`-C final_project_cs`인데
`final_project_sample/`을 `app/` 하위 상대경로로 찾으려 반복 시도)으로
세션이 코드 변경 0건인 채 중단됐다. 계약서에 정확한 상대경로
(`../final_project_sample/acop_basement/...`)와 cs 쪽 정확한 코드
위치·문제의 근본 원인을 명시해 재발송해 완료했다.
