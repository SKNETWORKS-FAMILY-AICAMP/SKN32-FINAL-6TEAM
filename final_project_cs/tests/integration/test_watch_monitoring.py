"""로컬 개발 DB에서 감시 회차·정상 결과·실패·과거 조회·권한을 검증한다."""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.watch import monitoring
from app.domains.travel_ops.components.watch.trip_watch_cases import TripWatchCaseOpener
from app.domains.travel_ops.components.watch.safety_pause import SafetySweep
from app.domains.travel_ops.components.itinerary.itinerary import Item, TripStore
from app.domains.travel_ops.entry import admin_watch_api
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.presentation import admin_api
from app.presentation.ui import auth


@pytest.fixture
def world(monkeypatch):
    with get_connection() as conn:
        sql=(Path(__file__).parents[2]/'app/infrastructure/db/migrations/228_watch_run_history.sql').read_text(encoding='utf-8')
        conn.execute(sql); conn.execute(sql)
        tenant,customer,place='watch_history_'+uuid4().hex,uuid4(),uuid4()
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES(%s,'감시 시험')",(tenant,))
        conn.execute("INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,'watch-test')",(customer,tenant))
        conn.execute("INSERT INTO places(place_id,tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) VALUES(%s,%s,'서울 시험 공원','activity',37.57,126.98,true,'{}')",(place,tenant))
        now=datetime.now(UTC)
        item=Item(uuid4(),1,'activity','서울 시험 공원',place,now+timedelta(minutes=15),now+timedelta(hours=1))
        store=TripStore(tenant)
        trip,_=store.create_trip(conn,customer_id=customer,title='서울 감시 시험',locale='ko',party_size=1,items=[item])
        @contextmanager
        def connect():yield conn
        monkeypatch.setattr(admin_watch_api,'get_connection',connect)
        monkeypatch.setattr(admin_watch_api,'get_settings',lambda:SimpleNamespace(tenant_id=tenant))
        app=FastAPI(); app.include_router(admin_watch_api.build_router(operator_dependency=admin_api.operator,require_permission=admin_api.require))
        client=TestClient(app)
        op=auth.Operator('watch-operator',frozenset({'ops:introspect'}))
        monkeypatch.setattr(auth,'operators',lambda:{op.id:('',op.scopes)})
        client.cookies.set(auth.COOKIE,auth.issue(op))
        yield SimpleNamespace(conn=conn,connect=connect,tenant=tenant,store=store,trip_id=trip,item=item,now=now,client=client)
        conn.rollback()


def run(w,work=lambda:{'checked':0},forced=False):
    return monitoring.execute(w.tenant,forced=forced,interval=180,work=work,connection_factory=w.connect)


def test_actual_safety_and_schedule_ticks_store_clear_results_and_forecast_attention(world):
    w=world
    def check(**kwargs):
        return dict(verdict='clear',checks=[{'category':c,'status':'ok','source':'여행 시험 입력','mode':'simulation','value':{'precipitation_probability':80}} for c in ['forecast','weather_warning','disaster_msg','traffic_control','air_quality','earthquake']],
                    disruptions=[],advisories=[{'category':'forecast','field':'precipitation_probability','value':80,'limit':60,'source':'여행 시험 입력'}])
    def work():
        # 실행 중 조회가 완료로 보이지 않는다.
        assert w.client.get('/admin/api/watch-runs').json()['latest']['status']=='running'
        sweep=SafetySweep(store=w.store,check=lambda **kw:{'verdict':'clear','checks':[{'category':c,'status':'ok'} for c in ['disaster_msg','earthquake']],'disruptions':[]},connection_factory=w.connect,clock=lambda:w.now)
        safety=sweep.tick(); monitoring.outcomes('safety_action',safety)
        opener=TripWatchCaseOpener(store=w.store,check=check,connection_factory=w.connect,clock=lambda:w.now,repository=repository,run_case=None)
        result=opener.tick(); monitoring.outcomes('schedule_action',result)
        return {'checked':result.checked,'opened':len(result.opened),'safety_checked':safety.checked}
    run(w,work)
    listing=w.client.get('/admin/api/watch-runs').json()
    assert listing['latest']['status']=='completed' and listing['latest']['counts']['checked']==1
    detail=w.client.get('/admin/api/watch-runs/'+listing['latest']['run_id']).json()
    assert {e['stage'] for e in detail['events']}=={'safety','schedule','schedule_action'}
    schedule=next(e for e in detail['events'] if e['stage']=='schedule')
    assert len(schedule['report']['checks'])==6 and schedule['report']['advisories'][0]['value']==80
    assert schedule['trip_title']=='서울 감시 시험'
    assert any(e['report'].get('action')=='notified' for e in detail['events'])


