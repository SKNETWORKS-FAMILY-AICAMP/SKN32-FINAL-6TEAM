---
type: concept
title: 근거 대조
description: 제안의 식별자·금액을 DB와 대조해 실행 전에 차단한다. 두 번 확인한다
status: draft
tags: [security, architecture]
owners: [human:미배정]
---

# 근거 대조

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/core/verification.py` (212줄, 순수 함수) · `proposal_guard`

## 책임

**제안이 실제 데이터와 맞는지 실행 전에 확인한다.** 안 맞으면 실행하지 않고 `escalated`로 보낸다.

이게 [중앙 허브 포지셔닝](../../../wiki/product/positioning.md)의 "잘못 자동화하지 않는 지점"을 실제로 만드는 코드다.

## 두 번 확인한다

```text
Team이 ActionProposal 반환
   ↓
① 제안 시점 검증        verify_proposal()  — 순수 함수
   ↓
   (승인 대기 · 시간 경과)
   ↓
② 승인 직전 재검증      proposal_guard    — DB 재조회
   ↓
실행
```

**두 번 하는 이유**는 승인 대기 중에 데이터가 바뀔 수 있기 때문이다. 제안할 때 맞았어도 승인 시점엔 틀릴 수 있다.

`[실측]` `tests/integration/api/test_recheck_before_execution.py`가 이를 검사한다.

## 무엇을 대조하는가

| 대상 | 예 |
|---|---|
| 식별자 | 이 `order_id`가 이 고객 것인가 |
| 금액 | 환불액이 주문 총액을 넘는가 |
| 수량 | 반품 수량이 주문 수량을 넘는가 |
| 소유권 | 이 배송이 이 주문 것인가 |

`Mismatch` 객체로 무엇이 왜 안 맞는지 남긴다.

## 순수 함수로 분리했다

`verification.py`는 **DB를 모른다.** `Facts`를 받아 판정만 한다.

```python
def verify_proposal(...) -> ...
class Facts: ...
class Mismatch: ...
class VerificationPolicy: ...
class QuantityRule: ...
```

**DB 재조회는 `proposal_guard`가 한다.** 판정 로직과 조회를 나눠서 판정을 테스트하기 쉽게 만들었다.

## 거부하면 무엇이 남는가

```
escalated 로 전환
실패한 필드 이름
값의 hash
```

**원본 값이 아니라 hash를 남긴다.** 감사 기록에 결제 식별자 원문이 남으면 안 되기 때문이다. → [../external/auth-boundary.md](../external/auth-boundary.md)

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-VER-001` | 존재하지 않는 주문은 거부된다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_unknown_order_is_rejected` |
| `INV-CS-VER-002` | 주문 총액을 넘는 환불은 거부된다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_refund_over_the_order_total_is_rejected` |
| `INV-CS-VER-003` | 부분 환불은 통과한다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_partial_refund_passes` |
| `INV-CS-VER-004` | 주문 수량을 넘는 반품은 거부된다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_return_quantity_over_the_item_count_is_rejected` |
| `INV-CS-VER-005` | 주문 범위 내 반품은 통과한다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_return_quantity_within_the_order_passes` |
| `INV-CS-VER-006` | 배송 소유권을 확인한다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_shipment_ownership_is_checked` |
| `INV-CS-VER-007` | 이 도메인의 불투명 필드는 거부된다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_this_domains_opaque_field_is_rejected` |

**003과 005가 있는 이유**는 "전부 거부"가 만점이 되는 걸 막기 위해서다. 통과해야 할 것은 통과해야 한다.

## ★ [2026-09-02 추가] 답을 안 내는 것이 정상적인 답이다

`[실측]` `_3차_인용검증_설계.md` 에서 이관. **원본 제목이 결론이다.**

> **판정 정직성 — 프롬프트를 방어선으로 삼지 않는다**

### 자유 텍스트를 받으면 검증할 수 없다

**형태를 강제한다.**

```json
{
  "verdict": "covered | not_covered | unknown",
  "cited_clauses": ["보통약관/제9조", "특별약관/제3조"],
  "reason": "…",
  "applied_terms": { "insurer": "…", "sale_start": "20190501" }
}
```

| 규칙 | |
|---|---|
| **`verdict="unknown"` 이 정상적인 답이다** | **부끄러운 답이 아니다** |
| `cited_clauses` 가 비어 있으면 | `covered`·`not_covered` 를 **낼 수 없다** |

**두 번째 줄이 강제다.** 근거를 못 대면 판정 자체를 못 하게 막는다.

### 인용 검증 — 무엇을 대조하나

```
1) cited_clauses 의 각 항목이 넘겨준 근거의 qualified_no 집합에 있는가
```

**모델이 지어낸 조항 번호를 걸러낸다.** 근거에 없는 조항을 인용하면 그 답은 버린다.

`[미확보]` **이 검증이 지금 구현돼 있는지 확인하지 않았다.** 원본이 작성된 2026-08-01 시점에는 **없었다**고 적혀 있다.

### 이 결정이 [D-005](../../../wiki/decisions/D-005-write-gate.md) 의 원형이다

원본의 방어 층 표에서 **"인용 조항이 근거에 실재하는지 대조"** 와 **"구조화 출력"** 두 줄이 ❌ 였다. D-005 의 7층은 그 표를 확장한 것이다.

**D-005 의 세 번째 층이 "약함"인 이유도 여기서 나왔다.**

> **프롬프트는 방어가 아니다. 넣되 그것만 믿지 않는다.**

## ★ 이게 못 잡는 것

**대조 대상 자체가 틀리면 통과한다.**

`INV-CS-VER-002`는 "환불 ≤ 주문 총액"만 본다.

```
30,000원 주문 · 5,000원 쿠폰 → 실결제 25,000원
2개 중 1개 반품 → 우리 계산 15,000원

15,000 ≤ 30,000  →  통과 ✅
실제 환불액 12,500원          ❌
```

**할루시네이션이 아니라 결정론적 코드의 계산 오류라서 근거 대조로 안 잡힌다.**

조치는 [중앙 허브 D-001](../../../wiki/decisions/D-001-payment-ownership.md) — 우리가 계산하지 말고 쇼핑몰이 계산한 값을 받아 대조한다.

**대조 구조는 이미 맞다.** 대조 대상만 바꾸면 된다.

## 평가 지표와의 연결

| 지표 | 무엇을 |
|---|---|
| `근거 정합률` | 제안 필드 중 실재·일치 비율 |
| `근거 초과율` | Context/DB에 없는 주장 비율 |
| `적절한 기권율` | 근거 부족 시 escalate 비율 |
| `과잉 기권율` | 근거 충분한데 escalate 비율 |

→ [../../../wiki/evaluation/metrics.md](../../../wiki/evaluation/metrics.md)

## 관계

- [action-proposal.md](action-proposal.md) — `rationale_evidence_ids`가 입력
- [approval.md](approval.md) — 통과 후 승인 판정
- [tool-gateway.md](tool-gateway.md) — 통과 후 실행
- [../quality/invariants.md](../quality/invariants.md) — 불변식 전체
