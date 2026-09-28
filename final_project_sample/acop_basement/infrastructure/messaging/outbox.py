"""Outbox-backed MessageBrokerPort. It does not implement Redis Streams."""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from psycopg.types.json import Json

from acop_basement.infrastructure.db.session import get_connection


class OutboxBrokerAdapter:
    def __init__(self, connection_factory: Callable = get_connection) -> None:
        self.connection_factory = connection_factory

    async def publish(self, topic: str, payload: dict[str, Any], dedupe_key: str) -> str:
        with self.connection_factory() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT tenant_id FROM customer_cases WHERE case_id=%s LIMIT 1", (payload.get("case_id"),))
                    row = cur.fetchone()
                    case_tenant_id = row[0] if row else None
                    tenant_id = payload.get("tenant_id") or case_tenant_id
                    if tenant_id is None:
                        raise ValueError("tenant_id is required for outbox publish")
                    # ★버그사냥 2026-08-17 — payload 의 tenant_id 가 case 의 실제
                    #   소유 tenant 와 다르면 조용히 payload 쪽을 따라갔다. 남의 tenant
                    #   case_id 를 가리키는 outbox 행이 만들어질 수 있었다(격리 위반).
                    if case_tenant_id is not None and payload.get("tenant_id") not in (None, case_tenant_id):
                        raise ValueError(
                            f"tenant_id mismatch: payload claims {payload.get('tenant_id')!r} "
                            f"but case belongs to {case_tenant_id!r}")
                    cur.execute("INSERT INTO outbox(tenant_id,topic,dedupe_key,payload_json) VALUES(%s,%s,%s,%s) "
                                "ON CONFLICT(tenant_id,topic,dedupe_key) DO NOTHING RETURNING message_id", (tenant_id, topic, dedupe_key, Json(payload)))
                    inserted = cur.fetchone()
        return str(inserted[0]) if inserted else dedupe_key

    async def ack(self, message_id: str) -> None:
        with self.connection_factory() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("UPDATE outbox SET status='delivered', locked_at=NULL WHERE message_id=%s", (message_id,))
