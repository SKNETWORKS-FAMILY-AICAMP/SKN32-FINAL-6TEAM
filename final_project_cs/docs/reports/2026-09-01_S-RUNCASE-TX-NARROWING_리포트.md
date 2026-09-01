# S-RUNCASE-TX-NARROWING — `run_case()` 의 트랜잭션을 LLM 호출 바깥으로 좁힌다

- 대상 결함: [`docs/reports/debugs/2026-09-01_Controller가_LLM호출을_트랜잭션_안에서_한다.md`](debugs/2026-09-01_Controller가_LLM호출을_트랜잭션_안에서_한다.md)
- 같은 종류의 앞선 수정: Case 생성 경로의 인라인 분류
  (`app/application/classification.py`, `app/presentation/api/cases.py::create`,
  v8 §3-A [2026-09-01 교정] 결함 2). 이번 것은 **같은 결함의 Controller 판**이다.

## 무엇이 문제였나

`Controller.run_case()` 가 `with conn.transaction():` 을 열고 그 안에서
`team_executor.execute(task)` 와 `_maybe_review(...)` 를 `await` 했다. 두
호출 모두 실제 OpenAI 네트워크 호출로 이어질 수 있고, 최대
`reliability.team_timeout_seconds` 만큼 걸린다.

결함 리포트가 든 세 가지 위험 중 **두 가지는 실측으로 확인됐고, 하나는 정정한다.**

| 리포트의 주장 | 실측 판정 |
|---|---|
| LLM 타임아웃·예외가 `start_run()` 의 실행 시작 기록까지 롤백한다 | **사실.** 아래 §"수정 전후 실측" 1행 — `agent_runs` 가 **0행**이었다 |
| 같은 Case 에 대한 동시 쓰기가 그동안 막힌다 | **사실이되 모양이 다르다.** UPDATE 잠금에 걸려 기다리기 **전에**, ROUTED 전이가 아직 커밋되지 않아 다른 커넥션은 옛 version(2)을 본다 → 그 커넥션이 `StateConflict` 로 즉시 튕긴다. 3행 참고 |
| 커넥션 풀에서 커넥션을 붙잡아 풀 고갈로 이어진다 | **부정확.** `app/infrastructure/db/session.py::get_connection` 은 풀이 아니라 호출마다 `psycopg.connect()` 를 새로 연다. 고갈 대상은 애플리케이션 풀이 아니라 **서버 `max_connections`** 다. 위험은 남지만 이유가 다르므로 그대로 적어 둔다 |

## 무엇을 고쳤나

`app/application/controller.py::run_case()` 를 세 토막으로 나눴다.

```
A. start_run · ROUTED · RESUMED · wall-clock 가드   ← 짧은 트랜잭션, 커밋하고 나간다
B. _task() · Team 실행 · 리뷰 패스                  ← 트랜잭션 밖. 외부 네트워크가 여기 있다
C. _apply_result · finish_run                      ← 다시 짧은 트랜잭션
```

`_task()` 안의 RAG 검색은 자기 커넥션을 쓰고, `case_service.checkpoint()` 는
순수 함수라 DB 를 건드리지 않는다. 그래서 B 단계 동안 이 커넥션에는 열린
트랜잭션이 없다.

### ★단계마다 `conn.commit()` 이 필요한 이유 (여기서 한 번 틀릴 뻔했다)

`with conn.transaction():` 만으로는 A 가 커밋되지 않는다. `run_case()` 는 그
앞에서 `repository.get_case()` 를 부르는데, psycopg3 의 비-autocommit 커넥션은
그 SELECT 하나로 이미 암묵 트랜잭션을 연다. 그 상태에서 `conn.transaction()` 은
새 트랜잭션이 아니라 **SAVEPOINT** 로 열리고, 블록을 나가도 커밋되지 않는다 —
경계를 좁힌 효과가 통째로 사라진다. 그래서 각 단계는 명시적 `conn.commit()` 으로
닫는다. `resume()` 이 이미 같은 이유로 명시적 commit 을 쓰고 있었다
(`controller.py` 의 "The connection context may roll back..." 주석).

커넥션은 하나(`with self.connection_factory() as conn:`)를 그대로 쓰고 그 안에서
트랜잭션 블록을 여러 번 연다 — `cases.py::create` 가 생성 트랜잭션과
`classify_case` 를 나눈 것과 같은 모양이다. 단계마다 커넥션을 새로 여는 쪽은
택하지 않았다: 이 저장소의 선례가 아니고, 위 표대로 여기엔 풀이 없어서 얻는 것도
없다.

## StateConflict 를 어떻게 다루기로 했나 (결함 리포트 §권고 2)

**`_apply_result` 는 `_transition_with_retry` 를 쓰지 않는다. 재시도하지 않는다.**

A 를 커밋하고 나면 Team 실행 중에 다른 쓰기가 같은 Case 를 바꿀 수 있게 된다 —
전에는 잠금이 막고 있던 창이 실제로 열린다. 그때 C 의 `transition_case` 는
`StateConflict` 를 받는다. 여기서 최신 version 을 다시 읽어 **같은 payload 를**
밀어 넣는 것이 `_transition_with_retry` 가 하는 일인데, 결과 반영에는 그게 맞지
않는다.

- `_transition_with_retry` 를 쓰는 전이(ROUTED · ROUTING_FAILED · VALID_INPUT)는
  payload 가 Case 내용에 의존하지 않는 **장부성 전이**다. version 만 갈아 끼워도
  뜻이 변하지 않는다.
