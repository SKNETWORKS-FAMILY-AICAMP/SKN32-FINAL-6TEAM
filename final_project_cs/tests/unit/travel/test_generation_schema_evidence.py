"""Generation contracts: active evidence and following-anchor identity."""
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from jsonschema import Draft202012Validator
from app.domains.travel_ops.components.conversation import decision_unit as du, edit_intent

MESSAGE='방문 뒤 일정 한 시간 이동 요청'

def fixture():
    stops=[du.Stop(f'i{n}',SimpleNamespace(starts_at=datetime(2030,1,1,tzinfo=timezone.utc))) for n in (1,2)]
    schema=du._schema(stops,[],message=MESSAGE)
    def first(s):
        if 'enum' in s:return s['enum'][0]
        if 'anyOf' in s:return first(s['anyOf'][0])
        if s.get('type')=='object':return {k:first(s['properties'][k]) for k in s.get('required',[])}
        return {'string':'','integer':0,'boolean':False,'array':[],'null':None}[s['type']]
    raw=first(schema)
    raw.update(action='change_time',target_item='i1',anchor_item='i1',minutes=60)
    raw['time_edit']=dict(boundary='shift',scope='following',time='',duration_minutes=0,cascade=False,continue_previous=False,evidence=MESSAGE)
    raw['place_search']=dict(relation='none',anchor_item='none',place_text='',evidence='')
    return schema,raw

@pytest.mark.parametrize('field',['time_edit','place_search'])
def test_active_object_cannot_have_empty_evidence(field):
    schema,raw=fixture()
    if field=='place_search':raw['place_search'].update(relation='near',anchor_item='i2')
    raw[field]['evidence']=''
    assert list(Draft202012Validator(schema).iter_errors(raw))

def test_following_generation_uses_one_anchor():
    schema,raw=fixture();raw['target_item']='i2'
    assert list(Draft202012Validator(schema).iter_errors(raw))

def test_exact_quote_and_consistent_anchor_are_valid():
    schema,raw=fixture()
    assert not list(Draft202012Validator(schema).iter_errors(raw))
    edit_intent.validate(raw,MESSAGE,{'none','i1','i2'})

def test_generation_is_action_first_without_permissive_root_object():
    schema,_=fixture()
    assert 'properties' not in schema
    assert all(next(iter(branch['properties']))=='action' for branch in schema['anyOf'])

def test_read_cannot_activate_temporal_edit():
    schema,raw=fixture();raw['action']='answer_fact'
    assert list(Draft202012Validator(schema).iter_errors(raw))
