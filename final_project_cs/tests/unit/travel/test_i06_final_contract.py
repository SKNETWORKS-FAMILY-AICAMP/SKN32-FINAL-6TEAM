from datetime import date
import hashlib, json
import pytest
from app.domains.travel_ops.components.intake import agent_read
from .test_intake_agent_locked import _run, _claim

def test_system_example_matches_required_lock_contract():
    text=agent_read.system_for(date(2026,10,25))
    example=json.loads(text.split('Output: ',1)[1])
    for item in example['items']:
        assert item['locked'] is None and item['locked_quote'] is None

def test_inline_reader_prompt_identity_is_persisted_in_report():
    class Chat:
        model='fixture'
        def structured(self, system, user, schema, **kw):
            self.system=system
            return {'items': []}
    c=Chat(); got=agent_read.read('서울 여행', ['서울 여행'], c, today=date(2026,10,25))
    assert got.report['prompt_version']=='intake.agent_read.v3-booked-not-locked'
    assert got.report['prompt_template_hash']==hashlib.sha256(agent_read.SYSTEM.encode()).hexdigest()
    assert got.report['prompt_hashes']==[hashlib.sha256(c.system.encode()).hexdigest()]

@pytest.mark.parametrize('quote',['','   ','원문에 없는 고정'])
def test_empty_or_non_source_quote_cannot_lock(quote):
    _,claims,got=_run({'locked':True,'locked_quote':quote})
    assert _claim(claims,'items[0].locked') is None
    assert 'customer_pinned' not in got.body['items'][0]['detail']

@pytest.mark.parametrize('words',['고정하지 마세요','고정 없음','예약만 했습니다'])
def test_negative_or_booked_control_is_not_pinned(words):
    text='2030-01-02 서울 2명, 19:00~20:30 명동난타극장 예약 완료, 예약번호 SYN-KY-20931. '+words
    _,claims,got=_run({'locked':False if words!='예약만 했습니다' else None,'locked_quote':words if words!='예약만 했습니다' else None},text)
    assert not got.body['items'][0]['detail'].get('customer_pinned',False)

def test_multiple_items_preserve_each_items_model_lock_without_cross_promotion():
    lines=['명동난타극장 예약 완료. 고정하지 마세요.','덕수궁 이 일정은 고정해 주세요.']
    got=agent_read.ground({'items':[{'place_quote':'명동난타극장','kind':'activity','locked':False,'locked_quote':'고정하지 마세요'}, {'place_quote':'덕수궁','kind':'activity','locked':True,'locked_quote':'이 일정은 고정해 주세요'}]},lines)
    assert [(i.title.text,i.locked,i.locked_quote.line) for i in got.items]==[('명동난타극장',False,1),('덕수궁',True,2)]
