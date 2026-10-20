"""고객 외부 발송 설정은 테넌트별 DB 값으로 매번 확인한다."""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg.types.json import Json

from app.domains.travel_ops.modules.web_account import customer_notice_delivery as delivery
from app.domains.travel_ops.modules.web_account import web_guard
from app.infrastructure.db.session import get_connection


@pytest.fixture
def state(monkeypatch):
    with get_connection() as conn:
        tenants = ['notice_switch_' + uuid4().hex for _ in range(2)]
        for tenant in tenants:
            conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'여행 알림 설정 시험')", (tenant,))

        @contextmanager
        def connection():
            yield conn

        monkeypatch.setattr(delivery, 'get_connection', connection)
        monkeypatch.setattr(delivery, 'get_guardrails', lambda: SimpleNamespace(get=lambda key: False))
        try:
            yield conn, tenants
        finally:
            conn.rollback()


def save(state, tenant, value):
    state[0].execute(
        "INSERT INTO runtime_limits(tenant_id,name,value,updated_by) VALUES(%s,%s,%s,'test-operator') "
        "ON CONFLICT(tenant_id,name) DO UPDATE SET value=EXCLUDED.value",
        (tenant, delivery.KEY, Json(value)))


def test_admin_setting_registers_a_boolean_switch():
    spec = web_guard.specs()[delivery.KEY]
    assert spec.type == 'bool'
    assert spec.check(True) is None and spec.check(False) is None
    assert spec.check('true') is not None


@pytest.mark.parametrize('value', [True, False])
def test_persisted_boolean_controls_delivery(state, value):
    tenant = state[1][0]
    save(state, tenant, value)
    assert delivery.enabled(tenant) is value


def test_next_delivery_reads_changed_value_without_restart(state):
    tenant = state[1][0]
    save(state, tenant, True)
    assert delivery.enabled(tenant) is True
    save(state, tenant, False)
    assert delivery.enabled(tenant) is False


def test_other_tenant_cannot_enable_this_tenant_delivery(state):
    own, other = state[1]
    save(state, other, True)
    assert delivery.enabled(own) is False
    assert delivery.enabled(other) is True


@pytest.mark.parametrize('value', ['true', 1, None])
def test_invalid_persisted_type_does_not_silently_enable_delivery(state, value):
    tenant = state[1][0]
    save(state, tenant, value)
    with pytest.raises(ValueError, match='boolean'):
        delivery.enabled(tenant)


@pytest.mark.parametrize('value', [True, False])
def test_missing_override_uses_configured_default(state, monkeypatch, value):
    monkeypatch.setattr(delivery, 'get_guardrails', lambda: SimpleNamespace(get=lambda key: value))
    assert delivery.enabled(state[1][0]) is value


def test_database_failure_is_not_treated_as_permission_to_send(monkeypatch):
    @contextmanager
    def failed_connection():
        raise RuntimeError('synthetic database unavailable')
        yield

    monkeypatch.setattr(delivery, 'get_connection', failed_connection)
    with pytest.raises(RuntimeError, match='synthetic database unavailable'):
        delivery.enabled('synthetic-tenant')
