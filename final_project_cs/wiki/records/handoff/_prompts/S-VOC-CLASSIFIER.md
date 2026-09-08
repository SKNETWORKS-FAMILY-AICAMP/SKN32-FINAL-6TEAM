# 구현 지시 — VOC 인라인 분류기(`feedback.py`) 어휘를 쇼핑몰 도메인으로 교체

## 0. 배경 — 왜 이 작업이 심각한가

`app/modules/customer_ops/feedback.py` 의 `classify()` 는 **VOC 분석 전용이 아니다.**
`app/composition.py::build_classifier()` 가 이 함수를 감싸서 만든 콜러블이
`app/presentation/api/app.py::create_app()` 의 **기본 classifier** 로 주입되고,
그게 `/v1/cases` REST 라우터(`app/presentation/api/cases.py` 의 `build_router`)에
꽂힌다. 즉 **이것이 지금 이 시스템이 신규 Case 를 분류하는 실제 운영 경로다.**

지금 `INTENTS = frozenset({"billing", "technical", "other"})` 다. LLM 이 쇼핑몰
메시지를 정직하게 분류하면 `"order"`/`"shipping"`/`"return"`/`"exchange"` 를
반환할 텐데, 그 값이 전부 `INTENTS` 밖이라 **`ClassificationFailed` 로 떨어진다.**
설계상 이건 조용히 실패하지 않고 `classification_failed` + `escalated` 로 안전하게
처리되긴 하지만(`CLAUDE.md` §1 — 분류 실패는 조용히 넘기지 않는다), 결과적으로
**REST API 로 들어오는 진짜 쇼핑몰 Case 가 단 하나도 정상 분류되지 못한다.**

## 1. 소유 범위

```
app/modules/customer_ops/feedback.py     ← INTENTS·ISSUE_CODES·시스템 프롬프트 텍스트만 교체
tests/unit/voc/test_feedback.py          ← 테스트 fixture 값만 새 어휘로 교체
wiki/records/reports/                            ← 작업 리포트 제출 (RULE.md §3.4 필수)
```

★금지: `app/composition.py`, `app/application/feedback_job.py`(도메인 무관 코드,
intent/issue_code 문자열을 검증하지 않고 그대로 집계한다 — 손댈 필요도 이유도 없다),
`app/core/**`, `config/**`, `eval/**`, `knowledge/**`. `classify()` 함수의 로직·
`ClassificationFailed` 예외 처리·`_openai_llm()` 구조는 **바꾸지 않는다** — 상수
값과 그 값을 담는 시스템 프롬프트 문자열만 바꾼다.

## 2. 새 어휘 (그대로 쓴다 — 고르거나 늘리지 않는다)

```python
INTENTS = frozenset({"order", "shipping", "return", "exchange", "other"})

ISSUE_CODES = frozenset({
    "order_payment_failed", "order_duplicate_charge", "order_change_or_cancel", "order_other",
    "shipping_delayed", "shipping_delivered_not_received", "shipping_other",
    "return_quantity_exceeded", "return_fee_or_period", "return_other",
    "exchange_stock_or_period", "exchange_other",
    "other",
})
```

`SENTIMENTS`·`SEVERITIES` 는 도메인과 무관하므로 **그대로 둔다.**

`INTENTS` 의 4개 도메인 값(`order`/`shipping`/`return`/`exchange`)은
`app/modules/customer_ops/order_shipping.py`·`return_exchange.py` 의
`TeamManifest.accepted_case_types` 와 **정확히 일치**한다 — Case 라우팅이 이 값을
그대로 쓰기 때문이다(`app/application/controller.py` 의 `registry.resolve(case_type=intent)`).
이 값들을 다시 바꾸지 않는다.

## 3. 무엇을 바꾸는가

### 3-1. `app/modules/customer_ops/feedback.py`

- `INTENTS`·`ISSUE_CODES` 를 §2 값으로 교체
- 모듈 docstring(파일 맨 위)의 `` ``post_cancel_charge``, ``payment_failed``, ... `` 나열을
  새 `ISSUE_CODES` 나열로 교체
- `_openai_llm()` 의 시스템 프롬프트 문자열 중
  `"intent is billing|technical|other; sentiment is ..."` 를
  `"intent is order|shipping|return|exchange|other; sentiment is ..."` 로 교체
  (`issue_code must be one of: ...` 부분은 이미 `ISSUE_CODES` 를 동적으로 join 하므로
  손댈 필요 없다 — 그대로 두면 자동으로 새 값이 들어간다)

### 3-2. `tests/unit/voc/test_feedback.py`

- `test_classifier_returns_all_four_fields_from_injected_llm`: 주입하는 값을
  `{"sentiment": "negative", "intent": "order", "issue_code": "order_payment_failed", "severity": "high"}`
  로 교체하고 그 아래 `assert` 문의 기대값도 맞춰 고친다
- `test_classifier_fails_when_any_field_is_missing`: `value` 의 `"intent": "other"`,
  `"issue_code": "other"` 는 새 어휘에서도 유효하므로 **그대로 둔다**(수정 불필요)
- `test_batch_is_tenant_scoped_and_idempotent`: `INSERT INTO customer_cases` 의
  하드코딩된 `'billing','payment_failed'` 를 `'order','order_payment_failed'` 로
  교체한다(이 테스트는 `feedback.py` 상수를 직접 참조하지 않고 SQL 리터럴을 쓰므로
  기능적으로는 실패하지 않았겠지만, 새 도메인과 일관되게 맞춘다)

## 4. 검증

```powershell
python -m pytest tests/unit/voc -q
python -m pytest -q -m "not live"
```

두 명령 모두 실패 0건이어야 한다. 추가로 다음을 직접 실행해 실제로 새 어휘로
분류가 되는지 확인한다(주입 함수로 실 LLM 호출 없이):

```powershell
python -c "from app.modules.customer_ops.feedback import classify; print(classify('배송이 너무 늦어요', lambda _: {'sentiment':'negative','intent':'shipping','issue_code':'shipping_delayed','severity':'medium'}))"
```

예외 없이 `Classification(sentiment='negative', intent='shipping', issue_code='shipping_delayed', severity='medium')` 이 출력돼야 한다.

## 5. 완료 조건

- [ ] `INTENTS`·`ISSUE_CODES` 가 §2 값과 정확히 일치(추가·누락 없음)
- [ ] `billing`/`technical`/`entitlement`/`payment_failed`/`login_issue`/
      `service_unavailable`/`post_cancel_charge` 등 옛 어휘가 `feedback.py`·
      `test_feedback.py` 어디에도 남지 않는다
- [ ] `pytest tests/unit/voc -q` 통과
- [ ] `pytest -q -m "not live"` 전체 통과(회귀 없음)
- [ ] §4 의 수동 확인 명령이 예외 없이 올바른 값을 출력
- [ ] `wiki/records/reports/2026-08-17_S-VOC-CLASSIFIER_리포트.md` 제출
