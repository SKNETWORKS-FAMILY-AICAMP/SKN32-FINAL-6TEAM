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


def two_stops_around(monkeypatch):
    """앞 일정(서쪽) · 고르는 일정(북쪽 경복궁) · 뒤 일정(서쪽) — 예전 중심(앞뒤 가운데)과 고른 장소가 4km 넘게 떨어진다."""
    item, review, assessed = setup_search(monkeypatch, 'dining')
    item.update({'id': '0-1', 'place': {'name': '경복궁', 'latitude': 37.5796, 'longitude': 126.9770, 'kind': 'activity'}})
    before = {'id': '0-0', 'kind': 'activity', 'date': item['date'], 'place': {'name': '홍대', 'latitude': 37.5563, 'longitude': 126.9220}}
    after = {'id': '0-2', 'kind': 'activity', 'date': item['date'], 'place': {'name': '합정', 'latitude': 37.5495, 'longitude': 126.9135}}
    review['items'] = [before, item, after]
    return item, review, assessed


class TwoOrderKakao(Kakao):
    """중심을 주면 거리순 답, 안 주면 관련도 순 답 — 실제 카카오처럼 부르는 방식에 따라 순서가 다르다."""
    def __init__(self, near_rows, plain_rows):
        super().__init__(near_rows)
        self.plain_rows = plain_rows

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return deepcopy(self.rows if kwargs.get('near') else self.plain_rows)


def shop(name, ident, lat, lon):
    return {**restaurant(name, ident), 'latitude': lat, 'longitude': lon}


def test_web_search_measures_from_the_stop_being_changed(monkeypatch):
    item, review, _ = two_stops_around(monkeypatch)
    near_gbg = shop('국수집 경복궁점', 'a', 37.5790, 126.9760)
    near_hongdae = shop('국수집 홍대점', 'b', 37.5560, 126.9230)
    source = TwoOrderKakao([near_hongdae, near_gbg], [near_hongdae, near_gbg])
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='국수집', kakao=source, around_self=True)
    # 기준은 고르는 일정(경복궁) — 앞뒤 일정(홍대 · 합정) 가운데가 아니다
    assert source.calls[0][1]['near'] == (37.5796, 126.9770)
    assert [r['place']['name'] for r in found['results']] == ['국수집 경복궁점', '국수집 홍대점']
    assert {r['reference'] for r in found['results']} == {'경복궁'}
    assert found['results'][0]['distance_m'] < 200 and found['results'][1]['distance_m'] > 5000
    assert found['center'] == {'name': '경복궁', 'basis': 'selected'}
    assert all(r['order'] == 'distance' for r in found['results'])


def test_other_stop_gives_another_centre(monkeypatch):
    item, review, _ = two_stops_around(monkeypatch)
    other = review['items'][0]
    other.update({'title': '점심', 'starts_at': '11:00', 'ends_at': '12:00', 'parts': {}})
    source = Kakao([shop('국수집 홍대점', 'b', 37.5560, 126.9230)])
    candidates.search(None, tenant_id='test', review=review, item=item, query='국수집', kakao=source, around_self=True)
    candidates.search(None, tenant_id='test', review=review, item=other, query='국수집', kakao=source, around_self=True)
    assert [call[1]['near'] for call in source.calls] == [(37.5796, 126.9770), (37.5563, 126.9220)]


def test_web_search_also_lists_best_name_matches(monkeypatch):
    item, review, _ = two_stops_around(monkeypatch)
    exact_far = shop('국수집', 'x', 37.5000, 127.0500)
    near_gbg = shop('옛날국수집 경복궁', 'a', 37.5790, 126.9760)
    source = TwoOrderKakao([near_gbg], [exact_far, near_gbg])
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='국수집', kakao=source,
                              around_self=True, by_relevance=True)
    assert [r['place']['name'] for r in found['results']] == ['옛날국수집 경복궁']
    assert [r['place']['name'] for r in found['relevance']] == ['국수집', '옛날국수집 경복궁']
    assert all(r['order'] == 'relevance' for r in found['relevance'])
    assert [r['rank'] for r in found['relevance']] == [1, 2]
    # 가까운 곳에 이름이 똑같은 곳이 없으니 카카오를 중심 없이(서울 관련도 순) 한 번 더 부른다 · 거리는 여전히 고른 장소에서 잰다
    assert len(source.calls) == 2 and 'near' not in source.calls[1][1]
    assert found['relevance_kakao'] == 'called'
    assert found['relevance'][0]['reference'] == '경복궁'


def test_second_map_call_is_skipped_when_an_exact_name_is_already_near(monkeypatch):
    """`[2026-10-22 사용자 지시]` 거리순으로 모은 곳에 이름이 검색어와 똑같은 곳이 있으면 카카오를 한 번만 부르고 그 결과를 일치도 목록에도 쓴다."""
    item, review, _ = two_stops_around(monkeypatch)
    exact_near = shop('국수집', 'x', 37.5780, 126.9750)
    other = shop('옛날국수집 경복궁', 'a', 37.5790, 126.9760)
    source = TwoOrderKakao([other, exact_near], [exact_near, other])
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='국수집', kakao=source,
                              around_self=True, by_relevance=True)
    assert len(source.calls) == 1 and found['relevance_kakao'] == 'reused'
    assert [r['place']['name'] for r in found['relevance']] == ['국수집', '옛날국수집 경복궁']
    assert [r['place']['name'] for r in found['results']] == ['옛날국수집 경복궁', '국수집']


def test_relevance_failure_is_reported_once(monkeypatch):
    item, review, _ = two_stops_around(monkeypatch)
    source = TwoOrderKakao(None, None)
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='국수집', kakao=source,
                              around_self=True, by_relevance=True)
    assert found['results'] == found['relevance'] == [] and found['notes'] == ['kakao:timeout']


