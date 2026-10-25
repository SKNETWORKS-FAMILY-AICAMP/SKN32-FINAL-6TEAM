"""Regression from T18 real-model raw reflow + source-validated nonzero minutes.
The executor must not discard the authoritative relative delta.
"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.conversation.edit_intent import time_ops,schemas

def test_generation_clock_does_not_allow_relative_minutes_as_clock():
 import re
 field=schemas(['none','i1'])['time_edit']['properties']['time']
 pattern=field.get('pattern','.*')
 assert re.fullmatch(pattern,'-60') is None
 assert re.fullmatch(pattern,'') is not None
 assert re.fullmatch(pattern,'14:30') is not None
 assert re.fullmatch(pattern,'24:00') is None

def items():
 def one(seq,title,start,end):
  return Item(item_id=uuid4(),seq=seq,kind='activity',title=title,place_id=None,starts_at=datetime.fromisoformat(start),ends_at=datetime.fromisoformat(end))
 return [one(1,'북촌한옥마을','2030-01-02T10:00:00+09:00','2030-01-02T11:00:00+09:00'),one(2,'인사동','2030-01-02T12:00:00+09:00','2030-01-02T13:00:00+09:00'),one(3,'N서울타워','2030-01-02T15:00:00+09:00','2030-01-02T16:30:00+09:00'),one(4,'다음날','2030-01-03T10:00:00+09:00','2030-01-03T11:00:00+09:00')]
def test_reflow_does_not_discard_source_validated_relative_delta():
 its=items();raw={'anchor_item':'i1','at_day':'none','time_edit':{'boundary':'reflow','scope':'following','cascade':True,'continue_previous':False,'time':'','duration_minutes':0}}
 d=SimpleNamespace(raw=raw,minutes=60,item=its[0]);ops,_=time_ops(d,items=its,now=datetime.fromisoformat('2030-01-01T09:00:00+09:00'))
 assert [o.item_id for o in ops]==[its[1].item_id,its[2].item_id]
 assert [(o.starts_at,o.ends_at) for o in ops]==[('13:00','14:00'),('16:00','17:30')]
 assert d.raw is raw and d.raw['time_edit']['boundary']=='reflow'
def test_zero_delta_reflow_still_preserves_anchor_end():
 its=items();d=SimpleNamespace(raw={'anchor_item':'i1','at_day':'none','time_edit':{'boundary':'reflow','scope':'following','cascade':True,'continue_previous':False}},minutes=None,item=its[0])
 ops,_=time_ops(d,items=its,now=datetime.fromisoformat('2030-01-01T09:00:00+09:00'))
 assert len(ops)==1 and ops[0].item_id==its[0].item_id and ops[0].ends_at=='11:00'