def test_failed_run_keeps_prior_results_and_does_not_leak_exception_text(world):
    w=world
    def work():
        monitoring.record('schedule',trip_id=w.trip_id,item_id=w.item.item_id,target_title=w.item.title,report={'verdict':'clear','password':'drop','reason':'api_key=private https://private.invalid/x'})
        raise RuntimeError('secret=private')
    with pytest.raises(RuntimeError):run(w,work)
    data=w.client.get('/admin/api/watch-runs').json()
    assert data['latest']['status']=='failed' and data['latest']['error_type']=='RuntimeError'
    detail=w.client.get('/admin/api/watch-runs/'+data['latest']['run_id'])
    assert len(detail.json()['events'])==1
    assert 'private' not in detail.text and 'password' not in detail.text
    # context must reset: an unrelated request cannot add an event to this run.
    monitoring.record('schedule',report={'verdict':'clear'})
    assert len(w.client.get('/admin/api/watch-runs/'+data['latest']['run_id']).json()['events'])==1


def test_safety_first_simulation_keeps_all_six_actual_input_checks(world,monkeypatch):
    from app.domains.travel_ops.components.watch import simulation
    from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
    from app.domains.travel_ops.ports.data_sources import simulation_hook
    w=world
    monkeypatch.setattr(simulation,'get_connection',w.connect)
    # ★`[2026-10-14]` 점검은 시험 입력을 연결 자리(simulation_hook)에서 꺼낸다 — 조립(composition) 없이 돌면 비어 있어
    #   시험 입력 경로를 안 타고 simulation_full 기록이 안 남았다(단독 실행에서 실패 · 앞 시험이 조립하면 통과하던 순서 의존).
    #   test_watch_simulation.py 와 같은 방식으로 이 시험 안에서만 채운다(monkeypatch 가 끝나면 되돌린다).
    monkeypatch.setattr(simulation_hook,'_provider',simulation)
    simulation.configure(w.conn,w.tenant,w.trip_id,actor='test',expected_revision=0,expected_version=1,
                         item_id=w.item.item_id,categories=list(simulation.CATEGORIES),duration_minutes=15,reason='6종 회차 기록 시험')
    checker=DisruptionCheck(SimpleNamespace())
    sweep=SafetySweep(store=w.store,check=checker.check_safety,connection_factory=w.connect,clock=lambda:w.now)
    run(w,lambda:sweep.tick().counts())
    identity=w.client.get('/admin/api/watch-runs').json()['latest']['run_id']
    events=w.client.get('/admin/api/watch-runs/'+identity).json()['events']
    full=next(e for e in events if e['stage']=='simulation_full')
    assert len(full['report']['checks'])==6
    assert all(c.get('mode')=='simulation' for c in full['report']['checks'])
    assert any(e['stage']=='safety' and len(e['report']['checks'])==2 for e in events)


