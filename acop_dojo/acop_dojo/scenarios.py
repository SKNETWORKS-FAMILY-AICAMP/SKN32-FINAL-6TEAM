"""학습 시나리오 목록.

각 시나리오는 대상 저장소의 실제 pytest 노드 하나를 가리킨다. 별도로 만든
축소 복제본이 아니라 진짜 코드가 도는 경로여야 배운 것이 그대로 쓰인다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    nodeid: str
    #: 이 시나리오로 무엇을 보게 하려는가
    objective: str
    #: DB 가 필요한가 (없으면 unit 만으로 돈다)
    needs_db: bool


SCENARIOS: dict[str, Scenario] = {
    "shipping-status-resolved-v1": Scenario(
        scenario_id="shipping-status-resolved-v1",
        title="배송 문의 하나가 주문을 건드리지 않고 끝난다",
        nodeid=(
            "tests/integration/controller/test_controller_integration.py"
            "::test_e2e_delivery_inquiry_does_not_touch_the_order"
        ),
        objective=(
            "Case 가 만들어지고 라우팅되고 Team 이 읽기만 한 뒤 종료되는 전체 경로를 한 번에 본다. "
            "조회 문의에서는 ActionProposal 이 나오지 않는다는 것이 핵심이다."
        ),
        needs_db=True,
    ),
    "case-reducer-versions-v1": Scenario(
        scenario_id="case-reducer-versions-v1",
        title="이벤트를 접으면 언제나 version 이 이벤트 수와 같다",
        nodeid="tests/unit/core/test_case_reducer.py::test_version_always_equals_event_count",
        objective="상태가 이벤트의 접기 결과라는 것을 DB 없이 확인한다.",
        needs_db=False,
    ),
    "api-idempotent-create-v1": Scenario(
        scenario_id="api-idempotent-create-v1",
        title="같은 생성 요청을 열 번 보내도 Action 은 한 건이다",
        nodeid=("tests/integration/api/test_api_runtime.py"
                "::test_same_create_request_ten_times_has_one_action_request"),
        objective="Core 2 — 외부 진입점에서 멱등성이 어떻게 지켜지는지 본다.",
        needs_db=True,
    ),
    "voc-batch-tenant-scoped-v1": Scenario(
        scenario_id="voc-batch-tenant-scoped-v1",
        title="VOC 배치는 tenant 안에서만 돌고 두 번 돌려도 같다",
        nodeid="tests/unit/voc/test_feedback.py::test_batch_is_tenant_scoped_and_idempotent",
        objective="VOC — 분류와 배치가 경계를 어떻게 지키는지 본다.",
        needs_db=False,
    ),
    "review-pii-escalates-v1": Scenario(
        scenario_id="review-pii-escalates-v1",
        title="PII 가 보이면 재시도하지 않고 사람에게 넘긴다",
        nodeid="tests/unit/teams/test_response_review.py::test_pii_escalates_without_retry",
        objective="답변 검토 — 무엇을 재시도하고 무엇을 넘기는지 본다.",
        needs_db=False,
    ),
    "procurement-policy-evidence-v1": Scenario(
        scenario_id="procurement-policy-evidence-v1",
        title="조달 견적은 정책과 가격 근거로만 만든다",
        nodeid=("tests/unit/teams/test_procurement_order_payment.py"
                "::test_procurement_quote_uses_policy_and_pricing_evidence"),
        objective="커머스 Team — 근거 없이 값을 지어내지 않는다는 규칙을 본다.",
        needs_db=False,
    ),
    "ui-evidence-free-proposal-v1": Scenario(
        scenario_id="ui-evidence-free-proposal-v1",
        title="근거 없는 제안은 화면에서 결정 버튼이 죽어 있다",
        nodeid="tests/e2e/test_operations_ui.py::test_evidence_free_proposal_has_disabled_decision",
        objective="프론트 — Core 의 근거 규칙이 화면까지 내려오는 지점을 본다.",
        needs_db=True,
    ),
    "return-refund-no-side-effect-v1": Scenario(
        scenario_id="return-refund-no-side-effect-v1",
        title="반품 Team 은 환불을 실행하지 않고 제안만 낸다",
        nodeid=(
            "tests/unit/teams/test_return_refund.py"
            "::test_refund_calculation_is_not_completed_side_effect"
        ),
        objective=(
            "보스전용. 0~2단계에서 한 번도 지나가지 않은 모듈이다. 같은 규칙이 다른 코드에서 "
            "어떻게 지켜지는지 스스로 찾아야 한다."
        ),
        needs_db=False,
    ),
}


def get(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError:
        known = ", ".join(SCENARIOS)
        raise SystemExit(f"모르는 시나리오다: {scenario_id}\n아는 것: {known}") from None
