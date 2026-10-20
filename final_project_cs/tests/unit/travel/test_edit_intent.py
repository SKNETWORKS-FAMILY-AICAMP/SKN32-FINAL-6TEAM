"""체류 끝·뒤 일정·검색 기준을 기존 수정 경로로 전달하는 회귀 시험."""
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import edit_intent
from app.domains.travel_ops.components.conversation.chat_edit import EditRefused, ops_for
from app.domains.travel_ops.components.conversation.decision_unit import Decision, decide, stops_of
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange, plan_fresh_alternate
from app.domains.travel_ops.components.intake import direct_schedule, hours

KST = ZoneInfo('Asia/Seoul')
NOW = datetime(2030, 1, 1, 11, 0, tzinfo=KST)


def spec(boundary='end', **kw):
    return {'boundary':boundary, 'scope':'item', 'time':'17:00', 'duration_minutes':0,
            'cascade':True, 'continue_previous':False, 'evidence':'5시까지', **kw}


def place(name, lat=37.57, lon=126.98, kind='dining', opening=('00:00','23:59')):
    return {'place_id':uuid4(), 'name':name, 'kind':kind, 'latitude':lat, 'longitude':lon,
            'attributes':{'hours':list(opening), 'payment':['card']}}


def item(name='여행 활동', start=10, end=12, seq=1, kind='activity', **kw):
    p=place(name, kind=kind)
    return Item(item_id=uuid4(),seq=seq,kind=kind,title=name,place_id=p['place_id'],place=p,
                starts_at=NOW.replace(hour=start),ends_at=NOW.replace(hour=end),**kw)


def decision(target, temporal=None, **raw):
    return Decision(action='change_time',item=target,change=None,fact='none',minutes=None,question='',
                    raw={'time_edit':temporal or spec(),**raw})


@pytest.mark.parametrize('name', ['여행 활동','전시 관람','강동선사문화축제'])
def test_end_changes_only_end_and_requests_existing_reflow(name):
    stop=item(name)
    ops,_=ops_for(decision(stop),items=[stop],now=NOW)
    assert len(ops)==1 and ops[0].item_id==stop.item_id
    assert ops[0].starts_at is None and ops[0].ends_at=='17:00' and ops[0].reflow
    assert stop.starts_at.hour==10 and stop.ends_at.hour==12


def test_ambiguous_end_asks_time_while_preserving_target():
    stop=item()
    with pytest.raises(EditRefused) as raised:
        ops_for(decision(stop,spec(time='')),items=[stop],now=NOW)
    assert raised.value.code=='need_end_time' and stop.title in raised.value.message


def test_duration_changes_stay_not_start():
    stop=item()
    ops,_=ops_for(decision(stop,spec('duration',time='',duration_minutes=240)),items=[stop],now=NOW)
    assert ops[0].starts_at is None and ops[0].ends_at=='14:00'


@pytest.mark.parametrize('protect', [{'locked':True},{'booking_id':uuid4()}])
def test_protected_anchor_is_not_rewritten(protect):
    stop=item(**protect)
    with pytest.raises(EditRefused,match='예약·고정'):
        ops_for(decision(stop),items=[stop],now=NOW)


def test_following_reflow_uses_anchor_without_moving_it_to_new_start():
    stop=item()
    d=decision(None,spec('reflow',scope='following',time=''),anchor_item='i1')
    ops,_=ops_for(d,items=[stop,item('식사',start=12,end=13,seq=2,kind='dining')],now=NOW)
    assert ops[0].item_id==stop.item_id and ops[0].ends_at=='12:00' and ops[0].starts_at is None


@pytest.mark.parametrize('age,version,anchor,expected', [
    (10,4,'i1',True), (600,4,'i1',False), (10,5,'i1',False), (10,4,'i2',False)])
def test_previous_goal_requires_version_ttl_and_same_explicit_anchor(age,version,anchor,expected):
    stop=item()
    goal=edit_intent.pending_goal(decision(stop),version=4,now=NOW-timedelta(seconds=age))
    turns=[{'role':'assistant','reply':{'edit_goal':goal}}]
    d=decision(None,spec('reflow',time='',scope='following',continue_previous=True),anchor_item=anchor)
    got=edit_intent.resume(d,items=[stop,item('다른 활동',start=18,end=19,seq=2)],turns=turns,
                           version=version,now=NOW,ttl_seconds=300)
    assert bool(got.raw.get('resumed_edit_goal')) is expected
    if expected:
        assert got.item.item_id==stop.item_id and got.raw['time_edit']['time']=='17:00'
    else:
        with pytest.raises(EditRefused) as raised:
            ops_for(got,items=[stop],now=NOW)
        assert raised.value.code=='need_time_goal'


