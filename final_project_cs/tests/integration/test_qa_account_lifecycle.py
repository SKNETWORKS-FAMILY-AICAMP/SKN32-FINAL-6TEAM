"""실제 DB의 별도 테넌트에서 수명·격리·권한·삭제를 검증하고 롤백한다."""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.application import admin_service as admin
from app.domains.travel_ops.modules.web_account import qa_account as qa, qa_account_api as api, web_cookie, web_guard, web_session
from app.infrastructure.db.session import get_connection
from app.presentation import admin_api
from app.presentation.ui import auth


@pytest.fixture
def state(monkeypatch):
    with get_connection() as conn:
        tenant = 'qa_lifecycle_' + uuid4().hex
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'QA 수명 시험')", (tenant,))
        regular, regular_key = web_session.issue(conn, tenant_id=tenant)
        conn.execute("INSERT INTO trips(tenant_id,customer_id,title) VALUES(%s,%s,'보호할 일반 여행')", (tenant, regular))
        @contextmanager
        def connection():
            yield conn
        monkeypatch.setattr(api, 'get_connection', connection)
        monkeypatch.setattr(web_guard, 'get_connection', connection)
        monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(tenant_id=tenant, public_base_url='https://customer.example', web_origin='https://customer.example'))
        try:
            yield conn, tenant, regular, regular_key
        finally:
            conn.rollback()


def start(conn, tenant):
    return qa.change(conn, tenant, 'qa-operator', enabled=True, expected_revision=0, reason='수명 시험')


def stop(conn, tenant, state):
    return qa.change(conn, tenant, 'qa-operator', enabled=False, expected_revision=state['revision'],
                     confirm_customer_id=state['customer_id'], reason='시험 종료')


def test_default_off_start_stop_deletes_only_qa_and_restart_is_fresh(state):
    conn, tenant, regular, regular_key = state
    assert qa.status(conn, tenant) == dict(enabled=False, revision=0, customer_id=None, trips=0, started_at=None)
    current = start(conn, tenant)
    customer = UUID(current['customer_id'])
    raw_key = web_session.add_key(conn, tenant_id=tenant, customer_id=customer)
    cookie, _ = web_cookie.start(conn, tenant_id=tenant, customer_id=customer)
    conn.execute("INSERT INTO trips(tenant_id,customer_id,title) VALUES(%s,%s,'지울 시험 여행')", (tenant, customer))
    conn.execute("INSERT INTO trip_intakes(tenant_id,customer_id) VALUES(%s,%s)", (tenant, customer))
    assert qa.status(conn, tenant)['trips'] == 1
    assert admin.access_policy(conn, tenant, str(customer))['chat_limit'] is None
    assert stop(conn, tenant, current)['enabled'] is False
    for table in ('customers', 'trips', 'trip_intakes', 'web_sessions', 'web_user_keys', 'admin_records'):
        assert conn.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s AND customer_id=%s", (tenant, customer)).fetchone()[0] == 0
    assert web_session.resolve(conn, tenant_id=tenant, raw=raw_key) is None
    assert web_cookie.lookup(conn, tenant_id=tenant, raw=cookie) is None
    assert web_session.resolve(conn, tenant_id=tenant, raw=regular_key) == regular
    assert conn.execute("SELECT count(*) FROM trips WHERE tenant_id=%s AND customer_id=%s", (tenant, regular)).fetchone()[0] == 1
    fresh = qa.change(conn, tenant, 'qa-operator', enabled=True, expected_revision=2, reason='다음 시험')
    assert fresh['customer_id'] != str(customer)


def test_stale_start_and_stop_cannot_target_new_generation(state):
    conn, tenant, _, _ = state
    current = start(conn, tenant)
    with pytest.raises(admin.AdminServiceError, match='다른 운영자'):
        start(conn, tenant)
    stop(conn, tenant, current)
    fresh = qa.change(conn, tenant, 'qa-operator', enabled=True, expected_revision=2, reason='다음 시험')
    with pytest.raises(admin.AdminServiceError, match='다른 운영자'):
        stop(conn, tenant, current)
    assert qa.status(conn, tenant) == fresh


def test_wrong_customer_confirmation_cannot_delete_regular_user(state):
    conn, tenant, regular, _ = state
    current = start(conn, tenant)
    with pytest.raises(admin.AdminServiceError, match='번호'):
        stop(conn, tenant, {**current, 'customer_id': str(regular)})
    assert qa.status(conn, tenant) == current


