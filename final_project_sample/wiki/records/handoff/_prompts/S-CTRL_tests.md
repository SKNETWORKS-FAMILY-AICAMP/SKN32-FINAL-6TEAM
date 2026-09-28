# Codex — S-CTRL **테스트만** 작성 (코드는 이미 있다)

## 0. 상황

지난 작업에서 코드는 만들었지만 **테스트를 하나도 만들지 않았다.**
리포트에 이렇게 썼다:

> "Controller 통합 테스트 디렉터리가 소유 범위에 없어서 실행할 테스트가 없었습니다."

★**오독이다.** 지시서 §1 소유 범위에 `tests/integration/controller/**` 가 **명시돼 있었다.**
이번 작업의 소유 범위에도 들어 있다. 아래를 확인하라.

## 1. 소유 범위 — **여기에만** 쓴다

```
tests/integration/controller/**        ← ★이번 작업의 산출물. 반드시 만든다
wiki/records/reports/ , wiki/records/history/
```

★그 밖 **전부 금지**. 특히 이미 완성된 코드를 고치지 마라:
`app/application/**`, `app/core/**`, `app/infrastructure/**`, `app/modules/**`,
`app/presentation/**`, `knowledge/**`, `eval/**`, `scripts/**`.

★**테스트를 통과시키려고 제품 코드를 고치지 마라.**
테스트가 결함을 드러내면 **고치지 말고 리포트에 적어라.** 그게 이번 작업의 목적이다.

## 2. 현재 상태 (실측 2026-08-12)

```
python -m pytest tests -q   →  99 passed, skipped 0
```

정적 검사 결과 (Claude 확인):
- `UPDATE customer_cases` / `case_events` 변경 **0건** (transition_case 우회 없음)
- `transition_case` 7회 사용 · `FOR UPDATE SKIP LOCKED` 있음 · hash 저장 있음
- `StateConflict` 처리 3곳 · `retrieval_failed` 전파 3곳 · dead-letter 있음
- `app/core/` 가 `app.modules` 를 import 하지 않음 (격리 유지)

**구조는 맞다. 이제 동작을 증명해야 한다.**

## 3. 만들 테스트 (8종) — `tests/integration/controller/`

읽어야 할 것: `app/application/controller.py`, `case_service.py`, `app/core/registry.py`,
`app/infrastructure/messaging/{outbox,worker,ports}.py`, `app/core/transition.py`,
`app/modules/customer_ops/{billing,technical}.py`

1. ★**end-to-end 시나리오 1 (해지 후 추가 결제)**
   Case 생성 → `classifying` → `routing` → Billing Team → `waiting_approval` →
   REST approve → `resuming` → `running` → `resolved`
   ★**상태·version 순서를 리스트로 단언**하라 (예: `[('classifying',1),('routing',2),...]`)

2. ★**end-to-end 시나리오 2 (Free/Pro 권한 불일치)**
   Technical Team → 진단·해결절차 응답 → `resolved`. **실권한 변경이 없음**을 DB 로 확인
   (`entitlements` 행이 변하지 않아야 한다)

3. ★**replay 동치성 (DoD 3)** — `customer_cases` projection 을 지우거나 무시하고
   `replay_case()` 로 재생 → **동일 status·version**

4. ★**outbox 원자성 (DoD 12)** — transition 도중 예외를 주입해 롤백되면
   `case_events` 와 `outbox` **둘 다 행이 없어야 한다** (하나만 남으면 실패)

5. ★**outbox 중복 차단** — 같은 `(topic, dedupe_key)` 2회 발행 → 행 **1개**,
   worker 가 **1회만** 전달

6. ★**resume token** — ① 재사용 시 거부 ② TTL(24h) 만료 시 `escalated`
   ③ **평문이 DB 에 저장되지 않음**(hash 만)

7. ★**loop guard** — 동일 tool + 동일 arguments 2회 반복 → `escalated`

8. ★**동시 전이 경합** — 같은 `expected_version` 으로 2요청 →
   1건 성공, 1건 `StateConflict`

## 4. 규칙

- ★**LLM 은 fake 주입**으로 결정적으로 돌린다. 실제 OpenAI 호출 금지
  (지난 실행에서 네트워크 차단으로 3건이 실패했다 — 테스트가 외부에 의존하면 안 된다)
- ★**임베딩 호출도 하지 마라.** 정책 검색이 필요하면 fake retriever 를 주입하거나
  이미 적재된 `knowledge_chunks` 를 쓰되, **질의 임베딩 호출을 회피**하라
- ★`pytest.skip` **금지.** 데이터가 없으면 fixture 로 만들고, 그래도 안 되면 **fail**
- ★테스트 전용 tenant(`test_<uuid>`), teardown 에서 자기 행 전부 삭제 (FK 순서 주의)
- ★**`demo` tenant 데이터를 지우지 마라** — seed 다
- 기존 방식 참고: `tests/integration/db/test_db_integration.py`, `tests/integration/api/test_api_runtime.py`

## 5. 완료 조건 (실제로 돌리고 출력을 붙인다)

```powershell
python -m pytest tests -q                        # ★기존 99건 + 신규. skipped 0
python -m pytest tests/integration/controller -v
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

기대: `tenants=1`, **skipped 0**.
★**테스트가 실패하면 실패한 채로 보고하라.** 제품 코드를 고쳐서 초록으로 만들지 마라.

## 6. 리포트

`wiki/records/reports/2026-08-12_S-CTRL_테스트_리포트.md`:
1. §5 명령의 **실제 출력 원문**
2. 시나리오 1·2 의 **상태 전이 순서(status, version)**
3. ★**실패한 테스트가 있으면 무엇이 왜 실패했는지** — 이게 가장 중요한 산출물이다
4. 테스트할 수 없었던 항목과 그 이유

`wiki/records/history/2026-08-12_S-CTRL_tests.md` 이력 추가.

## 7. 하지 말 것

- ❌ 제품 코드 수정 (테스트를 통과시키려는 목적이든 아니든)
- ❌ `tests/integration/controller/` 밖의 테스트 파일 수정
- ❌ 실제 LLM/임베딩 호출
- ❌ `pytest.skip`
- ❌ 단언을 느슨하게 해서 통과시키기
- ❌ 실패를 숨기고 "전부 통과" 라고 쓰기
