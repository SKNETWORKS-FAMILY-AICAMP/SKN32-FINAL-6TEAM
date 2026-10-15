"""실시간 재검증 결과를 안내에 소비하되 저장 일정과 기존 호출 계약을 보존한다."""
from datetime import datetime
from copy import deepcopy
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.watch.trip_reminders import build_departure

def t(hm):
    return datetime.fromisoformat(f'2026-10-09T{hm}:00+09:00')

class NoEvents:
    def affecting(self, targets):
        return {}

def scene():
    move = Item(item_id=uuid4(), seq=1, kind='mobility', title='A → B', place_id=None,
        starts_at=t('10:00'), ends_at=t('10:17'), detail={'route_def': {'planned': 'p',
        'options': [{'id': 'p', 'label': '버스', 'eta_min': 17, 'uses': ['버스:100']}]}})
    nxt = Item(item_id=uuid4(), seq=2, kind='activity', title='B 관람', place_id=None,
               starts_at=t('11:00'), ends_at=t('12:00'), detail={})
    return move, [move, nxt]

def result(**kw):
    return dict({'status': 'realtime', 'departure_at': t('10:01').isoformat(),
                'arrival_at': t('10:22').isoformat(), 'eta_min': 22}, **kw)

def test_fresh_departure_and_eta_are_displayed_without_mutating_saved_item():
    move, items = scene()
    before = deepcopy(move)
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=t('10:00'), departure_observer=lambda *a, **kw: result())
    text = phrase.render()
    assert status == 'ok' and '10:01 출발' in text and '약 22분' in text
    assert '현재 버스 대기 반영' in text and move == before

@pytest.mark.parametrize('value,expected', [
    ({'status': 'needs_replan'}, 'held'), ({'status': 'fatal'}, 'fatal'),
    (result(arrival_at=t('11:01').isoformat()), 'fatal'), (result(eta_min=True), 'fatal'),
    (result(departure_at='2026-10-09T10:01:00'), 'fatal'), (None, 'fatal'),
])
def test_invalid_or_late_observations_do_not_emit_stale_guidance(value, expected):
    move, items = scene()
    status, phrase = build_departure(move, items, route_events=NoEvents(), routes=None,
                                    now=t('10:00'), departure_observer=lambda *a, **kw: value)
    assert status == expected and phrase is None

def test_model_fallback_is_labelled_and_default_consumer_preserves_saved_eta():
    move, items = scene()
    _, model = build_departure(move, items, route_events=NoEvents(), routes=None, now=t('10:00'),
        departure_observer=lambda *a, **kw: result(status='model_revalidated'))
    _, legacy = build_departure(move, items, route_events=NoEvents(), routes=None, now=t('10:00'))
    assert '현재 시각 기준 예상' in model.render() and '약 17분' in legacy.render()
