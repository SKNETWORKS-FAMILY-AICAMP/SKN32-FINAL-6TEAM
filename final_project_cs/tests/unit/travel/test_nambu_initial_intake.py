"""출발점·거기서 식사·분 단위 기준을 초기 접수에서도 보존한다."""
from datetime import date, datetime
from uuid import uuid4
from types import SimpleNamespace
import pytest

from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.intake.assemble import assemble
from app.domains.travel_ops.components.intake.places import resolve
from app.domains.travel_ops.components.conversation.chat_edit import ops_for
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, check_itinerary
from .test_intake_agent_read import Agent, _answer, _items
from .test_intake_meal_landmark import Ledger


@pytest.mark.parametrize("finish_by", [False, True])
def test_origin_does_not_add_a_dwell_and_there_is_resolved_near_that_origin(finish_by):
    text='지금 남부터미널에서 8시에 시작해서 10분 뒤에 거기서 밥먹고 다이소 갔다가 노래방 갔다가 11시 전에 집에 들어갈 거야'
    moment=datetime.fromisoformat('2026-10-17T19:50:00+09:00')
    def item(quote,start,kind='activity',role='visit',time_quote=None):
        return {'place_quote':quote,'kind':kind,'role':role,'day':1,'date':'2026-10-17',
            'date_quote':'지금','start':start,'end':None,'time_quote':time_quote}
    agent=Agent(_answer([item('남부터미널','20:00',role='origin',time_quote='8시'),
        item('밥','20:10','dining',time_quote='10분 뒤'),item('다이소',None),item('노래방',None)],
        conditions=[{'code':'finish_by:23:00','quote':'11시 전에'}] if finish_by else []))
    our=[{'place_id':str(uuid4()),'name':name,'kind':'activity','latitude':37.485,'longitude':127.016}
        for name in ('남부터미널','다이소 남부터미널점','노래방')]
    shop={'matched_title':'백년옥','latitude':37.4849,'longitude':127.0159,
        'content_id':'12345','content_type_id':'39','dining_place_uid':str(uuid4()),'match':'meal_near','needs_review':True}
    ledger=Ledger(shop)
    rows=read_source(text,today=date(2026,10,17),now=moment,agent=agent,agent_mode='on',our_places=our,dining=ledger)
    values=_items(rows)
    assert values[1]['place']['name']=='백년옥'
    assert ledger.meal_asked==[(37.485,127.016)]
    built=assemble(intake_id='test',revision=1,sources=[{'source_id':'s','position':0,'transcript':text}],
        claims=[{**r,'source_id':'s'} for r in rows])
    origin,meal=built.body['items'][:2]
    assert origin['detail'].get('origin') is True and origin['ends_at'] is None, built.body
    assert meal['starts_at']=='2026-10-17T20:10:00+09:00'
    assert meal['title']=='백년옥 식사'
    if finish_by:
        assert built.body['items'][-1]['ends_at'] <= '2026-10-17T23:00:00+09:00'
        assert not any(p.code=='day_deadline' for p in built.problems)


def test_deictic_without_an_anchor_never_becomes_a_business_search():
    class Kakao:
        def search(self,*args,**kwargs):
            raise AssertionError('지시어를 상호로 검색하면 안 된다')
    got=resolve('거기',our_places=[],kakao=Kakao(),kind_hint='dining')
    assert got.status=='unresolved' and got.chain_deferred


def test_named_replacement_and_five_minutes_are_kept_in_one_edit_batch():
    from .test_journey_progress import visit, at
    meal=visit(1,'식사','20:20','20:58')
    decision=SimpleNamespace(action='replace_named',item=meal,minutes=5,query=None,
        raw={'destination_text':'돈까스','place_text':'남부터미널'})
    ops,_=ops_for(decision,items=[meal],now=at('19:54'))
    assert [op.kind for op in ops]==['place','time']
    assert ops[0].place_name=='돈까스' and ops[1].starts_at=='20:25'


def test_day_deadline_rejects_both_late_end_and_crossing_midnight():
    for start,end in [('22:10','23:40'),('23:30','00:10')]:
        begins=datetime.fromisoformat('2026-10-17T'+start+':00+09:00')
        ends=datetime.fromisoformat(('2026-10-18' if end=='00:10' else '2026-10-17')+'T'+end+':00+09:00')
        issues=check_itinerary([Part(seq=1,kind='activity',title='노래방',starts_at=begins,ends_at=ends)],
            constraints={'day_hours':{'end':'23:00'}})
        assert any(i.code=='day_deadline' for i in issues)
