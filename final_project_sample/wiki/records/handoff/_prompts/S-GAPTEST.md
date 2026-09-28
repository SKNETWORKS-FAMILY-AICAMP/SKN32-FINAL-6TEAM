# 구현 지시 — DoD 미검증 항목을 메우는 테스트 5종

## 0. 배경

DoD 판정에서 **"구현은 있는데 동작을 관측한 적이 없다"** 로 부분통과에 머문 항목이 5개다.
각 항목의 `wiki/records/evidence/DoD-NN_*.md` 마지막 절 **"재측정 조건"** 에 무엇이 필요한지 적혀 있다.
이번 작업은 그 조건을 만족시키는 **테스트를 추가**하는 것이다.

★**제품 코드를 고치지 마라.** 테스트가 결함을 드러내면 **고치지 말고 리포트에 적어라.**
그게 이 작업의 목적이다.

## 1. 소유 범위

```
tests/unit/core/**        (DoD-05)
tests/security/**         (DoD-07)
tests/integration/controller/**   (DoD-04)
tests/unit/voc/**         (DoD-10)
tests/e2e/**              (DoD-18)
wiki/records/reports/ , wiki/records/history/
```

★그 밖 **전부 금지**: `app/**`, `eval/**`(★다른 세션이 평가를 실행 중이다. **절대 열지 마라**),
`knowledge/**`, `scripts/**`, `config/**`, `wiki/records/evidence/**`.

## 2. 만들 테스트

### 2-1. DoD-05 — Context Broker 절삭 (`tests/unit/core/`)
`app/core/context.py` 의 `ContextBroker.build()` 를 **예산을 넘치는 입력**으로 호출한다.

1. `estimated_input_tokens <= 12000` 단언
2. ★`omissions` 에 **`similar_cases` 가 먼저** 들어간다 (제거 1순위, v5 §9-1)
3. ★`omissions` 에 **`case_state` 는 절대 없다** (제거 금지 섹션)
4. `system_instruction` 또는 `case_state` 가 예산을 넘으면 **`ContextBudgetError`**
5. 낮은 score 의 `PolicyChunk` 가 높은 것보다 먼저 빠진다

★LLM·임베딩 호출 없이 돈다 (`ContextInputs` 를 직접 만든다).

### 2-2. DoD-07 — PII redaction (`tests/security/`)
전화번호·카드번호 형태가 든 메시지로 Case 를 만들고:

1. `customer_cases`·`case_events` 에 **원문이 없고** masked 형태만 있는지 DB 로 확인
2. API 응답(`GET /v1/cases/{id}`)의 evidence 에 원문이 없는지
3. audit 성격 기록에 **API key 원문·결제 식별자 원문이 없는지**

★현재 구현이 masking 을 하지 않는다면 **테스트를 실패로 남기고 리포트에 적어라.**
통과시키려고 단언을 약화시키지 마라.

### 2-3. DoD-04 — checkpoint / projection 분리 (`tests/integration/controller/`)
1. run 을 실행해 `agent_runs` 에 행이 생기고 `graph_revision` 이 **채워지는지**
2. 한 run 안에서 `graph_revision` 이 **변하지 않는지** (시작 시 고정)
3. ★checkpoint 를 이전 노드 상태로 되돌려도 `customer_cases.status`·`version` 이
   **변하지 않는지**

### 2-4. DoD-10 — VOC 급증 alert 실데이터 (`tests/unit/voc/`)
fixture 가 아니라 **실제 Case 행**을 만들어 집계가 alert 를 내는지 본다.

1. 테스트 tenant 에 같은 `issue_code` 의 Case 를 **오늘 6건** 생성 (`intent`/`issue_code` 채움)
2. 직전 7일에는 소량만 생성해 평균을 낮춤
3. `feedback_job` 집계 실행 → ★`alerts` 가 **비어 있지 않음** 단언
4. 임계 바로 아래 시나리오에서는 alert 가 **없음** 단언

### 2-5. DoD-18 — UI 가 시나리오를 끝까지 보여준다 (`tests/e2e/`)
1. 시나리오 Case 를 `waiting_approval` 까지 만든 뒤
2. `/ui/cases` 목록에 그 Case 가 **보이는지**
3. `/ui/cases/{id}` trace 에 전이 이벤트가 **version 순으로** 나오는지
4. `/ui/approvals` 에 그 proposal 과 **rationale evidence 가 함께** 표시되는지
5. ★evidence 가 없는 proposal 은 **승인 버튼이 비활성**인지

## 3. 공통 규칙

- ★**테스트 전용 tenant**(`test_<uuid>`)를 쓰고 teardown 에서 자기 행을 전부 삭제 (FK 순서 주의)
- ★**`demo` tenant 를 지우지 마라** — seed 다
- ★`pytest.skip` **금지.** 데이터가 없으면 fixture 로 만들고, 그래도 안 되면 **fail**
- ★**실제 LLM/임베딩 호출 금지.** fake 주입으로 결정적으로
  (이 환경은 외부 네트워크가 막혀 있어 실제 호출은 어차피 실패한다)
- 기존 방식 참고: `tests/integration/db/`, `tests/integration/api/test_api_runtime.py`

## 4. 완료 조건

```powershell
python -m pytest tests -q
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

기대: **skipped 0**, `tenants=1`.
★**실패하는 테스트가 있으면 실패한 채로 두고 리포트에 원인을 적어라.**
기존 109건이 깨지면 그것도 적어라.

## 5. 리포트

`wiki/records/reports/2026-08-12_S-GAPTEST_리포트.md`:
1. 추가한 테스트 목록 (DoD 번호별)
2. §4 명령의 **실제 출력 원문**
3. ★**실패한 테스트와 그 원인** — 이게 가장 중요한 산출물이다
4. 테스트할 수 없었던 항목과 이유

`wiki/records/history/2026-08-12_S-GAPTEST.md` 이력 추가.

## 6. 하지 말 것
- ❌ `app/**` 등 제품 코드 수정
- ❌ `eval/**` 열기 (다른 세션 실행 중)
- ❌ `wiki/records/evidence/**` 수정
- ❌ `pytest.skip` / 단언 약화로 통과시키기
- ❌ 실제 LLM 호출
- ❌ 실패를 숨기고 "전부 통과" 라고 쓰기
