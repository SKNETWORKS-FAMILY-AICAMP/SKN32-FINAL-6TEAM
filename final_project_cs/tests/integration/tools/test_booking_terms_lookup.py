# -*- coding: utf-8 -*-
"""`read.booking_terms` — 취소 조건을 **좁은 범위부터** 찾는다. `[2026-09-23]`

★★왜 표를 따로 뒀나. 전에는 취소 기한·위약금율을 `read.policy` 가 준 RAG 청크에서
  꺼내려 했고, 청크는 `dict` 가 아니라 **두 값이 언제나 `None`** 이었다
  (`wiki/records/reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md`).
  이제 **수치는 이 도구가, 문장 근거는 `read.policy` 가** 댄다.

★찾는 순서 예약 → 공급자 → 종류. v11 결정 15 「값마다 대체 소스를 둔다」를 데이터로
  구현한 것이다. 셋 다 없으면 **모름**이고 모름이면 금액을 만들지 않는다.

재현:

    python -m pytest tests/integration/tools/test_booking_terms_lookup.py -v
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ReadToolbox, ToolContext


@pytest.fixture()
def world():
    tenant = "terms_" + uuid4().hex[:10]
    customer, booking = uuid4(), uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "terms"))
        cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,'c')",
                    (customer, tenant))
        cur.execute(
            "INSERT INTO bookings (booking_id,tenant_id,customer_id,booking_no,kind,status,"
            "starts_at,party_size) VALUES (%s,%s,%s,'BK-1','activity','confirmed',"
            "now()+interval '30 hours',2)", (booking, tenant, customer))
        cur.execute(
            "INSERT INTO supplier_bookings (tenant_id,booking_id,supplier,supplier_ref,status,tier) "
            "VALUES (%s,%s,'acme-tours','ref-1','confirmed','simulated')", (tenant, booking))

    def term(scope_type, scope_id, hours, table):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cancellation_terms (tenant_id,scope_type,scope_id,"
                "cancel_deadline_hours,penalty_by_hours,source) VALUES (%s,%s,%s,%s,%s,%s)",
                (tenant, scope_type, str(scope_id), hours, json.dumps(table), "test:fixture"))

    scope = ToolContext(tenant_id=tenant, customer_id=customer, case_id=uuid4(),
                        knowledge_scope=["travel_activity"])
    yield {"tenant": tenant, "booking": booking, "scope": scope, "term": term,
           "tools": ReadToolbox(get_connection)}

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for table in ("cancellation_terms", "supplier_bookings", "bookings",
                      "customers", "tenants"):
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))


def test_with_nothing_recorded_it_says_unknown_not_zero(world):
    """★0 을 내면 「위약금 없음」으로 읽힌다. **모름은 `None`** 이다."""
    assert world["tools"].booking_terms(world["scope"]) is None


def test_the_kind_default_is_the_last_resort(world):
    world["term"]("kind", "activity", 24, {"24": 0.5})
    found = world["tools"].booking_terms(world["scope"])
    assert found["matched_scope"] == "kind" and found["cancel_deadline_hours"] == 24.0


def test_the_supplier_beats_the_kind_default(world):
    world["term"]("kind", "activity", 24, {"24": 0.5})
    world["term"]("supplier", "acme-tours", 48, {"48": 0.3})
    found = world["tools"].booking_terms(world["scope"])
    assert found["matched_scope"] == "supplier" and found["cancel_deadline_hours"] == 48.0


def test_this_booking_beats_everything(world):
    world["term"]("kind", "activity", 24, {"24": 0.5})
    world["term"]("supplier", "acme-tours", 48, {"48": 0.3})
    world["term"]("booking", world["booking"], 6, {"6": 0.1})
    found = world["tools"].booking_terms(world["scope"])
    assert found["matched_scope"] == "booking" and found["cancel_deadline_hours"] == 6.0
    assert found["penalty_by_hours"] == {"6": 0.1}


def test_it_always_says_where_the_numbers_came_from(world):
    """★시연용 Mock 과 실제 업체 약관이 섞이면 지어낸 금액을 말하게 된다."""
    world["term"]("kind", "activity", 24, {"24": 0.5})
    found = world["tools"].booking_terms(world["scope"])
    assert found["source"] == "test:fixture" and found["observed_at"] is not None


def test_another_tenants_terms_are_invisible(world):
    """★조건 없는 조회는 그 자체가 보안 결함이다(CLAUDE.md §1)."""
    other = "terms_other_" + uuid4().hex[:6]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (other, "other"))
        cur.execute(
            "INSERT INTO cancellation_terms (tenant_id,scope_type,scope_id,"
            "cancel_deadline_hours,penalty_by_hours,source) "
            "VALUES (%s,'kind','activity',1,'{}'::jsonb,'other')", (other,))
    try:
        assert world["tools"].booking_terms(world["scope"]) is None
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM cancellation_terms WHERE tenant_id=%s", (other,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (other,))


def test_a_typo_in_the_scope_name_fails_loudly_instead_of_matching_nothing(world):
    """★조용히 0건이면 「조건이 없다」로 읽혀 모름이 된다 — DB 가 먼저 막는다."""
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation):
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cancellation_terms (tenant_id,scope_type,scope_id,"
                "cancel_deadline_hours,penalty_by_hours,source) "
                "VALUES (%s,'Supplier','acme-tours',24,'{}'::jsonb,'typo')", (world["tenant"],))
