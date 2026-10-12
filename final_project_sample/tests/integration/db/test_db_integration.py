from uuid import uuid4

import pytest

from acop_basement.core.contracts import CaseStatus, StateConflict
from acop_basement.core.transition import OutboxMessage, transition_case
from acop_basement.domain.events import EventType
from acop_basement.infrastructure.db.repository import create_case
from acop_basement.infrastructure.db.session import get_connection


@pytest.fixture()
def db():
    tenant = "test_" + uuid4().hex
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tenants VALUES (%s,%s)", (tenant, "integration"))
            conn.commit()
            yield conn, tenant
        finally:
            conn.rollback()
            with conn.transaction():
                with conn.cursor() as cur:
                    # Remove every row owned by this fixture tenant, in FK order.
                    cur.execute("DELETE FROM team_tasks WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM llm_calls WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM agent_runs WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM incidents WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM payments WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM entitlements WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM subscriptions WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def test_schema_constraints_and_indexes(db):
    db, _ = db
    with db.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = {r[0] for r in cur.fetchall()}
        assert {"tenants","customers","customer_cases","case_events","agent_runs","team_tasks","action_requests","action_approvals","outbox","prompts","llm_calls","knowledge_documents","knowledge_chunks","feedback_analytics_reports"} <= tables
        cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
        indexes = {r[0] for r in cur.fetchall()}
        assert {"knowledge_chunks_embedding_idx","cases_tenant_customer_idx","events_case_version_idx"} <= indexes
        cur.execute("SELECT conname FROM pg_constraint WHERE conrelid='case_events'::regclass")
        assert any("case_id" in r[0] for r in cur.fetchall())
        cur.execute("SELECT conname FROM pg_constraint WHERE conrelid='action_requests'::regclass")
        assert any("tenant_id" in r[0] for r in cur.fetchall())
        cur.execute("SELECT conname FROM pg_constraint WHERE conrelid='outbox'::regclass")
        assert any("topic" in r[0] for r in cur.fetchall())


def test_transition_round_trip_and_versions(db):
    db, tenant = db
    with db.cursor() as cur:
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id", (tenant, uuid4().hex)); customer = cur.fetchone()[0]
    case_id = create_case(db, tenant_id=tenant, customer_id=customer, subject="integration")
    with db.transaction(): transition_case(db, tenant_id=tenant, case_id=case_id, expected_version=0, event_type=EventType.CREATED, payload={"channel":"test","message":"hello"}, actor_type="test")
    with db.transaction(): transition_case(db, tenant_id=tenant, case_id=case_id, expected_version=1, event_type=EventType.CLASSIFIED, payload={"intent":"billing","issue_code":"invoice","sentiment":"neutral"}, actor_type="test")
    with db.cursor() as cur:
        cur.execute("SELECT version,status FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (tenant,case_id)); assert cur.fetchone() == (2, CaseStatus.ROUTING)
        cur.execute("SELECT max(aggregate_version) FROM case_events WHERE tenant_id=%s AND case_id=%s", (tenant,case_id)); assert cur.fetchone()[0] == 2


def test_version_conflict(db):
    db, tenant = db
    with db.cursor() as cur:
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id", (tenant,uuid4().hex)); customer=cur.fetchone()[0]
    case_id=create_case(db, tenant_id=tenant, customer_id=customer, subject="conflict")
    with db.transaction(): transition_case(db,tenant_id=tenant,case_id=case_id,expected_version=0,event_type=EventType.CREATED,payload={"channel":"test","message":"x"},actor_type="test")
    with pytest.raises(StateConflict):
        with db.transaction(): transition_case(db,tenant_id=tenant,case_id=case_id,expected_version=0,event_type=EventType.CLASSIFIED,payload={"intent":"x","issue_code":"x","sentiment":"neutral"},actor_type="test")


def test_outbox_dedupe(db):
    db, tenant = db
    with db.cursor() as cur:
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",(tenant,uuid4().hex)); customer=cur.fetchone()[0]
    case_id=create_case(db,tenant_id=tenant,customer_id=customer,subject="outbox")
    dedupe_key = "same-" + tenant
    msg=OutboxMessage(topic="test.topic",dedupe_key=dedupe_key,payload={"x":1})
    with db.transaction(): transition_case(db,tenant_id=tenant,case_id=case_id,expected_version=0,event_type=EventType.CREATED,payload={"channel":"test","message":"x"},actor_type="test",outbox=[msg])
    with db.transaction(): transition_case(db,tenant_id=tenant,case_id=case_id,expected_version=1,event_type=EventType.CLASSIFIED,payload={"intent":"x","issue_code":"x","sentiment":"neutral"},actor_type="test",outbox=[msg])
    db.commit()
    with db.cursor() as cur: cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='test.topic' AND dedupe_key=%s",(tenant, dedupe_key)); assert cur.fetchone()[0] == 1
