"""outbox worker 가 남의 tenant 메시지를 물지 않는지 검사한다.

★쇼핑몰 복사본(`final_project_cs`)에서 먼저 드러난 결함이다.

  `OutboxWorker` 는 `WHERE status='pending' ORDER BY available_at LIMIT 1` 로
  **tenant 무관하게 가장 오래된 행**을 집었다. 그래서 다른 tenant 의 pending 행이
  하나만 있어도 자기 행 대신 그것을 물고, 테스트가 엉뚱하게 실패했다.

  여기서 재현해 확인했다 — `zz_foreign` tenant 의 pending 1행을 심자
  `test_provider_timeout_stays_unknown_and_is_not_retried` 가 즉시 실패했다.

★운영에서도 같은 문제다. 전체를 집으면 한 tenant 의 적체가 다른 tenant 를 굶긴다.
  `tenant_id` 를 주면 나눠 돌릴 수 있다.

이 파일은 **간섭을 일부러 심어 놓고** 검사한다. 깨끗한 DB 에서만 통과하는 검사는
이 결함을 다시 놓친다.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from acop_basement.infrastructure.db.repository import create_case
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.infrastructure.messaging.outbox import OutboxBrokerAdapter
from acop_basement.infrastructure.messaging.worker import OutboxWorker

from .test_controller_integration import db, seed_case  # noqa: F401

FOREIGN = "zz_interference_probe"


def _plant_foreign_pending() -> None:
    """★남의 tenant 의, **더 오래된** pending 행을 심는다.

    더 오래되어야 `ORDER BY available_at` 에서 먼저 잡힌다 — 간섭을 확실히 만든다.
    """
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,'interference probe') "
                        "ON CONFLICT (tenant_id) DO NOTHING", (FOREIGN,))
            cur.execute(
                "INSERT INTO outbox (tenant_id,topic,dedupe_key,payload_json,status,available_at) "
                "VALUES (%s,'probe.topic',%s,'{}','pending', now() - interval '1 day')",
                (FOREIGN, "probe-" + uuid4().hex))
        conn.commit()


def _remove_foreign() -> None:
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (FOREIGN,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (FOREIGN,))
        conn.commit()


def test_scoped_worker_ignores_other_tenants_even_when_theirs_is_older(db):  # noqa: F811
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "mine-" + tenant
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    asyncio.run(adapter.publish("test.mine", {"tenant_id": tenant, "case_id": str(case_id)}, key))

    _plant_foreign_pending()
    try:
        delivered: list[dict] = []
        worker = OutboxWorker(get_connection, delivered.append, tenant_id=tenant)

        assert worker.process_once() is True
        # ★내 행이 배달됐다. 남의 더 오래된 행이 아니라.
        assert len(delivered) == 1
        assert delivered[0]["topic"] == "test.mine"
        # 내 tenant 에는 더 처리할 것이 없다
        assert worker.process_once() is False

        # ★남의 행은 그대로 pending 이다 — 건드리지 않았다
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM outbox WHERE tenant_id=%s", (FOREIGN,))
            assert [r[0] for r in cur.fetchall()] == ["pending"]
    finally:
        _remove_foreign()


def test_dedupe_key_collision_across_tenants_does_not_drop_a_message(db):  # noqa: F811
    """★버그사냥 2026-08-17 (라운드 01, 처리는 라운드 08) — UNIQUE(topic, dedupe_key)
    가 tenant_id 를 안 가르던 시절엔, 서로 다른 tenant 가 같은 (topic, dedupe_key)
    를 쓰면 뒤의 것이 ON CONFLICT DO NOTHING 으로 조용히 버려질 수 있었다.
    migrations/005 로 tenant_id 를 제약에 더했다 - 이제 같은 값이어도 서로
    다른 tenant 면 둘 다 살아남는다."""
    conn, tenant_a = db
    tenant_b = "zz_dedupe_collision_" + uuid4().hex
    case_a, _ = seed_case(conn, tenant_a)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,'dedupe collision test')", (tenant_b,))
        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                    (tenant_b, uuid4().hex))
        customer_b = cur.fetchone()[0]
    case_b = create_case(conn, tenant_id=tenant_b, customer_id=customer_b, subject="dedupe collision test")

    same_key = "collision-" + uuid4().hex  # ★두 tenant 가 똑같은 (topic, dedupe_key) 를 쓴다
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    try:
        asyncio.run(adapter.publish("test.collision", {"tenant_id": tenant_a, "case_id": str(case_a)}, same_key))
        asyncio.run(adapter.publish("test.collision", {"tenant_id": tenant_b, "case_id": str(case_b)}, same_key))

        with conn.cursor() as cur:
            cur.execute("SELECT tenant_id FROM outbox WHERE topic='test.collision' AND dedupe_key=%s ORDER BY tenant_id",
                        (same_key,))
            rows = sorted(r[0] for r in cur.fetchall())
        assert rows == sorted([tenant_a, tenant_b]), "tenant 하나의 메시지가 조용히 버려졌다"
    finally:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant_b,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant_b,))


def test_publish_rejects_payload_tenant_that_does_not_own_the_case(db):  # noqa: F811
    """★버그사냥 2026-08-17 — payload 가 주장하는 tenant_id 가 case 의 실제 소유
    tenant 와 다르면 그동안 payload 쪽을 조용히 따라갔다. 남의 tenant case_id 를
    가리키는 outbox 행이 만들어질 수 있었다(격리 위반) — 지금은 명시적으로 거부한다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    key = "mismatch-" + uuid4().hex

    with pytest.raises(ValueError, match="tenant_id mismatch"):
        asyncio.run(adapter.publish(
            "test.mismatch", {"tenant_id": "zz_not_the_owner", "case_id": str(case_id)}, key))

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (key,))
        assert cur.fetchone()[0] == 0, "거부된 publish 가 행을 남기면 안 된다"


def test_unscoped_worker_still_sees_everything(db):  # noqa: F811
    """★기본값은 바뀌지 않았다. 전체를 집는 동작이 필요할 수도 있다.

    범위를 좁히는 것은 **선택**이지 강제가 아니다.
    """
    conn, tenant = db
    _plant_foreign_pending()
    try:
        delivered: list[dict] = []
        assert OutboxWorker(get_connection, delivered.append).process_once() is True
        assert delivered and delivered[0]["topic"] == "probe.topic"
    finally:
        _remove_foreign()
