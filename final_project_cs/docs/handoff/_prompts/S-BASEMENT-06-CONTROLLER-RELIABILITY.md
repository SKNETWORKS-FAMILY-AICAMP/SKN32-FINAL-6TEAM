# S-BASEMENT-06-CONTROLLER-RELIABILITY — WAIT_EXPIRED commit 누락 + 데드라인 강제

## 0. 배경

★**경로 주의**: 이 작업은 `-C final_project_cs` 로 실행된다. sample 은
`final_project_cs` 의 하위가 아니라 **형제 디렉터리**다 — 참고할 정확한
경로는 `../final_project_sample/acop_basement/application/controller.py`
와 `../final_project_sample/acop_basement/core/remote_team/a2a_executor.py`
다(`app/` 가 아니라 `acop_basement/` 밑이다. `final_project_sample/` 를
`app/` 하위 상대경로로 찾으면 못 찾는다). `final_project_sample/.pytest_cache`
는 접근 거부되니 그 경로는 건드리지 마라(무관하다).

이전 dispatch 시도는 이 경로 혼동 때문에 tool 호출을 여러 번 반복하며
세션이 끝까지 못 가고 중단됐다(코드 변경 0건, 리포트 미생성). 이번엔
위 정확한 경로로 바로 읽고 빠르게 진행해라.

`final_project_sample/acop_basement/` (참고용, **절대 수정 금지**) 와
cs 대조에서 발견됨.

### 참고: cs 현재 코드의 정확한 위치 (`final_project_cs/app/application/controller.py`)

`resume()` 메서드 내부, stale 토큰(`ResumeTokenError`) 처리 지점:

```python
            except ResumeTokenError as exc:
                with conn.transaction():
                    transition_case(conn, tenant_id=tenant_id, case_id=case_id, expected_version=case["version"], event_type=EventType.WAIT_EXPIRED,
                                    payload={"wait_reason": (case.get("state_json") or {}).get("wait_reason", "customer_input")}, actor_type="controller", actor_id=actor_id)
                raise ControllerError(str(exc)) from exc
```

`conn.transaction()` 은 psycopg3 의 서브트랜잭션(savepoint) 컨텍스트다 —
이 블록을 정상적으로 빠져나가도 **바깥 연결 자체가 commit 되는 게
아니다**. 그 직후 `raise ControllerError` 가 나가면서 바깥
`with self.connection_factory() as conn:` 이 예외를 보고 전체를
rollback 하면 이 WAIT_EXPIRED escalation 도 함께 사라진다 — 그래서
`raise` 직전에 명시적 `conn.commit()` 이 필요하다.

`InvalidTransition` 은 `app/core/contracts.py` 에 정의돼 있고,
`resume()` 안의 `_transition_with_retry(...)`(VALID_INPUT) 나 그 뒤
`transition_case(...)`(RESUMED) 호출에서 발생할 수 있는데 지금
`resume()` 안에 이 예외를 잡는 코드가 없다 — 이미 resolved 된 Case 에
stale 토큰으로 재시도하면 (`validate_resume` 를 통과했더라도 그 사이
다른 경로로 이미 상태가 바뀌었으면) 이 지점에서 크래시한다.

### 1) `app/application/controller.py` — WAIT_EXPIRED 전이 후 commit 누락

- WAIT_EXPIRED escalation 전이를 실행한 뒤 명시적 `conn.commit()` 이
  없다. 이후 같은 연결 컨텍스트에서 다른 에러(`ControllerError`)가
  나서 바깥에서 롤백되면, **이 escalation 자체가 조용히 롤백**돼서
  Case 가 `waiting_input` 에 그대로 갇힌다(사람 눈엔 아무 일도 안
  일어난 것처럼 보인다).
- 같은 함수에 이미 해결된 Case 에 stale 토큰으로 재시도하면
  `InvalidTransition` 이 나는데, 이걸 안 잡아서 **예외로 죽는다**
  (우아하게 실패해야 하는데 크래시한다).

### 2) `app/core/remote_team/a2a_executor.py` — 데드라인 미강제

- 지금은 루프 반복 사이에서만 데드라인을 확인한다. 원격 `submit()`/
  `poll()` 호출 하나가 응답 없이 오래 걸리면(hung), 그 호출 자체는
  안 끊겨서 선언된 데드라인을 훨씬 넘길 수 있다.
- sample 은 각 원격 호출을 **남은 시간**(`deadline - now()`)만큼의
  `asyncio.wait_for()` 로 감싸고, 포기할 때 원격에 best-effort 취소
  요청도 보낸다.

## 1. 할 일

1. `controller.py` 의 WAIT_EXPIRED 전이 직후 명시적 `conn.commit()`
   을 추가해라(이 함수의 다른 전이 경로가 이미 commit 하는 패턴이
   있다면 그 패턴을 따라라 — 일관성 있게).
2. 같은 함수(또는 호출부)에 `except InvalidTransition: pass`(또는
   이 프로젝트의 실패 처리 관례에 맞는 형태)를 추가해서, 이미
   해결된 Case 에 대한 stale 재시도가 크래시 대신 조용히 무시되게
   해라(단, **완전히 조용한 건 아니다** — `CLAUDE.md` §3 "조용한
   스킵을 만들지 않는다" 원칙대로, 이 경우를 로그나 카운트로 남겨라).
3. `a2a_executor.py` 의 각 원격 `submit()`/`poll()` 호출을
   `asyncio.wait_for(call, timeout=remaining)` 로 감싸라(`remaining
   = deadline - now()`, 이미 지났으면 즉시 타임아웃 처리). 포기할 때
   원격 취소를 best-effort 로 시도해라(실패해도 무시 — 이미 포기하는
   중이니까).

## 2. 검증

- WAIT_EXPIRED commit 누락: 재현 테스트로 "escalation 후 바깥에서
  롤백이 일어나도 Case 상태가 유지되는지" 확인해라.
- stale 토큰 재시도: 이미 resolved 된 Case 에 재시도했을 때 크래시
  없이 처리되는지 테스트해라.
- a2a 데드라인: 원격 호출이 데드라인을 넘기도록 mock 해서(sleep 등),
  실제로 데드라인 안에서 timeout 처리되는지 확인해라.
- `python -m pytest -q -m "not live"` 결과를 리포트에 붙여라(359 passed
  기준 변화 명시).

## 3. 쓰기 대상

- `app/application/controller.py` (WAIT_EXPIRED/commit/except 관련
  부분만 — `response_review`/`_maybe_review()` 는 건드리지 마라, 이건
  DoD-29 기능이고 오늘 다른 작업으로 이미 완성됐다)
- `app/core/remote_team/a2a_executor.py`
- 관련 테스트 파일들
- `docs/reports/2026-08-24_S-BASEMENT-06-CONTROLLER-RELIABILITY_리포트.md` (신규)

## 4. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- `controller.py` 의 `response_review`/`_maybe_review()` 관련 코드
  수정 금지
