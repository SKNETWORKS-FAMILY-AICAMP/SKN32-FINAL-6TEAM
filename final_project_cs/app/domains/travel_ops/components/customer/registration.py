"""검증된 소셜 계정의 가입 대기 상태. 필수 동의 저장과 같은 트랜잭션에서 완료한다."""
from __future__ import annotations

from uuid import UUID
from psycopg.types.json import Jsonb

KIND = "customer_registration"


def pending(conn, tenant_id: str, customer_id: UUID) -> bool:
    row = conn.execute("SELECT value->>'status' FROM admin_records "
                       "WHERE tenant_id=%s AND kind=%s AND id=%s AND customer_id=%s",
                       (tenant_id, KIND, str(customer_id), customer_id)).fetchone()
    return row is not None and row[0] == "pending"


def begin(conn, tenant_id: str, customer_id: UUID) -> None:
    # 기존 회원을 소급해 미가입 상태로 바꾸지 않는다. 검증된 최초 소셜 연결만 부른다.
    conn.execute("INSERT INTO admin_records(tenant_id,kind,id,value,customer_id) VALUES(%s,%s,%s,%s,%s) "
                 "ON CONFLICT(tenant_id,kind,id) DO NOTHING",
                 (tenant_id, KIND, str(customer_id), Jsonb({"status": "pending"}), customer_id))


def complete(conn, tenant_id: str, customer_id: UUID, version: str) -> None:
    conn.execute("UPDATE admin_records SET value=value || %s,revision=revision+1,updated_at=now() "
                 "WHERE tenant_id=%s AND kind=%s AND id=%s AND customer_id=%s AND value->>'status'='pending'",
                 (Jsonb({"status": "complete", "terms_version": version}), tenant_id, KIND, str(customer_id), customer_id))
