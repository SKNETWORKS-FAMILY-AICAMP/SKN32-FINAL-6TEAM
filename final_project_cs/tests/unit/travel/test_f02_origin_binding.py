"""Synthetic F02 raw residual; no customer original input."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
NOW=datetime(2030,1,1,9,tzinfo=timezone.utc)
def stop(title, seq):
    return SimpleNamespace(item_id=uuid4(),title=title,kind="activity",seq=seq,detail={},starts_at=NOW.replace(day=2,hour=9+seq),ends_at=NOW.replace(day=2,hour=10+seq),place={"name":title,"attributes":{},"kind":"activity"})
from app.domains.travel_ops.components.conversation import decision_unit as du, read_requests
from unittest.mock import patch
import pytest

def exercise(*, origin='N서울타워', message='N서울타워의 운영시간을 알려줘', text='운영시간을 알려줘', turns=None, relation='before', target='i3', duplicate=False, requests=None):
    items=[stop(n,i) for i,n in enumerate(['북촌한옥마을','인사동','N서울타워','국립중앙박물관'],1)]
    if duplicate: items[3].title='N서울타워'; items[3].place['name']='N서울타워'
    req=dict(fact='hours',text=text,query=None,steps=1,advice='',at_day='none',relation=relation,
        reference='previous',anchor_item='i3',anchor_kind='item',anchor_time='',origin_item='i3',
        origin_text=origin,target_item=target,transport_mode='any')
    d=du.Decision('answer_fact',items[2],None,'hours',None,'',reads=requests or [req])
    if turns=='known': turns=[{'role':'assistant','reply':{'focus':{'item_id':str(items[2].item_id),'version':1,'at':NOW.isoformat()}}}]
    seen=[]
    original=read_requests.trip_facts.fact_reply
    def observe(*args,**kwargs):
        seen.append(kwargs.get('item').title if kwargs.get('item') else None)
        return original(*args,**kwargs)
    with patch.object(read_requests.trip_facts,'fact_reply',side_effect=observe):
        outcome,basis,focus=read_requests.reply(d,items=items,message=message,selected=None,turns=turns or [],version=1,
            now=NOW,context_now=NOW,ttl_seconds=1800,place_source=None)
    return outcome,basis,focus,seen

def test_fresh_raw_origin_only_subject_stops_wrong_reader_and_writer():
    out,basis,focus,seen=exercise()
    assert seen==[], 'a neighbour must not reach fact lookup'
    assert '인사동' not in out['text']
    # contract_correction(L05 port onto role-manager): the writer projection basis['response'] (status needs_input)
    # belongs to the L02a writer bundle; role-manager has no writer yet. The binding evidence itself is asserted below.
    assert basis['questions'][0]['unresolved']=='anchor'
    assert focus is None

@pytest.mark.parametrize('origin',['허구의장소','국립중앙박물관'])
def test_unquoted_origin_is_not_promoted_to_evidence(origin):
    out,basis,focus,seen=exercise(origin=origin)
    assert basis['questions'][0].get('unresolved')!='anchor'
    assert seen==['인사동']

def test_same_name_multiple_stops_not_forced_to_single_subject():
    out,basis,focus,seen=exercise(duplicate=True)
    assert seen==[], 'ambiguous subjects must not borrow an unrelated neighbour'
    assert basis['questions'][0].get('unresolved')=='anchor'

def test_pronoun_known_context_preserves_existing_temporal_semantics():
    out,basis,focus,seen=exercise(origin='거기',message='거기 운영시간을 알려줘',turns='known')
    assert basis['questions'][0].get('unresolved')!='anchor'
    assert seen==['인사동']

def test_multiple_questions_do_not_borrow_other_clause_subject():
    requests=[dict(fact='hours',text='N서울타워의 운영시간',query=None,reference='explicit',target_item='i3',anchor_kind='none',relation='at',origin_text='N서울타워'),
        dict(fact='address',text='인사동의 주소',query=None,reference='explicit',target_item='i2',anchor_kind='none',relation='at',origin_text='인사동')]
    out,basis,focus,seen=exercise(message='N서울타워의 운영시간, 인사동의 주소',requests=requests)
    assert seen==['N서울타워','인사동']
    assert all(q.get('unresolved')!='anchor' for q in basis['questions'])
