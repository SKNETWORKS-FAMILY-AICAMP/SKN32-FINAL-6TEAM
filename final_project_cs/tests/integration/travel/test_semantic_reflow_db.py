"""실제 격리 DB에서 수정·CAS·원자적 거절을 검증한다. 파이프라인 목업 없음."""
from datetime import datetime,timedelta
import json,os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import get_connection,database_dsn
from app.domains.travel_ops.components.conversation import chat_edit
from app.domains.travel_ops.components.conversation.decision_unit import Decision
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
from app.domains.travel_ops.components.itinerary.itinerary import Item,TripStore
from app.domains.travel_ops.components.planning.replan import distance_m

KST=ZoneInfo('Asia/Seoul')
NOW=datetime(2030,1,1,11,0,tzinfo=KST)
pytestmark=pytest.mark.skipif(not os.environ.get('SEMANTIC_SYNTHETIC_DATABASE_URL'),reason='requires explicit isolated synthetic database')


@pytest.fixture(autouse=True)
def isolated_db_guard():
    """Fail before any fixture writes if a production/unspecified DB was supplied."""
    expected=os.environ.get('SEMANTIC_SYNTHETIC_DATABASE_URL')
    assert expected and database_dsn()==expected
    parts=urlsplit(expected)
    assert (parts.hostname,parts.port,parts.path,parts.username)==('127.0.0.1',15544,'/semantic_synthetic','semantic_test')
    with get_connection() as conn:
        assert conn.execute('SELECT current_database(),current_user').fetchone()==('semantic_synthetic','semantic_test')
        assert conn.execute('SELECT owner FROM semantic_test_isolation_guard').fetchone()==('semantic-contract-repair',)


def make_trip(*,ongoing=False,protected=None,closing='23:59',nearby=False):
    tenant='semantic_test_'+uuid4().hex[:12];customer=uuid4();store=TripStore(tenant)
    day=NOW if ongoing else NOW+timedelta(days=1)
    def at(hour,minute=0):return day.replace(hour=hour,minute=minute)
    with get_connection() as conn,conn.transaction():
        conn.execute('INSERT INTO tenants(tenant_id,name) VALUES(%s,%s)',(tenant,'synthetic pipeline verification'))
        conn.execute('INSERT INTO customers(customer_id,tenant_id,external_id) VALUES(%s,%s,%s)',(customer,tenant,'synthetic'))
        def place(name,kind='activity',lon=127.1000,close='23:59'):
            attrs={'hours':['08:00',close],'payment':['card'],'source':'synthetic_test'}
            pid=conn.execute('INSERT INTO places(tenant_id,name,kind,latitude,longitude,weather_sensitive,attributes) VALUES(%s,%s,%s,%s,%s,false,%s) RETURNING place_id',
                             (tenant,name,kind,37.57,lon,json.dumps(attrs))).fetchone()[0]
            return pid
        festival=place('합성 문화축제');second=place('합성 점심' if nearby else '합성 전시',kind='dining' if nearby else 'activity',lon=127.02 if nearby else 127.101,close=closing)
        third=place('합성 전망대',lon=127.102)
        detail={'booking':{'booking_no':'SYNTHETIC-ONLY'}} if protected=='booked' else {}
        items=[Item(item_id=uuid4(),seq=1,kind='activity',title='합성 문화축제',place_id=festival,starts_at=at(10),ends_at=at(12)),
               Item(item_id=uuid4(),seq=2,kind='dining' if nearby else 'activity',title='합성 점심' if nearby else '합성 전시',place_id=second,starts_at=at(14 if nearby else 12,0 if nearby else 10),ends_at=at(15 if nearby else 13,0 if nearby else 10),locked=protected=='locked',detail=detail),
               Item(item_id=uuid4(),seq=3,kind='activity',title='합성 전망대',place_id=third,starts_at=at(18 if nearby else 14),ends_at=at(19 if nearby else 15))]
        if nearby:
            place('옛 점심 근처 후보',kind='dining',lon=127.021)
            place('축제 근처 후보',kind='dining',lon=127.1005)
        trip_id,version=store.create_trip(conn,customer_id=customer,title='synthetic verification only',locale='ko',party_size=2,items=items,constraints={})
    return SimpleNamespace(tenant=tenant,customer=customer,store=store,trip_id=trip_id,version=version,now=NOW)


def latest(case):
    with get_connection() as conn:return case.store.latest(conn,case.trip_id)


