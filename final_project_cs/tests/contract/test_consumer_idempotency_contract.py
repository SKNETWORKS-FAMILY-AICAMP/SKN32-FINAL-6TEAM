"""Reusable idempotency contract for message consumers.

Every consumer adapter registered in ``consumer_contract_factories`` must
prove the same three invariants: duplicate delivery has one side effect,
concurrent claims have one side effect, and transport timeout is left
``unknown`` without automatic retry.

The adapter is deliberately small.  A future consumer only needs to expose
the equivalent of ``MessageBrokerPort.publish`` plus a one-shot worker and a
status lookup; its implementation remains outside this contract test.
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.messaging.outbox import OutboxBrokerAdapter
from app.infrastructure.messaging.worker import OutboxWorker


class ConsumerContract(Protocol):
    """Minimal test harness for a MessageBrokerPort-compatible consumer."""

    def publish(self, topic: str, payload: dict[str, Any], dedupe_key: str) -> str: ...

    def process_once(self, publisher: Callable[[dict[str, Any]], Any]) -> bool: ...

    def status(self, dedupe_key: str) -> tuple[str, int, str | None]: ...


@dataclass
class OutboxWorkerContract:
    tenant_id: str

    def publish(self, topic: str, payload: dict[str, Any], dedupe_key: str) -> str:
        return asyncio.run(OutboxBrokerAdapter(get_connection).publish(topic, payload, dedupe_key))

    def process_once(self, publisher: Callable[[dict[str, Any]], Any]) -> bool:
        return OutboxWorker(get_connection, publisher, tenant_id=self.tenant_id).process_once()

    def status(self, dedupe_key: str) -> tuple[str, int, str | None]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT status, attempts, last_error FROM outbox "
                "WHERE tenant_id=%s AND dedupe_key=%s",
                (self.tenant_id, dedupe_key),
            )
            return cur.fetchone()


def outbox_worker_contract(tenant_id: str) -> ConsumerContract:
    return OutboxWorkerContract(tenant_id)


# Add each future consumer's adapter factory here.  The parametrization makes
# omission visible: every registered consumer runs all contract cases.
consumer_contract_factories = (outbox_worker_contract,)


@pytest.fixture(params=consumer_contract_factories, ids=lambda factory: factory.__name__)
def consumer_contract(request: pytest.FixtureRequest, consumer_db: str) -> ConsumerContract:
    return request.param(consumer_db)


@pytest.fixture()
def consumer_db() -> str:
    tenant = "consumer_contract_" + uuid4().hex
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "consumer contract"))
        try:
            yield tenant
        finally:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def _enqueue(consumer: ConsumerContract, tenant: str, key: str) -> None:
    consumer.publish("contract.consumer", {"tenant_id": tenant, "contract": True}, key)


def test_duplicate_dedupe_key_has_one_side_effect(consumer_contract: ConsumerContract, consumer_db: str):
    key = "duplicate-" + uuid4().hex
    _enqueue(consumer_contract, consumer_db, key)
    _enqueue(consumer_contract, consumer_db, key)
    delivered: list[dict[str, Any]] = []

    assert consumer_contract.process_once(delivered.append) is True
    assert consumer_contract.process_once(delivered.append) is False
    assert len(delivered) == 1
    assert consumer_contract.status(key)[:2] == ("delivered", 1)


def test_concurrent_claims_have_one_side_effect(consumer_contract: ConsumerContract, consumer_db: str):
    key = "race-" + uuid4().hex
    _enqueue(consumer_contract, consumer_db, key)
    delivered: list[dict[str, Any]] = []

    def publisher(message: dict[str, Any]) -> None:
        time.sleep(0.05)
        delivered.append(message)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consumer_contract.process_once(publisher), range(2)))

    assert sorted(results) == [False, True]
    assert len(delivered) == 1
    assert consumer_contract.status(key)[:2] == ("delivered", 1)


def test_timeout_is_unknown_and_not_automatically_retried(consumer_contract: ConsumerContract, consumer_db: str):
    key = "timeout-" + uuid4().hex
    _enqueue(consumer_contract, consumer_db, key)
    calls: list[dict[str, Any]] = []

    def timing_out(message: dict[str, Any]) -> None:
        calls.append(message)
        raise TimeoutError("consumer transport timed out")

    assert consumer_contract.process_once(timing_out) is True
    assert consumer_contract.status(key)[0] == "unknown"
    assert consumer_contract.status(key)[1] == 1
    assert consumer_contract.process_once(calls.append) is False
    assert len(calls) == 1
