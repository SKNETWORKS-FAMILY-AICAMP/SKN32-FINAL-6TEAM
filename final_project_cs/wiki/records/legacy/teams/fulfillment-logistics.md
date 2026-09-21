---
type: concept
title: Fulfillment & Logistics Team
description: 배송 상태와 예외를 다룬다. 모르는 상태를 아는 척하지 않는다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
domain: commerce
domain_note: v10 §0-2 가 MVP 경로에서 제외한 커머스 Team 이다. 2026-09-09 에 config/project.yaml 등록에서 빠졌고 소스만 app/modules/customer_ops/ 에 남아 있다
---

# Fulfillment & Logistics Team

`app/modules/customer_ops/fulfillment_logistics.py`

**Commerce Ops Pack.** 검증 쇼핑몰 일정에 따라 조정된다.

## manifest

`[실측]`

```python
capabilities        = ["fulfillment.track", "shipment.status", "shipment.exception"]
accepted_case_types = ["fulfillment", "shipping", "shipment"]
required_context    = ["case_state", "policy", "db_facts", "history"]
allowed_tools       = ["read.order", "read.shipment", "read.policy"]
knowledge_scope     = ["order", "shipping", "warehouse", "delivery_exception"]
max_steps           = 6
```

## ★ 모르는 상태를 아는 척하지 않는다

`[실측]` dojo가 심은 결함 두 개가 이 Team에서 잡혔다. **둘 다 "정직함"에 관한 것이다.**

| 심은 결함 | 잡은 테스트 |
|---|---|
| 배송 상태를 모르는데 아는 척 답한다 | `test_unknown_shipment_status_escalates_instead_of_answering[UNAVAILABLE]` 외 2건 |
| 조회된 배송 건수를 세지 않고 0으로 답한다 | `test_tracking_answer_counts_the_shipments_it_read` |

**첫 번째가 이 프로젝트의 성격을 보여준다.** 택배사 상태가 `UNAVAILABLE`일 때 "배송 중입니다"라고 답하면 고객이 잘못된 기대를 갖는다.

**모르면 escalate한다.**

**두 번째도 같은 종류다.** 실제로 읽은 건수와 답변의 건수가 달라지면 안 된다. **세지 않고 0이라고 말하는 것**은 조용한 거짓말이다.

## 배송 소유권을 확인한다

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-VER-006` | 배송 소유권을 확인한다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_shipment_ownership_is_checked` |

**이 배송이 이 주문 것인지 확인한다.** 남의 배송 정보를 알려주면 안 된다.

## 상태 값

`[실측]` `002_domain_commerce.sql`

```sql
shipments.status text NOT NULL,  -- ready / in_transit / delivered / lost
```

`lost`가 있다는 게 중요하다. **분실이 정상 상태값이다.** 예외 처리가 아니라 흐름의 일부다.

## 골든셋 대표 시나리오

`[실측]` "배송완료 미수령"이 시연 시나리오 1이다.

```
cust_01 / ORD-0101 배송완료 미수령 → fulfillment_logistics
  → waiting_approval 에서 멈춘다
```

**`delivered`인데 못 받았다는 상황이다.** 시스템 상태와 현실이 어긋난 케이스라 사람 판단이 필요하다.

## Live 연동은 Mock이다

`[실측]` **국외 배송·해외 구매대행의 실제 Live 연동은 Mock으로 남긴다.**

`datasets/commerce/courier_tracking`이 실제 택배 조회 도구지만, 이 Team의 실행부와 연결하는 것은 검증 쇼핑몰 범위다.

## 관계

- [team-contract.md](../../../teams/team-contract/index.md) — 계약
- [procurement-order.md](procurement-order.md) — 주문 쪽
- [return-refund.md](return-refund.md) — 반품 쪽
- [../actions/evidence-check.md](../../../actions/evidence-check.md) — 소유권 확인
- [../quality/blind-spots.md](../../../quality/blind-spots.md) — 심어 본 결함
