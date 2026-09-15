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
    "voc-degraded-escalates-v1": Scenario(
        scenario_id="voc-degraded-escalates-v1",
        title="근거가 부족하면 정책을 찾지 않고 사람에게 넘긴다",
        nodeid=("tests/unit/teams/test_voc_store_manager.py"
                "::test_degraded_context_escalates_without_policy_lookup"),
        objective="VOC Team — ContextPack 이 축소됐을 때 무엇을 하지 않는지 본다.",
        needs_db=False,
    ),
    "fulfillment-lost-shipment-approval-v1": Scenario(
        scenario_id="fulfillment-lost-shipment-approval-v1",
        title="분실 배송은 재발송을 제안하고 승인을 기다린다",
        nodeid=("tests/unit/teams/test_fulfillment_logistics.py"
                "::test_lost_shipment_proposes_replacement_with_approval"),
        objective="배송 Team — 실행하지 않고 제안까지만 가는 경계를 본다.",
        needs_db=False,
    ),
    "catalog-compliance-escalates-v1": Scenario(
        scenario_id="catalog-compliance-escalates-v1",
        title="규정 적합성은 결과를 주장하지 않고 넘긴다",
        nodeid=("tests/unit/teams/test_catalog_verification.py"
                "::test_compliance_check_always_escalates_without_claiming_a_result"),
        objective="카탈로그·검증 Team(A2A Remote 대상) — 모르는 것을 지어내지 않는 규칙을 본다.",
        needs_db=False,
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

# ★2026-09-14 커머스 중지 — 이 시나리오들이 가리키던 테스트가 저장소에서 나갔다.
#  지우지 않는다. 정의는 위에 그대로 있고, 이 집합에서 빼면 되살아난다.
PARKED_SCENARIO_IDS = frozenset({
    "shipping-status-resolved-v1", "voc-batch-tenant-scoped-v1", "review-pii-escalates-v1",
    "procurement-policy-evidence-v1", "voc-degraded-escalates-v1",
    "fulfillment-lost-shipment-approval-v1", "catalog-compliance-escalates-v1",
    "return-refund-no-side-effect-v1",
})
PARKED_SCENARIOS = {k: v for k, v in SCENARIOS.items() if k in PARKED_SCENARIO_IDS}
# 오타 난 id 를 조용히 넘기지 않는다 — 중지했다고 믿는 시나리오가 살아 있게 된다.
assert PARKED_SCENARIO_IDS <= set(SCENARIOS), PARKED_SCENARIO_IDS - set(SCENARIOS)
for _scenario_id in PARKED_SCENARIO_IDS:
    SCENARIOS.pop(_scenario_id)

# ★베이스먼트 시나리오. 도메인이 바뀌어도 승계되는 코어(v11 §0-2)만 돈다 —
#  Team 은 테스트용 가짜(FakeTeam)라 여행 Team 이 바뀌어도 이 경로는 그대로다.
SCENARIOS["status-inquiry-untouched-v1"] = Scenario(
    scenario_id="status-inquiry-untouched-v1",
    title="조회형 문의 하나가 도메인 데이터를 건드리지 않고 끝난다",
    nodeid=(
        "tests/integration/controller/test_controller_integration.py"
        "::test_e2e_status_inquiry_does_not_touch_the_booking"
    ),
    objective=(
        "Case 가 만들어지고 라우팅되고 Team 이 읽기만 한 뒤 닫히는 코어 전 구간을 본다. "
        "Team 은 가짜라 도메인이 무엇이든 같은 경로다. 조회는 제안을 내지 않는다."
    ),
    needs_db=True,
)
SCENARIOS["checkpoint-not-projection-v1"] = Scenario(
    scenario_id="checkpoint-not-projection-v1",
    title="실행 스냅샷은 업무 상태가 아니다",
    nodeid=(
        "tests/integration/controller/test_controller_integration.py"
        "::test_run_persists_fixed_graph_revision_and_checkpoint_is_not_projection_state"
    ),
    objective="checkpoint 를 고쳐도 Case 가 안 바뀐다 — 권위 있는 상태는 customer_cases 하나다.",
    needs_db=True,
)
SCENARIOS["engine-serves-another-domain-v1"] = Scenario(
    scenario_id="engine-serves-another-domain-v1",
    title="같은 검증 엔진이 다른 도메인을 한 줄도 안 고치고 돌린다",
    nodeid=(
        "tests/architecture/test_engine_serves_another_domain.py"
        "::test_refund_over_the_order_total_is_rejected"
    ),
    objective=(
        "보스전용. 코어는 도메인을 모른다는 주장의 유일한 대조군이다. "
        "선언만 갈아 끼우고 app/core/verification.py 는 그대로 쓴다."
    ),
    needs_db=False,
)
# ★2026-09-14 codex-alt 검수 — 승계 목록(v11 §0-2) 중 바깥함·Registry·TeamExecutorPort 가
#  학습 시나리오에 없었다. 셋 다 도메인 어휘 없이 도는 테스트를 골랐다.
SCENARIOS["outbox-tenant-guard-v1"] = Scenario(
    scenario_id="outbox-tenant-guard-v1",
    title="바깥함은 tenant 를 모르는 메시지를 내보내지 않는다",
    nodeid=(
        "tests/integration/messaging/test_outbox_tenant_guard.py"
        "::test_publishing_without_any_tenant_is_rejected"
    ),
    objective=(
        "메시지는 되돌릴 수 없다. tenant 가 비면 'unknown' 같은 임시값으로 채우지 않고 "
        "발행을 거절한다 — 모르는 값을 지어내면 오류가 데이터가 된다."
    ),
    needs_db=True,
)
SCENARIOS["registry-default-capability-v1"] = Scenario(
    scenario_id="registry-default-capability-v1",
    title="Registry 는 맞는 기능이 없을 때 선언된 기본값으로 간다",
    nodeid=(
        "tests/unit/core/test_registry_capability_default.py"
        "::test_unmatched_intent_falls_back_to_declared_default_capability"
    ),
    objective=(
        "Core 는 Team 내부를 모른다. TeamManifest 선언만 보고 기능을 고르고, "
        "요청 종류와 맞는 것이 없으면 Team 이 선언한 default_capability 를 쓴다."
    ),
    needs_db=False,
)
SCENARIOS["remote-team-failure-escalates-v1"] = Scenario(
    scenario_id="remote-team-failure-escalates-v1",
    title="원격 Team 이 실패하면 실패로 매핑되고 사람에게 넘어간다",
    nodeid=(
        "tests/integration/a2a/test_travel_remote_round_trip.py"
        "::test_remote_failure_maps_to_escalate"
    ),
    objective=(
        "TeamExecutorPort 뒤에 로컬 대신 A2A 원격이 붙어도 Core 가 받는 것은 같은 TeamResult 다. "
        "원격이 못 하면 성공으로 추정하지 않고 escalate 로 돌려준다."
    ),
    needs_db=False,
)
# ★2026-09-14 승계 목록의 남은 빈 행 둘 — 감사·tenant 격리, 평가 하네스.
#  RLS 는 tests/ 에서 'rls|RLS|row level' 로 찾았고 안 나왔다(다른 이름의 검사는 놓칠 수 있다).
SCENARIOS["audit-pii-redacted-v1"] = Scenario(
    scenario_id="audit-pii-redacted-v1",
    title="PII 는 DB·API·감사 기록 어디에도 원문으로 남지 않는다",
    nodeid=(
        "tests/security/test_pii_redaction_runtime.py"
        "::test_case_message_is_redacted_in_db_api_and_audit"
    ),
    objective=(
        "DB 에만 가리고 감사 기록에 원문이 남는 실수를 한 번에 막는다. 원문은 저장 전에 가려지고, "
        "LLM 과 감사 기록에는 가린 것만 간다(정본 INV-CS-SEC-004)."
    ),
    needs_db=True,
)
SCENARIOS["tenant-scope-query-v1"] = Scenario(
    scenario_id="tenant-scope-query-v1",
    title="고객을 지정하지 않은 조회도 tenant 밖으로 나가지 않는다",
    nodeid=(
        "tests/security/test_query_scope.py"
        "::test_case_list_without_customer_stays_inside_the_tenant"
    ),
    objective=(
        "조건 없는 조회는 그 자체가 보안 결함이다. customer 를 비워도 tenant 조건은 빠지지 않는다"
        "(정본 INV-CS-SEC-006)."
    ),
    needs_db=True,
)
SCENARIOS["eval-defense-blocks-attacks-v1"] = Scenario(
    scenario_id="eval-defense-blocks-attacks-v1",
    title="방어 지표는 fixture 의 정답을 세지 않고 실제 방어를 돌려 잰다",
    nodeid="tests/unit/eval/test_defense_metrics.py::test_attack_fixtures_are_all_blocked",
    objective=(
        "평가 하네스가 공격 fixture 마다 코어 검증 엔진을 실제로 돌려 막혔는지 센다. "
        "정답과 판정을 같은 파일에서 읽으면 무엇을 재도 100% 가 나온다 — 처음 구현이 그랬다."
    ),
    needs_db=False,
)
# ★v11 결정 15 — 모르는 값을 만들지 않는다. 사슬 자체는 여행 인프라에 있지만 구조는 도메인이 없다
#  (소스 목록을 받아 차례로 묻는다). ☆처음엔 "cs 에 경로가 없다" 고 믿었다 — 확인 안 한 오류였다.
SCENARIOS["fallback-chain-says-so-v1"] = Scenario(
    scenario_id="fallback-chain-says-so-v1",
    title="1차 소스가 못 주면 대체 소스가 답하고, 넘어간 사실을 숨기지 않는다",
    nodeid=(
        "tests/unit/travel/test_kma_weather.py"
        "::test_when_the_primary_fails_the_fallback_answers_and_says_so"
    ),
    objective=(
        "값을 모른다고 비워 두지도, 지어내지도 않는다 — 다음 소스에 묻는다. 누가 답했는지는 source 에, "
        "대체로 넘어간 사실은 fell_back_from 에 남는다. 전부 실패하면 all_failed 로 센다(치명)."
    ),
    needs_db=False,
)
