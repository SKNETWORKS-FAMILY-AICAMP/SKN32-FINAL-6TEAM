"""롤백되는 별도 tenant에서 QA 예외와 일반 고객의 제한을 실제 DB로 확인한다."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.application import admin_service as admin
from app.domains.travel_ops.modules.web_account import guest_policy, web_guard
from app.infrastructure.db.session import get_connection


@pytest.fixture
def state(monkeypatch):
    with get_connection() as conn:
        tenant, qa, regular = "qa_policy_" + uuid4().hex, uuid4(), uuid4()
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'QA 정책 시험')", (tenant,))
        for customer in (qa, regular):
            conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)",
                         (customer, tenant, "web:" + uuid4().hex))

        @contextmanager
        def connection():
            yield conn

        monkeypatch.setattr(web_guard, "get_connection", connection)
        monkeypatch.setattr(web_guard, "values", lambda _: {"web.limits_enabled": True, **{
            f"web.{action}.{scope}": 100 if scope == "service_day" else 1
            for action in web_guard.ACTIONS for scope in ("service_day", "per_ip_day", "per_key_day")}})
        admin.set_usage_exemption(conn, tenant, str(qa), enabled=True, actor="qa-test", reason="고객별 예외 검증")
        try:
            yield conn, tenant, qa, regular
        finally:
            conn.rollback()


@pytest.mark.parametrize("action", ["intake", "trip_create", "plan", "confirm", "place_search", "risk_check", "move_judge"])
def test_only_qa_passes_key_and_ip_caps_and_all_usage_is_counted(state, action):
    conn, tenant, qa, regular = state
    for _ in range(3):
        result = web_guard.count(tenant, action, customer_id=qa, ip="127.0.0.1")
    assert set(result["used"].values()) == {3}
    with pytest.raises(web_guard.UsageRefused) as refused:
        web_guard.count(tenant, action, customer_id=regular, ip="127.0.0.1")
    assert refused.value.limit == "per_ip"
    assert not admin.usage_exempt(conn, tenant, str(regular))
    assert not admin.usage_exempt(conn, tenant + "_other", str(qa))


def test_qa_chat_unlimited_but_regular_chat_still_limited(state):
    conn, tenant, qa, regular = state
    admin.mutate(conn, tenant, "test", {"type": "save-limits", "chatLimit": 1, "rules": []})
    for _ in range(3):
        result = web_guard.count(tenant, "message", customer_id=qa, ip="127.0.0.1")
    assert result["used"]["per_key_day"] == 3
    assert admin.consume_chat(conn, tenant, str(regular)) == 1
    with pytest.raises(admin.AdminPolicyRefused) as refused:
        admin.consume_chat(conn, tenant, str(regular))
    assert refused.value.code == "chat_limit"


def test_qa_cannot_skip_service_budget(state, monkeypatch):
    _, tenant, qa, _ = state
    values = web_guard.values(tenant)
    values["web.intake.service_day"] = 1
    monkeypatch.setattr(web_guard, "values", lambda _: values)
    web_guard.count(tenant, "intake", customer_id=qa, ip="127.0.0.1")
    with pytest.raises(web_guard.UsageRefused) as refused:
        web_guard.count(tenant, "intake", customer_id=qa, ip="127.0.0.1")
    assert refused.value.code == "service_daily_cap"


@pytest.mark.parametrize("blocked", [True, False])
def test_qa_still_obeys_block_and_maintenance(state, blocked):
    conn, tenant, qa, _ = state
    if blocked:
        admin.mutate(conn, tenant, "test", {"type": "block-user", "userId": str(qa), "blocked": True})
    else:
        admin.mutate(conn, tenant, "test", {"type": "maintenance", "enabled": True, "message": "점검",
            "messageEn": "", "endsAt": "2099-01-01T00:00"})
    with pytest.raises(admin.AdminPolicyRefused) as refused:
        admin.consume_chat(conn, tenant, str(qa))
    assert refused.value.code == ("user_blocked" if blocked else "maintenance")


def test_qa_skips_trip_count_but_not_dates_and_regular_keeps_cap(state, monkeypatch):
    conn, tenant, qa, regular = state
    class Guard:
        def get(self, key):
            return {"web_guard.guest.max_trips": 0, "web_guard.guest.trip_start_max_days": 365,
                    "web_guard.guest.trip_length_max_days": 7}[key]
    monkeypatch.setattr(guest_policy, "get_guardrails", Guard)
    now = datetime.now(guest_policy.KST)
    guest_policy.check_new_trip(conn, tenant_id=tenant, customer_id=qa, starts=[now], ends=[now])
    with pytest.raises(guest_policy.GuestLimit) as refused:
        guest_policy.check_new_trip(conn, tenant_id=tenant, customer_id=regular, starts=[now], ends=[now])
    assert refused.value.detail["error"]["code"] == "guest_trip_limit"
    with pytest.raises(guest_policy.GuestLimit) as refused:
        guest_policy.check_new_trip(conn, tenant_id=tenant, customer_id=qa, starts=[now], ends=[now + timedelta(days=8)])
    assert refused.value.detail["error"]["code"] == "guest_trip_too_long"


@pytest.mark.parametrize("value", ["true", 1, False, None])
def test_only_explicit_boolean_true_grants_exception(state, value):
    conn, tenant, qa, _ = state
    admin.put(conn, tenant, "user", str(qa), {"usageExempt": value}, actor="test", action="test", reason="엄격한 값 검사")
    assert not admin.usage_exempt(conn, tenant, str(qa))


def test_exception_is_audited_revocable_and_tenant_scoped(state):
    conn, tenant, qa, _ = state
    row = conn.execute("SELECT action,after_value FROM admin_audit WHERE tenant_id=%s AND target=%s",
                       (tenant, str(qa))).fetchone()
    assert row[0] == "usage-exemption" and row[1]["usageExempt"] is True
    admin.set_usage_exemption(conn, tenant, str(qa), enabled=False, actor="test", reason="해제 검증")
    assert not admin.usage_exempt(conn, tenant, str(qa))
    with pytest.raises(admin.AdminServiceError) as refused:
        admin.set_usage_exemption(conn, tenant + "_other", str(qa), enabled=True, actor="test", reason="범위 검사")
    assert refused.value.status_code == 404
