"""실제 로컬 DB에서 여행별 주입·6종 조합·감시·안전정지·중지·감사 기록을 확인한다."""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.admin_service import AdminServiceError
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.components.watch import simulation
from app.domains.travel_ops.components.watch.safety_pause import SafetySweep
from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
from app.domains.travel_ops.entry import admin_simulation_api
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.presentation.ui import auth
from app.presentation import admin_api


@pytest.fixture
def world(monkeypatch):
    with get_connection() as conn:
        conn.execute((Path(__file__).parents[2] / 'app/infrastructure/db/migrations/227_watch_simulation_proposal_scope.sql').read_text(encoding='utf-8'))
        tenant, customer = 'simulation_test_' + uuid4().hex, uuid4()
        now = datetime.now(UTC)
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'재난 시험')", (tenant,))
        conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,'test')", (customer, tenant))
        places = []
        for name, outdoor in [('서울 시험 공원', True), ('서울 시험 박물관', False)]:
            identity = uuid4()
            conn.execute("INSERT INTO places(place_id,tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) "
                         "VALUES(%s,%s,%s,'activity',37.57,126.98,%s,'{}')", (identity, tenant, name, outdoor))
            places.append(identity)
        store = TripStore(tenant)
        item = Item(uuid4(), 1, 'activity', '서울 시험 공원', places[0], now-timedelta(minutes=5), now+timedelta(minutes=50))
        next_item = Item(uuid4(), 2, 'activity', '서울 시험 박물관', places[1], now+timedelta(hours=2), now+timedelta(hours=3))
        trip_id, _ = store.create_trip(conn, customer_id=customer, title='서울 재난 시험', locale='ko', party_size=1, items=[item, next_item])
        @contextmanager
        def connection():
            yield conn
        monkeypatch.setattr(simulation, 'get_connection', connection)
        monkeypatch.setattr(admin_simulation_api, 'get_connection', connection)
        monkeypatch.setattr(admin_simulation_api, 'get_settings', lambda: SimpleNamespace(tenant_id=tenant))
        checker = DisruptionCheck(SimpleNamespace())
        calls = []
        for method, category in [('_forecast','forecast'),('_warning','weather_warning'),('_disaster','disaster_msg'),('_traffic','traffic_control'),('_air','air_quality'),('_earthquake','earthquake')]:
            def clear(*args, category=category):
                calls.append(category)
                return {'category':category, 'status':'ok'}
            monkeypatch.setattr(checker, method, clear)
        yield SimpleNamespace(conn=conn, connect=connection, tenant=tenant, customer=customer, now=now, store=store,
                              trip_id=trip_id, item=item, next_item=next_item, checker=checker, calls=calls)
        conn.rollback()


def set_inputs(w, selected, **overrides):
    current = simulation.state(w.conn, w.tenant, w.trip_id)
    args = dict(actor='test-operator', expected_revision=current['revision'], expected_version=1,
                item_id=w.item.item_id, categories=list(selected), duration_minutes=15, reason='재난 시험')
    args.update(overrides)
    return simulation.configure(w.conn, w.tenant, w.trip_id, **args)


ALL_COMBINATIONS = [choice for n in range(7) for choice in combinations(simulation.CATEGORIES, n)]


@pytest.mark.parametrize('selected', ALL_COMBINATIONS)
def test_all_64_combinations_only_replace_selected_sources(world, selected):
    w = world
    set_inputs(w, selected)
    _, [item, other] = w.store.latest(w.conn, w.trip_id)
    report = w.checker.check(place=item.place, starts_at=w.now)
    found = {cause['category'] for cause in report['disruptions'] + report['advisories']}
    assert found == set(selected)
    assert set(w.calls) == set(simulation.CATEGORIES) - set(selected)
    assert report['verdict'] == ('disrupted' if set(selected)-{'forecast'} else 'clear')
    assert simulation.resolve(other.place) is None


