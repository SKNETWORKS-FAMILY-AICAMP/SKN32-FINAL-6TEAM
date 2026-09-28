# DoD-07 — tenant/customer scope 와 PII redaction

- v5 §20 항목 7 / 검증 방법: security test
- 최초 판정: 2026-08-12 23:20 **부분 통과** (PII 미검증)
- 재측정: 2026-08-13 · 실측 원문 `wiki/records/evidence/_raw/DoD-07_v2.md`
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/security -q
python  # PII 포함 메시지로 Case 생성 후 customer_cases·case_events 직접 조회
```

## 실제 출력 (재측정)

```
tests/security: 3 passed

customer_cases.subject 에 포함된 값:
  010-****-5678
  **** **** **** 1111
  [REDACTED_API_KEY]
  [REDACTED_PAYMENT_ID]

case_events = ['created', 'classified']
```

## 판정 근거

| 요구 (v5 §9-3, §12) | 결과 |
|---|---|
| 전화번호 마스킹 | **통과** — `010-****-5678` |
| 카드번호 마스킹 | **통과** — `**** **** **** 1111` |
| ★API key **원문 미기록** | **통과** — `[REDACTED_API_KEY]` (마스킹이 아니라 **제거**) |
| ★결제 식별자 **원문 미기록** | **통과** — `[REDACTED_PAYMENT_ID]` |
| tenant/customer 범위 강제 | **통과** — 남의 Case → **404** |
| RAG tenant 격리 | **통과** — 다른 tenant → 0건 |
| RAG scope 필터 | **통과** — `['billing']` → billing 만 |
| ★그래프 질의 tenant 격리 | **통과** — `SqlGraphAdapter` 테스트 (2026-08-13 추가) |

★v5 §12 는 API key·결제 식별자를 **audit 에 원문 기록 금지**로 정했다.
마스킹이 아니라 **제거**로 처리한 것이 계약에 맞다.

## 최초 판정에서 무엇이 바뀌었나

2026-08-12 실측:
```
E  assert '010-1234-5678' not in
E    'phone=010-1234-5678 card=4111 1111 1111 1111
E     api_key=sk-test-original-api-key payment=pay_original_987654'
```
**네 가지가 전부 원문으로 저장**되고 있었다. → `wiki/records/reports/debugs/2026-08-13_1230_PII가_평문으로_저장된다.md`

★그때 `security.py` 에 `masked` 함수는 **존재했다.** 그래서 1차 실측은
"masked 함수가 있다" 만 관측했고, 나는 판정에 이렇게 적었다:

> 함수가 있다는 것과 경로마다 실제로 적용된다는 것은 다르다.

**부분 통과로 둔 판단이 옳았다.** 통과로 적었다면 거짓 보고였다.

## 한계 · 미검증

| 항목 | 상태 |
|---|---|
| 저장 시 마스킹 | **통과** |
| ★**LLM 입력이 masked 인가** | **미검증** — 분류기·Team·평가 경로 각각을 확인하지 않았다 |
| ★`demo` tenant 기존 데이터에 PII 잔존 여부 | **미검증** — 전체 검색을 돌리지 않았다 |
| API 응답의 evidence 마스킹 | 부분 — 테스트가 저장분만 본다 |

★**저장이 막혔다고 LLM 으로 새는 경로까지 막힌 것은 아니다.**
v5 §9-3 은 "LLM 에는 masked text 만 전달한다" 를 따로 요구한다. 그 경로는 아직 증명되지 않았다.
