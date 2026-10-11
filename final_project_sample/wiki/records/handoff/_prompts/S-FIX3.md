# 구현 지시 — 갭 테스트가 드러낸 3건 수정

전체 테스트 현재 **113 passed / 3 failed**. 그 3건을 고친다.
★**셋 중 하나는 테스트가 틀렸다.** 무엇이 틀렸는지 판단해서 맞는 쪽을 고쳐라.

## 소유 범위
```
app/presentation/**        (PII 마스킹)
app/core/context.py        (제거 순서)
app/modules/customer_ops/feedback.py   (필요 시)
tests/**
wiki/records/reports/ , wiki/records/history/
```
★`eval/**` **금지** — 다른 세션 작업 중. `knowledge/**`, `scripts/**`, `wiki/records/evidence/**` 금지.

---

## 결함 1 (★심각) — PII 가 평문으로 저장된다

`tests/security/test_pii_redaction_runtime.py` 실패:

```
E  assert '010-1234-5678' not in
E    'phone=010-1234-5678 card=4111 1111 1111 1111
E     api_key=sk-test-original-api-key payment=pay_original_987654 ...'
```

전화번호·카드번호·**API key**·**결제 식별자**가 전부 원문으로 DB 에 남는다.
v5 §9-3 과 §12 가 금지한 것이다. 상세: `wiki/records/reports/debugs/2026-08-13_1230_PII가_평문으로_저장된다.md`

### 고칠 것
1. **Case 생성 경로에서 저장 전에 마스킹**한다 —
   `customer_cases.subject`·`state_json`, `case_events.payload_json` **모두**
2. 마스킹 규칙을 **한 곳**에 모은다 (`app/presentation/security.py` 의 기존 `masked` 활용 또는 확장):
   - 전화번호 `010-1234-5678` → `010-****-5678`
   - 카드번호 `4111 1111 1111 1111` → `**** **** **** 1111`
   - 이메일 → 로컬파트 마스킹
   - ★**API key(`sk-...`)와 결제 식별자(`pay_...`)는 마스킹이 아니라 제거 또는 hash** —
     v5 §12 는 audit 에 **원문 기록 자체를 금지**한다
3. ★**LLM 에 넘기는 텍스트도 masked** 여야 한다 (분류기 입력 포함)
4. ★**테스트 단언을 약화시키지 마라.** DB 에 실제로 남은 값을 검사하는 지금 방식이 맞다

---

## 결함 2 — Context Broker 가 전역 제거 순서를 구현하지 않는다

`tests/unit/core/test_context_budget.py` 실패:
```
assert pack.omissions[0].startswith("similar_cases:")
E  실제: 'policy_rag:low_score:low#c1'
```

### 판단이 필요하다
`config/guardrails.yaml` 의 `context.eviction_order` 는
`similar_cases → history_detail → low_score_rag → duplicate_tool_facts` 다.

현재 `app/core/context.py` 는 **섹션별 예산에 각각 맞추는** 방식이라,
policy 가 자기 예산(3600)을 넘으면 similar_cases 에 여유가 있어도 policy 를 버린다.
총량 12,000 은 지키지만 **전역 제거 순서는 구현되지 않았다.**

### 고칠 것
전역 제거 순서를 구현한다:
1. 각 섹션을 자기 예산으로 채우되, **남는 예산은 공용 풀로 모은다**
2. 예산이 모자란 섹션은 풀에서 빌린다 (우선순위: tool_facts → policy_rag → history → similar)
3. 그래도 총량이 넘치면 **`eviction_order` 순서대로** 버린다
4. ★`case_state`·`system_instruction` 은 **절대 버리지 않는다** (넘치면 `ContextBudgetError`)
5. `omissions` 에 버린 것을 **버린 순서대로** 기록한다

★섹션별 "제거 순서"(오래된 fact부터 / 낮은 similarity부터)는 **유지**한다. 그건 맞다.

---

## 결함 3 — ★**테스트가 틀렸다**

`tests/unit/voc/test_feedback_runtime.py` 실패:
```
assert not boundary_report["alerts"]
E  실제: [{'avg7': 1.0, 'intent': 'billing', 'issue_code': 'runtime_boundary', 'today': 5}]
```

급증 규칙(v5 §14-3, `config/guardrails.yaml` §4):
```
today >= max(5, 1.5 * avg7)   AND   today - avg7 >= 3
```
`today=5, avg7=1.0` 을 넣으면:
- `max(5, 1.5) = 5` → `5 >= 5` ✓
- `5 - 1.0 = 4` → `4 >= 3` ✓

★**alert 가 나는 것이 맞다. 구현이 옳고 테스트의 기대가 틀렸다.**

### 고칠 것
`test_feedback_runtime.py` 의 **"경계에서 alert 없음"** 시나리오를 진짜 경계로 바꾼다.
두 조건을 각각 단독으로 깨는 값을 써라. 예:
- `today=4, avg7=1.0` → `4 >= max(5,1.5)` 실패 → alert **없음**
- `today=5, avg7=3.0` → `5 >= max(5,4.5)` 통과지만 `5-3=2 < 3` → alert **없음**
- `today=6, avg7=1.0` → 둘 다 통과 → alert **있음**

★**구현을 테스트에 맞추지 마라.** 규칙은 v5 §14-3 그대로 유지한다.

---

## 완료 조건
```powershell
python -m pytest tests -q
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
기대: **116 passed, 0 failed, skipped 0**, `tenants=1`.

★PG 가 죽어 있으면 (`connection refused`):
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```
★`-o "-p 5433"` 를 빠뜨리면 5432 로 뜬다.

## 리포트
`wiki/records/reports/2026-08-13_S-FIX3_리포트.md` — 3건 각각의 원인·수정·실제 출력.
★결함 3 에 대해 **"테스트가 틀렸다"고 판단한 근거**를 규칙 계산과 함께 적어라.

## 하지 말 것
- ❌ PII 테스트 단언 약화
- ❌ 급증 규칙 변경 (v5 §14-3 고정)
- ❌ `case_state` 를 제거 대상에 넣기
- ❌ `eval/**` 열기
- ❌ 돌려보지 않고 "완료"
