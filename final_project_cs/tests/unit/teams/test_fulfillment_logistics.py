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