def snapshot(case):
    with get_connection() as conn:
        version=conn.execute('SELECT latest_version FROM trips WHERE trip_id=%s',(case.trip_id,)).fetchone()[0]
        rows=conn.execute('SELECT version,item_id,seq,kind,title,place_id,starts_at,ends_at,locked,booking_id,replaces_item_id,detail FROM itinerary_items WHERE trip_id=%s ORDER BY version,seq',(case.trip_id,)).fetchall()
        versions=conn.execute('SELECT version,reason,cause_json FROM itinerary_versions WHERE trip_id=%s ORDER BY version',(case.trip_id,)).fetchall()
        notices=conn.execute('SELECT dedupe_key,payload_json FROM outbox WHERE tenant_id=%s ORDER BY dedupe_key',(case.tenant,)).fetchall()
    return version,rows,versions,notices


def extend(case):
    trip,items=latest(case);anchor=items[0]
    semantic={'boundary':'end','scope':'item','time':'17:00','duration_minutes':0,'cascade':True,'continue_previous':False,'evidence':'17시까지'}
    d=Decision('change_time',anchor,None,'none',None,'',raw={'time_edit':semantic})
    ops,_=chat_edit.ops_for(d,items=items,now=case.now,message='17시까지 머물고 뒤 일정도 맞춰줘')
    return chat_edit.run(store=case.store,connect=get_connection,tenant=case.tenant,customer_id=case.customer,trip_id=case.trip_id,base_version=trip['version'],ops=ops,lookups=lambda:(None,None,None),now=case.now)


def assert_reflow_saved(case,before):
    result=extend(case);trip,items=latest(case)
    assert result['changed'] and trip['version']==before[0]+1
    stops=[i for i in items if i.kind!='mobility'];anchor,following,last=stops
    assert anchor.starts_at==before[1][0][6] and anchor.ends_at.astimezone(KST).strftime('%H:%M')=='17:00'
    assert following.starts_at>=anchor.ends_at and last.starts_at>=following.ends_at
    assert following.ends_at-following.starts_at==timedelta(hours=1)
    assert last.ends_at-last.starts_at==timedelta(hours=1)
    assert len([i for i in items if i.kind=='mobility'])==2
    after=snapshot(case);assert len(after[2])==len(before[2])+1 and len(after[3])==len(before[3])+1
    assert [row for row in after[1] if row[0]<=before[0]]==before[1]
    with pytest.raises(chat_edit.EditRefused) as caught:
        chat_edit.run(store=case.store,connect=get_connection,tenant=case.tenant,customer_id=case.customer,trip_id=case.trip_id,base_version=before[0],ops=[chat_edit.EditOp('time',item_id=anchor.item_id,ends_at='18:00',reflow=True)],lookups=lambda:(None,None,None),now=case.now)
    assert caught.value.code=='stale_itinerary' and snapshot(case)==after


def test_future_end_is_fixed_and_following_times_commit_one_new_version():
    case=make_trip();before=snapshot(case);assert_reflow_saved(case,before)


def test_ongoing_stay_end_can_be_extended_without_changing_its_past_start():
    case=make_trip(ongoing=True);before=snapshot(case);assert_reflow_saved(case,before)


@pytest.mark.parametrize('protect',['locked','booked'])
def test_protected_following_stop_refuses_and_preserves_every_trip_row(protect):
    case=make_trip(protected=protect);before=snapshot(case)
    with pytest.raises(chat_edit.EditRefused) as caught:extend(case)
    assert caught.value.code=='schedule_conflict'
    assert snapshot(case)==before
    with get_connection() as conn:
        assert conn.execute('SELECT count(*) FROM trip_intakes WHERE reopen_trip_id=%s AND status=%s',(case.trip_id,'review')).fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM intake_claims c JOIN trip_intakes i USING(intake_id) WHERE i.reopen_trip_id=%s AND c.revision>1',(case.trip_id,)).fetchone()[0]==0


def test_following_closing_time_conflict_keeps_version_items_and_notices():
    case=make_trip(closing='16:30');before=snapshot(case)
    with pytest.raises(chat_edit.EditRefused) as caught:extend(case)
    assert caught.value.code in {'schedule_conflict','itinerary_infeasible'}
    assert snapshot(case)==before


