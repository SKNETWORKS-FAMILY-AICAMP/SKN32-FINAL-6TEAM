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


def test_unsaved_chat_limit_uses_the_default_the_screen_shows(state, monkeypatch):
    """`[2026-10-15]` 「② 채팅 하루 한도」를 저장한 적이 없어도 화면에 보이는 기본값으로 막는다(전에는 한도 없음으로 통과)."""
    conn, tenant, customer = state
    monkeypatch.setattr(admin, "default_chat_limit", lambda: 2)
    now = datetime.now(admin.KST)
    assert [admin.consume_chat(conn, tenant, str(customer), now) for _ in range(2)] == [1, 2]
    with pytest.raises(admin.AdminPolicyRefused) as refused:
        admin.consume_chat(conn, tenant, str(customer), now)
    assert refused.value.code == "chat_limit"


def test_zero_chat_limit_means_unlimited_for_everyone_and_for_one_user(state, monkeypatch):
    """0 은 한도 없음 — 모든 사용자 기본값이든 사용자별 예외든 같다."""
    conn, tenant, customer = state
    now = datetime.now(admin.KST)
    mutate(state, {"type": "save-limits", "chatLimit": 0, "rules": [], "reason": "시험"})
    assert admin.access_policy(conn, tenant, str(customer), now)["chat_limit"] is None
    assert all(admin.consume_chat(conn, tenant, str(customer), now) == 0 for _ in range(5))
    mutate(state, {"type": "save-limits", "chatLimit": 1, "rules": [], "reason": "시험"})
    mutate(state, {"type": "user-limit", "userId": str(customer), "limit": 0, "period": "until-cleared", "reason": "시험"})
    assert admin.access_policy(conn, tenant, str(customer), now)["chat_limit"] is None


def test_guard_key_cap_is_unlimited_when_operator_says_zero(state, monkeypatch):
    """웹 횟수 한도가 켜져 있어도 관리자 화면에서 0(한도 없음)으로 정하면 사용자 한 명 칸으로는 막지 않는다."""
    conn, tenant, customer = state
    @contextmanager
    def connection():
        yield conn
    monkeypatch.setattr(web_guard, "get_connection", connection)
    monkeypatch.setattr(web_guard, "values", lambda _: {"web.limits_enabled": True, "web.message.service_day": 100, "web.message.per_ip_day": 100, "web.message.per_key_day": 1})
    mutate(state, {"type": "save-limits", "chatLimit": 0, "rules": [], "reason": "시험"})
    for _ in range(3):
        result = web_guard.count(tenant, "message", customer_id=customer, ip="127.0.0.1")
    assert result["used"]["per_key_day"] == 3


def test_api_cap_for_budgeted_source_without_calls_and_clear(state, monkeypatch):
    """`[2026-10-15]` 호출 기록이 없어도 DB 예산 소스면 운영자 상한을 정하고, ENV 보다 높게는 못 정하고, 지정 해제로 ENV 로 돌린다."""
    from app.application import api_limits
    conn, _, _ = state
    meter = "admin_test_" + uuid4().hex
    monkeypatch.setattr(api_limits, "adjustable", lambda settings=None: {meter: {"day": 10, "month": None}})
    with pytest.raises(admin.AdminServiceError) as refused:
        mutate(state, {"type": "api-cap", "apiId": meter, "daily": 11, "monthly": 100, "reason": "시험"})
    assert refused.value.status_code == 422 and "ENV" in refused.value.detail
    mutate(state, {"type": "api-cap", "apiId": meter, "daily": 3, "monthly": 50, "reason": "시험"})
    assert admin.api_cap(conn, meter, {"day": 10, "month": 2_000_000_000}) == {"day": 3, "month": 50}
    mutate(state, {"type": "api-cap-clear", "apiId": meter, "reason": "시험"})
    assert admin.api_cap(conn, meter, {"day": 10, "month": 2_000_000_000}) == {"day": 10, "month": 2_000_000_000}
    with pytest.raises(admin.AdminServiceError) as refused:
        mutate(state, {"type": "api-cap-clear", "apiId": meter, "reason": "시험"})
    assert refused.value.status_code == 404
    with pytest.raises(admin.AdminServiceError):
        mutate(state, {"type": "api-cap", "apiId": "not_budgeted_" + uuid4().hex, "daily": 1, "monthly": 1, "reason": "시험"})
