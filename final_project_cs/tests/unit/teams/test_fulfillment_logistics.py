from __future__ import annotations

import pytest

from app.core.contracts import NextAction
from app.modules.customer_ops.fulfillment_logistics import FulfillmentLogisticsTeam
from legacy.final_project_cs.team_modules_v1.tests.test_team_scenarios import FakeTools, pack, task


def make_task(capability: str):
    context = pack("fulfillment_logistics")
    return context, task("fulfillment_logistics", capability, context, FulfillmentLogisticsTeam.manifest.allowed_tools)


def test_manifest_matches_fulfillment_logistics_contract():
    manifest = FulfillmentLogisticsTeam.manifest
    assert manifest.team_id == "fulfillment_logistics"
    assert manifest.capabilities == ["fulfillment.track", "shipment.status", "shipment.exception"]
    assert manifest.accepted_case_types == ["fulfillment", "shipping", "shipment"]
    assert manifest.allowed_tools == ["read.order", "read.shipment", "read.policy"]
    assert manifest.knowledge_scope == ["order", "shipping", "warehouse", "delivery_exception"]


@pytest.mark.asyncio
async def test_fulfillment_track_explains_order_and_shipment_facts():
    _, request = make_task("fulfillment.track")
    result = await FulfillmentLogisticsTeam(FakeTools({
        "read.order": {"order_id": "o1", "status": "packed"},
        "read.shipment": [{"shipment_id": "s1", "status": "label_created"}],
    })).execute(request)
    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert result.decisions[0]["status"] == "packed"


@pytest.mark.asyncio
async def test_shipment_status_explains_provider_status():
    _, request = make_task("shipment.status")
    result = await FulfillmentLogisticsTeam(FakeTools({
        "read.shipment": [{"shipment_id": "s1", "status": "in_transit"}],
    })).execute(request)
    assert result.outcome == "completed"
    assert "in_transit" in result.answer


@pytest.mark.asyncio
async def test_lost_shipment_proposes_replacement_with_approval():
    _, request = make_task("shipment.exception")
    result = await FulfillmentLogisticsTeam(FakeTools({
        "read.shipment": [{"shipment_id": "s1", "status": "lost"}],
    })).execute(request)
    assert result.outcome == "waiting"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "shipment.replace"
    assert result.action_proposals[0].approval_required is True
    assert result.action_proposals[0].rationale_evidence_ids


@pytest.mark.asyncio
async def test_delayed_shipment_proposes_reroute_with_approval():
    _, request = make_task("shipment.exception")
    result = await FulfillmentLogisticsTeam(FakeTools({
        "read.shipment": [{"shipment_id": "s1", "status": "delayed"}],
    })).execute(request)
    assert result.action_proposals[0].action_type == "shipment.reroute"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL


@pytest.mark.asyncio
async def test_missing_provider_status_escalates_without_action_proposal():
    _, request = make_task("shipment.exception")
    result = await FulfillmentLogisticsTeam(FakeTools({"read.shipment": []})).execute(request)
    assert result.outcome == "escalated"
    assert result.next_action is NextAction.ESCALATE
    assert result.failure_code == "shipment_status_unknown"
    assert result.action_proposals == []


# ── 2026-08-31: 모르는 상태와 근거-답변 일치를 안 세던 사각지대 ────────
#
# 두 변경이 전체 424개를 전부 통과했다.
#   1. 배송 상태의 unknown/unavailable 검사를 None 검사로 좁히기
#   2. 조회된 배송 건수를 세지 않고 0 으로 답하기
# 첫째는 "배송 상태는 unknown입니다" 가 고객에게 가는 것이고,
# 둘째는 근거에는 배송이 있는데 답변은 없다고 말하는 것이다.


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["unknown", "UNAVAILABLE", "", None])
async def test_unknown_shipment_status_escalates_instead_of_answering(status):
    _, request = make_task("shipment.status")
    result = await FulfillmentLogisticsTeam(FakeTools({
        "read.shipment": [{"shipment_id": "s1", "status": status}],
    })).execute(request)
    assert result.outcome == "escalated"
    assert result.next_action is NextAction.ESCALATE
    assert result.failure_code == "shipment_status_unknown"
    assert not result.answer, "모르는 상태를 답변 문장으로 만들었다"


