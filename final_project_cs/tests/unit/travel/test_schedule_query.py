from datetime import datetime,timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du
from app.domains.travel_ops.components.conversation import schedule_query as sq

NOW = datetime.fromisoformat('2030-01-01T09:00:00+09:00')


def item(hour, *, day=0, kind='activity', locked=False, detail=None, place=True):
    start=NOW.replace(hour=hour)+timedelta(days=day)
    return SimpleNamespace(item_id=uuid4(),title=f'{day+1}일 {hour}시 {kind}',seq=hour,
                           starts_at=start,ends_at=start+timedelta(hours=1),kind=kind,
                           locked=locked,booking_id=None,detail=detail or {},place={"name":"서울 관람"} if place else None)


def answer(items, *, fact='changeability', day='all', period='afternoon', kind='all'):
    return sq.reply(fact,dict(day=day,period=period,kind=kind),items=items,now=NOW)


def test_empty_afternoon_does_not_substitute_the_morning():
    text,basis=answer([item(9)])
    assert '오후' in text and '등록된 일정이 없어요' in text
    assert basis['item_ids']==[] and '09:00' not in text


def test_scope_boundaries_use_korean_time_and_exclude_moves():
    items=[item(h) for h in (11,12,17,18)]+[item(14,kind='mobility')]
    _,basis=answer(items,fact='schedule')
    assert basis['item_ids']==[str(items[1].item_id),str(items[2].item_id)]
    # 같은 순간의 UTC 표현이어도 한국 시간 범위를 따른다.
    items[1].starts_at=items[1].starts_at.astimezone(__import__('datetime').timezone.utc)
    assert answer(items,fact='schedule')[1]['item_ids']==basis['item_ids']


@pytest.mark.parametrize('day,expected',[('all',2),('d1',1),('d2',1),('today',1),('tomorrow',1)])
def test_day_filters(day,expected):
    assert len(answer([item(13),item(13,day=1)],day=day)[1]['item_ids'])==expected


def test_booking_and_pinning_are_not_labeled_freely_changeable():
    items=[item(13),item(14,locked=True),item(15,detail={'customer_pinned':True}),
           item(16,detail={'booking':{'booking_no':'travel-test'}}),item(17,kind='lodging')]
    text,basis=answer(items)
    assert [c['state'] for c in basis['checks']]==['reviewable','confirm_first','pinned','confirm_first','unsupported']
    assert '예약 여부' in text and '아직 바꾸지는 않았어요' in text
    assert items[1].locked and items[2].detail['customer_pinned']


def test_kind_filter_and_missing_place():
    dining=item(14,kind='dining',place=False)
    _,basis=answer([item(13),dining],kind='dining')
    assert basis['item_ids']==[str(dining.item_id)] and basis['checks'][0]['state']=='missing_place'


class Model:
    def __init__(self,raw):self.raw=raw
    def structured(self,*args,**kwargs):return self.raw


def raw(**extra):
    return dict(action='answer_fact',fact='changeability',target_item='none',target_change='none',minutes=0,
                choices=[],query=dict(day='all',period='afternoon',kind='all')) | extra


def decide(value):
    return du.decide(Model(value),stops=du.stops_of([item(9),item(14)]),changes=[],history=[],
                     selected_item_id=None,message='오후 일정 중에 바꿀 수 있는 일정이 뭐가 있어?')


def test_query_survives_decision_record():
    d=decide(raw())
    assert d.item is None and d.action=='answer_fact' and d.record()['query']['period']=='afternoon'


def test_identical_read_choice_is_canonicalized_without_losing_raw_evidence():
    value=raw(choices=[dict(action='answer_fact',fact='changeability',target_item='none',target_change='none')])
    d=decide(value)
    assert d.action=='answer_fact' and d.choices==[] and d.raw['choices']==value['choices']


@pytest.mark.parametrize('extra',[
    {'query':None},{'query':{'day':'all','period':'night','kind':'all'}},
    {'query':{'day':'d99','period':'afternoon','kind':'all'}},
    {'query':{'day':[],'period':'afternoon','kind':'all'}},
    {'query':{'day':'all','period':'afternoon','kind':'all','execute':True}},
    {'target_item':'i1'},
    {'choices':None},{'choices':''},{'choices':0},
    {'choices':[{'action':'apply_change','target_item':'i1'}]},
])
def test_invalid_or_write_query_fails_closed(extra):
    with pytest.raises(du.DecisionFailed):decide(raw(**extra))


