"""조회 스코프 — 2026-08-31 추가.

`CLAUDE.md` 는 "모든 query 에 tenant_id 와 customer_id(또는 case_id) 조건을 적용한다.
조건 없는 조회 쿼리는 그 자체가 보안 결함이다 — `tests/security/` 가 검사한다" 고
적고 있다. 그런데 `list_cases` 에서 customer 조건을 지워도 전체 테스트가 전부
통과했다. 문서가 검사한다고 말한 것이 실제로는 검사되지 않고 있었다.
"""
from __future__ import annotations

from uuid import uuid4

from app.infrastructure.db.repository import create_case, list_cases

from tests.integration.controller.test_controller_integration import db  # noqa: F401


def _customer_with_case(conn, tenant: str, subject: str):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
            (tenant, uuid4().hex),
        )
        customer = cur.fetchone()[0]
    case_id = create_case(conn, tenant_id=tenant, customer_id=customer, subject=subject)
    conn.commit()
    return customer, case_id


def test_case_list_does_not_leak_across_customers_in_one_tenant(db):  # noqa: F811
    """같은 tenant 안에서도 고객끼리 섞이면 안 된다."""
    conn, tenant = db
    first, first_case = _customer_with_case(conn, tenant, "first customer")
    second, second_case = _customer_with_case(conn, tenant, "second customer")

    rows = list_cases(conn, tenant_id=tenant, customer_id=first)
    returned = {row["case_id"] for row in rows}
    assert first_case in returned
    assert second_case not in returned, "다른 고객의 Case 가 보인다"
    assert all(row["customer_id"] == first for row in rows)


def test_case_list_without_customer_stays_inside_the_tenant(db):  # noqa: F811
    """customer 를 안 주면 tenant 전체다 — 그래도 tenant 밖으로는 안 나간다."""
    conn, tenant = db
    _customer_with_case(conn, tenant, "inside")
    rows = list_cases(conn, tenant_id=tenant)
    assert rows, "tenant 안에 Case 가 있는데 아무것도 안 나왔다"

    other_tenant = "test_scope_other_" + uuid4().hex
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (other_tenant, "scope other"))
    outside_customer, outside_case = _customer_with_case(conn, other_tenant, "outside")
    try:
        rows = list_cases(conn, tenant_id=tenant)
        assert outside_case not in {row["case_id"] for row in rows}
    finally:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (other_tenant,))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (other_tenant,))
            cur.execute("DELETE FROM customers WHERE tenant_id=%s", (other_tenant,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (other_tenant,))
