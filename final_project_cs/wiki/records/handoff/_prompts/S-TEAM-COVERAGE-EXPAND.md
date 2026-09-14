# 구현 지시 — Team 모듈 시나리오 커버리지 확장 (order 취소, exchange 구분)

## 0. 배경

`app/modules/customer_ops/{order_shipping,return_exchange}.py` 는 각각
**시나리오 하나만** 하드코딩 분기하고(배송완료 미수령 → 환불 제안 /
반품 신청 존재 → 반품 제안), 나머지는 전부 LLM 자유 응답으로 떨어진다.
`return_exchange.py` 는 `accepted_case_types=["return","exchange"]` 로
exchange 를 받는다고 선언해 놓고 **exchange 전용 로직이 전혀 없다** —
반품과 똑같이 처리된다. 이 결함을 좁혀서 두 가지를 추가한다. 아래
규칙은 실제 정책 문서(`knowledge/documents/08_order_cancel-timing.md`,
`knowledge/documents/15_exchange_period.md`)를 근거로 Claude 가 이미
확정했다 — **규칙 자체를 재해석하거나 다르게 바꾸지 않는다.**

★**하지 않는 것**: 교환의 "재고 확인"(`knowledge/documents/15` §"재고
확인의 선행")은 DB 에 재고/인고 데이터가 없어 구현하지 않는다. 없는
데이터를 지어내지 않는다(`CLAUDE.md` §1). 대신 재고를 확인할 수 없다는
사실 자체를 근거에 남기고 항상 사람 승인으로 보낸다 — 이게 정직한 처리다.

## 1. 소유 범위

```
쓰기 대상:
  app/modules/customer_ops/order_shipping.py
  app/modules/customer_ops/return_exchange.py
  tests/unit/teams/test_team_scenarios.py   (기존 파일에 케이스 추가)

★금지: 그 외 모든 파일. `app/core/**`·`app/application/**`·
  `app/modules/customer_ops/verification_policy.py`·
  `app/infrastructure/db/migrations/**` 는 이번 범위에서 건드리지 않는다
  (아래 두 기능 모두 **기존 스키마·기존 대조 어휘로 충분하다** — 새 필드
  이름을 만들지 않고 기존 `order_id`/`return_quantity` 를 재사용한다).
```

## 2. `order_shipping.py` — 주문 취소/변경 분기 추가

`execute()` 안, 기존 `delivered and order` 분기 **앞에** 새 분기를 넣는다
(취소 판단이 배송완료 판단보다 우선한다 — 취소 요청인데 배송완료
분기로 새는 걸 막는다).

### 판단 근거 (`knowledge/documents/08_order_cancel-timing.md`)

```python
issue_code = task.context.current_state.get("issue_code")
order_status = (order or {}).get("status")

if issue_code == "order_change_or_cancel" and order:
    if order_status in ("placed", "paid"):
        # doc_08 "결제 승인 직후 취소"/"물류센터 전달 후 취소" —
        # 아직 출고 전이면 취소 제안을 만든다. 시스템이 자동 확정하는
        # 실물류 규칙과 무관하게, 이 시스템은 항상 사람 승인을 거친다
        # (CLAUDE.md §0.2 — Team 은 side effect 를 실행하지 않는다).
        proposal = ActionProposal(
            action_type="order.cancel",
            arguments={"order_id": str(order["order_id"])},
            idempotency_key=idempotency_key(
                tenant_id=task.context.tenant_id, request_id=request_id,
                action_type="order.cancel", business_subject=str(task.case_id)),
            approval_required=True, risk_level="medium",
            rationale_evidence_ids=[e.evidence_id for e in evidence],
        )
        return TeamResult(..., outcome="waiting", confidence=0.85, evidence=evidence,
                          next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                          action_proposals=[proposal],
                          decisions=[{"classification": "cancel_before_shipment"}])
    if order_status in ("shipped", "delivered"):
        # doc_08 "출고 후 취소 요청" — 취소가 아니라 반품 절차다.
        # 여기서 임의로 반품을 대신 접수하지 않는다 — LLM 이 정책 근거를
        # 바탕으로 반품 절차를 안내하도록 아래 공통 LLM 경로로 그대로 둔다.
        pass  # fallthrough — 아래 delivered 분기·LLM 답변으로 이어짐
```

`request_id`/`evidence` 변수는 기존 코드에 이미 있는 것을 그대로 쓴다
(순서상 `evidence = self._evidence(...)` 호출 뒤에 이 분기를 넣는다).
`order_status in ("shipped","delivered")` 케이스는 **새 코드를 추가하지
않는다** — 기존 `delivered and order` 분기와 그 아래 LLM 공통 경로가
이미 그 상황을 처리한다(정책 근거가 RAG 로 이미 공급되므로 LLM 이
doc_08 내용을 보고 반품 절차를 안내할 수 있다). 즉 이 케이스는 **분기를
안 타고 그냥 통과시키는 것 자체가 올바른 구현**이다 — 주석으로 왜
아무것도 안 하는지 남긴다.

`ActionProposal`/`TeamResult` 생성자 인자는 기존 `refund.request` 분기와
같은 패턴(`task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id`
등 공통 필드)을 그대로 따른다 — 기존 코드를 읽고 정확히 맞춘다.

## 3. `return_exchange.py` — exchange 구분 추가

### reason_code 로 exchange 판별

```python
EXCHANGE_REASON_CODES = frozenset({"size_mismatch", "color_mismatch", "wrong_option"})
```

(이 상수를 모듈 최상단, `class ReturnExchangeTeam` 앞에 둔다.)

`pending = [r for r in returns if r.get("status") == "requested"]` 로 뽑은
뒤, `action_type` 을 조건부로 정한다:

```python
if pending and order:
    latest = pending[0]
    is_exchange = latest.get("reason_code") in EXCHANGE_REASON_CODES
    action_type = "exchange.request" if is_exchange else "return.accept"
    classification = (
        "exchange_requested" if is_exchange
        else ("return_quantity_exceeds_order" if over_requested else "return_requested")
    )
    proposal = ActionProposal(
        action_type=action_type,
        # ★필드 이름은 그대로 재사용한다 — return.accept 때와 동일하게
        #   order_id/return_quantity 로 대조한다(verification_policy.py
        #   변경 불필요, doc_14 의 "이 원칙은 교환 신청에도 동일하게
        #   적용된다"를 그대로 따른 것).
        arguments={"order_id": str(order["order_id"]), "return_quantity": latest.get("quantity")},
        idempotency_key=idempotency_key(tenant_id=task.context.tenant_id, request_id=request_id,
                                        action_type=action_type, business_subject=str(task.case_id)),
        # ★교환은 재고를 확인할 수단이 없다(doc_15 "재고 확인의 선행") —
        #   실시간 재고 없이 승인하면 안 되는 조건이므로 항상 high 로
        #   보낸다. 수량 초과 여부와 무관하게 교환이면 무조건 high.
        approval_required=True,
        risk_level="high" if (is_exchange or over_requested) else "medium",
        rationale_evidence_ids=[e.evidence_id for e in evidence],
    )
```

`evidence` 리스트에 exchange 판정인 경우 아래 항목을 하나 더 추가한다
(재고 미확인을 숨기지 않는다 — `CLAUDE.md` §0.1):

```python
if is_exchange:
    evidence.append(Evidence(
        evidence_id="policy:exchange_stock_unverified", source_type="policy_chunk",
        source_id="doc_15#재고 확인의 선행",
        claim="이 시스템은 실시간 재고 데이터가 없어 교환 대상 옵션의 재고를 자동으로 확인하지 못한다 — 승인자가 재고를 직접 확인해야 한다",
        value={}, confidence=1.0,
        observed_at=evidence[0].observed_at if evidence
        else __import__("datetime").datetime.now(__import__("datetime").UTC)))
```

`decisions=[{"classification": classification}]` 로 위에서 정한 값을 쓴다
(기존 `"return_quantity_exceeds_order"`/`"return_requested"` 두 값에
`"exchange_requested"` 를 추가하는 것 — 기존 두 값의 조건은 그대로 둔다).

## 4. 테스트 (`tests/unit/teams/test_team_scenarios.py` 에 추가)

기존 파일의 fixture 패턴(`FakeTools`, `task(...)` 헬퍼 등)을 그대로 써서:

- `order_shipping`: `issue_code="order_change_or_cancel"` 이고
  주문 status 가 `"paid"` 인 fixture → `action_proposals[0].action_type
  == "order.cancel"`, `next_action == WAIT_FOR_APPROVAL` 확인
- `order_shipping`: 같은 issue_code 인데 주문 status 가 `"delivered"` →
  `action_proposals` 가 비어 있음(취소 제안을 만들지 않음) 확인 —
  `llm=None` 이면 fallback 고정 문구로 `completed` 가 나오는 기존 경로를
  그대로 확인하면 된다
- `return_exchange`: `reason_code="size_mismatch"` 인 pending return
  fixture → `action_proposals[0].action_type == "exchange.request"`,
  `risk_level == "high"`, evidence 에 `doc_15#재고 확인의 선행` 이 포함됨 확인
- `return_exchange`: `reason_code="defective"` (기존 값) → 여전히
  `action_type == "return.accept"` 로 회귀 없음 확인

## 5. 검증

```powershell
python -m pytest tests/unit/teams -q
python -m pytest -q
```

기존 테스트 전부 통과 + 신규 케이스 통과. 회귀 0.

## 6. 완료 조건

- [ ] `order.cancel` 제안이 `placed`/`paid` 상태에서만 생성되고
      `shipped`/`delivered` 에서는 생성되지 않는다(코드로 확인 가능하게)
- [ ] `exchange.request` 제안이 `EXCHANGE_REASON_CODES` 일 때만 생성되고
      항상 `risk_level="high"` 다
- [ ] 기존 `refund.request`/`return.accept` 경로에 회귀가 없다
- [ ] `verification_policy.py`·마이그레이션·Core 는 건드리지 않았다
- [ ] `wiki/records/reports/2026-08-18_S-TEAM-COVERAGE-EXPAND_리포트.md` 제출
      (재현 명령 + 실제 출력)
