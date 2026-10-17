from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import os
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import psycopg
from psycopg.types.json import Jsonb
import pytest

from app.domains.travel_ops.components.watch import receipt_history as history
from app.infrastructure.db.session import database_dsn


@pytest.fixture
def db():
    # 저장소의 시험 DB 설정을 따르며 실제 표는 TEMP 표로 가린다.
    with psycopg.connect(os.environ.get('TEST_DATABASE_URL') or database_dsn()) as conn:
        conn.execute('CREATE TEMP TABLE admin_records(tenant_id text,kind text,id text,value jsonb,updated_at timestamptz DEFAULT now(),PRIMARY KEY(tenant_id,kind,id))')
        conn.execute('CREATE TEMP TABLE admin_audit(tenant_id text,action text,target text,after_value jsonb,at timestamptz)')
        conn.execute('CREATE TEMP TABLE travel_watch_checks(check_id bigserial,tenant_id text,at timestamptz,trip_id uuid,target_title text,stage text,report jsonb)')
        yield conn
        conn.rollback()


def now(db):
    return db.execute('SELECT clock_timestamp()').fetchone()[0]


def message(db, identity, at, tenant='one'):
    db.execute('INSERT INTO admin_records VALUES(%s,%s,%s,%s,%s)',
               (tenant, 'watch_disaster_receipt', str(identity), Jsonb({'text': '화면·DB 시험 문자', 'regions': ['서울'], 'published_at': at.isoformat()}), at))


def check(db, values, *, tenant='one', at=None, report=None):
    db.execute('INSERT INTO travel_watch_checks(tenant_id,at,stage,report) VALUES(%s,%s,%s,%s)',
               (tenant, at or now(db)-timedelta(seconds=1), 'schedule', Jsonb(report or {'checks': values})))


def mock_input(db, *, categories=None):
    receipt = {'run_id': 'mock-run', 'categories': ['forecast'] if categories is None else categories,
               'mock_receipt': {'sources': {'forecast': {'category': 'forecast', 'mode': 'simulation', 'status': 'ok', 'value': {'wind_speed_kmh': 100}}}}}
    db.execute('INSERT INTO admin_audit VALUES(%s,%s,%s,%s,%s)',
               ('one', 'watch-simulation', str(uuid4()), Jsonb(receipt), now(db)-timedelta(seconds=1)))


@pytest.mark.parametrize('mode,total', [('actual', 8), ('simulation', 2), ('all', 10)])
def test_all_six_sources_messages_and_mock_inputs_are_filtered(db, mode, total):
    at = now(db)-timedelta(seconds=1)
    categories = ['forecast', 'weather_warning', 'disaster_msg', 'traffic_control', 'air_quality', 'earthquake']
    check(db, [{'category': c, 'mode': 'api', 'status': 'ok', 'value': {'temperature': 23}} for c in categories])
    check(db, [{'category': 'forecast', 'mode': 'simulation', 'status': 'ok'}])
    message(db, 'text', at)
    message(db, 'another-tenant', at, tenant='two')
    db.execute('INSERT INTO admin_records VALUES(%s,%s,%s,%s,%s)', ('one', 'watch_disaster_api_receipt', 'api', Jsonb({'status': 'received', 'count': 1}), at))
    mock_input(db)
    result = history.view(db, 'one', mode=mode)
    assert result['total'] == total
    assert len(result['records']) == total
    assert all(r['id'] != 'message:another-tenant' for r in result['records'])
    if mode != 'all':
        assert {r['mode'] for r in result['records']} == {mode}
    if mode == 'actual':
        assert {r['category'] for r in result['records']} == set(categories)


def test_default_is_seven_korean_calendar_days(db):
    today = now(db).astimezone(history.KST).date()
    edge = datetime.combine(today-timedelta(days=6), datetime.min.time(), history.KST)
    message(db, 'before', edge-timedelta(microseconds=1))
    message(db, 'first', edge)
    message(db, 'last', now(db)-timedelta(seconds=1))
    result = history.view(db, 'one')
    assert result['date_from'] == (today-timedelta(days=6)).isoformat()
    assert result['date_to'] == today.isoformat()
    assert result['total'] == 2


