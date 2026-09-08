# Controller가 LLM 호출을 트랜잭션 안에서 한다

## 해결됨 (2026-09-01)

수정 리포트: [`wiki/records/reports/2026-09-01_S-RUNCASE-TX-NARROWING_리포트.md`](../2026-09-01_S-RUNCASE-TX-NARROWING_리포트.md)

아래 "권고 방향" 1~4를 그대로 따랐다. `run_case()`를 A(시작·커밋) /
B(Team 실행, 트랜잭션 밖) / C(결과 반영, 새 트랜잭션)로 쪼갰고,
`_apply_result`의 `StateConflict`는 **재시도하지 않고** 이긴 쪽 상태를 둔 채
실행만 `failed`로 닫기로 결정했다(이유는 리포트 §"StateConflict를 어떻게
다루기로 했나"). `test_active_run_uniqueness.py`는 그대로 통과하며 여전히
같은 불변식을 잡는다.

★"왜 문제인가" 세 항목 중 커넥션 풀 이야기는 **부정확**했다 —
`get_connection()`은 풀이 아니라 호출마다 새 커넥션을 연다. 나머지 둘은
실측으로 확인됐고 전후 수치가 리포트에 있다. 아래 서술은 당시 기록 그대로 둔다.

---

- 발견 경위: 계획서 §3-A 개정 근거(다른 세션이 v8 baseline 문서 작업 중 실측)로
  relay된 주장 두 건 중 하나. "voc: false로 기동 불가"는 확인하는 사이 다른
  세션이 `app/application/feedback_job.py`의 `require_module("voc")`를 이미
  제거해 해소됐다(2026-09-01, "인라인 분류와 똑같은 범주 오류"). 이 문서는
  남은 한 건만 다룬다.
- 판정: **실재, 미수정**. `wiki/records/reports/debugs/` 관례대로 재현 코드 위치를
  적고, 직접 고치지는 않았다 — 이유는 아래 "왜 지금 안 고쳤는가".

## 재현

`Controller.run_case()` (`app/application/controller.py:113-171`):

```python
async def run_case(self, *, tenant_id: str, case_id: UUID, actor_id: str = "controller") -> dict[str, Any]:
    started = time.monotonic()
    with self.connection_factory() as conn:
        case = self.repository.get_case(conn, tenant_id=tenant_id, case_id=case_id)
        ...
        with conn.transaction():                              # ← 119: 여기서 연다
            run_id = self.case_service.start_run(conn, ...)
            ...
            result: TeamResult = await asyncio.wait_for(
                self.team_executor.execute(task), ...)         # ← 156: LLM 네트워크 호출이 여기 안에서 await 된다
            ...
            result = await self._maybe_review(task, result)    # ← 167: 리뷰 패스도 마찬가지
            transition = self._apply_result(conn, case, run_id, result, actor_id, context=task.context)
            self.case_service.finish_run(conn, run_id, "succeeded")
            return {...}                                       # ← with 블록이 여기서 끝나며 트랜잭션이 닫힌다
```

`team_executor.execute(task)`가 `response_generation_review` Team으로 라우팅되면
`ResponseGenerationReviewTeam.execute()` → `self.llm.complete(...)`
(`app/infrastructure/llm/openai.py:83`, `await asyncio.to_thread(call)`)로
이어져 OpenAI API를 실제로 부른다. `config/project.yaml`에서 이 Team은
`active: true`로 등록돼 있어 **리뷰 패스(`_maybe_review`)뿐 아니라 primary
owner Team으로도 라우팅될 수 있다** — `response_review.enabled: false`인
지금도 이 경로가 죽어 있지 않다.

즉 이 요청은 하나의 열린 Postgres 트랜잭션 안에서 최대
`reliability.team_timeout_seconds`(가드레일 설정값)만큼 걸리는 외부 네트워크
호출을 `await`한다.

## 왜 문제인가

- 트랜잭션이 열려 있는 동안 커넥션 풀에서 커넥션 하나를 계속 붙잡는다.
  동시 Case 처리량이 늘면 커넥션 고갈로 이어진다.
- `start_run()`이 잡는 활성 실행 유일성(`INV-CS-RT-011`,
  `tests/integration/controller/test_active_run_uniqueness.py`)이 이
  트랜잭션 범위에 걸려 있다면, LLM 호출이 오래 걸릴수록 같은 Case에 대한
  동시 재시도/재개 요청이 그만큼 오래 블록되거나 충돌한다.
- LLM 타임아웃·예외가 발생하면 트랜잭션 전체가 롤백된다 — `start_run()`이
  기록한 실행 시작 사실까지 함께 사라진다. 실행이 시도됐다는 감사 기록 자체가
  안 남을 수 있다.

## 왜 지금 안 고쳤는가

`run_case()`는 이 저장소에서 가장 안전 규칙이 몰린 지점이다
(`CLAUDE.md` §0.3 "상태는 한 문으로만 바뀐다", 낙관적 잠금
`expected_version`, `StateConflict` 재시도, outbox 발행이 전부 이 메서드
안에 있다). 트랜잭션 경계를 좁히려면 "시작 단계(커밋) → Team 실행(트랜잭션
밖) → 결과 반영 단계(새 트랜잭션)"로 쪼개야 하는데, `_apply_result`가 지금
`_transition_with_retry` 없이 `transition_case`를 직접 부른다 — 트랜잭션을
쪼개면 그 호출도 재시도 경로가 필요해지는지 다시 판단해야 한다. 이걸
세션 하나에서 서두르면 "오진 위에 수정을 쌓지 않는다" 원칙을 어긴다.
재현 지점과 위험을 여기 남기고, 별도 세션에서 집중해서 다룬다.

## 권고 방향 (다음에 손댈 때)

1. `run_case()`를 세 단계로 쪼갠다 — start(커밋) / execute(트랜잭션 밖) /
   apply(새 트랜잭션, 필요하면 `_transition_with_retry`로).
2. `_apply_result` 호출부가 `StateConflict`를 만났을 때의 처리를
   (현재: 트랜잭션 롤백에 의존) 명시적 재시도로 바꿀지 결정한다.
3. `tests/integration/controller/test_active_run_uniqueness.py`가
   커넥션 경계 변경 후에도 여전히 같은 불변식을 잡는지 확인한다.
4. `response_review.enabled`를 켜기 전에 반드시 먼저 처리한다 — 지금은
   기능이 꺼져 있어 리뷰 패스 쪽 위험은 잠재적이지만, primary 라우팅 경로는
   이미 살아 있다.