def test_history_cursor_filters_detail_pages_and_tenant_isolation(world,monkeypatch):
    w=world
    for i in range(3):
        run(w,lambda i=i: (monitoring.record('schedule',trip_id=w.trip_id,report={'verdict':'fatal' if i==1 else 'clear'}) or {'checked':1,'fatal':int(i==1)}),forced=i==2)
    page=w.client.get('/admin/api/watch-runs',params={'limit':1}).json()
    seen={page['runs'][0]['run_id']}
    while page['next_cursor']:
        page=w.client.get('/admin/api/watch-runs',params={'limit':1,'cursor':page['next_cursor']}).json()
        assert page['runs'][0]['run_id'] not in seen
        seen.add(page['runs'][0]['run_id'])
    assert len(seen)==3
    attention=w.client.get('/admin/api/watch-runs',params={'status':'attention','trip_id':str(w.trip_id)}).json()
    assert len(attention['runs'])==1
    identity=attention['runs'][0]['run_id']
    assert len(w.client.get('/admin/api/watch-runs/'+identity,params={'limit':1}).json()['events'])==1
    monkeypatch.setattr(admin_watch_api,'get_settings',lambda:SimpleNamespace(tenant_id='another_tenant'))
    assert w.client.get('/admin/api/watch-runs').json()['runs']==[]
    assert w.client.get('/admin/api/watch-runs/'+identity).status_code==404


def test_stale_running_run_and_empty_results_are_not_success(world):
    w=world
    assert w.client.get('/admin/api/watch-runs').json()['freshness']=='not_recorded'
    identity=uuid4()
    w.conn.execute("INSERT INTO travel_watch_runs(tenant_id,run_id,forced,interval_seconds,status,started_at) VALUES(%s,%s,false,180,'running',now()-interval '10 minutes')",(w.tenant,identity))
    data=w.client.get('/admin/api/watch-runs').json()
    assert data['freshness']=='delayed' and data['latest']['finished_at'] is None
    run(w,forced=True)
    after=w.client.get('/admin/api/watch-runs').json()
    assert after['latest']['forced'] is True
    assert after['latest_scheduled']['run_id']==str(identity) and after['freshness']=='delayed'


@pytest.mark.parametrize('params',[{'cursor':'bad!'},{'since':'2026-10-10T00:00:00+09:00','until':'2026-10-09T00:00:00+09:00'},{'limit':51},{'status':'invented'},{'since':'2026-10-09T00:00:00'}])
def test_invalid_filters_are_refused(world,params):
    assert world.client.get('/admin/api/watch-runs',params=params).status_code==422


def test_auth_and_revoked_scope_and_customer_app_separation(world,monkeypatch):
    w=world
    w.client.cookies.clear()
    assert w.client.get('/admin/api/watch-runs').status_code==401
    op=auth.Operator('watch-operator',frozenset({'ops:introspect'}))
    w.client.cookies.set(auth.COOKIE,auth.issue(op))
    monkeypatch.setattr(auth,'operators',lambda:{op.id:('',frozenset())})
    assert w.client.get('/admin/api/watch-runs').status_code==403
    from app.presentation.api.app import create_app
    app=create_app(classifier=lambda _: {'intent':'other','issue_code':'other','sentiment':'neutral'})
    assert not any(getattr(r,'path','').startswith('/admin/api/watch-runs') for r in app.routes)


def test_detail_paging_and_trip_deletion_remove_item_logs(world):
    w=world
    def work():
        for _ in range(3):monitoring.record('schedule',trip_id=w.trip_id,report={'verdict':'clear'})
        return {'checked':3}
    run(w,work)
    identity=w.client.get('/admin/api/watch-runs').json()['latest']['run_id']
    first=w.client.get('/admin/api/watch-runs/'+identity,params={'limit':2}).json()
    assert len(first['events'])==2 and first['next_after']
    last=w.client.get('/admin/api/watch-runs/'+identity,params={'limit':2,'after':first['next_after']}).json()
    assert len(last['events'])==1 and last['next_after'] is None
    # Migration owns the FK; other trip children may reject a direct DELETE, so verify the cascading FK explicitly.
    row=w.conn.execute("SELECT confdeltype FROM pg_constraint WHERE conrelid='travel_watch_checks'::regclass AND confrelid='trips'::regclass").fetchone()
    assert row[0]=='c'