def test_both_calendar_end_dates_are_inclusive_in_korean_time(db):
    day = now(db).astimezone(history.KST).date()-timedelta(days=2)
    start = datetime.combine(day, datetime.min.time(), history.KST)
    for identity, at in [('before', start-timedelta(microseconds=1)), ('first', start),
                         ('last', start+timedelta(days=1, microseconds=-1)), ('after', start+timedelta(days=1))]:
        message(db, identity, at)
    result = history.view(db, 'one', date_from=day, date_to=day)
    assert {r['id'] for r in result['records']} == {'message:first', 'message:last'}


def test_fifty_per_page_and_stable_snapshot_with_new_receipts(db):
    stamp = now(db)-timedelta(hours=1)
    for number in range(123):
        message(db, number, stamp+timedelta(seconds=number))
    first = history.view(db, 'one')
    message(db, 'new-after-first-page', now(db))
    snapshot = datetime.fromisoformat(first['as_of'])
    second = history.view(db, 'one', page=2, as_of=snapshot)
    third = history.view(db, 'one', page=3, as_of=snapshot)
    assert [len(p['records']) for p in (first, second, third)] == [50, 50, 23]
    assert [p['total_pages'] for p in (first, second, third)] == [3, 3, 3]
    ids = [r['id'] for p in (first, second, third) for r in p['records']]
    assert len(set(ids)) == 123
    assert 'message:new-after-first-page' not in ids
    assert history.view(db, 'one', page=999, as_of=snapshot)['page'] == 3


def test_stopping_mock_does_not_repeat_its_input(db):
    mock_input(db)
    mock_input(db, categories=[])
    result = history.view(db, 'one', mode='simulation')
    assert result['total'] == 1
    assert result['records'][0]['payload']['value']['wind_speed_kmh'] == 100


@pytest.mark.parametrize('payload', [{'mode': 'sample'}, {'value': {'mode': 'sample'}}])
def test_sample_provider_is_never_labelled_actual(db, payload):
    check(db, [{'category': 'disaster_msg', 'status': 'ok', **payload}])
    assert history.view(db, 'one', mode='actual')['total'] == 0
    assert history.view(db, 'one', mode='simulation')['total'] == 1


def test_safe_payload_does_not_mix_other_sources_or_expose_secrets(db):
    report = {'checks': [{'category': 'forecast', 'status': 'ok', 'source': 'https://example.test/?token=private',
                           'value': {'temperature': 22, 'password': 'private'}}],
              'advisories': [{'category': 'forecast', 'value': 22}, {'category': 'air_quality', 'mode': 'simulation', 'value': 100}]}
    check(db, [], report=report)
    row = history.view(db, 'one')['records'][0]
    assert row['payload']['value'] == {'temperature': 22}
    assert row['source'] == '[주소 가림]'
    assert row['payload']['advisories'] == [{'category': 'forecast', 'value': 22}]
    from app.domains.travel_ops.components.watch.monitoring import _safe
    assert _safe({'value': {'events': [{'depth_km': 10, 'location': '서울', 'password': 'private'}]},
                  'window': {'from': '2026-10-17', 'to': '2026-10-18'}}) == {
        'value': {'events': [{'depth_km': 10, 'location': '서울'}]},
        'window': {'from': '2026-10-17', 'to': '2026-10-18'}}


@pytest.mark.parametrize('args', [{'mode': 'bad'}, {'page': 0}, {'as_of': datetime(2026, 1, 1)},
                                 {'date_from': datetime(2026, 10, 20).date(), 'date_to': datetime(2026, 10, 19).date()}])
def test_invalid_filters_are_explicit_errors(db, args):
    with pytest.raises(HTTPException) as raised:
        history.view(db, 'one', **args)
    assert raised.value.status_code == 422


def target(start, *, end=None, trial=False, kind='activity'):
    return SimpleNamespace(item_id=uuid4(), starts_at=start, ends_at=end, kind=kind,
                           place={'_watch_simulation': {'active': True}} if trial else {}, title='창덕궁 · 시험')


def test_future_changdeokgung_trial_is_not_a_real_ninety_minute_target():
    start = datetime(2026, 10, 17, 6, tzinfo=UTC)
    future = start+timedelta(days=7)
    actual, simulated = history.targets([(uuid4(), target(future, trial=True))], start=start, end=start+timedelta(minutes=90))
    assert actual == []
    assert len(simulated) == 1
    assert simulated[0]['reason'] == 'simulation'


