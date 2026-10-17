from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest

from app.domains.travel_ops.components.watch import receipt_history as history
from tests.integration.test_receipt_history import db, now  # noqa: F401 — TEMP 표 fixture 재사용
from tests.unit.travel.test_receipt_impact import rules  # noqa: F401


def add(db, scope, *, tenant='one', mode='api', at=None):
    category = 'traffic_control' if scope == 'item' else 'earthquake'
    causes = ([{'category': category, 'kind': '통제'}] if scope == 'item' else
              [{'category': category, 'magnitude': 7 if scope == 'trip' else 4.5}] if scope in ('trip', 'day') else [])
    report = {'verdict': 'clear' if scope == 'none' else 'disrupted',
              'checks': [{'category': category, 'status': 'failed' if scope == 'unassessed' else 'ok', 'mode': mode}],
              'disruptions': causes}
    db.execute('INSERT INTO travel_watch_checks(tenant_id,at,trip_id,target_title,stage,report) VALUES(%s,%s,%s,%s,%s,%s)',
               (tenant, at or now(db)-timedelta(minutes=1), uuid4(), '필터 검증 일정', 'schedule', Jsonb(report)))


def test_impact_filter_precedes_counts_and_pagination_and_keeps_snapshot(db, monkeypatch, rules):
    monkeypatch.setattr(history.SafetyRules, 'from_guardrails', lambda: rules)
    for scope, count in [('trip', 61), ('day', 53), ('item', 3), ('none', 1), ('unassessed', 2)]:
        for _ in range(count):
            add(db, scope)
    add(db, 'trip', tenant='two')
    first = history.view(db, 'one', impacts=['trip', 'day'])
    snapshot = datetime.fromisoformat(first['as_of'])
    add(db, 'trip', at=now(db))
    second = history.view(db, 'one', impacts=['trip', 'day'], page=2, as_of=snapshot)
    third = history.view(db, 'one', impacts=['trip', 'day'], page=3, as_of=snapshot)
    assert [r['total'] for r in (first, second, third)] == [114]*3
    assert [len(r['records']) for r in (first, second, third)] == [50, 50, 14]
    records = [r for p in (first, second, third) for r in p['records']]
    assert len({r['id'] for r in records}) == 114
    assert {r['impact']['scope'] for r in records} == {'trip', 'day'}
    assert first['impacts'] == ['trip', 'day']


def test_mode_date_and_impact_are_combined_and_unknown_is_not_none(db, monkeypatch, rules):
    monkeypatch.setattr(history.SafetyRules, 'from_guardrails', lambda: rules)
    for scope in ('trip', 'item', 'none', 'unassessed'):
        add(db, scope)
    add(db, 'trip', mode='simulation')
    assert history.view(db, 'one', mode='simulation', impacts=['trip'])['total'] == 1
    assert history.view(db, 'one', mode='all', impacts=['trip'])['total'] == 2
    none = history.view(db, 'one', impacts=['none'])
    assert none['total'] == 1
    assert none['records'][0]['impact']['scope'] == 'none'
    day = now(db).astimezone(history.KST).date()-timedelta(days=2)
    assert history.view(db, 'one', impacts=['trip'], date_from=day, date_to=day)['total'] == 0
    assert history.view(db, 'one', mode='all')['total'] == 5


def test_real_source_in_a_mixed_simulation_target_is_labelled_as_a_trial(db, monkeypatch, rules):
    monkeypatch.setattr(history.SafetyRules, 'from_guardrails', lambda: rules)
    report = {'checks': [{'category': 'earthquake', 'mode': 'api', 'status': 'ok'},
                         {'category': 'forecast', 'mode': 'simulation', 'status': 'ok'}],
              'disruptions': [{'category': 'earthquake', 'magnitude': 7}]}
    db.execute('INSERT INTO travel_watch_checks(tenant_id,at,trip_id,stage,report) VALUES(%s,%s,%s,%s,%s)',
               ('one', now(db)-timedelta(seconds=1), uuid4(), 'safety', Jsonb(report)))
    record = history.view(db, 'one', mode='actual', impacts=['trip'])['records'][0]
    assert record['mode'] == 'actual'
    assert record['impact']['scope'] == 'trip'
    assert record['impact']['target_mode'] == 'simulation'
    assert record['impact']['affects_itinerary'] is False


@pytest.mark.parametrize('query', ['impact=bad', 'impact=trip&impact=day&impact=item&impact=none&impact=trip'])
def test_invalid_impact_query_is_rejected_before_storage(query, monkeypatch):
    from app.domains.travel_ops.entry import admin_simulation_api as api
    monkeypatch.setattr(api, 'get_connection', lambda: pytest.fail('invalid filter opened storage'))
    app = FastAPI()
    app.include_router(api.build_router(operator_dependency=lambda: 'operator', require_permission=lambda *args: None))
    assert TestClient(app).get('/admin/api/simulations/receipts?'+query).status_code == 422


def test_http_multiple_filters_preserve_operator_permission_and_readonly(db, monkeypatch, rules):
    from app.domains.travel_ops.entry import admin_simulation_api as api
    from app.domains.travel_ops.components.watch import notice_receipts
    monkeypatch.setattr(history.SafetyRules, 'from_guardrails', lambda: rules)
    add(db, 'trip')
    add(db, 'day')
    add(db, 'none')
    db.commit()

    @contextmanager
    def connect():
        yield db

    def due(conn, **kwargs):
        assert conn.execute("SELECT current_setting('transaction_read_only')").fetchone()[0] == 'on'
        return []

    scopes = []
    monkeypatch.setattr(api, 'get_connection', connect)
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(tenant_id='one'))
    monkeypatch.setattr(api, 'TripStore', lambda tenant: SimpleNamespace(due=due))
    monkeypatch.setattr(notice_receipts, 'view', lambda conn, tenant: {})
    app = FastAPI()
    app.include_router(api.build_router(operator_dependency=lambda: 'operator', require_permission=lambda op, scope: scopes.append(scope)))
    response = TestClient(app).get('/admin/api/simulations/receipts?impact=trip&impact=day')
    assert response.status_code == 200
    assert response.json()['history']['total'] == 2
    assert scopes == ['ops:introspect']
