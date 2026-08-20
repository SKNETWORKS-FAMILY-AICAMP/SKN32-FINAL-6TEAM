# S-TEAM-PROCUREMENT-ORDER-PAYMENT — Procurement + Order & Payment Team

## 0. 배경 (읽기만)

- `program/plan/A-COP_예제Team모듈_확충설계.md` — 확정 설계 문서. 이미
  결정된 스펙을 그대로 구현해라, 새로 설계하지 마라.
- `program/plan/A-COP_구현계획서_v8.md` §8-B — 이 Team 은 "검증 쇼핑몰
  프로젝트를 실제로 운영하기 위해 필요한 연계 범위이며, 그 프로젝트의
  진행 범위와 일정에 따라 배치·착수 범위가 달라질 수 있다." 즉 이번
  구현은 **Registry 계약 + 검증 가능한 로직**까지이지, 실제 결제 게이트웨이
  연동이 아니다(`app/infrastructure/messaging/mock_payment_publisher.py`
  가 이미 있다 — 결제 관련 outbox 발행이 필요하면 그 패턴을 참고해라,
  진짜 게이트웨이를 새로 만들지 마라).
- ★**주의**: 설계 문서는 "Catalog Remote 도 order 를 받으므로 `order.verify`
  와 `catalog.lookup` 을 명시적으로 구분한다"고 경고한다. 이 Team 의
  `order.verify` 는 **우리 쪽 주문 데이터(DB)** 대조이지, 외부 A2A
  Catalog&Verification 원격 서비스 호출이 아니다 — 그건 다른(아직 없는)
  Team 의 역할이다. 혼동하지 마라.
- `legacy/final_project_cs/team_modules_v1/customer_ops/order_shipping.py`
  — 옛 구현. evidence 구성·환불제안 패턴은 참고 가치가 있으나 그대로
  복사하지 마라 — case_type·capability 이름이 다르다(이 Team 은 shipping
  이 아니라 order/payment/procurement 을 다룬다 — shipping 은 별도
  Fulfillment&Logistics Team 몫이다).

## 1. 확정 스펙

```
team_id: procurement_order_payment
capabilities: [procurement.quote, order.verify, order.create, payment.status]
accepted_case_types: [procurement, order, payment]
allowed_tools: [read.order, read.account, read.policy]
knowledge_scope: [catalog, pricing, order, payment, procurement]
```

Action Gateway 어휘(제안에 쓸 action_type 후보, 고정됨):
`order.create, payment.authorize, payment.capture, shipment.investigate,
shipment.reroute, shipment.replace, return.request, refund.request,
voc.escalate` — 이 중 이 Team 의 capability 범위에 맞는 것만 실제로 쓴다
(예: `payment.authorize`/`payment.capture` 는 이 Team, `shipment.*` 는
Fulfillment&Logistics 쪽이라 이 Team 에서 발행하지 않는다).

## 2. 원칙

- **side effect 없음** — 전부 `ActionProposal`. 결제 승인(`payment.authorize`)
  같은 민감 액션은 `approval_required=True`, `risk_level` 을 적절히
  높게(high) 설정해라.
- 근거 없이 견적·주문검증·결제상태를 확정하지 않는다 — Evidence 필수.

## 3. 할 일

1. `app/modules/customer_ops/procurement_order_payment.py` 작성.
   `execute()` 는 최소 다음을 다룬다:
   - `procurement.quote`: 견적 제시(근거: 정책/가격 정보)
   - `order.verify`: 우리 DB 주문 데이터 대조 검증
   - `order.create`: 신규 주문 생성 **제안**(승인 필요)
   - `payment.status`: 결제 상태 조회·설명(읽기, 확정 처리 아님)
2. `app/modules/customer_ops/__init__.py` export 추가.
3. `tests/unit/teams/test_procurement_order_payment.py` — 각 capability
   최소 1건 + evidence 없을 때 escalate 케이스.

## 4. 쓰기 대상

- `app/modules/customer_ops/procurement_order_payment.py` (신규)
- `app/modules/customer_ops/__init__.py` (export 추가만)
- `tests/unit/teams/test_procurement_order_payment.py` (신규)
- `docs/reports/2026-08-20_S-TEAM-PROCUREMENT-ORDER-PAYMENT_리포트.md` (신규)

## 5. 하지 말 것

- `config/project.yaml` 수정 금지 — 등록은 Claude 가 한다
- 실제 결제 게이트웨이 SDK 연동 금지
- `legacy/` 수정 금지, 다른 Team 파일 수정 금지

## 6. 검증

- `python -m pytest -q -m "not live"` 실제 출력을 리포트에 붙여라(현재
  338 passed 기준으로 변화 명시).