def test_real_targets_include_ongoing_and_upcoming_only():
    start = datetime(2026, 10, 17, 6, tzinfo=UTC)
    items = [target(start-timedelta(minutes=30), end=start+timedelta(minutes=30)),
             target(start+timedelta(minutes=89)), target(start+timedelta(minutes=90)),
             target(start+timedelta(days=7)), target(start, kind='mobility')]
    actual, simulated = history.targets([(uuid4(), item) for item in items], start=start, end=start+timedelta(minutes=90))
    assert [r['reason'] for r in actual] == ['ongoing', 'upcoming']
    assert simulated == []


def test_disaster_poll_history_is_append_only_and_messages_are_deduplicated(db, monkeypatch):
    from app.domains.travel_ops.components.watch import notice_receipts
    @contextmanager
    def connect():
        yield db
    monkeypatch.setattr(notice_receipts, 'get_connection', connect)
    monkeypatch.setattr(notice_receipts, 'get_settings', lambda: SimpleNamespace(tenant_id='one'))
    receipt = {'status': 'received', 'source': 'disaster_msg', 'region': '서울', 'from_cache': False,
               'rows': [{'serial': 'one-message', 'text': '수신 기록 시험', 'created_at': now(db).isoformat(), 'regions': ['서울']}]}
    notice_receipts.record(receipt)
    notice_receipts.record({**receipt, 'from_cache': True})
    kinds = dict(db.execute('SELECT kind,count(*) FROM admin_records GROUP BY kind').fetchall())
    assert kinds['watch_disaster_receipt'] == 1
    assert kinds['watch_disaster_api_receipt'] == 2
    assert kinds['watch_disaster_receipt_status'] == 1


def test_receipts_http_filters_and_readonly_transaction(db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.domains.travel_ops.entry import admin_simulation_api as api
    from app.domains.travel_ops.components.watch import notice_receipts
    for number in range(51):
        message(db, number, now(db)-timedelta(minutes=1))
    db.commit()
    @contextmanager
    def connect():
        yield db
    permissions = []
    def due(conn, *, start, end):
        assert conn.execute("SELECT current_setting('transaction_read_only')").fetchone()[0] == 'on'
        return [(uuid4(), target(start+timedelta(days=7), trial=True))]
    monkeypatch.setattr(api, 'get_connection', connect)
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(tenant_id='one'))
    monkeypatch.setattr(api, 'TripStore', lambda tenant: SimpleNamespace(due=due))
    monkeypatch.setattr(notice_receipts, 'view', lambda conn, tenant: {'statuses': [], 'messages': [], 'total': 0, 'latest_run': None})
    app = FastAPI()
    app.include_router(api.build_router(operator_dependency=lambda: SimpleNamespace(id='test'),
                                       require_permission=lambda op, scope: permissions.append(scope)))
    response = TestClient(app).get('/admin/api/simulations/receipts?mode=actual&page=2')
    assert response.status_code == 200
    data = response.json()
    assert data['history']['total'] == 51
    assert len(data['history']['records']) == 1
    assert data['targets'] == []
    assert len(data['simulation_targets']) == 1
    assert permissions == ['ops:introspect']


@pytest.mark.parametrize('query', ['mode=unknown', 'page=0'])
def test_receipts_http_rejects_invalid_query_without_storage(query, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.domains.travel_ops.entry import admin_simulation_api as api
    monkeypatch.setattr(api, 'get_connection', lambda: pytest.fail('invalid query opened storage'))
    app = FastAPI()
    app.include_router(api.build_router(operator_dependency=lambda: SimpleNamespace(id='test'), require_permission=lambda *args: None))
    assert TestClient(app).get('/admin/api/simulations/receipts?'+query).status_code == 422


def test_receipts_http_requires_operator_introspection_permission(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.domains.travel_ops.entry import admin_simulation_api as api
    def deny(op, scope):
        assert scope == 'ops:introspect'
        raise HTTPException(403, '권한 필요')
    monkeypatch.setattr(api, 'get_connection', lambda: pytest.fail('permission denial opened storage'))
    app = FastAPI()
    app.include_router(api.build_router(operator_dependency=lambda: SimpleNamespace(id='test'), require_permission=deny))
    assert TestClient(app).get('/admin/api/simulations/receipts').status_code == 403