def test_read_focus_cannot_authorize_previous_write_goal():
    stop=item()
    got=edit_intent.resume(decision(None,spec('reflow',continue_previous=True)),items=[stop],
            turns=[{'role':'assistant','reply':{'focus':{'item_id':str(stop.item_id),'version':4,'at':NOW.isoformat()}}}],
            version=4,now=NOW,ttl_seconds=300)
    assert got.raw['stale_edit_goal']


@pytest.mark.parametrize('value', ['25:00','17:99','17','invented'])
def test_malformed_clock_is_rejected(value):
    with pytest.raises(ValueError):
        edit_intent.validate({'time_edit':spec(time=value)},'5시까지',{'none','i1'})


def test_spatial_evidence_and_anchor_must_come_from_request_and_trip():
    with pytest.raises(ValueError):
        edit_intent.validate({'place_search':{'relation':'near','anchor_item':'i9','place_text':'','evidence':'근처'}},'근처',{'none','i1'})
    with pytest.raises(ValueError):
        edit_intent.validate({'place_search':{'relation':'near','anchor_item':'i1','place_text':'없는동네','evidence':'근처'}},'근처',{'none','i1'})


def test_lunch_target_and_search_anchor_survive_decision_separately():
    festival=item('산책 행사',start=10,end=12)
    lunch=item('원래 점심',start=13,end=14,seq=2,kind='dining')
    raw={'action':'apply_change','target_item':'i2','target_change':'none','fact':'none','minutes':0,'choices':[],
         'change_scope':'place','destination_text':'','condition_text':'',
         'place_search':{'relation':'near','anchor_item':'i1','place_text':'','evidence':'행사 근처'}}
    model=SimpleNamespace(structured=lambda *a,**k:dict(raw))
    got=decide(model,stops=stops_of([festival,lunch]),changes=[],history=[],selected_item_id=None,
               message='점심을 산책 행사 근처로 바꿔줘',now=NOW)
    assert got.action=='apply_change' and got.item.item_id==lunch.item_id
    assert got.raw['place_search']['anchor_item']=='i1'


def _near(target, anchor='none', place_text='', action='apply_change'):
    return Decision(action=action,item=target,change=None,fact='none',minutes=None,question='',
                    raw={'action':action,'place_search':{'relation':'near','anchor_item':anchor,'place_text':place_text,
                                                          'evidence':'다른 데로'}})


@pytest.mark.parametrize('anchor,place_text', [('i1',''),('none','북촌한옥마을'),('none','')])
@pytest.mark.parametrize('action', ['apply_change','propose_alternatives'])
def test_activity_near_itself_is_a_plain_change_not_a_meal_question(anchor,place_text,action):
    """☆x600 서버 2026-10-20: 「북촌한옥마을 다른 데로 바꿔 줘」가 「어느 식사 일정을 바꿀지 알려 주세요」로 끝났다 — 근처 기준이 그 활동 자신이면 보통 바꾸기다."""
    from app.domains.travel_ops.components.conversation.decision_unit import settle_near_search
    bukchon=item('북촌한옥마을',start=10,end=12)
    lunch=item('점심',start=13,end=14,seq=2,kind='dining')
    got=settle_near_search(_near(bukchon,anchor,place_text,action),[bukchon,lunch])
    assert got.action==action and got.item is bukchon
    assert got.raw['place_search']['relation']=='none' and got.raw['near_dropped']['reason']=='anchor_is_target'


def test_meal_near_another_item_keeps_the_near_search():
    from app.domains.travel_ops.components.conversation.decision_unit import settle_near_search
    festival=item('산책 행사',start=10,end=12)
    lunch=item('원래 점심',start=13,end=14,seq=2,kind='dining')
    original=_near(lunch,'i1')
    assert settle_near_search(original,[festival,lunch]) is original


def test_activity_near_another_item_asks_instead_of_dropping_the_condition():
    from app.domains.travel_ops.components.conversation.decision_unit import settle_near_search
    bukchon=item('북촌한옥마을',start=10,end=12)
    insadong=item('인사동',start=14,end=16,seq=2)
    got=settle_near_search(_near(bukchon,'i2'),[bukchon,insadong])
    assert got.action=='clarify' and got.item is None
    assert [c['item'] for c in got.choices]==[bukchon] and got.choices[0]['action']=='apply_change'
    assert '인사동 근처' in got.question and got.raw['near_guard']['reason']=='non_dining_near_other'


