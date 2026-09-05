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

## ★ [2026-09-04] 대조 자체가 세 번 뚫릴 뻔했다

`[실측]` [DoD-24](../../../../final_project_cs/docs/evidence/DoD-24_ActionProposal_근거대조.md)에서 이관. **대조 코드를 만드는 과정에서 대조 코드 자체가 뚫릴 뻔한 경우가 셋 있었다.**

### ① 근거 대조가 순환할 뻔했다

처음엔 `pack_evidence or result.evidence`로 짰다 — Context에 근거가 없으면 **Team이 자기가 만든 근거로 자기 제안을 검증**하는 순환이 생긴다. Team이 근거와 제안을 둘 다 지어낼 수 있으니 방어가 통째로 풀린다.

**대조 대상은 위조할 수 없는 쪽이어야 한다.** `task.context`(Controller가 만든 ContextPack)로만 대조하도록 폴백을 지웠다 — 근거 없는 Context면 근거를 든 제안이라도 전부 거부한다.

### ② 대조 코드의 컬럼명 오타가 대조와 무관한 전이까지 무너뜨렸다

`load_facts()`를 savepoint 없이 짰는데 `entitlements` 테이블 컬럼명을 하나 틀렸다(`feature/state`가 아니라 `plan/source`). 이 한 번의 실패가 트랜잭션을 `InFailedSqlTransaction`으로 만들어 **대조와 무관한 뒤따르는 전이까지 전부 무너졌다.**

`conn.transaction()` 안으로 격리해 고쳤다. **대조는 거들 뿐이지 본 흐름을 망가뜨리면 안 된다.**

### ③ 재검증 자체가 상태기계·트랜잭션 설계 구멍 셋을 먼저 드러냈다

승인 직전 재검증(`recheck_before_execution`)을 만들다가 코드가 아니라 **기계가 먼저 잡은** 구멍이 셋이었다.

| 무엇을 놓쳤나 | 어떻게 드러났나 |
|---|---|
| `waiting_approval --guardrail_escalated-->` 전이가 전이표에 없었다 | 재검증 코드를 먼저 쓰고 전이표를 안 열어 봄 — 상태기계가 런타임에 거부 |
| 거부 기록이 예외와 함께 롤백돼 사라졌다 | 승인 트랜잭션 **안에서** escalated를 쓰고 409를 던졌더니 기록도 같이 사라짐 — "조용히 무시하지 않는다" 원칙이 그대로 깨질 뻔함. 재검증을 트랜잭션 **밖**으로 옮겨 거부 기록만 따로 커밋 |
| 존재 확인(404)보다 재검증이 먼저 돌았다 | 없는 action에 재검증이 돌아 `routing` 상태 Case에 escalated를 쓰려다 상태기계에 걸림 — 순서를 바로잡음 |

**셋 다 사람이 리뷰로 못 잡고 실행 중에 기계가 잡았다.** 상태 전이표와 append-only 이벤트 원칙([CLAUDE.md §0.3](../../../../final_project_cs/CLAUDE.md))이 없었으면 조용히 넘어갔을 결함들이다.

### ④ 이 재검증 게이트가 반대 방향으로도 뚫렸다 — 정상 제안을 잘못 막았다

`[실측]` 2026-09-03. `calculation_basis` 필드를 선언 없이 `ignored`로 처리해 **모든 환불 제안이 이 재검증에서 "선언되지 않은 필드"로 기계적으로 막혔다.** DoD-28 방어지표의 과잉 기권율이 35%로 튄 원인이 여기 있었다 — 모델이 과하게 기권한 게 아니라 게이트가 정상 제안을 오탐했다. → [dod28-rerun.md](../../../../program/wiki/evaluation/dod28-rerun.md)

## ★ [2026-09-04] 비정상 금액이 거부가 아니라 500 크래시였다

`[실측]` 2026-08-24 갱신분. `_to_decimal()`이 `Decimal("NaN")`/`Decimal("Infinity")`/`Decimal("-Infinity")`를 `.is_finite()`로 걸러내지 않아, 파싱은 통과했다가 이후 비교 연산(`>`, `int()`)에서 `InvalidOperation`/`OverflowError`로 **500 에러**를 냈다.

**이게 근거 대조 코드에서 특히 나쁜 이유** — "거부해야 할 제안"이 서버 에러가 되면 `escalated`로도 못 가고 감사 로그도 안 남는다. [CLAUDE.md §0.1](../../../../final_project_cs/CLAUDE.md)이 요구하는 "근거 없으면 답하지 않는다"가 **에러로 조용히 새는 경로**였다. 세 비정상 값 모두 크래시 대신 안전한 검증 실패로 처리되도록 고쳤다.

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
