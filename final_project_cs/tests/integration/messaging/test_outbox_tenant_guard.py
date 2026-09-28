"""outbox 발행의 tenant 경계 — 2026-08-31 추가.

두 변경이 전체 테스트를 전부 통과했다(`../program/research/테스트_사각지대_실측.md`).

1. Case 의 tenant 와 payload 의 tenant 가 다를 때의 검사를 꺼두기
2. tenant 를 모를 때 `"unknown"` 이라는 임시값으로 채우기

메시지는 되돌릴 수 없다. 한 tenant 의 사건이 다른 tenant 의 이름을 달고 나가면
받는 쪽에서는 정상 메시지와 구분되지 않는다.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.infrastructure.db.repository import create_case
from app.infrastructure.db.session import get_connection
from app.infrastructure.messaging.outbox import OutboxBrokerAdapter

from tests.integration.controller.test_controller_integration import db  # noqa: F401

TOPIC = "test.tenant.guard"


def _make_case(conn, tenant: str):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
            (tenant, uuid4().hex),
        )
        customer = cur.fetchone()[0]
    case_id = create_case(conn, tenant_id=tenant, customer_id=customer, subject="outbox tenant guard")
    conn.commit()
    return case_id


def test_publishing_a_case_under_another_tenant_is_rejected(db):  # noqa: F811
    conn, tenant = db
    case_id = _make_case(conn, tenant)
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    with pytest.raises(ValueError, match="tenant"):
        asyncio.run(adapter.publish(
            TOPIC,
            {"tenant_id": "tenant_that_does_not_own_this_case", "case_id": str(case_id)},
            "guard-" + uuid4().hex,
        ))


def test_publishing_without_any_tenant_is_rejected(db):  # noqa: F811
    """모르는 값을 그럴듯한 문자열로 채우면 오류가 데이터가 된다."""
    conn, tenant = db
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    with pytest.raises(ValueError, match="tenant_id is required"):
        asyncio.run(adapter.publish(
            TOPIC, {"case_id": str(uuid4())}, "guard-" + uuid4().hex,
        ))


def test_no_row_is_written_when_the_guard_rejects(db):  # noqa: F811
    """거부됐으면 흔적이 남지 않아야 한다."""
    conn, tenant = db
    case_id = _make_case(conn, tenant)
    dedupe = "guard-" + uuid4().hex
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    with pytest.raises(ValueError):
        asyncio.run(adapter.publish(
            TOPIC, {"tenant_id": "someone_else", "case_id": str(case_id)}, dedupe,
        ))
    with get_connection() as check, check.cursor() as cur:
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (dedupe,))
        assert cur.fetchone()[0] == 0


def test_tenant_is_taken_from_the_case_when_payload_omits_it(db):  # noqa: F811
    """payload 에 없으면 Case 의 tenant 를 쓴다 — 임시값을 지어내지 않는다."""
    conn, tenant = db
    case_id = _make_case(conn, tenant)
    dedupe = "guard-" + uuid4().hex
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    asyncio.run(adapter.publish(TOPIC, {"case_id": str(case_id)}, dedupe))
    with get_connection() as check, check.cursor() as cur:
        cur.execute("SELECT tenant_id FROM outbox WHERE dedupe_key=%s", (dedupe,))
        assert cur.fetchone()[0] == tenant