def test_forecast_runs_current_item_through_default_watch_and_app_notice(world):
    w = world
    state = set_inputs(w, ['forecast'])
    opener = TripWatchCaseOpener(store=w.store, check=w.checker.check, connection_factory=w.connect,
                                 clock=lambda: w.now, repository=repository, run_case=None)
    result = opener.tick()
    assert len(result.notified) == 1 and not result.opened
    notices = w.conn.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND payload_json->>'simulation_id'=%s", (w.tenant,state['run_id'])).fetchall()
    [notice] = [row[0] for row in notices]
    assert notice['simulation'] is True and notice['text'].startswith('[시뮬레이션]')
    assert notice['consent_key'] == 'change' and '예보에 맞게 일정 변경' in notice['text']
    full = admin_simulation_api._view(w.conn,w.tenant,w.trip_id)['reports']['full']
    assert len(full['checks']) == 6 and sum(c.get('mode') == 'simulation' for c in full['checks']) == 1
    assert w.store.latest(w.conn,w.trip_id)[0]['version'] == 1
    assert opener.tick().notified == []
    set_inputs(w, [])
    state = set_inputs(w, ['forecast'])
    assert len(opener.tick().notified) == 1
    assert w.conn.execute("SELECT count(*) FROM pending_changes WHERE tenant_id=%s AND status='open'",(w.tenant,)).fetchone()[0] == 1
    assert w.conn.execute("SELECT count(*) FROM pending_changes WHERE tenant_id=%s AND status='superseded'",(w.tenant,)).fetchone()[0] == 1


def test_earthquake_goes_through_safety_pause_before_schedule_change(world):
    w = world
    state = set_inputs(w, list(simulation.CATEGORIES))
    sweep = SafetySweep(store=w.store, check=w.checker.check_safety, connection_factory=w.connect, clock=lambda:w.now)
    result = sweep.tick()
    assert len(result.opened) == 1 and not result.fatal
    full = admin_simulation_api._view(w.conn,w.tenant,w.trip_id)['reports']['full']
    assert {c['category'] for c in full['checks'] if c.get('mode')=='simulation'} == set(simulation.CATEGORIES)
    assert w.store.due(w.conn, start=w.now, end=w.now+timedelta(hours=2)) == []
    notice = w.conn.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND payload_json->>'simulation_id'=%s", (w.tenant,state['run_id'])).fetchone()[0]
    assert notice['simulation'] and notice['type'] == 'safety_alert'
    assert sweep.tick().opened == []
    # 입력 중지가 실제 정지를 몰래 풀지 않는다.
    set_inputs(w, [])
    assert w.conn.execute("SELECT count(*) FROM trip_safety_pauses WHERE tenant_id=%s AND resumed_at IS NULL", (w.tenant,)).fetchone()[0] == 1
    # 자동 종료·중지 뒤 나가는 재안내에도 시험 출처가 남아 외부 발송에서 제외된다.
    pause_id=result.opened[0]['pause_id']
    later=simulation.mark_notice(w.conn,w.tenant,w.trip_id,{'pause_id':pause_id,'text':'정지 재안내'})
    assert later['simulation'] is True and later['simulation_id']==state['run_id']


def test_disable_expiry_and_forgery_cannot_keep_inputs_alive(world):
    w = world
    set_inputs(w, ['traffic_control'])
    _, items = w.store.latest(w.conn,w.trip_id)
    saved = items[0].place
    assert simulation.resolve(saved)
    forged = {**saved, simulation.MARKER:{**saved[simulation.MARKER], 'revision':999}}
    assert simulation.resolve(forged) is None
    set_inputs(w, [])
    assert simulation.resolve(saved) is None
    latest = set_inputs(w, ['earthquake'])
    assert simulation.state(w.conn,w.tenant,w.trip_id,now=w.now+timedelta(hours=2))['active'] is False
    assert latest['revision'] == 3
    rows = w.conn.execute("SELECT actor,action,reason FROM admin_audit WHERE tenant_id=%s ORDER BY seq",(w.tenant,)).fetchall()
    assert rows == [('test-operator','watch-simulation','재난 시험')]*3


