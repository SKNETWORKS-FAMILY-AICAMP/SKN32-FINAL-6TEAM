# S-TEAM-FULFILLMENT-LOGISTICS — Fulfillment & Logistics Team

## 0. 배경 (읽기만)

- `program/plan/A-COP_예제Team모듈_확충설계.md` — 확정 설계 문서. 이미
  결정된 스펙을 그대로 구현해라, 새로 설계하지 마라.
- `program/plan/A-COP_구현계획서_v8.md` §8-B — Procurement+Order&Payment
  와 같은 사유로 "검증 쇼핑몰 프로젝트 일정에 따라 배치·착수 범위가
  달라질 수 있다."
- `legacy/final_project_cs/team_modules_v1/customer_ops/order_shipping.py`
  — 옛 구현이 `order.investigate`/`refund.propose` 를 다뤘는데, 그중
  **배송 관련 조사 로직**(shipment 조회·예외 판정)은 이 Team 의 참고가
  될 수 있다. capability 이름·case_type 은 다르니 그대로 복사하지 마라 —
  이 Team 은 order/payment 가 아니라 순수 배송/이행만 다룬다.
- `app/infrastructure/messaging/mock_payment_publisher.py` — 결제 관련
  mock publisher 패턴(오늘 다른 작업에서 만들어짐). 배송 provider timeout
  시뮬레이션이 필요하면 이 패턴(순수 인메모리, 실제 네트워크 없음)을
  따라 별도 mock 을 만들어도 된다 — 진짜 배송 API 연동은 하지 마라.

## 1. 확정 스펙

```
team_id: fulfillment_logistics
capabilities: [fulfillment.track, shipment.status, shipment.exception]
accepted_case_types: [fulfillment, shipping, shipment]
allowed_tools: [read.order, read.shipment, read.policy]
knowledge_scope: [order, shipping, warehouse, delivery_exception]
```

Action Gateway 어휘 중 이 Team 이 실제로 쓰는 것: `shipment.investigate,
shipment.reroute, shipment.replace` (전부 `ActionProposal`, side effect 없음).

## 2. 원칙

- side effect 없음, 전부 제안. 재발송(`shipment.replace`)·경로변경
  (`shipment.reroute`) 은 `approval_required=True`.
- 배송 지연/예외 판정은 실제 배송 상태 데이터(근거) 없이 확정하지 않는다.
  `docs/manuals/운영_unknown상태_대응절차.md` 참고 — provider(배송사)
  상태를 우리가 확실히 모르면 `unknown`/`escalated` 로 정직하게 남긴다,
  안다고 지어내지 않는다.

## 3. 할 일

1. `app/modules/customer_ops/fulfillment_logistics.py` 작성. `execute()`
   최소 범위:
   - `fulfillment.track`: 주문의 이행(피킹·포장·출고) 상태 조회·설명
   - `shipment.status`: 배송 상태 조회·설명
   - `shipment.exception`: 배송 예외(분실·파손·지연) 판정 → 재발송/경로변경
     **제안**
2. `app/modules/customer_ops/__init__.py` export 추가.
3. `tests/unit/teams/test_fulfillment_logistics.py` — 각 capability
   최소 1건 + 배송 데이터 불충분 시 escalate 케이스.

## 4. 쓰기 대상

- `app/modules/customer_ops/fulfillment_logistics.py` (신규)
- `app/modules/customer_ops/__init__.py` (export 추가만)
- `tests/unit/teams/test_fulfillment_logistics.py` (신규)
- `docs/reports/2026-08-20_S-TEAM-FULFILLMENT-LOGISTICS_리포트.md` (신규)

## 5. 하지 말 것

- `config/project.yaml` 수정 금지 — 등록은 Claude 가 한다
- 실제 배송사 API 연동 금지
- `legacy/` 수정 금지, 다른 Team 파일 수정 금지

## 6. 검증

- `python -m pytest -q -m "not live"` 실제 출력을 리포트에 붙여라(현재
  338 passed 기준으로 변화 명시).
