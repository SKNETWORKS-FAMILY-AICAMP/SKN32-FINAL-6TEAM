"""End-to-end payment-provider timeout coverage for the outbox worker."""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.transition import OutboxMessage, transition_case
from app.domain.events import EventType
from app.infrastructure.db.session import get_connection
from app.infrastructure.messaging.mock_payment_publisher import MockProviderPublisher
from app.infrastructure.messaging.outbox import OutboxBrokerAdapter
from app.infrastructure.messaging.worker import OutboxWorker

from tests.integration.controller.test_controller_integration import db, seed_case  # noqa: F401


PAYMENT_TOPIC = "payment.provider.capture"


def _publish_payment(tenant: str, case_id, dedupe_key: str) -> None:
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    asyncio.run(adapter.publish(PAYMENT_TOPIC, {
        "tenant_id": tenant,
        "case_id": str(case_id),
        "provider_ref": "mock-payment-" + dedupe_key,
    }, dedupe_key))


def _unknown_row(conn, tenant: str, dedupe_key: str):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT message_id, topic, dedupe_key, payload_json, attempts, last_error, locked_at "
            "FROM outbox WHERE tenant_id=%s AND dedupe_key=%s",
            (tenant, dedupe_key),
        )
        return cur.fetchone()


def _put_case_in_waiting_external(conn, tenant: str, case_id, outbox: OutboxMessage | None = None) -> None:
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=2,
                        event_type=EventType.ROUTED,
                        payload={"owner_team_id": "payment-test", "capability": "payment.capture"},
                        actor_type="test")
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=3,
                        event_type=EventType.ASYNC_PROVIDER,
                        payload={"provider_ref": "mock-payment-ref"}, actor_type="test",
                        outbox=[outbox] if outbox else None)
    conn.commit()


@pytest.mark.parametrize("mode,expected_error", [
    ("timeout", "timed out"),
    ("connection_error", "connection failed"),
])
def test_payment_provider_transport_error_becomes_unknown_in_db(db, mode, expected_error):  # noqa: F811
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "payment-error-" + uuid4().hex
    _publish_payment(tenant, case_id, key)
    publisher = MockProviderPublisher(mode=mode)
    worker = OutboxWorker(get_connection,
                          lambda message: asyncio.run(publisher.publish(message["topic"], message["payload"], key)),
                          tenant_id=tenant)

    assert worker.process_once() is True
    row = _unknown_row(conn, tenant, key)
    assert row[1:3] == (PAYMENT_TOPIC, key)
    assert row[4] == 1
    assert expected_error in row[5]
    assert row[6] is None
    assert publisher.published == []

    # Unknown is deliberately outside the worker's pending queue.
    assert worker.process_once() is False
    assert _unknown_row(conn, tenant, key)[4:6] == (1, row[5])

    # This is the exact operational SQL pattern from the runbook.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT message_id, topic, dedupe_key, payload_json, attempts, last_error, locked_at "
            # The runbook's ordering intent is retained with this repository's
            # actual outbox schema, which has no created_at column.
            "FROM outbox WHERE tenant_id=%s AND status='unknown' ORDER BY available_at",
            (tenant,),
        )
        assert any(found[0] == row[0] for found in cur.fetchall())


@pytest.mark.parametrize("event_type,expected_status,payload", [
    (EventType.VALID_CALLBACK, "resuming", {
        "provider_ref": "mock-confirmed-ref",
        "state_patch": {
            "manual_provider_check": "confirmed_completed",
            "manual_provider_check_actor": "test-operator",
        },
    }),
    (EventType.WAIT_EXPIRED, "escalated", {"wait_reason": "external_callback"}),
])
def test_runbook_case_join_and_human_transition_are_executable(db, event_type, expected_status, payload):  # noqa: F811
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "payment-case-" + uuid4().hex
    _put_case_in_waiting_external(conn, tenant, case_id)
    _publish_payment(tenant, case_id, key)
    publisher = MockProviderPublisher(mode="timeout")
    worker = OutboxWorker(get_connection,
                          lambda message: asyncio.run(publisher.publish(message["topic"], message["payload"], key)),
                          tenant_id=tenant)
    assert worker.process_once() is True
    unknown = _unknown_row(conn, tenant, key)

    # Exact join shape from the runbook, including messages without a case_id.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT cc.case_id, cc.status, cc.version, o.message_id, o.topic, o.payload_json, o.last_error "
            "FROM outbox AS o LEFT JOIN customer_cases AS cc "
            "ON cc.tenant_id=o.tenant_id AND cc.case_id=(o.payload_json ->> 'case_id')::uuid "
            "WHERE o.tenant_id=%s AND o.status='unknown' AND o.message_id=%s",
            (tenant, unknown[0]),
        )
        joined = cur.fetchone()
    assert joined[0] == case_id
    assert joined[1] == "waiting_external"
    assert joined[3] == unknown[0]
    assert "timed out" in joined[6]

    # Runbook §4: human confirmation uses transition_case(), never a direct UPDATE.
    # The Case is independent from outbox unknown; it remains waiting_external.
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=4,
                        event_type=event_type, payload=payload, actor_type="human", actor_id="test-operator")
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        assert cur.fetchone()[0] == expected_status


def test_mock_payment_publisher_success_is_delivered(db):  # noqa: F811
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "payment-success-" + uuid4().hex
    _publish_payment(tenant, case_id, key)
    publisher = MockProviderPublisher(mode="success")
    worker = OutboxWorker(get_connection,
                          lambda message: asyncio.run(publisher.publish(message["topic"], message["payload"], key)),
                          tenant_id=tenant)

    assert worker.process_once() is True
    row = _unknown_row(conn, tenant, key)
    assert row[4:] == (1, None, None)
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM outbox WHERE message_id=%s", (row[0],))
        assert cur.fetchone()[0] == "delivered"
    assert len(publisher.published) == 1