@pytest.mark.parametrize('target', ['regular', 'unmarked-qa'])
def test_managed_marker_required_even_if_pointer_or_user_record_changes(state, target):
    conn, tenant, regular, _ = state
    current = start(conn, tenant)
    if target == 'regular':
        value = {**admin.record(conn, tenant, 'settings', 'qa-account'), 'customer_id':str(regular)}
        conn.execute("UPDATE admin_records SET value=%s WHERE tenant_id=%s AND kind='settings' AND id='qa-account'", (Jsonb(value),tenant))
    else:
        admin.put(conn, tenant, 'user', current['customer_id'], {'usageExempt':True}, actor='qa-operator', action='test', reason='표시 손상 검증')
    with pytest.raises(admin.AdminServiceError, match='일반 계정'):
        stop(conn, tenant, qa.status(conn, tenant))
    assert conn.execute('SELECT count(*) FROM customers WHERE tenant_id=%s', (tenant,)).fetchone()[0] == 2


def test_repeated_same_state_does_not_create_more_accounts(state):
    conn, tenant, _, _ = state
    current = start(conn, tenant)
    assert qa.change(conn, tenant, 'qa-operator', enabled=True, expected_revision=1, reason='재조회') == current
    assert conn.execute("SELECT count(*) FROM customers WHERE tenant_id=%s", (tenant,)).fetchone()[0] == 2
    stopped = stop(conn, tenant, current)
    assert qa.change(conn, tenant, 'qa-operator', enabled=False, expected_revision=2, reason='재조회') == stopped


def test_one_time_ticket_not_stored_raw_and_cannot_replay(state):
    conn, tenant, _, _ = state
    current = start(conn, tenant)
    raw, seconds = qa.issue_ticket(conn, tenant, 'qa-operator', expected_revision=1, reason='화면 열기')
    assert 0 < seconds <= 300
    assert raw not in str(admin.record(conn, tenant, 'settings', 'qa-account'))
    assert raw not in str(conn.execute('SELECT after_value FROM admin_audit WHERE tenant_id=%s', (tenant,)).fetchall())
    assert qa.consume_ticket(conn, tenant, raw) == UUID(current['customer_id'])
    with pytest.raises(admin.AdminServiceError) as refused:
        qa.consume_ticket(conn, tenant, raw)
    assert refused.value.status_code == 410


@pytest.mark.parametrize('mode', ['wrong', 'expired', 'stopped', 'newer', 'other-tenant'])
def test_unusable_ticket_is_refused(state, mode):
    conn, tenant, _, _ = state
    current = start(conn, tenant)
    raw, _ = qa.issue_ticket(conn, tenant, 'qa-operator', expected_revision=1, reason='화면 열기')
    if mode == 'wrong': raw = 'x' * 43
    if mode == 'expired':
        value = {**admin.record(conn, tenant, 'settings', 'qa-account'), 'ticket_expires_at': (datetime.now(UTC)-timedelta(seconds=1)).isoformat()}
        conn.execute("UPDATE admin_records SET value=%s WHERE tenant_id=%s AND kind='settings' AND id='qa-account'", (Jsonb(value), tenant))
    if mode == 'stopped': stop(conn, tenant, current)
    if mode == 'newer': qa.issue_ticket(conn, tenant, 'qa-operator', expected_revision=1, reason='새 링크')
    with pytest.raises(admin.AdminServiceError) as refused:
        qa.consume_ticket(conn, tenant if mode != 'other-tenant' else tenant+'_other', raw)
    assert refused.value.status_code == 410


@pytest.mark.parametrize('policy', ['blocked', 'maintenance'])
def test_login_still_obeys_block_and_maintenance(state, policy):
    conn, tenant, _, _ = state
    current = start(conn, tenant)
    raw, _ = qa.issue_ticket(conn, tenant, 'qa-operator', expected_revision=1, reason='화면 열기')
    command = {'type': 'block-user', 'userId': current['customer_id'], 'blocked': True} if policy == 'blocked' else {'type':'maintenance', 'enabled':True, 'message':'점검', 'messageEn':'', 'endsAt':'2099-01-01T00:00'}
    admin.mutate(conn, tenant, 'qa-operator', command)
    with pytest.raises(admin.AdminServiceError) as refused:
        qa.consume_ticket(conn, tenant, raw)
    assert refused.value.status_code == 503


