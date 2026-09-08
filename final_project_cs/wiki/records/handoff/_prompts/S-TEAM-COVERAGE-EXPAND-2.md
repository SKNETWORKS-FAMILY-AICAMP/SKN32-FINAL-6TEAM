# 구현 지시 — Team 커버리지 확장 2차 (반품 기한, 배송 지연 보상)

## 0. 배경

`wiki/records/reports/2026-08-18_S-TEAM-COVERAGE-EXPAND_리포트.md`(1차, 완료)에
이어 두 issue_code 를 더 커버한다. **두 가지를 먼저 조사해서 확정한 값이니
재량으로 바꾸지 마라:**

1. `return_fee_or_period` → `knowledge/documents/11_return_period.md` 근거로
   **반품 기한 대조**를 `return_exchange.py` 에 추가한다.
2. `shipping_delayed` → `knowledge/documents/02_shipping_delivery-schedule.md`
   근거로 **배송 지연 보상 검토 제안**을 `order_shipping.py` 에 추가한다.

★**`order_payment_failed`/`order_duplicate_charge` 는 이번 범위에 없다.**
`knowledge/documents/10_order_payment-failure.md` 를 확인한 결과, 판정에
필요한 "결제 시도 이력"(실패 코드·재시도 이력)이 이 저장소 DB 스키마에
아예 없다(`orders` 테이블은 주문당 최종 상태만 있지 결제 시도 이력을
안 남긴다). 없는 데이터를 있는 것처럼 대조하면 지어내는 것이다
(`CLAUDE.md` §1). 이 두 issue_code 는 계속 LLM 자유 응답 경로로 둔다 —
**이 파일에서 손대지 않는다.**

## 1. 소유 범위

```
쓰기 대상:
  app/modules/customer_ops/order_shipping.py
  app/modules/customer_ops/return_exchange.py
  tests/unit/teams/test_team_scenarios.py

★금지: 그 외 모든 파일. verification_policy.py, 마이그레이션, Core,
  Application, prompts/**, wiki/records/handoff/04(설명은 필요하면 사람이 나중에
  갱신한다 — 이번 계약 범위 아니다)
```

## 2. `return_exchange.py` — 반품 기한 대조

`doc_11#청약철회 기한의 원칙`: 단순변심은 **주문일(`ordered_at`)로부터
역일 7일**. `doc_11#표시·광고와 다른 경우의 특례`: 상품 하자·표시 상이
사유는 **주문일로부터 역일 3개월**(30일-안날 기준 특례는 "안 날"이
DB 에 없어 이번 범위에서 대조하지 않는다 — 3개월 상한만 대조한다).

- `latest`(가장 최근 pending return, 이미 `pending[0]` 으로 정해져 있다)의
  `reason_code` 가 `defective` 인지 아닌지로 두 기한 중 하나를 고른다:
  - `reason_code == "defective"` → 상한 **90일**(3개월의 근사치로 역일
    90일을 쓴다 — 정확한 월 단위 계산은 이번 범위 아니다)
  - 그 외(단순변심 포함, `size_mismatch`/`color_mismatch`/`wrong_option`
    도 여기 포함 — 이건 이미 교환 분기로 먼저 걸러지므로 실제로는 이
    분기에 안 온다) → 상한 **7일**
- 경과일 = `(now(UTC) - order["ordered_at"]).days` — `ordered_at` 은
  `datetime.now(UTC)` 와 같은 방식으로 이미 timezone-aware 로 온다
  (기존 evidence 타임스탬프 코드가 `datetime.now(__import__("datetime").UTC)`
  를 쓰는 것과 같은 패턴을 따른다).
- 경과일이 상한을 넘으면: **제안을 만들지 않는다.** 대신
  `TeamResult(outcome="escalated", next_action=NextAction.ESCALATE,
  failure_code="return_period_expired", evidence=evidence,
  warnings=["반품 기한(7일/하자 90일)을 넘겨 접수됨 — 고지 누락 등 예외
  사유 확인이 먼저 필요함"])` 을 반환한다. 근거(evidence)는 지금처럼
  채운다.
- 넘지 않았으면 **기존 로직 그대로**(교환/반품 분기, 수량 초과 대조 등
  1차 작업 결과) 진행한다 — 이 검사는 기존 분기 **앞에** 추가하는 문지기
  (gate) 역할이다.
- `order["ordered_at"]` 이 없거나(이론상 없을 수 없지만 방어적으로)
  파싱할 수 없으면 이 검사를 건너뛰고 기존 로직으로 진행한다(모르는
  걸 안다고 하지 않는다 — 그렇다고 막지도 않는다. 판단 불가는 보수적
  기본값인 "기존 로직 유지"로 처리).

## 3. `order_shipping.py` — 배송 지연 보상 검토 제안

