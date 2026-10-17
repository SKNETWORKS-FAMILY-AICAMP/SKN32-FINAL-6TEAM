"""게스트 목록·한국 날짜·페이지와 명시적인 시험 중에만 감시하는 경계를 확인한다."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.itinerary import trip_scope
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
from app.domains.travel_ops.entry import admin_simulation_api
from app.domains.travel_ops.modules.web_account.guest_policy import watch_scope_sql
from app.infrastructure.db import repository
from tests.integration.test_watch_simulation import set_inputs, world  # noqa: F401


def client_for(w):
    app = FastAPI()
    app.include_router(admin_simulation_api.build_router(
        operator_dependency=lambda: SimpleNamespace(id="operator"), require_permission=lambda *args: None))
    return TestClient(app)


def guest_trip(w, *, start=None, end=None):
    customer = uuid4()
    w.conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)",
                   (customer, w.tenant, "web:" + uuid4().hex))
    item = Item(uuid4(), 1, 'activity', '서울 시험 공원', w.item.place_id,
                start or w.item.starts_at, end or w.item.ends_at)
    identity, _ = w.store.create_trip(w.conn, customer_id=customer, title='게스트 서울 여행',
                                     locale='ko', party_size=1, items=[item])
    return identity


def test_guest_pages_are_separate_complete_and_stable(world):
    w = world
    expected = {str(guest_trip(w)) for _ in range(23)}
    client = client_for(w)
    found = []
    for page in range(1, 4):
        response = client.get('/admin/api/simulations', params={'audience': 'guest', 'page': page})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['total'] == 23 and data['total_pages'] == 3 and data['page'] == page
        found.extend(trip['trip_id'] for trip in data['trips'])
    assert len(found) == len(set(found)) == 23 and set(found) == expected
    assert client.get('/admin/api/simulations?audience=guest&page=4').json()['trips'] == []
    normal = client.get('/admin/api/simulations').json()
    assert normal['total'] == 1 and normal['trips'][0]['trip_id'] == str(w.trip_id)
    assert normal['trips'][0]['can_simulate'] is True
    # 다른 테넌트 고객의 여행은 같은 목록 조건에서도 나오지 않는다.
    other_tenant = 'guest_other_' + uuid4().hex
    w.conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'다른 여행 시험')", (other_tenant,))
    other_customer = uuid4()
    w.conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)",
                   (other_customer, other_tenant, 'web:' + uuid4().hex))
    TripStore(other_tenant).create_trip(w.conn, customer_id=other_customer, title='다른 게스트 여행',
                                       locale='ko', party_size=1, items=[
                                           Item(uuid4(), 1, 'activity', '서울 공원', None, w.item.starts_at, w.item.ends_at)])
    assert client.get('/admin/api/simulations?audience=guest').json()['total'] == 23


@pytest.mark.parametrize('selected_date', ['2031-01-02', '2031-01-03'])
def test_date_filter_uses_inclusive_korean_trip_period(world, selected_date):
    w = world
    identity = guest_trip(w, start=datetime.fromisoformat('2031-01-02T23:30:00+09:00'),
                          end=datetime.fromisoformat('2031-01-03T00:30:00+09:00'))
    guest_trip(w, start=datetime.fromisoformat('2031-01-04T10:00:00+09:00'),
               end=datetime.fromisoformat('2031-01-04T11:00:00+09:00'))
    data = client_for(w).get('/admin/api/simulations', params={
        'audience': 'guest', 'date_from': selected_date, 'date_to': selected_date}).json()
    assert data['total'] == 1 and data['trips'][0]['trip_id'] == str(identity)


@pytest.mark.parametrize('query', [
    'audience=unknown', 'page=0', 'page_size=51', 'page_size=0',
    'date_from=bad', 'date_from=2031-01-03&date_to=2031-01-02',
])
def test_invalid_filters_and_unbounded_pages_are_refused(world, query):
    assert client_for(world).get('/admin/api/simulations?' + query).status_code == 422


def test_finished_guests_can_be_found_but_not_simulated(world):
    w = world
    identity = guest_trip(w, start=w.now-timedelta(days=2), end=w.now-timedelta(days=1))
    client = client_for(w)
    data = client.get('/admin/api/simulations?audience=guest').json()
    assert data['trips'][0]['trip_id'] == str(identity) and data['trips'][0]['can_simulate'] is False
    view = client.get(f'/admin/api/simulations/{identity}').json()
    assert view['can_simulate'] is False and view['items'] == [] and view['unavailable_reason']
    response = client.patch(f'/admin/api/simulations/{identity}', json={
        'expected_revision': 0, 'expected_version': 1, 'item_id': str(w.item.item_id),
        'categories': ['forecast'], 'duration_minutes': 15, 'reason': '지난 여행 시험'})
    assert response.status_code == 422


@pytest.mark.parametrize('finish', ['stop', 'expiry', 'version'])
def test_only_explicit_guest_trial_is_watched_and_exception_ends(world, monkeypatch, finish):
    w = world
    monkeypatch.setattr(trip_scope, '_narrowers', [('web_account.guest', watch_scope_sql)])
    w.conn.execute("UPDATE customers SET external_id=%s WHERE customer_id=%s", ('web:' + uuid4().hex, w.customer))
    guest_trip(w)
    assert w.store.due(w.conn, start=w.now, end=w.now+timedelta(hours=1)) == []
    set_inputs(w, ['forecast'])
    opener = TripWatchCaseOpener(store=w.store, check=w.checker.check, connection_factory=w.connect,
                                 clock=lambda: w.now, repository=repository, run_case=None)
    result = opener.tick()
    assert len(result.notified) == 1 and not result.opened
    assert {identity for identity, _ in w.store.due(w.conn, start=w.now, end=w.now+timedelta(hours=1))} == {w.trip_id}
    if finish == 'stop':
        set_inputs(w, [])
    elif finish == 'expiry':
        w.conn.execute("UPDATE admin_records SET value=jsonb_set(value,'{expires_at}',to_jsonb((now()-interval '1 minute')::text)) "
                       "WHERE tenant_id=%s AND kind='watch_simulation'", (w.tenant,))
    else:
        w.conn.execute("UPDATE trips SET latest_version=2 WHERE tenant_id=%s AND trip_id=%s", (w.tenant, w.trip_id))
    assert w.store.due(w.conn, start=w.now, end=w.now+timedelta(hours=1)) == []
