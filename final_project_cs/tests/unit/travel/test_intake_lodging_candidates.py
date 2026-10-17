"""숙소 후보는 앞뒤 일정 주변의 숙박만 쓰며, 선택 후에도 숙박 조건을 유지한다."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.intake import autofix, candidates


HOTEL = {"name": "광화문스테이", "latitude": 37.578, "longitude": 126.976,
         "source": "kakao", "kind": "activity", "category": "여행 > 숙박 > 호텔"}
PARK = {**HOTEL, "name": "광화문공원", "category": "여행 > 관광,명소 > 공원"}


class MapSearch:
    def __init__(self):
        self.asked = []

    def search(self, query, *, size=10, near=None):
        self.asked.append((query, near))
        return [{**HOTEL, "id": "stay", "category_group": "AD5"},
                {**PARK, "id": "park", "category_group": "AT4"},
                {**HOTEL, "name": "호텔 앞 식당", "id": "meal", "category_group": "FD6",
                 "category": "음식점 > 한식"}]


def review(state="needs_choice", *, meal=False, area=None):
    parts = {"content_type": "32", "label": "숙소", "lodging_meal": meal, "area": area}
    item = {"id": "0-0", "source_id": "source", "index": 0, "title": "호텔 조식" if meal else "호텔",
            "date": "2030-01-05", "starts_at": "09:00", "ends_at": "09:30", "kind": "dining" if meal else "activity",
            "kind_known": True, "place_state": state,
            "place": None if state == "needs_choice" else {**HOTEL, "name": "기존숙소"},
            "parts": parts if state == "needs_choice" else None, "status": "review", "locked": False,
            "booked": None, "rows": [{"row": "place", "result": "bad", "text": "장소를 골라 주세요"}]}
    following = {**item, "id": "0-1", "title": "경복궁", "starts_at": "10:00", "ends_at": "12:00",
                 "kind": "activity", "place_state": "found", "parts": None, "status": "keep",
                 "place": {**PARK, "name": "경복궁", "latitude": 37.5796, "longitude": 126.9770}}
    return {"items": [item, following], "moves": []}


@pytest.fixture
def sources(monkeypatch):
    from app.domains.travel_ops.components.intake import taste

    calls = []

    def catalog(conn, tenant, ref, content_type, now, **kwargs):
        calls.append((ref, content_type, kwargs))
        return [{**HOTEL, "content_type_id": "32"}] if content_type == "32" else [dict(PARK)]

    monkeypatch.setattr(candidates, "_catalog_places", catalog)
    monkeypatch.setattr(candidates, "_original_class", lambda *args: None)
    monkeypatch.setattr(candidates, "_team_lodging_places", lambda *args: None)
    monkeypatch.setattr(taste, "profile", lambda *args: {})
    monkeypatch.setattr(taste, "places", lambda *args, **kwargs: [])
    monkeypatch.setattr(candidates, "_ledger_places", lambda *args, **kwargs: pytest.fail("숙소를 음식점에서 찾았습니다"))
    monkeypatch.setattr(candidates, "_db_places_by_name", lambda *args: [dict(HOTEL), dict(PARK)])
    monkeypatch.setattr(candidates, "assess", lambda *args: {
        "rows": [], "fits": True, "status": "ok", "slack": {}, "estimated": True})
    monkeypatch.setattr(autofix, "facts_for", lambda *args: SimpleNamespace(known=False))
    return calls, MapSearch()


@pytest.mark.parametrize("state", ["needs_choice", "customer", "found", "unresolved"])
@pytest.mark.parametrize("meal", [False, True])
def test_lodging_candidates_use_the_next_stop_and_exclude_other_activities(state, meal, sources):
    calls, kakao = sources
    view = review(state, meal=meal)
    got = candidates.alternatives(None, tenant_id="travel", review=view, item=view["items"][0],
                                 kakao=kakao, use_engine=False)
    assert got["candidates"], got
    assert {row["place"]["name"] for row in got["candidates"]} == {HOTEL["name"]}, got
    assert got["reference"]["after"] == "경복궁"
    assert calls and all(ref == (37.5796, 126.9770) and kind == "32" for ref, kind, _ in calls)


@pytest.mark.parametrize("meal", [False, True])
def test_lodging_search_never_returns_a_park_or_restaurant(meal, sources):
    _, kakao = sources
    view = review(meal=meal)
    got = candidates.search(None, tenant_id="travel", review=view, item=view["items"][0], query="호텔", kakao=kakao)
    assert {row["place"]["name"] for row in got["results"]} == {HOTEL["name"]}, got


def test_no_reference_point_is_reported_without_an_unanchored_map_search(sources):
    calls, kakao = sources
    view = review()
    view["items"] = view["items"][:1]
    got = candidates.alternatives(None, tenant_id="travel", review=view, item=view["items"][0],
                                 kakao=kakao, use_engine=False)
    assert got["notes"] == ["no_reference_point"] and got["candidates"] == []
    assert not calls and not kakao.asked


def test_a_named_area_wins_over_the_next_stop_and_far_hotels_are_excluded(sources, monkeypatch):
    calls, kakao = sources
    area = {"name": "성수", "latitude": 37.5449, "longitude": 127.0512, "radius_m": 1000}
    view = review(area=area)
    monkeypatch.setattr(candidates, "_catalog_places", lambda *args, **kwargs: [])
    got = candidates.alternatives(None, tenant_id="travel", review=view, item=view["items"][0],
                                 kakao=kakao, use_engine=False)
    assert got["candidates"] == [], got
    assert kakao.asked and kakao.asked[0][1] == (area["latitude"], area["longitude"])


@pytest.mark.parametrize("state", ["needs_choice", "customer"])
def test_autofix_preserves_breakfast_as_a_meal_when_picking_a_hotel(state, sources):
    _, kakao = sources
    view = review(state, meal=True)
    original = deepcopy(view)
    got = autofix.plan(None, tenant_id="travel", review=view, kakao=kakao, use_engine=False)
    assert got["changes"], got
    place = next(edit["value"] for edit in got["changes"][0]["edits"] if edit["field"] == "place")
    assert place["name"] == HOTEL["name"] and place["kind"] == "dining", got
    assert view == original


def test_a_reserved_hotel_without_a_name_is_never_replaced(sources):
    calls, kakao = sources
    view = review(meal=True)
    item = view["items"][0]
    item.update(place_state="needs_name", booked=True)
    got = candidates.alternatives(None, tenant_id="travel", review=view, item=item, kakao=kakao, use_engine=False)
    assert got["candidates"] == [] and got["notes"] == ["booked_needs_name"]
    changed = autofix.plan(None, tenant_id="travel", review=view, kakao=kakao, use_engine=False)
    assert changed["changes"] == [] and changed["kept"][0]["reason"] == "booked"
    assert not calls and not kakao.asked
