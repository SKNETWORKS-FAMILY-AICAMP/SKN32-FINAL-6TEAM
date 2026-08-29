from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, NextAction, TeamTask
from app.modules.customer_ops.catalog_verification import CatalogVerificationTeam


class FakeTools:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def call(self, name, context, arguments, allowed_tools, seen):
        self.calls.append((name, arguments))
        return self.values.get(name)


def make_task(capability: str, **state):
    case_id = uuid4()
    context = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id="catalog_verification", tenant_id="tenant",
        knowledge_scope=CatalogVerificationTeam.manifest.knowledge_scope,
        current_state={"customer_id": str(uuid4()), **state}, estimated_input_tokens=10,
    )
    return TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="catalog_verification",
        capability=capability, case_version=1, input_text="catalog verification",
        context=context, allowed_tools=CatalogVerificationTeam.manifest.allowed_tools,
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )


@pytest.mark.asyncio
async def test_lookup_sku_returns_catalog_fact():
    task = make_task("catalog.lookup_sku", sku="SKU-1")
    tools = FakeTools({"read.catalog": {"sku": "SKU-1", "name": "Widget", "unit_cents": 1200, "status": "active"}})
    result = await CatalogVerificationTeam(tools).execute(task)
    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert result.decisions[0]["classification"] == "sku_found"


@pytest.mark.asyncio
async def test_lookup_unknown_sku_responds_not_found():
    task = make_task("catalog.lookup_sku", sku="SKU-MISSING")
    result = await CatalogVerificationTeam(FakeTools({"read.catalog": None})).execute(task)
    assert result.outcome == "completed"
    assert "찾을 수 없습니다" in result.answer
    assert result.decisions[0]["classification"] == "sku_not_found"


@pytest.mark.asyncio
async def test_verify_listing_matches_order_item():
    task = make_task("catalog.verify_listing", order_id="order-1", sku="SKU-1", product_name="Widget")
    tools = FakeTools({"read.order_items": [{"order_id": "order-1", "sku": "SKU-1", "name": "Widget",
                                               "quantity": 1, "unit_cents": 1200}]})
    result = await CatalogVerificationTeam(tools).execute(task)
    assert result.outcome == "completed"
    assert result.next_action is NextAction.RESPOND
    assert tools.calls == [("read.order_items", {"order_id": "order-1"})]


@pytest.mark.asyncio
async def test_verify_listing_mismatch_escalates():
    task = make_task("catalog.verify_listing", order_id="order-1", sku="SKU-CLAIMED", product_name="Claimed")
    tools = FakeTools({"read.order_items": [{"order_id": "order-1", "sku": "SKU-ACTUAL", "name": "Actual",
                                               "quantity": 1, "unit_cents": 1200}]})
    result = await CatalogVerificationTeam(tools).execute(task)
    assert result.outcome == "escalated"
    assert result.next_action is NextAction.ESCALATE
    assert result.failure_code == "listing_mismatch"


@pytest.mark.asyncio
async def test_compliance_check_always_escalates_without_claiming_a_result():
    task = make_task("catalog.compliance_check", sku="SKU-1")
    result = await CatalogVerificationTeam(FakeTools({})).execute(task)
    assert result.outcome == "escalated"
    assert result.next_action is NextAction.ESCALATE
    assert result.failure_code == "compliance_data_unavailable"
    assert result.warnings == ["컴플라이언스 데이터가 아직 없어 확인할 수 없습니다"]
