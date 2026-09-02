"""Mock-only Return & Refund Team.

This module may calculate and propose actions, but it never performs a return
or refund side effect.  Approval is the boundary for every such proposal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.contracts import ActionProposal, Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.core.idempotency import idempotency_key
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


@dataclass(frozen=True)
class RefundOutcome:
    """환불 금액을 구했거나, 왜 못 구했는지.

    ★"못 구했다" 를 0 이나 None 으로 돌려주지 않는다. 부르는 쪽이 그걸 금액으로
      쓰면 고객에게 잘못된 액수가 나간다. 실패는 이유와 함께 돌려준다.
    """

    amount: int = 0
    basis: dict[str, Any] = field(default_factory=dict)
    failure_code: str | None = None
    reason: str = ""


class ReturnRefundTeam:
    manifest = TeamManifest(
        team_id="return_refund",
        display_name="Return & Refund Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["return.check_eligibility", "return.request", "refund.calculate"],
        accepted_case_types=["return", "refund", "exchange"],
        required_context=["case_state", "policy", "db_facts", "history"],
        # ★`read.order_items` 는 2026-09-01 에 더했다. 환불 금액을 주문 총액의
        #   균등 분할로 추정하던 것을 품목 단가로 정확히 구하기 위해서다(D-001 1-A).
        #   툴은 이미 있었지만 이 Team 의 allowed_tools 에 없어 Registry 가 막고 있었다.
        # ★`read.catalog` 는 2026-09-03 에 더했다. 반품 제한(주문제작 등)을
        #   보려면 상품을 조회할 수단이 있어야 하는데 없었다 — `read.order_items`
        #   를 더할 때와 같은 상황이다(툴은 있는데 allowlist 에 없어 Registry 가
        #   막고 있었다).
        allowed_tools=["read.order", "read.order_items", "read.return", "read.policy",
                       "read.catalog"],
        knowledge_scope=["order", "return", "refund", "exchange", "policy"],
        max_steps=6,
        active=True,
        implementation_revision="2026-09-01",
        # ★"exchange" intent 는 이름으로 매칭되는 capability 가 없다 — 셋 다
        #   "exchange." 로 시작하지 않는다(return./refund.). 지금 실제
        #   동작(capabilities[0])과 같은 값을 명시적으로 선언한다.
        default_capability="return.check_eligibility",
    )

    def __init__(self, tools: ReadToolbox) -> None:
        self.tools = tools

    # ★실행 요청임을 분명히 밝히는 문구만 잡는다. 안전 쪽으로 좁게 — 애매하면
    #   지금 기본 동작(check_eligibility, 정보성 응답)을 그대로 둔다.
    # ★"교환해 주세요"(요청)와 "교환해야 하나요?"(고민)를 가른다. 전에는
    #   `"교환해"` 하나로 잡아서 후자까지 실행 요청으로 봤다 — 같은 결함을
    #   procurement 의 `"취소해"` 에서 holdout 실측으로 확인했다(2026-09-02,
    #   h-order-02 "주문 전체를 취소해야 하나요?"). 여기도 같이 좁힌다.
    _ACTION_REQUEST_MARKERS = (
        "교환해 주", "교환해주", "교환 신청", "교환하고 싶", "교환 원해",
        "반품해 주", "반품해주", "반품 신청", "반품하고 싶", "반품 원해",
        "바꿔주세요", "바꿔 주세요", "바꾸고 싶",
    )

    # ★"교환하고 싶습니다. **신청 기한을 알려 주세요**" 처럼 의사와 문의가
    #   한 문장에 같이 오면 **문의 쪽으로 둔다.** 자격부터 확인해 주는 것이
    #   맞고, 이 저장소의 안전 방향과도 같다 — 정보성 응답은 되돌릴 수 있지만
    #   잘못 만든 신청은 승인 큐를 오염시킨다.
    #   golden 라벨도 이런 혼합 문장을 `return.check_eligibility` 로 매긴다
    #   (g-exchange-01/02, 2026-09-03 실측). `fulfillment_logistics` 에 넣은
    #   같은 성격의 억제를 여기에도 맞춘다.
    _INQUIRY_MARKERS = ("기준", "알려 주", "알려주", "궁금", "해당하나요",
                        "가능한가요", "되나요", "얼마나")

    @staticmethod
    def select_capability(intent: str | None, input_text: str) -> str | None:
        """"return"/"exchange" intent가 자격 문의인지 실행 요청인지 가른다.

        ★2026-09-01 — intent 문자열만으로는 팀의 capability 3종 중 어느 것도
          제대로 못 고른다(특히 "exchange"는 이름으로 매칭되는 capability가
          하나도 없어 늘 check_eligibility 로만 갔다 — 실제 교환/반품 신청
          경로(return.request)에 영원히 도달 못 함,
          docs/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md).
          여기서 신호가 없으면 `None`을 돌려줘 기존 규칙(네임스페이스 매칭 →
          default_capability)에 그대로 맡긴다 — 기존 동작을 바꾸지 않는다.
        """
        if intent not in {"return", "exchange"}:
            return None
        if any(marker in input_text for marker in ReturnRefundTeam._INQUIRY_MARKERS):
            return None  # 의사와 문의가 섞여 있으면 자격 확인 쪽으로 둔다
        if any(marker in input_text for marker in ReturnRefundTeam._ACTION_REQUEST_MARKERS):
            return "return.request"
        return None

    @staticmethod
    def _result(task: TeamTask, **kwargs: Any) -> TeamResult:
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, **kwargs)

    @staticmethod
    def _evidence(task: TeamTask, order: Any, returns: Any, policy: Any) -> list[Evidence]:
        evidence = list(task.context.evidence)
        evidence.append(Evidence(
            evidence_id="tool:return_refund",
            source_type="tool_result",
            source_id="read.order+read.return+read.policy",
            claim="주문, 반품 이력, 반품·환불 정책을 조회했다.",
            value={"order": order, "returns": returns, "policy": policy},
            confidence=1.0,
            observed_at=datetime.now(UTC),
        ))
        return evidence

    @staticmethod
    def _policy_days(policy: Any, reason: str | None) -> int:
        # The mock accepts common policy shapes while retaining conservative defaults.
        values: list[Any] = policy if isinstance(policy, list) else [policy]
        for item in values:
            value = item.value if isinstance(item, Evidence) else item
            if isinstance(value, dict):
                key = "defective_return_period_days" if reason == "defective" else "return_period_days"
                if isinstance(value.get(key), int):
                    return value[key]
                if isinstance(value.get("return_period_days"), int):
                    return value["return_period_days"]
        return 90 if reason == "defective" else 7

    @staticmethod
    def _refund_amount(items: Any, order_total_cents: int, quantity: int,
                       order_item_id: str | None = None) -> "RefundOutcome":
        """반품 수량에 해당하는 환불 금액을 **구할 수 있을 때만** 구한다.

        ★이전 구현은 `total_cents * quantity // item_count` 였다. 이 한 줄에
          말하지 않은 가정이 둘 들어 있었다(D-001):

            (1) 주문의 모든 품목 값이 같다
            (2) 주문에 할인이 없다

          둘 다 틀리면 고객이 받을 금액이 달라진다. 여기서는 두 가정을 **검사
          가능한 조건**으로 바꾼다 — 성립하면 정확히 계산하고, 안 하면 계산하지
          않는다.

        ★(2)를 어떻게 아는가: 품목 단가 합이 주문 총액과 다르면 그 차액이
          할인·쿠폰·배송비 같은 조정이다. 그게 있으면 "이 품목의 실결제액" 을
          이 데이터만으로는 모른다 — 쇼핑몰이 실결제액을 줘야 한다(D-001 1-B).

        ★(1)을 어떻게 아는가: 품목이 하나면 가정이 필요 없다. 여럿이면 **어느
          품목을 반품하는지** 를 알아야 한다. 2026-09-01 마이그레이션 007 로
          `returns.order_item_id` 가 생겨서, 그 값이 있으면 다품목 주문도 정확히
          계산한다. **없으면(NULL) 여전히 만들지 않는다** — 그 이전에 쌓인
          반품에는 품목 정보가 없고, 지금 와서 찍으면 지어낸 값이다.
        """
        if not isinstance(items, list) or not items:
            return RefundOutcome(failure_code="refund_calculation_evidence_missing",
                                 reason="주문 품목을 읽지 못해 환불 금액을 계산할 수 없습니다.")
        try:
            lines = [(str(item.get("order_item_id") or ""), str(item["sku"]),
                      int(item["quantity"]), int(item["unit_cents"]))
                     for item in items]
        except (KeyError, TypeError, ValueError, AttributeError):
            return RefundOutcome(failure_code="refund_calculation_evidence_missing",
                                 reason="주문 품목에 수량·단가가 없어 환불 금액을 계산할 수 없습니다.")

        subtotal = sum(unit * count for _, _, count, unit in lines)
        if subtotal != order_total_cents:
            # 차액이 곧 할인·쿠폰·배송비다. 어느 품목에 얼마가 붙었는지 모른다.
            return RefundOutcome(
                failure_code="refund_amount_not_derivable",
                reason=(f"품목 단가 합({subtotal})과 주문 총액({order_total_cents})이 달라 "
                        "실제 결제액을 알 수 없습니다. 쇼핑몰의 실결제 내역이 필요합니다."))
        if len(lines) == 1:
            selected = lines[0]
        elif order_item_id:
            # 반품이 어느 품목인지 밝혔다(마이그레이션 007).
            selected = next((line for line in lines if line[0] == str(order_item_id)), None)
            if selected is None:
                return RefundOutcome(
                    failure_code="refund_item_not_in_order",
                    reason=("반품이 가리키는 품목이 이 주문에 없습니다. "
                            "주문과 반품이 어긋나 있습니다."))
        else:
            return RefundOutcome(
                failure_code="refund_item_unattributable",
                reason=("주문에 품목이 여러 개인데 반품 요청에 어느 품목인지가 없어 "
                        "환불 금액을 정할 수 없습니다."))

        item_id, sku, ordered_quantity, unit_cents = selected
        if quantity <= 0 or quantity > ordered_quantity:
            return RefundOutcome(
                failure_code="refund_quantity_exceeds_order",
                reason=f"반품 수량({quantity})이 주문 수량({ordered_quantity})을 벗어납니다.")
        return RefundOutcome(amount=unit_cents * quantity,
                             basis={"basis": "order_item_unit_price", "sku": sku,
                                    "order_item_id": item_id or None,
                                    "unit_cents": unit_cents, "return_quantity": quantity,
                                    "order_total_cents": order_total_cents,
                                    "order_item_lines": len(lines)})

    @staticmethod
    def _date(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                return None
        return None

    #: 상품 속성으로 판정할 수 있는 반품 제한 코드 → 고객에게 말할 사유.
    #  ★여기 없는 코드가 오면 **모르는 제한**이다 — 통과시키지 않고 사람에게 넘긴다.
    RETURN_RESTRICTIONS = {
        "made_to_order": "주문제작·맞춤 상품이라 일반 반품 절차로 처리되지 않을 수 있습니다.",
    }

    def _restriction(self, task: TeamTask, order: Any, seen: set[str]) -> tuple[str | None, Any]:
        """반품 대상 품목의 상품 제한을 조회한다. (제한코드|None, 조회한 상품들)

        ★**모름과 제한없음을 구분한다.** `products.return_restriction` 이 NULL 이면
          "모름" 이고(마이그레이션 008), 그때는 제한이 없다고 단정하지 않는다.
          반환값 첫 자리:
              None        판정할 수 없음(모름) 또는 조회 실패
              "none"      제한 없음이 확인됨
              그 밖        제한 코드
        """
        order_id = str(order.get("order_id")) if isinstance(order, dict) else None
        if not order_id:
            return None, None
        try:
            items = self.tools.call("read.order_items", task.context, {"order_id": order_id},
                                    task.allowed_tools, seen)
        except (ToolLoopExceeded, Exception):
            return None, None
        if not isinstance(items, list) or not items:
            return None, None

        found: list[dict[str, Any]] = []
        for item in items:
            sku = item.get("sku") if isinstance(item, dict) else None
            if not sku:
                continue
            try:
                product = self.tools.call("read.catalog", task.context, {"sku": str(sku)},
                                          task.allowed_tools, seen)
            except (ToolLoopExceeded, Exception):
                continue
            if isinstance(product, dict):
                found.append(product)

        if not found:
            return None, None
        restrictions = [str(p.get("return_restriction")) for p in found
                        if p.get("return_restriction") is not None]
        if len(restrictions) != len(found):
            # 하나라도 모르면 전체를 "모름" 으로 둔다 — 아는 것만 보고 단정하지 않는다.
            return None, found
        blocking = [r for r in restrictions if r != "none"]
        return (blocking[0] if blocking else "none"), found

    async def execute(self, task: TeamTask) -> TeamResult:
        evidence = list(task.context.evidence)
        if task.context.degraded:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="degraded_context")
        if task.capability not in self.manifest.capabilities:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="unsupported_capability")

        seen: set[str] = set()
        try:
            order = self.tools.call("read.order", task.context, {}, task.allowed_tools, seen)
            returns = self.tools.call("read.return", task.context, {}, task.allowed_tools, seen)
            policy = self.tools.call("read.policy", task.context, {"query": task.input_text}, task.allowed_tools, seen)
        except ToolLoopExceeded:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="tool_loop_guard")

        evidence = self._evidence(task, order, returns, policy)
        history = returns if isinstance(returns, list) else []
        current = task.context.current_state
        request = next((item for item in history if isinstance(item, dict)), None)
        reason = (request or {}).get("reason_code") or current.get("reason_code")
        quantity = (request or {}).get("quantity") or current.get("return_quantity")
        if not order or not policy:
            return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="required_evidence_missing")
        if reason is None or quantity is None:
            return self._result(task, outcome="waiting", confidence=0.0, evidence=evidence,
                                next_action=NextAction.WAIT_FOR_INPUT, wait_reason="customer_input",
                                required_input_schema={"required": ["reason_code", "return_quantity"]},
                                warnings=["반품 사유와 수량을 확인할 근거가 필요합니다."])

        # ``requested`` can be the current request supplied by the read tool;
        # only a previously accepted/in-flight/completed record blocks a new one.
        active_history = {"approved", "processing", "completed"}
        if any(item.get("status") in active_history for item in history if isinstance(item, dict)):
            return self._result(task, outcome="escalated", confidence=0.9, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="return_already_in_history")

        ordered_at = self._date(order.get("ordered_at")) if isinstance(order, dict) else None
        period_days = self._policy_days(policy, reason)
        if ordered_at and (datetime.now(UTC) - ordered_at.astimezone(UTC)).days > period_days:
            return self._result(task, outcome="escalated", confidence=0.9, evidence=evidence,
                                next_action=NextAction.ESCALATE, failure_code="return_period_expired",
                                warnings=[f"반품 가능 기간 {period_days}일이 경과했습니다."])

        # ★상품 자체의 반품 제한을 본다 (2026-09-03,
        #   docs/reports/debugs/2026-09-03_반품제한을_안_보고_정책근거상_가능하다고_답한다.md).
        #   전에는 이 검사가 아예 없으면서 답변만 "정책 근거상" 이라고 말했다.
        restriction, catalog_rows = self._restriction(task, order, seen)
        if catalog_rows:
            evidence.append(Evidence(
                evidence_id="tool:return_refund:read.catalog", source_type="tool_result",
                source_id="read.catalog", claim="반품 대상 품목의 상품 반품 제한을 조회했다.",
                value={"products": catalog_rows}, confidence=1.0, observed_at=datetime.now(UTC)))
        if restriction is not None and restriction != "none":
            reason_text = self.RETURN_RESTRICTIONS.get(
                restriction, "이 상품에는 일반 반품 절차로 처리되지 않을 수 있는 제한이 있습니다.")
            return self._result(task, outcome="escalated", confidence=0.9, evidence=evidence,
                                next_action=NextAction.ESCALATE,
                                failure_code="return_restricted_product",
                                warnings=[reason_text])

        if task.capability == "return.check_eligibility":
            if restriction is None:
                # ★제한 여부를 **모른다.** 그러면 "정책 근거상 가능" 이라고 말하지
                #   않는다 — 실제로 확인한 것(기간·이력)만 말하고 나머지는 열어 둔다.
                return self._result(task, outcome="completed", confidence=0.7, evidence=evidence,
                                    answer=("반품 가능 기간과 기존 반품 이력에는 걸리는 점이 없습니다. "
                                            "다만 이 상품의 반품 제한 여부는 확인되지 않아, "
                                            "상담원이 상품 정책을 함께 확인한 뒤 안내드립니다."),
                                    next_action=NextAction.RESPOND,
                                    decisions=[{"eligible": None, "period_days": period_days,
                                                "restriction": "unknown"}],
                                    warnings=["상품 반품 제한 정보가 없어 자격을 단정하지 않았습니다."])
            return self._result(task, outcome="completed", confidence=0.9, evidence=evidence,
                                answer="제공된 주문·반품 이력·정책 근거상 반품 요청을 검토할 수 있습니다.",
                                next_action=NextAction.RESPOND,
                                decisions=[{"eligible": True, "period_days": period_days}])

        order_id = str(order.get("order_id"))
        request_id = str(current.get("request_id") or task.case_id)
        if task.capability == "return.request":
            action_type = "return.request"
            arguments = {"order_id": order_id, "reason_code": reason, "return_quantity": quantity}
            decision = {"classification": "return_request_proposed", "mock_side_effect": False}
        else:
            total = order.get("total_cents")
            if not isinstance(total, int):
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE, failure_code="refund_calculation_evidence_missing")
            try:
                items = self.tools.call("read.order_items", task.context, {"order_id": order_id},
                                        task.allowed_tools, seen)
            except ToolLoopExceeded:
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE, failure_code="tool_loop_guard")

            # ★어느 품목을 반품하는가 — 반품 레코드가 밝혔으면 그것을 쓴다.
            #   없으면(옛 데이터) 다품목 주문에서는 금액을 만들지 않는다.
            returned_item = (request or {}).get("order_item_id") or current.get("order_item_id")
            outcome = self._refund_amount(items, total, int(quantity),
                                          str(returned_item) if returned_item else None)
            if outcome.failure_code is not None:
                # ★근거 없이 금액을 만들지 않는다. "환불됩니다" 를 잘못 말하면
                #   고객이 손해를 본다(`CLAUDE.md` §0). 못 구하면 사람에게 넘긴다.
                return self._result(task, outcome="escalated", confidence=0.0, evidence=evidence,
                                    next_action=NextAction.ESCALATE, failure_code=outcome.failure_code,
                                    warnings=[outcome.reason])
            amount = outcome.amount
            action_type = "refund.calculate"
            arguments = {"order_id": order_id, "refund_amount_cents": amount, "return_quantity": quantity,
                         "calculation_basis": outcome.basis}
            decision = {"classification": "refund_calculation_proposed", "calculated_amount_cents": amount,
                        "mock_side_effect": False}
        proposal = ActionProposal(action_type=action_type, arguments=arguments,
                                  idempotency_key=idempotency_key(tenant_id=task.context.tenant_id,
                                  request_id=request_id, action_type=action_type, business_subject=str(task.case_id)),
                                  approval_required=True, risk_level="medium",
                                  rationale_evidence_ids=[item.evidence_id for item in evidence])
        return self._result(task, outcome="waiting", confidence=0.9, evidence=evidence,
                            next_action=NextAction.WAIT_FOR_APPROVAL, wait_reason="human_approval",
                            action_proposals=[proposal], decisions=[decision],
                            warnings=["Mock 단계에서는 승인 제안만 생성하며 실제 처리는 수행하지 않습니다."])


__all__ = ["ReturnRefundTeam"]
