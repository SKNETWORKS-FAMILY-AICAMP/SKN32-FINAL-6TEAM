"""Generation-contract regression, not a model substitute."""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
import jsonschema
import pytest
from app.domains.travel_ops.components.conversation import decision_unit as du
from app.domains.travel_ops.components.conversation import edit_intent
from app.domains.travel_ops.components.conversation.chat_edit import ops_for, EditRefused
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST=ZoneInfo('Asia/Seoul')
NOW=datetime(2030,1,1,9,tzinfo=KST)
MESSAGE='북촌한옥마을을 한 시간 당기고 머무는 시간은 유지해줘'

def items():
    names=['북촌한옥마을','인사동','N서울타워','국립중앙박물관']
    return [Item(item_id=uuid4(),place_id=None,seq=n+1,kind='activity',title=name,starts_at=datetime(2030,1,2+(n==3),[10,12,15,10][n],tzinfo=KST),ends_at=datetime(2030,1,2+(n==3),[11,13,16,11][n],30 if n==2 else 0,tzinfo=KST)) for n,name in enumerate(names)]

def raw(message=MESSAGE, boundary='shift', scope='item', target='i1', anchor='none', kind='none', clock='', relation='at', day='none', query=None, minutes=-60):
    r=dict(action='change_time',target_item=target,target_change='none',fact='none',minutes=minutes,choices=[],reads=[],social='',general_requests=[],destination_text='',condition_text='',anchor_kind=kind,anchor_item=anchor,anchor_time=clock,at_day=day,relation=relation,steps=1,time_edit=dict(boundary=boundary,scope=scope,time='',duration_minutes=0,cascade=False,continue_previous=False,evidence=message),place_search=dict(relation='none',anchor_item='none',place_text='',evidence=''),
           place_setting=dict(want='any',evidence=''))  # v9: QA place_setting is a required generation field; neutral value per edit_intent.SYSTEM
    if query is not None:r['query']=query
    return r

def schema(message=MESSAGE):return du._schema(du.stops_of(items()),[],message=message)

@pytest.mark.parametrize('bad',[
    {'boundary':'start','time':'10:00'},
    {'boundary':'start','time':''},
    {'boundary':'end','time':'14:00'},
    {'boundary':'shift','time':'10:00'},
    {'boundary':'duration','duration_minutes':60},
])
def test_generation_cannot_combine_relative_delta_and_absolute_boundary(bad):
    r=raw();r['time_edit'].update(bad)
    assert not jsonschema.Draft202012Validator(schema()).is_valid(r)

def test_generation_relative_item_has_no_absolute_anchor_clock():
    r=raw(kind='time',clock='10:00')
    assert not jsonschema.Draft202012Validator(schema()).is_valid(r)

def test_generation_empty_start_without_relative_delta_can_still_ask_for_missing_time():
    r=raw(boundary='start',minutes=0)
    jsonschema.validate(r,schema())

def test_quoted_relative_item_preserves_duration():
    source=items();r=raw();jsonschema.validate(r,schema())
    edit_intent.validate(r,MESSAGE,{'none','i1','i2','i3','i4'})
    d=du.Decision('change_time',source[0],None,'none',-60,'',raw=r)
    ops,_=ops_for(d,items=source,now=NOW,message=MESSAGE)
    assert [(o.item_id,o.date,o.starts_at,o.ends_at) for o in ops]==[(source[0].item_id,'2030-01-02','09:00','10:00')]

@pytest.mark.parametrize('case,message,kind,anchor,clock,relation,expected,delta',[
 ('T03','1월 2일 오전 11시 이후 일정들을 전부 한 시간 미뤄줘','time','none','11:00','after',[1,2],60),
 ('T04','1월 2일 오후 2시 이전 일정들을 전부 한 시간 당겨줘','time','none','14:00','before',[0,1],-60),
 ('T08','인사동 이전 일정만 한 시간 당겨줘. 인사동은 그대로야','item','i2','','before',[0],-60),
 ('T12','1월 2일 일정만 한 시간 미뤄줘. 다음 날은 바꾸지 마','none','none','','at',[0,1,2],60),
])
def test_relative_range_generation_and_exact_targets(case,message,kind,anchor,clock,relation,expected,delta):
    source=items();q=dict(day='all' if case=='T08' else 'd1',period='all',kind='all',position='all')
    r=raw(message,scope='range',target='none',kind=kind,anchor=anchor,clock=clock,relation=relation,day='none',query=q,minutes=delta)
    jsonschema.validate(r,du._schema(du.stops_of(source),[],message=message))
    edit_intent.validate(r,message,{'none','i1','i2','i3','i4'})
    d=du.Decision('change_time',None,None,'none',delta,'',raw=r,query=q)
    ops,_=ops_for(d,items=source,now=NOW,message=message)
    assert [o.item_id for o in ops]==[source[n].item_id for n in expected]
    for o in ops:
        original=next(i for i in source if i.item_id==o.item_id)
        begin=datetime.fromisoformat(o.date+'T'+o.starts_at).replace(tzinfo=KST)
        end=datetime.fromisoformat(o.date+'T'+o.ends_at).replace(tzinfo=KST)
        assert (begin-original.starts_at).total_seconds()==delta*60
        assert end-begin==original.ends_at-original.starts_at
        assert o.date=='2030-01-02'