@pytest.mark.asyncio
async def test_tracking_answer_counts_the_shipments_it_read():
    """답변의 건수가 읽어 온 근거와 어긋나면 안 된다."""
    _, request = make_task("fulfillment.track")
    shipments = [{"shipment_id": "s1", "status": "in_transit"},
                 {"shipment_id": "s2", "status": "in_transit"}]
    result = await FulfillmentLogisticsTeam(FakeTools({
        "read.order": {"order_id": "o1", "fulfillment_status": "partially_shipped"},
        "read.shipment": shipments,
    })).execute(request)
    assert result.outcome == "completed"
    assert f"{len(shipments)}건" in result.answer
    assert result.decisions[0]["shipment_count"] == len(shipments)


# ★2026-09-01 — "shipping" intent 는 이름으로 매칭되는 capability 가 없어
#   늘 fulfillment.track(주문 단위 정보성 응답)으로만 갔다. select_capability
#   가 분실·파손·지연 신고 문구를 잡아 shipment.exception 경로로 보낼 수
#   있는지 확인한다
#   (wiki/records/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md).
def test_select_capability_routes_damage_report_to_shipment_exception():
    assert FulfillmentLogisticsTeam.select_capability("shipping", "받은 상품이 파손되어 왔어요") == "shipment.exception"


def test_select_capability_routes_missing_delivery_to_shipment_exception():
    assert FulfillmentLogisticsTeam.select_capability("shipping", "배송이 계속 지연되고 있어요") == "shipment.exception"


def test_select_capability_returns_none_for_plain_status_inquiry():
    assert FulfillmentLogisticsTeam.select_capability("shipping", "제 주문 배송 상태가 궁금해요") is None


def test_select_capability_ignores_unrelated_intents():
    assert FulfillmentLogisticsTeam.select_capability("order", "파손됐어요") is None
    assert FulfillmentLogisticsTeam.select_capability(None, "파손됐어요") is None


# ★2026-09-02 holdout 실측으로 좁힌 경계 — "내 배송이 잘못됐다"와 "그럴 때
#   규칙이 뭐냐"는 다르다. 같은 낱말("지연")이 둘 다에 나오므로 규칙 문의는
#   이상 신고로 보지 않는다. 실제로 오탐 2건이 이렇게 잡혔다.
def test_policy_inquiry_containing_a_problem_word_is_not_an_exception_report():
    assert FulfillmentLogisticsTeam.select_capability("shipping", "배송 지연 기준을 알려 주세요") is None
    assert FulfillmentLogisticsTeam.select_capability("shipping", "명절 기간에 배송이 늦어질 수 있는지 미리 알고 싶습니다") is None


def test_an_actual_problem_report_still_routes_to_exception():
    """★규칙 문의를 걸러내면서 진짜 신고까지 놓치면 안 된다 — 양쪽을 같이 잰다."""
    assert FulfillmentLogisticsTeam.select_capability(
        "shipping", "배송완료 사진은 있는데 물건이 보이지 않습니다. 분실로 판정되려면 어떤 확인이 필요한가요?"
    ) == "shipment.exception"


def test_a_request_to_review_a_drafted_reply_is_not_an_exception_report():
    """★golden g-response-review-10 실측 — 배송 낱말이 있어도 대상이 다르다.

    "배송 지연 사유를 안내한 답변에 전화번호가 포함되지 않았는지 확인해 주세요"
    는 고객 자신의 배송을 신고하는 것이 아니라 **작성된 답변을 검토해 달라는**
    요청이다. 이걸 이상 신고로 보면 골든셋 결과가 통째로 흔들린다.
    """
    assert FulfillmentLogisticsTeam.select_capability(
        "shipping", "배송 지연 사유를 안내한 답변에 고객의 전화번호가 포함되지 않았는지 확인해 주세요") is None


def test_a_hypothetical_policy_question_is_not_an_exception_report():
    """★golden g-shipping-04 — "~지나면 …보는 건가요?" 는 가정형 질문이다."""
    assert FulfillmentLogisticsTeam.select_capability(
        "shipping", "아직 출고되지 않은 주문인데 출고 마감 시간이 지나면 배송 지연으로 보는 건가요?") is None


def test_a_request_to_check_is_not_a_request_to_act():
    """★golden g-shipping-05 — "확인해 주세요" 는 조회 요청이지 이상 신고가 아니다."""
    assert FulfillmentLogisticsTeam.select_capability(
        "shipping", "주문한 지 오래됐는데 출고 자체가 안 됐습니다. 지연 여부를 확인해 주세요.") is None
