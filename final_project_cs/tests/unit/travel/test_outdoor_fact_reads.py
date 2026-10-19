"""A real API response for one outdoor question must remain a read of one item."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation import decision_unit as du, read_requests

NOW = datetime(2031, 3, 10, tzinfo=timezone.utc)
FIXTURE = json.loads((Path(__file__).parents[2] / 'fixtures/outdoor_single_model_response.json').read_text(encoding='utf8'))


def item(name, seq, indoor):
    return SimpleNamespace(item_id=uuid4(), title=name, kind='activity', seq=seq, detail={},
        starts_at=NOW + timedelta(hours=seq), ends_at=NOW + timedelta(hours=seq + 1),
        place={'name': name, 'attributes': {'indoor': indoor, 'indoor_assumed': True}})


def decide(raw, items):
    class Chat:
        def structured(self, *args, **kwargs):
            return deepcopy(raw)
    return du.decide(Chat(), stops=du.stops_of(items), changes=[], history=[], selected_item_id=None,
                     message='광화문 일정은 야외 일정이야?', now=NOW)


def render(decision, items, message='광화문 일정은 야외 일정이야?', turns=(), selected=None):
    return read_requests.reply(decision, items=items, message=message, selected=selected,
        turns=turns, version=1, now=NOW, context_now=NOW, ttl_seconds=1800, place_source=None)


@pytest.mark.parametrize('indoor,label', [(False, '야외'), (True, '실내'), (None, '확인되지')])
def test_real_api_response_reads_only_the_selected_place(indoor, label):
    a, b = item('광화문광장', 1, indoor), item('다른 전시관', 2, True)
    original = deepcopy(a.place)
    decision = decide(FIXTURE, [a, b])
    result, basis, _ = render(decision, [a, b])
    assert result['status'] == 'answered'
    assert a.title in result['text'] and label in result['text']
    assert b.title not in result['text']
    assert basis['questions'][0]['item_id'] == str(a.item_id)
    assert a.place == original
    if indoor is None:
        assert basis['questions'][0]['unresolved'] == 'indoor'


def test_top_level_outdoor_question_uses_the_same_single_place_read():
    raw = {**FIXTURE, 'reads': []}
    a = item('광화문광장', 1, False)
    decision = decide(raw, [a])
    assert len(decision.reads) == 1 and decision.query is None
    assert '야외' in render(decision, [a])[0]['text']


def test_explicit_outdoor_list_keeps_its_validated_scope():
    raw = deepcopy(FIXTURE)
    query = {'day': 'all', 'period': 'all', 'kind': 'all', 'position': 'all'}
    raw.update(target_item='none', query=query)
    raw['reads'][0].update(target_item='none', reference='none', query=query)
    a, b = item('광화문광장', 1, False), item('전시관', 2, True)
    decision = decide(raw, [a, b])
    text = render(decision, [a, b], message='전체 일정의 실내 야외를 알려줘')[0]['text']
    assert a.title in text and b.title in text
    assert decision.query == query


def test_invalid_outdoor_scope_never_becomes_an_all_items_read():
    raw = deepcopy(FIXTURE)
    raw['reads'][0]['query'] = {'day': 'd99', 'period': 'all', 'kind': 'all', 'position': 'all'}
    with pytest.raises(du.DecisionFailed):
        decide(raw, [item('광화문광장', 1, False)])


def test_outdoor_response_cannot_refer_to_an_unknown_item():
    raw = deepcopy(FIXTURE)
    raw['reads'][0]['target_item'] = 'i99'
    with pytest.raises(du.DecisionFailed):
        decide(raw, [item('광화문광장', 1, False)])


def test_outdoor_followup_uses_the_valid_previous_item():
    a, b = item('광화문광장', 1, False), item('전시관', 2, True)
    raw = deepcopy(FIXTURE)
    raw['reads'][0].update(target_item='i2', reference='previous', text='거기는 야외야?')
    decision = decide(raw, [a, b])
    turns = [{'role': 'assistant', 'reply': {'focus': {'item_id': str(a.item_id),
              'version': 1, 'at': NOW.isoformat()}}}]
    text = render(decision, [a, b], message='거기는 야외야?', turns=turns)[0]['text']
    assert a.title in text and b.title not in text and '야외' in text


def test_missing_outdoor_target_is_a_question_not_a_model_error_or_broader_read():
    raw = deepcopy(FIXTURE)
    raw.update(target_item='none')
    raw['reads'][0].update(target_item='none', reference='none', text='야외야?')
    decision = decide(raw, [item('광화문광장', 1, False)])
    result, basis, _ = render(decision, [item('다른 곳', 1, True)], message='야외야?')
    assert '일정 이름' in result['text']
    assert basis['questions'][0]['unresolved'] == 'target'