def test_anchor_without_target_asks_which_instead_of_meal_only_question():
    from app.domains.travel_ops.components.conversation.decision_unit import settle_near_search
    from app.domains.travel_ops.components.conversation.trip_messages import _clarify_with_choices
    bukchon=item('북촌한옥마을',start=10,end=12)
    lunch=item('점심',start=13,end=14,seq=2,kind='dining')
    got=settle_near_search(_near(None,'i1'),[bukchon,lunch])
    assert got.action=='clarify' and got.raw['near_guard']['reason']=='anchor_without_target'
    reply=_clarify_with_choices(got,[bukchon,lunch],lead=got.question)
    assert '어느 식사 일정' not in reply['text'] and reply['text'].startswith('어느 일정을 바꿀지')
    assert reply['choices'][0]['message'].endswith('북촌한옥마을 다른 곳으로 바꿔 줘')
    assert reply['choices'][0]['item_id']==str(bukchon.item_id)


def test_restaurants_and_relaxed_options_remain_near_requested_origin():
    old=place('옛 점심',37.57,126.98)
    meal=replace(item('옛 점심',start=13,end=14,kind='dining'),place=old,place_id=old['place_id'])
    origin=place('요청 기준',37.57,127.10,kind='activity')
    wrong=place('옛 점심 근처',37.5705,126.9805)
    right=place('요청 기준 근처',37.5705,127.1005)
    plan=plan_fresh_alternate(trip={'constraints':{}},trip_version=1,base_version=1,items=[meal],
            places=[old,wrong,right],item_id=meal.item_id,message='다른 활동 근처로 점심 변경',request_id='test',search_origin=origin)
    assert not isinstance(plan,NoChange),plan
    assert plan.summary['to']=='요청 기준 근처'
    assert '옛 점심 근처' not in plan.notice['other_options']


def row(index,start,end,**kw):
    return {'source_id':'source','index':index,'date':'2030-01-01','start':start,'end':end,'kind':'activity',
            'title':f'일정{index}','locked':False,'booked':False,'booking_no':None,
            'place':place(f'장소{index}',37.57,126.98+index*.001),**kw}


def walk(a,b,arrive,not_before=None):
    return {'starts_at':arrive-timedelta(minutes=11),'ends_at':arrive,'eta_min':11,
            'route':{'planned':'walk','options':[{'id':'walk','eta_min':11,'walk_m':880,'label':'도보'}]}},None


def fit(rows,monkeypatch):
    monkeypatch.setattr(hours,'facts_for',lambda *a:hours.HoursFacts(True,{'hours':['00:00','23:59']}))
    return direct_schedule.fit(None,tenant_id='synthetic',rows=rows,touched={('source',0)},fixed_times={('source',0)},
                               forward_only=True,engine=walk,use_engine=False)


def test_reflow_keeps_end_and_moves_only_following_same_day(monkeypatch):
    rows=[row(0,'10:00','17:00'),row(1,'12:10','13:10'),row(2,'14:00','15:30'),row(3,'10:00','11:00',date='2030-01-02')]
    changes=fit(rows,monkeypatch)
    got={c['field']:c['value'] for c in changes}
    assert got['items[1].starts_at']=='17:15' and got['items[1].ends_at']=='18:15'
    assert got['items[2].starts_at']=='18:30' and got['items[2].ends_at']=='20:00'
    assert not any(c['field'].startswith(('items[0]','items[3]')) for c in changes)
    assert rows[0]['end']=='17:00' and rows[1]['start']=='12:10'


@pytest.mark.parametrize('protection',[{'locked':True},{'booked':True},{'booking_no':'RES1'}])
def test_reflow_cannot_pull_anchor_back_for_protected_following_stop(monkeypatch,protection):
    with pytest.raises(direct_schedule.ScheduleConflict,match='指定|지정'):
        fit([row(0,'10:00','17:00'),row(1,'12:10','13:10',**protection)],monkeypatch)


def test_reflow_cannot_pull_anchor_back_at_midnight(monkeypatch):
    with pytest.raises(direct_schedule.ScheduleConflict,match='하루'):
        fit([row(0,'22:00','23:00'),row(1,'23:05','23:59')],monkeypatch)