def test_stop_without_a_place_keeps_the_old_centre(monkeypatch):
    item, review, _ = two_stops_around(monkeypatch)
    item['place'] = None
    source = Kakao([shop('국수집 홍대점', 'b', 37.5560, 126.9230)])
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='국수집', kakao=source, around_self=True)
    lat, lon = source.calls[0][1]['near']
    assert abs(lat - (37.5563 + 37.5495) / 2) < 1e-9 and abs(lon - (126.9220 + 126.9135) / 2) < 1e-9
    assert found['center']['basis'] == 'neighbours'


def test_zero_metres_counts_as_the_nearest_stop():
    """`[2026-10-22 점검]` 앞 일정과 같은 자리(0m)인 후보는 앞 일정 기준 0m — 뒤 일정 기준 거리로 적지 않는다."""
    here = {'name': '홍대', 'latitude': 37.5563, 'longitude': 126.9220}
    prev, nxt = {'place': here}, {'place': {'name': '경복궁', 'latitude': 37.5796, 'longitude': 126.9770}}
    shown = candidates._present({**here, 'name': '같은 자리 가게'}, {'rows': [], 'fits': True, 'status': 'ok', 'slack': {}, 'estimated': False},
                                prev, nxt, None)
    assert shown['reference'] == '홍대' and shown['distance_m'] == 0


def test_web_search_shows_up_to_fifteen_in_each_list(monkeypatch):
    """`[2026-10-23 사용자 지시]` 웹 검색은 목록마다 15곳 — 카카오 한 번에 받는 최대와 같다."""
    item, review, _ = two_stops_around(monkeypatch)
    rows = [shop(f'국수집 {n}호점', f'k{n}', 37.57 + n / 1000, 126.97) for n in range(15)]
    source = TwoOrderKakao(rows, rows)
    found = candidates.search(None, tenant_id='test', review=review, item=item, query='국수집', kakao=source,
                              around_self=True, by_relevance=True, limit=candidates.WEB_SEARCH_LIMIT)
    assert candidates.WEB_SEARCH_LIMIT == 15
    assert len(found['results']) == len(found['relevance']) == 15
    assert source.calls[0][1]['size'] == 15


def add_between(monkeypatch, *, before_kind='activity'):
    """일정 추가 — 경복궁(앞) · 광장시장(뒤) 사이에 새 일정을 끼운다. 판정 함수가 받은 일정 값을 모은다."""
    _, review, assessed = setup_search(monkeypatch, 'activity')
    before = {'id': '0-0', 'title': '앞', 'kind': before_kind, 'date': '2030-01-05', 'starts_at': '10:00', 'ends_at': '12:00', 'parts': {},
              'place': {'name': '경복궁', 'latitude': 37.5796, 'longitude': 126.9770}}
    after = {'id': '0-1', 'title': '뒤', 'kind': 'activity', 'date': '2030-01-05', 'starts_at': '15:00', 'ends_at': '16:00', 'parts': {},
             'place': {'name': '광장시장', 'latitude': 37.5700, 'longitude': 126.9996}}
    review['items'] = [before, after]
    return review, assessed


def test_add_search_orders_by_the_way_between_the_two_stops(monkeypatch):
    """`[2026-10-23 사용자 지시 — Codex 합의]` 경복궁 옆(가는 길) 식당이 가운데 북쪽(길에서 벗어남) 식당보다 먼저 — 「동선순」."""
    review, assessed = add_between(monkeypatch)
    on_way = shop('국수집 경복궁점', 'x', 37.5790, 126.9780)
    off_way = shop('국수집 북촌점', 'y', 37.5880, 126.9883)
    source = TwoOrderKakao([off_way, on_way], [off_way, on_way])
    found = candidates.add_search(None, tenant_id='test', review=review, query='국수집', previous_id='0-0', next_id='0-1',
                                  date='2030-01-05', starts_at='12:30', ends_at='13:30', kind='dining', kakao=source)
    assert [r['place']['name'] for r in found['results']] == ['국수집 경복궁점', '국수집 북촌점']
    assert {r['order'] for r in found['results']} == {'route'} and found['center'] == {'name': '경복궁 · 광장시장', 'basis': 'between'}
    lat, lon = source.calls[0][1]['near']                                   # 후보는 두 일정 가운데 둘레에서 모은다
    assert abs(lat - (37.5796 + 37.5700) / 2) < 1e-9 and abs(lon - (126.9770 + 126.9996) / 2) < 1e-9
    # 판정은 새 일정 폼 값으로(옆 일정 값이 아니다)
    assert set(assessed) == {('dining', 'dining', '12:30', '13:30')}
    assert len(found['results']) <= candidates.WEB_SEARCH_LIMIT and 'relevance' in found


def test_add_search_after_a_hotel_keeps_restaurants(monkeypatch):
    """☆전에는 옆 일정(숙소)의 「바꾸기」 검색을 빌려 숙소만 남겼다 — 새 일정이 식사면 식당이 보여야 한다."""
    review, _ = add_between(monkeypatch, before_kind='lodging')
    source = Kakao([shop('국수집 경복궁점', 'x', 37.5790, 126.9780)])
    found = candidates.add_search(None, tenant_id='test', review=review, query='국수집', previous_id='0-0', next_id=None,
                                  date='2030-01-05', starts_at='12:30', ends_at='13:30', kind='dining', kakao=source)
    assert [r['place']['name'] for r in found['results']] == ['국수집 경복궁점'] and 'no_same_kind' not in found['notes']
    assert found['results'][0]['order'] == 'distance'                         # 한쪽 일정만 있으면 그 장소에서 가까운 순