def test_an_item_fact_ignores_a_stray_list_scope_instead_of_failing():
    # ★`[2026-10-14]` 한 일정을 묻는 사실(시각)에 붙은 조회 범위는 쓰지 않는 칸이라 버린다 — 일정을 바꾸지 않는 읽기라 안전하다.
    #   전에는 해석 전체를 버렸다(학습 E4B 재생 434건 중 30건). 바꾸는 할 일에 붙은 범위는 위 시험대로 계속 막는다.
    d=decide(raw(fact='time'))
    assert d.action=='answer_fact' and d.fact=='time' and d.query is None and 'query' in d.raw['ignored_for_action']


def test_read_scope_rejects_a_valid_but_unrequested_change_target():
    change=du.Change('c1',1,'customer_request',None,'기존 변경')
    with pytest.raises(du.DecisionFailed):
        du.decide(Model(raw(target_change='c1')),stops=du.stops_of([item(14)]),changes=[change],history=[],
                  selected_item_id=None,message='오후 일정의 변경 가능 여부를 알려 주세요')


def test_empty_place_is_not_claimed_ready_for_alternative_review():
    value=item(14)
    value.place={}
    _,basis=answer([value])
    assert basis['checks'][0]['state']=='missing_place'


@pytest.mark.parametrize("position,index", [("first", 0), ("last", 1)])
def test_first_or_last_is_applied_after_day_and_period_filter(position,index):
    items=[item(9),item(13,day=1),item(17,day=1),item(19,day=1),item(14,day=2)]
    query=dict(day="d2",period="afternoon",kind="all",position=position)
    text,basis=sq.reply("schedule",query,items=list(reversed(items)),now=NOW)
    expected=items[1:3][index]
    assert basis["item_ids"] == [str(expected.item_id)]
    assert expected.title in text and "일정 1개" in text
    assert all(i.title not in text for i in items if i.item_id != expected.item_id)


def test_position_schema_and_validation_reject_unknown_values():
    stops=du.stops_of([item(9),item(14)])
    assert "position" in sq.query_schema(stops)["required"]
    assert sq.valid_query(dict(day="all",period="all",kind="all",position="last"),stops)
    assert not sq.valid_query(dict(day="all",period="all",kind="all",position="random"),stops)


@pytest.mark.parametrize("position", ["first", "last"])
def test_single_position_query_uses_scope_instead_of_redundant_item_hint(position):
    value=raw(fact="schedule",target_item="i2",query=dict(day="d1",period="all",kind="all",position=position),
              choices=[dict(action="answer_fact",fact="schedule",target_item="i2",target_change="none")])
    d=decide(value)
    assert d.item is None and not d.choices and d.query["position"] == position
    assert d.raw["target_item"] == "i2"


def test_first_last_scope_does_not_canonicalize_a_write_or_other_trip_hint():
    base=raw(fact="schedule",query=dict(day="d1",period="all",kind="all",position="last"))
    for extra in [dict(target_item="i999"),
                  dict(choices=[dict(action="apply_change",fact="schedule",target_item="i2",target_change="none")])]:
        with pytest.raises(du.DecisionFailed):decide(base|extra)
    assert_scoped_change_is_asked_back(decide(base|dict(action="apply_change")))


def assert_scoped_change_is_asked_back(d, fact='schedule'):
    """`[2026-10-15]` 바꾸기(`apply_change`)에 조회 범위가 붙으면 예전엔 해석 전체가 실패했다(「어제 일정 바꿔줘」가 「해석하지 못했어요」). 이제 **되묻는다** —
    여전히 아무것도 바꾸지 않고(바꾸는 할 일로 남지 않는다) 읽기로 답하지도 않는다."""
    assert d.action == "clarify" and d.item is None and d.change is None and d.query is None and d.fact == "none"
    assert d.raw["scoped_change"] == {"action": "apply_change", "fact": fact} and "통째로 바꾸지는 못해요" in d.question


def test_a_change_with_a_list_scope_is_asked_back_and_changes_nothing():
    assert_scoped_change_is_asked_back(decide(raw(action='apply_change')), fact='changeability')