def test_indoor_inputs_keep_existing_applicability_and_other_trip_is_clear(world):
    w = world
    set_inputs(w, list(simulation.CATEGORIES), item_id=w.next_item.item_id)
    _, items = w.store.latest(w.conn,w.trip_id)
    report = w.checker.check(place=items[1].place,starts_at=items[1].starts_at)
    assert {r['category'] for r in report['checks'] if r['status']=='not_applicable'} == {'forecast','weather_warning','air_quality'}
    assert simulation.state(w.conn,'another_tenant',w.trip_id)['active'] is False
    other_trip,_ = w.store.create_trip(w.conn,customer_id=w.customer,title='다른 서울 여행',locale='ko',party_size=1,items=[w.item,w.next_item])
    _, others = w.store.latest(w.conn,other_trip)
    assert simulation.resolve(others[0].place) is None


@pytest.mark.parametrize('override,status', [({'expected_revision':99},409),({'expected_version':99},409),({'item_id':uuid4()},422),({'categories':['earthquake','earthquake']},422),({'categories':['unknown']},422)])
def test_stale_or_invalid_configuration_is_refused(world,override,status):
    with pytest.raises(AdminServiceError) as error:
        set_inputs(world,['earthquake'],**override)
    assert error.value.status_code == status


def test_operator_auth_scope_csrf_and_customer_api_separation(world,monkeypatch):
    w = world
    app = FastAPI(); app.include_router(admin_simulation_api.build_router(operator_dependency=admin_api.operator,require_permission=admin_api.require))
    client = TestClient(app)
    path=f'/admin/api/simulations/{w.trip_id}'
    assert client.get(path).status_code == 401
    op = auth.Operator('operator',frozenset({'ops:introspect','limits:write'}))
    cookie = auth.issue(op)
    monkeypatch.setattr(auth,'operators',lambda:{'operator':('',op.scopes)})
    client.cookies.set(auth.COOKIE,cookie)
    body=dict(expected_revision=0,expected_version=1,item_id=str(w.item.item_id),categories=['forecast'],duration_minutes=15,reason='시험')
    assert client.patch(path,json=body).status_code == 403
    headers={'X-CSRF-Token':auth.csrf_for(cookie)}
    response=client.patch(path,json=body,headers=headers)
    assert response.status_code == 200,response.text
    assert response.json()['configuration']['categories'] == ['forecast']
    assert client.get('/admin/api/simulations').json()['trips'][0]['trip_id'] == str(w.trip_id)
    assert client.get(f'/admin/api/simulations/{uuid4()}').status_code == 404
    assert client.patch(path,json=body,headers=headers).status_code == 409
    monkeypatch.setattr(auth,'operators',lambda:{'operator':('',frozenset({'ops:introspect'}))})
    assert client.patch(path,json=body,headers=headers).status_code == 403


def test_trial_notifications_never_call_external_customer_or_development_channel(world):
    from app.domains.travel_ops.components.watch.notice_routing import CustomerNoticeRouter
    from app.infrastructure.notify.suppressed import NoticeSuppressed
    def unexpected(*args, **kwargs):
        pytest.fail('시험 알림이 외부 발송 경로를 불렀습니다.')
    router = CustomerNoticeRouter(operator=unexpected, connection_factory=unexpected, enabled=lambda:True, renderer=unexpected)
    with pytest.raises(NoticeSuppressed):
        router({'topic':'trip.notice','tenant_id':world.tenant,'payload':{'simulation':True,'text':'시험'}})


def test_case_team_reads_the_same_trial_input_and_tags_its_result(world,monkeypatch):
    from app import composition
    from app.domains.travel_ops.scenarios import case_engine
    w = world
    monkeypatch.setattr(composition,'get_connection',w.connect)
    monkeypatch.setattr(case_engine,'get_connection',w.connect)
    set_inputs(w,['weather_warning'])
    engine = case_engine.CaseEngine(tenant_id=w.tenant, check=w.checker.check, route_events=None,
                                    classifier=None, report_extractor=None, clock=lambda:w.now)
    result = engine.tick()
    assert len(result.opened) == 1 and len(result.ran) == 1 and not result.failed
    notices = w.conn.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND dedupe_key LIKE %s",(w.tenant,f'{w.trip_id}:%')).fetchall()
    assert notices and all(notice[0].get('simulation') for notice in notices)
