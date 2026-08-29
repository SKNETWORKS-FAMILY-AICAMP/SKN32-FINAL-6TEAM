from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, Evidence, TeamTask
from app.infrastructure.db.session import get_connection
from app.modules.customer_ops import ProcurementOrderPaymentTeam
from app.tools.read_tools import ReadToolbox
from scripts.seed import load_catalog
from tests.integration.db.test_db_integration import db  # noqa: F401


@pytest.mark.asyncio
async def test_procurement_quote_reads_seeded_product_without_injected_pricing(db):
    conn, tenant = db
    customer_id = uuid4()
    sku, name, unit_cents, _status = next(item for item in load_catalog() if item[0].startswith("SKU-CPG-"))
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s,%s,%s)",
            (customer_id, tenant, "catalog-customer"),
        )
        cur.execute(
            "INSERT INTO products (tenant_id, sku, name, unit_cents, status) VALUES (%s,%s,%s,%s,'active')",
            (tenant, sku, name, unit_cents),
        )
    conn.commit()

    case_id = uuid4()
    evidence = Evidence(
        evidence_id="ev:catalog-request", source_type="customer_message", source_id=str(case_id),
        claim="customer requested a catalog quote", value={"sku": sku}, confidence=1.0,
        observed_at=datetime.now(UTC),
    )
    context = ContextPack(
        pack_id=uuid4(), case_id=case_id, team_id="procurement_order_payment", tenant_id=tenant,
        knowledge_scope=["catalog", "pricing"], current_state={"customer_id": str(customer_id), "sku": sku},
        evidence=[evidence], estimated_input_tokens=10,
    )
    task = TeamTask(
        task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="procurement_order_payment",
        capability="procurement.quote", case_version=1, input_text=f"Quote {sku}", context=context,
        allowed_tools=["read.policy", "read.catalog"],
        deadline_at=datetime.now(UTC) + timedelta(seconds=30),
    )

    result = await ProcurementOrderPaymentTeam(
        ReadToolbox(get_connection, policy_search=lambda *_: [{"policy_ref": "test-pricing"}])
    ).execute(task)

    assert result.outcome == "completed"
    assert result.decisions[0]["quote"] == {sku: unit_cents}