- 결과 반영은 다르다. 답변 문장과 `ActionProposal` 은 **우리가 읽은 스냅샷**을
  근거로 만들어졌고, `_reject_unverified` 의 사실 대조도 그 스냅샷 기준이다.
  version 이 밀렸다는 것은 그 근거가 더 이상 사실이 아닐 수 있다는 **증거**다.
  확인하지 않은 상태 위에 답을 얹지 않는다(`CLAUDE.md` §0.1).

그래서 진 쪽은 **이긴 쪽 상태를 그대로 두고 물러난다**: 실행을 `failed` 로 닫고,
`logger.warning` 을 남기고, `{"stale": True, "status": <최신>, "version": <최신>}`
를 돌려준다. `resume()` 이 같은 종류의 경합(`InvalidTransition`)을 다루는 방식과
같은 모양이다 — 조용히 삼키지 않되, 이긴 쪽을 덮지도 않는다.

`asyncio.TimeoutError` 경로도 같은 규칙을 따른다. Team 을 부른 **뒤의** 전이는
전부 평범한 `transition_case` 로 하고, 거기서 나온 `StateConflict` 는 위 한
군데에서 처리한다. 규칙이 하나여야 다음 사람이 헷갈리지 않는다.

## 트랜잭션을 좁히면서 **새로 생긴 책임** — `_abandon_run()`

전에는 어떤 예외든 트랜잭션 전체가 롤백돼 `agent_runs` 행 자체가 사라졌고, 그래서
그 Case 를 다시 돌릴 수 있었다. 이제 그 행은 **살아남는다** — 그게 이 수정의
목적이다. 대신 `active` 로 둔 채 나가면 활성 실행 유일성(`INV-CS-RT-011`,
`004_agent_runs_active_uniqueness.sql`)이 그 Case 를 **영원히** 막는다.

그래서 B·C 를 감싸는 `except BaseException:` 이 `_abandon_run()` 으로 실행을
`failed` 로 닫고 원래 예외를 다시 던진다. `CancelledError` 도 닫아야 하므로
`Exception` 이 아니라 `BaseException` 이다. `_abandon_run()` 자체가 실패하면
(커넥션이 죽은 경우) `logger.exception` 으로 남기고 원래 예외를 가리지 않는다.

`INV-CS-RT-011` 은 오히려 더 곧게 지켜진다. 전에는 A 의 `SELECT ... FOR UPDATE`
잠금이 실행 내내 걸려 있어 경쟁자가 **기다렸다**. 지금은 `active` 행이 커밋돼
있으므로 경쟁자가 그 행을 곧바로 보고 `ActiveRunError` 로 즉시 튕긴다.
`tests/integration/controller/test_active_run_uniqueness.py` 는 `CaseService` 를
직접 쓰므로 이 변경과 무관하게 그대로 통과하고, 여전히 부분 유니크 인덱스가
INSERT 경합을 중재하는지를 검사한다(무의미해지지 않았다).

## 수정 전후 실측

새 테스트 3건을 **수정 전 `run_case()`** (한 트랜잭션 판)에 그대로 걸어 봤다.
임시 파일로 옛 구현을 인스턴스에 다시 묶어 돌리고 지웠다.

| 검사 | 수정 전 | 수정 후 |
|---|---|---|
| Team 예외 뒤 `agent_runs` 행 | `[]` — 시도했다는 기록이 통째로 사라졌다 | `[('failed', True, True)]` |
| Team 예외 뒤 재실행하면 남는 실행 기록 | `['succeeded']` — 실패한 시도가 흔적이 없다 | `['failed', 'succeeded']` |
| Team 실행 중 다른 커넥션의 쓰기 | `StateConflict: expected=3 actual=2` — 커밋 안 된 ROUTED 가 안 보여 경쟁자가 튕긴다 | 통과. 이 실행은 `stale` 로 물러난다 |

3행이 이 수정의 핵심 주장이다. **"트랜잭션을 좁혔다" 는 코드를 읽어서가 아니라
다른 커넥션이 그 시간 동안 실제로 쓸 수 있는가로 판정한다.** 회귀가 나도 테스트가
매달리지 않도록 그 커넥션에 `SET lock_timeout = '3s'` 를 건다.

## 테스트

- 새 파일 `tests/integration/controller/test_run_case_transaction_boundaries.py` 3건.
- 기존 테스트의 assert 는 **한 줄도 바꾸지 않았다.**
- 전체: **508 passed → 513 passed** (`-m "not live"`, skipped 0 · failed 0 ·
  xfailed 1 · deselected 4). 늘어난 5건 = 이 작업 3건 + 다른 세션 커밋
  `0a8d454`(DoD-29 테스트) 2건.

## 남긴 것

- 새 테스트에 `# invariant:` 표식을 달지 않았다. 불변식 대장은
  `program/final_project_cs/wiki/quality/invariants.md` 에 있고 지금 다른 세션이
  편집 중이다. 새 id 를 여기서 임의로 발급하면 대장과 어긋난다 — 대장 쪽에서
  발급하고 표식을 다는 것이 맞다.
- 결함 리포트 §권고 4(`response_review.enabled` 를 켜기 전 처리)는 이것으로
  해소됐다. 리뷰 패스도 B 단계, 즉 트랜잭션 밖이다.