`doc_02#지연에 따른 보상 검토`: **표준 배송 기간을 영업일 5일 이상
초과**한 건은 보상 검토 대상. `doc_02#지연 판정의 기준`: 출고 후 영업일
3일 지나도 스캔 이력 없으면 "지연"으로 판정(이번 범위는 스캔 이력
데이터가 없으므로 이 세부 판정 없이 곧장 5영업일 기준만 쓴다).

- 대상: `shipments` 중 `status` 가 `"delivered"` 가 아니고 `shipped_at`
  이 있는 것. `delivered and order`(1차에서 이미 있는 미수령 분기)와
  겹치지 않도록 **그 분기보다 먼저** 검사한다(하나의 shipment 가 동시에
  두 상태일 수 없으므로 실질적으로 배타적이지만, 코드 순서를 명시한다).
- 영업일 계산: 월~금만 세고 토·일은 뺀다. **공휴일 달력이 없으므로
  공휴일은 빼지 않는다** — 이건 근사치다. 헬퍼 함수를 만들어라(예:
  `_business_days_since(start: datetime, now: datetime) -> int`).
- 경과 영업일이 **5 이상**이면 제안을 만든다:
  ```python
  proposal = ActionProposal(
      action_type="shipping.delay_compensation_propose",
      arguments={"order_id": str(order["order_id"])},
      idempotency_key=idempotency_key(tenant_id=..., request_id=...,
          action_type="shipping.delay_compensation_propose", business_subject=str(task.case_id)),
      approval_required=True, risk_level="medium",
      rationale_evidence_ids=[e.evidence_id for e in evidence],
  )
  ```
  ★**금액·보상 방식(배송비 환급 vs 적립)을 Team 이 정하지 않는다** —
  `arguments` 에 금액 필드를 넣지 않는다(`doc_02` 가 "상담원이 임의로
  금액이나 방식을 제시하지 않는다"고 명시한다 — 승인자가 결정한다).
  `outcome="waiting"`, `next_action=NextAction.WAIT_FOR_APPROVAL`,
  `wait_reason="human_approval"`,
  `decisions=[{"classification": "shipping_delay_compensation_review"}]`.
- 5영업일 미만이면 이 제안을 만들지 않고 기존 로직(LLM 응답 등)으로
  진행한다.
- ★이 검사도 `order_change_or_cancel` 분기·미수령 분기와 마찬가지로
  **제안을 만들고 나면 그 자리에서 TeamResult 를 반환**한다(뒤 로직으로
  안 내려간다) — 기존 두 분기와 같은 패턴을 따른다.

## 4. 테스트 (`tests/unit/teams/test_team_scenarios.py` 에 추가)

- 반품 기한 대조:
  - 단순변심, `requested_at - ordered_at` 8일 → `escalated`,
    `failure_code=="return_period_expired"`, `action_proposals==[]`
  - 단순변심, 5일 → 기존처럼 `return.accept` 제안 생성(회귀 확인)
  - `reason_code="defective"`, 100일 → `escalated`,
    `failure_code=="return_period_expired"`
  - `reason_code="defective"`, 60일 → 기존처럼 `return.accept` 제안 생성
- 배송 지연 보상:
  - `shipped_at` 이 영업일 6일 전(테스트에서 `datetime.now(UTC) - timedelta(days=8)`
    처럼 주말 안 걸리게 확실히 8일 이상 잡아서 5영업일 이상 보장),
    `status="in_transit"` → `action_proposals[0].action_type ==
    "shipping.delay_compensation_propose"`, `arguments` 에 금액 필드 없음
  - `shipped_at` 이 2일 전, `status="in_transit"` → 제안 없음(기존
    LLM/기본 응답 경로)
  - 기존 미수령 시나리오(`test_delivered_shipment_waits_for_refund_approval`)
    회귀 확인 — 그대로 통과해야 한다

## 5. 검증

```powershell
python -m pytest tests/unit/teams -v
python -m pytest -q
```

전체 스위트 회귀 0. Codex 자체 샌드박스에서 RAG 통합 테스트 3건이 외부망
차단으로 실패하는 것은 **이번 변경과 무관한 환경 제약**이니 그대로
리포트에 적고 원인 문구를 남겨라(직전 리포트와 같은 방식).

## 6. 완료 조건

- [ ] §2·§3 정확히 구현, 금액 필드 임의 추가 없음
- [ ] `order_payment_failed`/`order_duplicate_charge` 관련 코드 추가 없음
- [ ] 신규 테스트 8건(§4) 전부 통과
- [ ] 기존 회귀 테스트(1차분 포함) 전부 통과
- [ ] `wiki/records/reports/2026-08-18_S-TEAM-COVERAGE-EXPAND-2_리포트.md` 제출
