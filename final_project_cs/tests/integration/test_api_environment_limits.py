"""API 한도 조회: 실제 로컬 개발 DB, 비밀 배제, 권한, 기간 경계와 읽기 전용 보장."""
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.application import api_limits
from app.core.settings import Settings
from app.infrastructure.db.session import get_connection
from app.presentation import admin_api, admin_limits_api
from app.presentation.ui import auth


@pytest.fixture
def world(monkeypatch):
    settings = Settings.model_construct(database_url='private-db-url', openai_api_key='never-display-api-key',
        llm_model='test', embedding_model='test', rate_its_per_day=777, rate_its_per_month=0,
        rate_odsay_per_day=0, llm_failover_daily_cap=0)
    now = datetime(2099, 11, 1, 1, tzinfo=ZoneInfo('Asia/Seoul'))
    with get_connection() as conn:
        @contextmanager
        def connect():
            yield conn
        monkeypatch.setattr(admin_limits_api, 'snapshot', lambda **kwargs: api_limits.snapshot(settings=settings, connection_factory=connect, now=now))
        app = FastAPI()
        app.include_router(admin_limits_api.build_router(operator_dependency=admin_api.operator, require_permission=admin_api.require))
        client = TestClient(app)
        op = auth.Operator('limits-test', frozenset({'ops:introspect'}))
        monkeypatch.setattr(auth, 'operators', lambda: {op.id: ('', op.scopes)})
        client.cookies.set(auth.COOKIE, auth.issue(op))
        yield settings, now, conn, connect, client
        conn.rollback()


def test_all_configured_sources_even_without_usage_and_no_secret_serialization(world):
    settings, _, _, _, client = world
    response = client.get('/admin/api/api-limits')
    assert response.status_code == 200
    data = response.json()
    rows = {row['id']: row for row in data['limits']}
    assert set(rows) == set(settings.source_rate_limits()) | {'openai_failover'}
    assert rows['its']['daily'] == dict(env='ACOP_RATE_ITS_PER_DAY', value=777, origin='configured', zero_meaning='no_interval_limit')
    assert rows['kma']['daily']['origin'] == 'default'
    assert rows['its']['monthly']['value'] == 0 and rows['its']['monthly']['zero_meaning'] == 'unset'
    assert rows['odsay']['daily']['value'] == 0 and rows['odsay']['daily']['zero_meaning'] == 'no_interval_limit'
    assert rows['openai_failover']['daily']['value'] == 0 and rows['openai_failover']['daily']['zero_meaning'] == 'blocked'
    assert rows['odsay']['recorded'] == {'day': None, 'month': None}
    assert rows['kma']['monthly']['origin'] == 'absent'
    assert all(value not in response.text for value in ['never-display-api-key', 'private-db-url', 'openai_api_key', 'database_url'])


def test_actual_db_usage_last_cap_override_and_kst_utc_boundary_are_distinct(world):
    settings, now, conn, connect, client = world
    for meter, period, used, cap in [('its', 'day:2099-11-01', 12, 700), ('its', 'month:2099-11', 99, 2000000000),
                                   ('openai_failover', 'day:2099-10-31', 3, 10), ('openai_failover', 'month:2099-10', 4, 100)]:
        conn.execute('INSERT INTO external_call_budget(meter,period,used,cap) VALUES(%s,%s,%s,%s)', (meter,period,used,cap))
    conn.execute("INSERT INTO admin_api_caps(meter,daily,monthly,updated_by) VALUES('its',500,800,'limits-test') "
                 "ON CONFLICT(meter) DO UPDATE SET daily=500,monthly=800")
    before = conn.execute('SELECT meter,period,used,cap,updated_at FROM external_call_budget ORDER BY meter,period').fetchall()
    rows = {row['id']: row for row in client.get('/admin/api/api-limits').json()['limits']}
    assert rows['its']['daily']['value'] == 777
    assert rows['its']['recorded']['day']['cap'] == 700
    assert rows['its']['recorded']['day']['used'] == 12
    assert rows['its']['operator_cap'] == dict(day=500, month=800)
    assert rows['openai_failover']['budget_timezone'] == 'UTC'
    assert rows['openai_failover']['recorded']['day']['used'] == 3
    assert rows['openai_failover']['recorded']['month']['used'] == 4
    assert conn.execute('SELECT meter,period,used,cap,updated_at FROM external_call_budget ORDER BY meter,period').fetchall() == before


def test_database_failure_is_explicit_and_does_not_hide_environment_settings(world):
    settings, now, _, _, _ = world
    @contextmanager
    def broken():
        raise OperationalError('secret-connection-string')
        yield
    data = api_limits.snapshot(settings=settings, connection_factory=broken, now=now)
    assert data['usage_error'] and 'secret-connection-string' not in str(data)
    assert len(data['limits']) == len(settings.source_rate_limits()) + 1
    assert all(row['recorded'] == dict(day=None, month=None) for row in data['limits'])


def test_login_and_introspection_scope_are_required(world, monkeypatch):
    *_, client = world
    client.cookies.clear()
    assert client.get('/admin/api/api-limits').status_code == 401
    op = auth.Operator('no-scope', frozenset())
    monkeypatch.setattr(auth, 'operators', lambda: {op.id: ('', op.scopes)})
    client.cookies.set(auth.COOKIE, auth.issue(op))
    assert client.get('/admin/api/api-limits').status_code == 403


def test_only_operations_app_registers_limit_reader():
    from app.ops_entrypoint import create_ops_app
    from app.presentation.api.app import create_app
    path = '/admin/api/api-limits'
    assert path in {route.path for route in create_ops_app(routers=[]).routes}
    assert path not in {route.path for route in create_app().routes}


def test_running_local_settings_can_be_read_without_exposing_keys():
    app = FastAPI()
    app.include_router(admin_limits_api.build_router(operator_dependency=lambda: None, require_permission=lambda *args: None))
    response = TestClient(app).get('/admin/api/api-limits')
    assert response.status_code == 200
    data = response.json()
    assert data['usage_error'] is None
    assert {row['id'] for row in data['limits']} == set(api_limits.get_settings().source_rate_limits()) | {'openai_failover'}
    assert all(isinstance(row['daily']['value'], int) for row in data['limits'])