@pytest.mark.parametrize('protection',['locked','booking_id'])
def test_relative_range_keeps_protected_target_and_moves_the_rest(protection):
    # contract_correction 2026-10-26 integ-rm9 (Codex): was `locked_item` all-or-nothing refusal (L05).
    # The range policy is now one place (`chat_edit.shift_range`): a protected stop stays and is shown, the rest move.
    source=items();setattr(source[1],protection,True if protection=='locked' else uuid4())
    before={i.item_id:(i.starts_at,i.ends_at) for i in source}
    q=dict(day='d1',period='all',kind='all',position='all');r=raw(scope='range',target='none',query=q,minutes=60)
    ops,what=ops_for(du.Decision('change_time',None,None,'none',60,'',raw=r,query=q),items=source,now=NOW)
    assert [o.item_id for o in ops]==[source[0].item_id,source[2].item_id] and what=='일정 2개 시각 옮기기'
    assert [(o.starts_at,o.ends_at) for o in ops]==[('11:00','12:00'),('16:00','17:30')]
    assert not any(o.reflow for o in ops)
    label='고정' if protection=='locked' else '예약'
    assert [k for o in ops for k in o.kept]==[f'1월 2일(수) 12:00 인사동({label})']
    assert {i.item_id:(i.starts_at,i.ends_at) for i in source}==before   # ops only, items untouched

@pytest.mark.parametrize('minutes,code',[(9*60,'crosses_midnight'),(-25*60,'crosses_midnight')])
def test_relative_range_still_refuses_all_when_one_moved_stop_crosses_midnight(minutes,code):
    source=items();q=dict(day='d1',period='all',kind='all',position='all');r=raw(scope='range',target='none',query=q,minutes=minutes)
    with pytest.raises(EditRefused) as e:
        ops_for(du.Decision('change_time',None,None,'none',minutes,'',raw=r,query=q),items=source,now=NOW)
    assert e.value.code==code

def test_relative_range_before_anchor_excludes_anchor_from_targets_and_kept():
    source=items();q=dict(day='d1',period='all',kind='all',position='all')
    r=raw('인사동 이전 일정만 한 시간 당겨줘. 인사동은 그대로야',scope='range',target='none',kind='item',anchor='i2',relation='before',query=q,minutes=-60)
    ops,_=ops_for(du.Decision('change_time',None,None,'none',-60,'',raw=r,query=q),items=source,now=NOW)
    assert [o.item_id for o in ops]==[source[0].item_id] and not [k for o in ops for k in o.kept]

def test_scope_range_and_following_query_path_share_one_policy_on_a_started_trip():
    # 「일정 전부다 1시간씩 미뤄줘」 on a trip in progress: ended stop dropped, started stop kept, the rest move — same on both paths.
    source=items();now=datetime(2030,1,2,12,30,tzinfo=KST)
    q=dict(day='all',period='all',kind='all',position='all')
    rng=raw('일정 전부다 1시간씩 미뤄줘',scope='range',target='none',query=q,minutes=60)
    fol=raw('일정 전부다 1시간씩 미뤄줘',scope='following',target='none',query=q,minutes=60)
    got=[ops_for(du.Decision('change_time',None,None,'none',60,'',raw=r,query=q),items=source,now=now,message='일정 전부다 1시간씩 미뤄줘') for r in (rng,fol)]
    assert got[0]==got[1]
    ops,_=got[0]
    assert [o.item_id for o in ops]==[source[2].item_id,source[3].item_id]
    assert [k for o in ops for k in o.kept]==['1월 2일(수) 12:00 인사동(이미 시작)']

@pytest.mark.parametrize('wrong', ['day','item','period','position'])
def test_generated_range_cannot_invent_unquoted_date_or_visit_or_extra_filter(wrong):
    message='1월 2일 오전 11시 이후 일정들을 전부 한 시간 미뤄줘'
    q=dict(day='d1',period='all',kind='all',position='all')
    r=raw(message,scope='range',target='none',kind='time',clock='11:00',relation='after',query=q,minutes=60)
    if wrong=='day':q['day']='today'
    elif wrong=='item':r.update(anchor_kind='item',anchor_item='i2',anchor_time='')
    elif wrong=='period':q['period']='morning'
    else:q['position']='last'
    assert not jsonschema.Draft202012Validator(schema(message)).is_valid(r)

def test_relative_range_refuses_all_when_one_moved_stop_would_start_in_the_past():
    source=items();now=datetime(2030,1,2,10,30,tzinfo=KST)   # 북촌 10:00 already started (kept); 인사동 12:00 -2h → 10:00 < now
    q=dict(day='d1',period='all',kind='all',position='all');r=raw(scope='range',target='none',query=q,minutes=-120)
    with pytest.raises(EditRefused) as e:
        ops_for(du.Decision('change_time',None,None,'none',-120,'',raw=r,query=q),items=source,now=now)
    assert e.value.code=='time_in_past'

def test_relative_range_with_only_protected_stops_answers_range_kept_with_the_list():
    source=items()
    for stop in source[:3]:
        stop.locked=True
    q=dict(day='d1',period='all',kind='all',position='all');r=raw(scope='range',target='none',query=q,minutes=60)
    with pytest.raises(EditRefused) as e:
        ops_for(du.Decision('change_time',None,None,'none',60,'',raw=r,query=q),items=source,now=NOW)
    assert e.value.code=='range_kept'
    assert '· 그대로 둔 일정: 1월 2일(수) 10:00 북촌한옥마을(고정)' in e.value.message and 'N서울타워(고정)' in e.value.message

def test_relative_range_skips_lodging_and_mobility_without_listing_them():
    from dataclasses import replace as _replace
    source=items();source[1]=_replace(source[1],kind='lodging')
    q=dict(day='d1',period='all',kind='all',position='all');r=raw(scope='range',target='none',query=q,minutes=60)
    ops,_=ops_for(du.Decision('change_time',None,None,'none',60,'',raw=r,query=q),items=source,now=NOW)
    assert source[1].item_id not in [o.item_id for o in ops] and not [k for o in ops for k in o.kept]
    assert [o.item_id for o in ops]==[source[0].item_id,source[2].item_id]
