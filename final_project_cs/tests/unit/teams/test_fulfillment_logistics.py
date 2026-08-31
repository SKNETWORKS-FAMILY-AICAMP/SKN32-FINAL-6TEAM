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
