"""F02 historical fixture, controlled offline; never real-model evidence."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
from app.domains.travel_ops.components.conversation import decision_unit as du, read_requests

NOW = datetime(2030, 1, 1, 9, tzinfo=timezone.utc)

def stop(title, seq):
    return SimpleNamespace(item_id=uuid4(), title=title, kind='activity', seq=seq, detail={},
        starts_at=NOW.replace(day=2 if seq < 4 else 3, hour=9+seq), ends_at=NOW.replace(day=2 if seq < 4 else 3, hour=10+seq),
        place={'name':title,'attributes':{},'kind':'activity'})

def exercise():
    items=[stop(n,i) for i,n in enumerate(['북촌한옥마을','인사동','N서울타워','국립중앙박물관'],1)]
    req=dict(fact='hours',text='N서울타워의 운영시간을 알려줘',query=None,steps=1,advice='',at_day='none',
        relation='after',reference='previous',anchor_item='i3',anchor_kind='item',anchor_time='',origin_item='i3',
        origin_text='N서울타워의 운영시간을 알려줘',target_item='i3',transport_mode='any')
    d=du.Decision('answer_fact',items[2],None,'hours',None,'',reads=[req])
    seen=[]
    original=read_requests.trip_facts.fact_reply
    def observe(*args,**kwargs):
        seen.append(kwargs.get('item').title if kwargs.get('item') else None)
        return original(*args,**kwargs)
    with patch.object(read_requests.trip_facts,'fact_reply',side_effect=observe):
        outcome,basis,focus=read_requests.reply(d,items=items,message=req['text'],selected=None,turns=[],version=1,
            now=NOW,context_now=NOW,ttl_seconds=1800,place_source=None)
    return outcome,basis,focus,seen

def test_tool_query_target_never_substitutes_different_factual_subject():
    _,_,_,seen=exercise()
    assert '국립중앙박물관' not in seen

def test_response_factual_subject_binding_and_writer_proof():
    outcome,basis,focus,_=exercise()
    assert '국립중앙박물관' not in outcome['text']
    # contract_correction(L05 port onto role-manager): the writer projection basis['response'] belongs to the L02a
    # writer bundle (not on role-manager yet). The stored read evidence carries the same binding refusal.
    q=basis['questions'][0]
    assert q['unresolved']=='anchor'
    assert focus is None