def test_near_meal_commits_only_candidates_inside_requested_origin_radius():
    case=make_trip(nearby=True);trip,items=latest(case);before=snapshot(case)
    desk=TripDesk(store=case.store,connection_factory=get_connection,dining_ledger=False)
    result=desk.near_alternate(trip_id=case.trip_id,item_id=items[1].item_id,base_version=trip['version'],origin=items[0].place,message='점심을 축제 근처로 바꿔줘',request_id='synthetic-near-meal')
    assert result['status']=='adjusted',result
    trip,after=latest(case);meal=next(i for i in after if i.kind=='dining')
    assert trip['version']==before[0]+1 and meal.title=='축제 근처 후보'
    assert distance_m(meal.place,items[0].place)<=3000
    notice=result.get('notice') or {}
    assert '옛 점심 근처 후보' not in json.dumps(notice,ensure_ascii=False)


@pytest.fixture()
def synthetic_routes(monkeypatch):
    """Only the movement data source is synthetic; pipeline/review/commit remain real."""
    from app.domains.travel_ops.components.team_hooks import legs
    calls=[]
    def planner(*args,**kwargs):
        def leg(a,b,arrive,not_before=None):
            begin=arrive-timedelta(minutes=5)
            if not_before is not None and begin<not_before:
                return None,{'code':'arrive_late','source':'synthetic_movement_source'}
            calls.append((a['name'],b['name'],begin,arrive))
            return {'starts_at':begin,'ends_at':arrive,'eta_min':5,'route':{
                'planned':'walk','options':[{'id':'walk','label':'합성 도보 구간','eta_min':5,'uses':[],'source':'synthetic_movement_source'}]}},None
        return leg
    monkeypatch.setattr(legs,'_leg_planner',planner)
    return calls


def test_shift_following_recomputes_stored_moves_and_keeps_requested_delta(synthetic_routes):
    case=make_trip();extend(case)
    trip,items=latest(case);stops=[i for i in items if i.kind!='mobility']
    old_moves={i.item_id for i in items if i.kind=='mobility'}
    assert len(old_moves)==2
    before=snapshot(case);calls_before=len(synthetic_routes)
    d=Decision('change_time',None,None,'none',30,'',raw={'anchor_item':'i1','time_edit':{
        'boundary':'shift','scope':'following','time':'','duration_minutes':0,'cascade':False,'continue_previous':False,'evidence':'30분 미뤄'}})
    ops,_=chat_edit.ops_for(d,items=items,now=case.now,message='축제 뒤 일정 30분 미뤄')
    assert len(ops)==2
    result=chat_edit.run(store=case.store,connect=get_connection,tenant=case.tenant,customer_id=case.customer,trip_id=case.trip_id,base_version=trip['version'],ops=ops,lookups=lambda:(None,None,None),now=case.now)
    assert result['changed']
    meta,after=latest(case);new_stops=[i for i in after if i.kind!='mobility'];moves=[i for i in after if i.kind=='mobility']
    assert meta['version']==before[0]+1 and new_stops[0].starts_at==stops[0].starts_at and new_stops[0].ends_at==stops[0].ends_at
    for old,new in zip(stops[1:],new_stops[1:]):
        assert new.starts_at==old.starts_at+timedelta(minutes=30) and new.ends_at==old.ends_at+timedelta(minutes=30)
    assert len(moves)==2 and not old_moves.intersection(i.item_id for i in moves)
    assert len(synthetic_routes)>calls_before
    for index,move in enumerate(moves):
        assert move.starts_at>=new_stops[index].ends_at and move.ends_at<=new_stops[index+1].starts_at
        assert move.detail.get('route_def')


def test_explicit_new_start_before_now_is_refused_even_when_new_end_is_future():
    case=make_trip(ongoing=True);case.now=NOW.replace(hour=9)
    trip,items=latest(case);before=snapshot(case)
    d=Decision('change_time',items[0],None,'none',None,'',raw={'anchor_kind':'time','anchor_time':'08:30','time_edit':{
        'boundary':'start','scope':'item','time':'08:30','duration_minutes':0,'cascade':False,'continue_previous':False,'evidence':'오전 8시 30분'}})
    with pytest.raises(chat_edit.EditRefused) as caught:
        ops,_=chat_edit.ops_for(d,items=items,now=case.now,message='축제 시작을 오전 8시 30분으로 바꿔')
        chat_edit.run(store=case.store,connect=get_connection,tenant=case.tenant,customer_id=case.customer,trip_id=case.trip_id,base_version=trip['version'],ops=ops,lookups=lambda:(None,None,None),now=case.now)
    assert caught.value.code in {'time_in_past','item_in_past'}
    assert snapshot(case)==before