def test_new_semantic_objects_are_required_for_each_model_call():
    from app.domains.travel_ops.components.conversation.decision_unit import _schema
    from app.infrastructure.llm_failover import strict_schema
    schema = _schema(stops_of([item()]), [])
    assert {"time_edit", "place_search"} <= set(schema["required"])
    strict = strict_schema(schema)
    for field in ("time_edit", "place_search"):
        assert strict["properties"][field]["type"] == "object"
        assert "anyOf" not in strict["properties"][field]


@pytest.mark.parametrize("quote,clock", [("저녁까지", "17:00"), ("오후 5시까지", "18:00"), ("17:30까지", "17:00")])
def test_clock_must_be_supported_by_numeric_quote(quote, clock):
    with pytest.raises(ValueError):
        edit_intent.validate({"time_edit":spec(time=clock,evidence=quote)},quote,{"none","i1"})


def test_explicit_start_uses_new_time_instead_of_conflicting_legacy_anchor():
    stop=item(start=12,end=14)
    got=decision(stop,spec("start",time="16:00",cascade=False),anchor_time="15:00",anchor_kind="time")
    ops,_=ops_for(got,items=[stop],now=NOW)
    assert ops[0].starts_at=="16:00" and ops[0].ends_at=="18:00"


def test_explicit_other_day_is_not_ignored_by_end_change():
    stop=item()
    later=item("다음 날 활동",start=12,end=14,seq=2)
    later=replace(later,starts_at=later.starts_at+timedelta(days=1),ends_at=later.ends_at+timedelta(days=1))
    got=decision(stop,at_day="d2")
    with pytest.raises(EditRefused) as caught:
        ops_for(got,items=[stop,later],now=NOW)
    assert caught.value.code=="combined_date_boundary"
    assert edit_intent.pending_goal(got,version=1,now=NOW) is None


def test_following_shift_excludes_anchor_and_next_day():
    anchor=item(start=12,end=14)
    lunch=item("점심",start=14,end=15,seq=2,kind="dining")
    later=item("다음 날",start=14,end=15,seq=3)
    later=replace(later,starts_at=later.starts_at+timedelta(days=1),ends_at=later.ends_at+timedelta(days=1))
    got=replace(decision(None,spec("shift",scope="following",time=""),anchor_item="i1"),minutes=30)
    ops,_=ops_for(got,items=[anchor,lunch,later],now=NOW)
    assert len(ops)==1 and ops[0].item_id==lunch.item_id
    assert ops[0].starts_at=="14:30" and ops[0].ends_at=="15:30" and ops[0].reflow


@pytest.mark.parametrize("protect", [{"locked":True},{"booking_id":uuid4()}])
def test_following_shift_is_atomic_when_one_target_is_protected(protect):
    anchor=item(start=12,end=14)
    lunch=item("점심",start=14,end=15,seq=2,kind="dining")
    fixed=item("보호 활동",start=16,end=17,seq=3,**protect)
    got=replace(decision(None,spec("shift",scope="following",time=""),anchor_item="i1"),minutes=30)
    with pytest.raises(EditRefused) as caught:
        ops_for(got,items=[anchor,lunch,fixed],now=NOW)
    assert caught.value.code=="locked_item" and lunch.starts_at.hour==14


@pytest.mark.parametrize("boundary,scope", [("end","following"),("start","following"),("duration","following"),("reflow","item")])
def test_temporal_boundary_and_scope_cannot_rewrite_the_wrong_anchor(boundary,scope):
    with pytest.raises(ValueError,match="scope"):
        edit_intent.validate({"time_edit":spec(boundary,scope=scope)},"5시까지",{"none","i1"})


def test_explicit_now_keeps_existing_server_clock_behavior():
    stop=item(start=12,end=14)
    ops,_=ops_for(decision(stop,spec("start",time="",cascade=False),anchor_kind="now"),items=[stop],now=NOW)
    assert ops[0].starts_at=="11:00" and ops[0].ends_at=="13:00"


def test_explicit_start_in_the_past_is_refused_while_end_would_still_be_future():
    stop=item(start=12,end=14)
    with pytest.raises(EditRefused) as caught:
        ops_for(decision(stop,spec("start",time="10:30",cascade=False)),items=[stop],now=NOW)
    assert caught.value.code=="time_in_past" and stop.starts_at.hour==12


@pytest.mark.parametrize("quote,clock", [("오전 5시까지", "17:00"), ("오후 5시까지", "05:00")])
def test_explicit_meridian_cannot_be_reversed_by_the_model(quote,clock):
    with pytest.raises(ValueError,match="meridian"):
        edit_intent.validate({"time_edit":spec(time=clock,evidence=quote)},quote,{"none","i1"})
