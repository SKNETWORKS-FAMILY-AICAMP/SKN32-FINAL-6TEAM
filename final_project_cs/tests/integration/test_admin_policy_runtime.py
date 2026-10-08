"""운영 설정이 고객 제한과 외부 호출에 실제 적용되는지 DB로 검증한다."""
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

import pytest

from app.application import admin_service as admin
from app.domains.travel_ops.modules.web_account import web_guard
from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget
from app.infrastructure.db.session import get_connection


@pytest.fixture
def state():
    with get_connection() as conn:
        tenant, customer = "admin_test_" + uuid4().hex, uuid4()
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'관리자 시험')", (tenant,))
        conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,'test')", (customer, tenant))
        try:
            yield conn, tenant, customer
        finally:
            conn.rollback()


def mutate(state, command):
    conn, tenant, _ = state
    admin.mutate(conn, tenant, "test-operator", command)


def test_customer_limit_exception_increases_and_expires(state):
    conn, tenant, customer = state
    mutate(state, {"type": "save-limits", "chatLimit": 2, "rules": []})
    mutate(state, {"type": "user-limit", "userId": str(customer), "limit": 3, "period": "today", "reason": "시험"})
    now = datetime.now(admin.KST)
    assert [admin.consume_chat(conn, tenant, str(customer), now) for _ in range(3)] == [1, 2, 3]
    with pytest.raises(admin.AdminPolicyRefused) as refused:
        admin.consume_chat(conn, tenant, str(customer), now)
    assert refused.value.status == 429
    from datetime import timedelta
    assert admin.access_policy(conn, tenant, str(customer), now + timedelta(days=1))["chat_limit"] == 2


def test_block_and_maintenance_are_enforced(state):
    conn, tenant, customer = state
    mutate(state, {"type": "block-user", "userId": str(customer), "blocked": True, "reason": "시험"})
    with pytest.raises(admin.AdminPolicyRefused) as refused:
        admin.consume_chat(conn, tenant, str(customer))
    assert refused.value.status == 403
    mutate(state, {"type": "block-user", "userId": str(customer), "blocked": False, "reason": "시험"})
    mutate(state, {"type": "maintenance", "enabled": True, "message": "점검 중", "messageEn": "", "endsAt": "2099-01-01T03:00"})
    with pytest.raises(admin.AdminPolicyRefused) as refused:
        admin.consume_chat(conn, tenant, str(customer))
    assert refused.value.status == 503


def test_api_cap_reaches_actual_reservation(state):
    conn, _, _ = state
    meter = "admin_test_" + uuid4().hex
    @contextmanager
    def connection():
        yield conn
    budget = CallBudget(connection_factory=connection, caps={meter: {"day": 10, "month": 100}})
    assert budget.try_reserve(meter)
    mutate(state, {"type": "api-cap", "apiId": meter, "daily": 2, "monthly": 20, "reason": "시험"})
    assert budget.try_reserve(meter)
    assert not budget.try_reserve(meter)
    assert budget.used(meter) == {"day": 2, "month": 2}


def test_guard_honors_exception_above_existing_key_cap(state, monkeypatch):
    conn, tenant, customer = state
    @contextmanager
    def connection():
        yield conn
    monkeypatch.setattr(web_guard, "get_connection", connection)
    monkeypatch.setattr(web_guard, "values", lambda _: {"web.limits_enabled": True, "web.message.service_day": 100, "web.message.per_ip_day": 100, "web.message.per_key_day": 2})
    mutate(state, {"type": "save-limits", "chatLimit": 2, "rules": []})
    mutate(state, {"type": "user-limit", "userId": str(customer), "limit": 3, "period": "always", "reason": "시험"})
    for _ in range(3):
        result = web_guard.count(tenant, "message", customer_id=customer, ip="127.0.0.1")
    assert result["used"]["per_key_day"] == 3


def test_other_tenant_cannot_change_customer_and_watch_is_fixed(state):
    conn, tenant, customer = state
    with pytest.raises(admin.AdminServiceError) as refused:
        admin.mutate(conn, tenant + "_other", "operator", {"type": "block-user", "userId": str(customer), "blocked": True, "reason": "시험"})
    assert refused.value.status_code == 404
    with pytest.raises(admin.AdminServiceError) as refused:
        mutate(state, {"type": "save-limits", "chatLimit": 10, "rules": [{"id": "rule", "threshold": 80, "multiplier": 2}]})
    assert refused.value.status_code == 422


def test_snapshot_uses_real_schema_and_registered_provider(state):
    from app.composition import build_admin_snapshot
    conn, tenant, customer = state
    data = build_admin_snapshot(conn, tenant, 10)
    assert data["live"] is True
    assert [user["id"] for user in data["users"]] == [str(customer)]
    assert data["server"]["dbConnections"] >= 1
    assert data["server"]["cpu"] is None
