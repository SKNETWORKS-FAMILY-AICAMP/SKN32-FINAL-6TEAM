"""매니저 복수 조회와 플러그인 읽기 복구 병합의 실제 손실을 막는다."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.contracts import StateConflict
from app.domains.travel_ops.components.conversation import fact_read_retry, read_requests
from app.domains.travel_ops.components.conversation.decision_unit import Decision


def example():
    at=datetime(2031,1,1,9,tzinfo=timezone.utc)
    items=[SimpleNamespace(item_id=uuid4(),title=name,kind='activity',seq=n,detail={},
             starts_at=at+timedelta(hours=n),ends_at=at+timedelta(hours=n+1),
             place={'name':name,'attributes':{},'kind':'activity'})
           for n,name in enumerate(('솔빛전시관','푸른수목원'),1)]
    trip={'trip_id':uuid4(),'version':1}
    requests=[dict(fact=fact,target_item=target,origin_item='none',origin_text='',
                    reference='explicit',transport_mode='any',query=None,text='',advice='')
              for fact,target in [('time','i1'),('duration','i2')]]
    decision=Decision('answer_fact',items[0],None,'time',None,'',reads=requests)
    snapshot=fact_read_retry.read_snapshot(decision,at=at,selected=None,trip=trip,turns=[])
    return at,items,trip,decision,snapshot


def test_recovered_read_preserves_both_questions_and_their_individual_targets():
    at,items,trip,decision,snapshot=example()
    restored,when,selected=fact_read_retry.restore(snapshot,state={'decision':decision.record()},trip=trip,items=items)
    outcome,basis,_=read_requests.reply(restored,items=items,message='',selected=selected,turns=[],version=1,
         now=when,context_now=at,ttl_seconds=1800,place_source=None)
    assert [q['item_id'] for q in basis['questions']]==[str(i.item_id) for i in items]
    assert all(i.title in outcome['text'] for i in items) and '60분' in outcome['text']
    assert 'reads' not in snapshot and 'raw' not in snapshot and 'message' not in snapshot


@pytest.mark.parametrize('mutation',['second_target','query','social'])
def test_changed_saved_read_interpretation_is_rejected_instead_of_recomputed(mutation):
    _,items,trip,decision,snapshot=example()
    record=deepcopy(decision.record())
    if mutation=='second_target':record['reads'][1]['target_item']='i1'
    elif mutation=='query':record['query']={'day':'d2','period':'all','kind':'all'}
    else:record['social']='뒤에서 추가된 답변'
    with pytest.raises(StateConflict):
        fact_read_retry.restore(snapshot,state={'decision':record},trip=trip,items=items)


def test_legacy_snapshot_cannot_silently_reduce_multiple_questions_to_one():
    _,items,trip,decision,snapshot=example()
    snapshot.pop('read_signature')
    with pytest.raises(StateConflict):
        fact_read_retry.restore(snapshot,state={'decision':decision.record()},trip=trip,items=items)


def test_scoped_read_retry_preserves_the_selected_day_kind_and_position():
    from app.domains.travel_ops.components.conversation import schedule_query
    at,items,trip,_,_=example()
    query={'day':'d1','period':'all','kind':'activity','position':'last'}
    decision=Decision('answer_fact',None,None,'schedule',None,'',query=query)
    snapshot=fact_read_retry.read_snapshot(decision,at=at,selected=None,trip=trip,turns=[])
    restored,when,_=fact_read_retry.restore(snapshot,state={'decision':decision.record()},trip=trip,items=items)
    text,basis=schedule_query.reply(restored.fact,restored.query,items=items,now=when)
    assert basis['query']==query and items[-1].title in text and items[0].title not in text


@pytest.mark.parametrize('with_choices',[False,True])
def test_clarification_helper_uses_its_current_item_input(with_choices):
    from app.domains.travel_ops.components.conversation.trip_messages import _clarify_with_choices

    at,items,_,_,_=example()
    decision=Decision('clarify',None,None,'none',None,'어떤 일정인가요?',choices=(
        [{'action':'answer_fact','item':items[0],'change':None,'fact':'time'}] if with_choices else []))
    got=_clarify_with_choices(decision,items,at=at)
    assert got['status']=='clarify' and got['choices']
    assert any(choice['item_id']==str(items[0].item_id) for choice in got['choices'])