def test_cannot_adopt_regular_or_other_tenant_customer(state):
    conn, tenant, regular, _ = state
    with pytest.raises(admin.AdminServiceError): qa.adopt_existing(conn, tenant, 'qa-operator', regular, reason='거부 시험')
    with pytest.raises(admin.AdminServiceError): qa.adopt_existing(conn, tenant+'_other', 'qa-operator', regular, reason='거부 시험')
    admin.set_usage_exemption(conn, tenant, str(regular), enabled=True, actor='qa-operator', reason='기존 QA 확인')
    assert qa.adopt_existing(conn, tenant, 'qa-operator', regular, reason='기존 승인 계정 편입')['customer_id'] == str(regular)


def test_partial_delete_is_rolled_back_not_reported_off(state, monkeypatch):
    conn, tenant, _, _ = state
    current = start(conn, tenant)
    def partial(conn, tenant, customer):
        conn.execute('DELETE FROM web_sessions WHERE tenant_id=%s AND customer_id=%s', (tenant, customer))
        return {'customer':0, 'kept':1}
    monkeypatch.setattr(qa.member_cleanup, 'erase_customer', partial)
    with pytest.raises(admin.AdminServiceError), conn.transaction(): stop(conn, tenant, current)
    assert qa.status(conn, tenant) == current


def test_admin_http_permissions_csrf_actor_and_input_boundary(state, monkeypatch):
    conn, tenant, _, _ = state
    hashed = auth.hash_password('correct-password', iterations=1000)
    scopes = frozenset({'ops:introspect','limits:write'})
    monkeypatch.setattr(auth, 'operators', lambda: {'qa-operator': (hashed, scopes)})
    app = FastAPI(); app.include_router(admin_api.build_router())
    app.include_router(api.build_admin_router(admin_api.operator, admin_api.require))
    app.include_router(api.build_customer_router())
    client = TestClient(app)
    assert client.get('/admin/api/qa-account', headers={'X-User-Key':'acop_u_customer'}).status_code == 401
    pre = client.get('/admin/api/session').json()['csrf']
    assert client.post('/admin/api/login', json={'operatorId':'qa-operator','password':'correct-password'}, headers={'X-CSRF-Token':pre}).status_code == 200
    csrf = client.get('/admin/api/session').json()['csrf']; headers = {'X-CSRF-Token':csrf}
    payload = {'enabled':True, 'expected_revision':0, 'reason':'수명 시험'}
    assert client.patch('/admin/api/qa-account', json=payload).status_code == 403
    assert client.patch('/admin/api/qa-account', json={**payload,'customer_id':str(uuid4())}, headers=headers).status_code == 422
    assert client.patch('/admin/api/qa-account', json={**payload,'actor':'spoof'}, headers=headers).status_code == 422
    assert client.patch('/admin/api/qa-account', json={**payload,'enabled':'true'}, headers=headers).status_code == 422
    got = client.patch('/admin/api/qa-account', json=payload, headers=headers)
    assert got.status_code == 200
    opened = client.post('/admin/api/qa-account/open', json={'expected_revision':1,'reason':'화면 열기'}, headers=headers)
    assert opened.status_code == 200 and opened.headers['cache-control'] == 'no-store'
    exchanged = client.post(opened.json()['url'], data={'ticket':opened.json()['ticket']}, follow_redirects=False)
    assert exchanged.status_code == 303 and exchanged.headers['location'] == 'https://customer.example/trips/new'
    assert 'HttpOnly' in exchanged.headers['set-cookie'] and exchanged.headers['referrer-policy'] == 'no-referrer'
    assert client.post(opened.json()['url'], data={'ticket':opened.json()['ticket']}, follow_redirects=False).status_code == 410
    assert client.get(opened.json()['url']).status_code == 405
    assert set(row[0] for row in conn.execute('SELECT actor FROM admin_audit WHERE tenant_id=%s', (tenant,)).fetchall()) == {'qa-operator','qa-session'}
    scopes = frozenset({'ops:introspect'})
    assert client.patch('/admin/api/qa-account', json=payload, headers=headers).status_code == 403
    assert client.post('/admin/api/qa-account/open', json={'expected_revision':1,'reason':'화면'}, headers=headers).status_code == 403
    assert client.get('/admin/api/qa-account').status_code == 200


def test_customer_auth_router_cannot_create_or_delete_qa_accounts():
    from app.domains.travel_ops.modules.web_account.web_auth_api import build_auth_router
    app = FastAPI(); app.include_router(build_auth_router())
    client = TestClient(app)
    for method in ('GET', 'PATCH', 'POST'):
        assert client.request(method, '/admin/api/qa-account').status_code == 404
    assert client.post('/v1/web/auth/qa-session').status_code == 422
    assert client.post('/v1/web/auth/qa-session', data={'ticket':'short'}).status_code == 422
