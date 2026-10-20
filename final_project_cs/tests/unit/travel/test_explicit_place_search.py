"""직접 상호 검색은 활동·식사를 함께 표시하고 기존 자동대안·숙소 경계는 유지한다."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.components.intake import areas, candidates


def setup_search(monkeypatch, kind='activity'):
    item = {'id': '0-0', 'title': '전시 공간', 'kind': kind, 'date': '2030-01-05',
            'starts_at': '12:00', 'ends_at': '13:30', 'place': None, 'parts': {}}
    review = {'items': [item]}
    monkeypatch.setattr(candidates, '_db_places_by_name', lambda *a, **k: [])
    monkeypatch.setattr(candidates, '_ledger_places', lambda *a, **k: [])
    monkeypatch.setattr(areas, 'areas_for', lambda *a: {})
    assessed = []
    def assess(conn, tenant, current, place, prev, nxt, engine):
        assessed.append((current['kind'], place['kind'], current['starts_at'], current['ends_at']))
        return {'rows': [{'row': 'hours', 'result': 'unknown', 'text': '운영시간 미확인'}],
                'fits': False, 'status': 'warn', 'slack': {'before': None, 'after': None}, 'estimated': False}
    monkeypatch.setattr(candidates, 'assess', assess)
    return item, review, assessed


class Kakao:
    def __init__(self, rows):
        self.rows, self.calls = rows, []
        self.misses = {'timeout': 1} if rows is None else {}

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return deepcopy(self.rows)


def restaurant(name, ident, lat=37.55):
    return {'id': ident, 'name': name, 'latitude': lat, 'longitude': 127.0,
            'category_group': 'FD6', 'category': '음식점 > 태국음식', 'address': '서울 시험구'}


@pytest.mark.parametrize('kind,query', [('activity', '레몬그라스'), ('activity', '레몬그라스 타이'), ('dining', '레몬그라스타이')])
def test_manual_search_keeps_restaurant_branches_and_actual_kind(monkeypatch, kind, query):
    item, review, assessed = setup_search(monkeypatch, kind)
    before = deepcopy(review)
    source = Kakao([restaurant('레몬그라스타이 가점', 'one'), restaurant('레몬그라스타이 나점', 'two', 37.56)])
    found = candidates.search(None, tenant_id='test', review=review, item=item, query=query, kakao=source)
    assert len(found['results']) == 2 and 'no_same_kind' not in found['notes']
    assert {r['place']['kind'] for r in found['results']} == {'dining'}
    assert all(r['status'] == 'warn' and not r['fits'] for r in found['results'])
    assert source.calls[0][0] == query and len(source.calls) == 1
    assert assessed == [(kind, 'dining', '12:00', '13:30')] * 2
    assert review == before  # 검색·목록 정렬로 일정·지점을 선택하지 않는다.


def test_manual_dining_search_can_keep_an_explicit_activity_choice(monkeypatch):
    item, review, _ = setup_search(monkeypatch, 'dining')
    source = Kakao([{**restaurant('전시관', 'one'), 'category_group': 'CT1', 'category': '문화시설'}])
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='전시관', kakao=source)
    assert found['results'][0]['place']['kind'] == 'activity'


@pytest.mark.parametrize('kind', ['lodging', 'flight'])
def test_other_item_kinds_do_not_gain_restaurant_choices(monkeypatch, kind):
    item, review, assessed = setup_search(monkeypatch, kind)
    source = Kakao([restaurant('레몬그라스타이', 'one')])
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='레몬그라스', kakao=source)
    assert not found['results'] and 'no_same_kind' in found['notes'] and not assessed


def test_failed_map_lookup_is_distinct_from_zero_matches(monkeypatch):
    item, review, _ = setup_search(monkeypatch)
    failed = candidates.search(None, tenant_id='test', review=review, item=item, query='레몬그라스', kakao=Kakao(None))
    empty = candidates.search(None, tenant_id='test', review=review, item=item, query='레몬그라스', kakao=Kakao([]))
    absent = candidates.search(None, tenant_id='test', review=review, item=item, query='레몬그라스', kakao=None)
    assert failed['results'] == empty['results'] == absent['results'] == []
    assert failed['notes'] == ['kakao:timeout'] and empty['notes'] == [] and absent['notes'] == ['kakao:unavailable']
