"""2030 is an explicit synthetic fixture date, never a product threshold."""
from datetime import date
import jsonschema
import pytest
from app.domains.travel_ops.components.intake import agent_read

TEXT = '2030년 1월 2일 오후 1시 30분부터 오후 2시 30분까지 덕수궁을 추가해줘'

from datetime import datetime
from app.domains.travel_ops.components.conversation import chat_edit

@pytest.mark.parametrize('text,expected', [
    ('2030-01-02 13:30~14:30 덕수궁 추가', '2030-01-02'),
    ('내일 13:30~14:30 덕수궁 추가', '2030-01-02'),
    ('오늘 13:30~14:30 덕수궁 추가', '2030-01-01'),
])
def test_grounded_date_reaches_add_args_without_routing_today_override(text, expected):
    raw = item(date=expected, date_quote=text, time_quote=text)
    got = agent_read.ground({'items': [raw]}, [text])
    now = datetime.fromisoformat('2030-01-01T09:00:00+09:00')
    ops = chat_edit._read_adds(text, lambda *args: got, stops=[], now=now, day='2030-01-01')
    assert [(op.date, op.starts_at, op.ends_at, op.title) for op in ops] == [(expected,'13:30','14:30','덕수궁')]

def test_multiday_hotel_identifiers_survive_ground_and_add():
    text = '2030-01-02 13:30~14:30 덕수궁\n2030-01-03 10:00~11:00 경복궁스테이 예약AB123'
    rows = [item(date_quote=text.splitlines()[0],time_quote=text.splitlines()[0]),
            item(place_quote='경복궁스테이',date='2030-01-03',date_quote=text.splitlines()[1],start='10:00',end='11:00',time_quote=text.splitlines()[1],kind='lodging')]
    got = agent_read.ground({'items': rows}, text.splitlines())
    assert [(it.title.text,it.date,it.start,it.end,it.kind) for it in got.items] == [('덕수궁','2030-01-02','13:30','14:30','activity'),('경복궁스테이','2030-01-03','10:00','11:00','lodging')]
    assert text.endswith('예약AB123')  # source itself is never rewritten

class Capture:
    def structured(self, system, user, schema, **kw):
        self.schema = schema
        return {'items': []}

def schema_for(text=TEXT):
    chat = Capture()
    agent_read.read(text, text.splitlines(), chat, today=date(2030, 1, 1))
    return chat.schema['properties']['items']['items']

def item(**changes):
    value = dict(place_quote='덕수궁', day=1, date='2030-01-02', date_quote=TEXT,
                 start='13:30', end='14:30', time_quote=TEXT, kind='activity',
                 locked=None, locked_quote=None)   # L07 I06: 명시 고정 칸은 필수(말이 없으면 null)
    value.update(changes)
    return value

# contract_correction(L05 port onto role-manager a465c602): the local lineage pinned date/time quotes with an
# `enum` of source lines in the agent_read schema. role-manager L03 (a465c602, Codex P1) removed source lines from
# schemas because a schema reaches the paid fallback unmasked. The same evidence rule is enforced by `ground`:
# a value without its own source quote (missing or not in the source) is dropped, and the schema carries no source text.
def test_schema_carries_no_source_text():
    import json
    assert TEXT not in json.dumps(schema_for(), ensure_ascii=False)

def test_ground_drops_date_without_its_quote():
    assert agent_read.ground({'items': [item(date_quote=None)]}, [TEXT]).items[0].date is None

def test_ground_drops_non_source_date_quote():
    assert agent_read.ground({'items': [item(date_quote='.')]}, [TEXT]).items[0].date is None

def test_ground_drops_clock_without_its_quote():
    got = agent_read.ground({'items': [item(time_quote=None)]}, [TEXT]).items[0]
    assert (got.start, got.end) == (None, None)

@pytest.mark.parametrize('text', [TEXT, '내일 13:30~14:30 덕수궁 추가', '오늘 13:30~14:30 덕수궁 추가', '2030-01-02 덕수궁 13:30~14:30\n2030-01-03 인사동 10:00~11:00'])
def test_quoted_values_and_missing_date_contract(text):
    schema = schema_for(text)
    jsonschema.validate(item(date_quote=text.splitlines()[0], time_quote=text.splitlines()[0]), schema)
    jsonschema.validate(item(date=None, date_quote=None, start=None, end=None, time_quote=None), schema)

def test_ground_exact_value_remains_and_unquoted_value_is_still_dropped():
    good = agent_read.ground({'items': [item()]}, [TEXT])
    assert (good.items[0].date, good.items[0].start, good.items[0].end) == ('2030-01-02','13:30','14:30')
    bad = agent_read.ground({'items': [item(date_quote=None)]}, [TEXT])
    assert bad.items[0].date is None
