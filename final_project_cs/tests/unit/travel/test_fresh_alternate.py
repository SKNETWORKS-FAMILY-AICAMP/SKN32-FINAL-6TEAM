# -*- coding: utf-8 -*-
"""「다른 데로 바꿔 줘」 — 후보를 **실제로 다 뒤져도** 없을 때만 「없어요」, 그 이유를 싣는다. `[2026-09-29]`"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import NoChange, plan_fresh_alternate

KST = ZoneInfo("Asia/Seoul")


def _place(name, kind, lat, lon, hours=("09:00", "22:00")):
    return {"place_id": uuid4(), "name": name, "kind": kind, "latitude": lat, "longitude": lon,
            "attributes": {"hours": list(hours), "payment": ["card", "cash"]}}


def _item(place, hour):
    return Item(item_id=uuid4(), seq=1, kind=place["kind"], title=f"{place['name']} 식사", place_id=place["place_id"],
                starts_at=datetime(2030, 1, 1, hour, tzinfo=KST), ends_at=datetime(2030, 1, 1, hour + 1, tzinfo=KST),
                place=place)


def _plan(item, places):
    return plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[item], places=places,
                                item_id=item.item_id, message="다른 데로 바꿔 줘", request_id="r1")


def test_a_nearby_open_place_is_chosen_and_the_rest_become_other_options():
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    near_a = _place("가까운 식당", "dining", 37.5705, 126.9805)
    near_b = _place("조금 먼 식당", "dining", 37.5712, 126.9812)
    plan = _plan(_item(home, 12), [home, near_a, near_b])
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "가까운 식당" and plan.notice["other_options"] == ["조금 먼 식당"]


def test_no_alternate_only_when_nothing_fits_and_it_says_why():
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    closed = _place("그 시각 닫는 식당", "dining", 37.5705, 126.9805, hours=("17:00", "22:00"))
    far = _place("먼 식당", "dining", 37.6500, 127.0800)
    plan = _plan(_item(home, 12), [home, closed, far])
    assert isinstance(plan, NoChange) and plan.status == "no_alternate"
    assert plan.detail["rejected"], plan.detail                          # 무엇이 왜 떨어졌는지


def test_a_replacement_never_repeats_a_place_already_in_the_trip():
    """`[2026-09-29 ui 세션 지적]` 점심을 바꿨더니 같은 날 저녁 식당이 골라져 하루에 같은 곳이 두 번 들어갔다.
    일정 짜기와 같게 여행 전체에서 이미 쓴 곳은 뺀다 — 다른 장소 행이어도 **이름이 같으면** 같은 곳이다."""
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    dinner_spot = _place("저녁 식당", "dining", 37.5705, 126.9805)          # 가장 가깝다 — 전에는 이게 골라졌다
    same_name_row = {**_place("저녁 식당", "dining", 37.5706, 126.9806)}     # 같은 가게의 다른 장소 행
    other = _place("다른 식당", "dining", 37.5712, 126.9812)
    lunch, dinner = _item(home, 12), _item(dinner_spot, 18)
    dinner = replace(dinner, seq=2)
    plan = plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[lunch, dinner],
                                places=[home, dinner_spot, same_name_row, other], item_id=lunch.item_id,
                                message="다른 데로 바꿔 줘", request_id="r2")
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "다른 식당" and "저녁 식당" not in plan.notice["other_options"]


def test_when_nothing_is_near_it_widens_the_search_before_saying_no():
    """`[2026-09-29 ui 세션 지적]` 700m 안에 0곳이면 1.5km · 3km 로 넓혀 다시 찾는다(08:00 아침이 「없어요」로 끝났다)."""
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    two_km = _place("2km 식당", "dining", 37.5880, 126.9800)
    plan = _plan(_item(home, 12), [home, two_km])
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "2km 식당"


def test_saying_no_names_the_time_the_distance_and_the_main_reason():
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    closed = _place("아침엔 닫는 식당", "dining", 37.5705, 126.9805, hours=("11:00", "22:00"))
    plan = _plan(_item(home, 8), [home, closed])
    assert isinstance(plan, NoChange) and plan.status == "no_alternate"
    assert "08:00" in plan.detail["text"] and "3km" in plan.detail["text"], plan.detail
    assert "살펴본 곳: 아침엔 닫는 식당 — 그 시각 영업하지 않는다" in plan.detail["text"] and plan.detail["radius_m"] == 3000


def test_an_activity_is_not_replaced_by_the_same_site_under_another_name():
    """`[2026-09-29 ui 세션 지적]` 「건청궁 대신 경복궁」 — 건청궁은 경복궁 안 전각이라 사실상 같은 곳이다."""
    from app.modules.travel_ops.itinerary_changes import same_site

    gyeongbok = {"name": "경복궁", "latitude": 37.576, "longitude": 126.9767, "attributes": {}}
    geoncheong = {"name": "건청궁", "latitude": 37.57608, "longitude": 126.97674,
                  "attributes": {"address": "서울특별시 종로구 사직로 161 (세종로)"}}
    garden = {"name": "창덕궁과 후원 [유네스코 세계유산]", "latitude": 37.57765, "longitude": 126.99023, "attributes": {}}
    tree = {"name": "창덕궁 다래나무", "latitude": 37.58645, "longitude": 126.98923, "attributes": {}}
    market = {"name": "광장시장", "latitude": 37.5700, "longitude": 126.9996, "attributes": {}}
    assert same_site(gyeongbok, geoncheong) and same_site(garden, tree)
    assert not same_site(gyeongbok, market) and not same_site(garden, gyeongbok)

    home = _place("건청궁", "activity", 37.57608, 126.97674)
    inside = _place("경복궁", "activity", 37.5760, 126.9767)
    other = _place("국립민속박물관", "activity", 37.5815, 126.9790)
    plan = _plan(_item(home, 10), [home, inside, other])
    assert not isinstance(plan, NoChange), plan
    assert plan.summary["to"] == "국립민속박물관" and "경복궁" not in plan.notice["other_options"]


def _at(place, day_hour, seq):
    item = _item(place, day_hour)
    return replace(item, seq=seq, title=place["name"])


def test_when_nothing_opens_at_that_time_it_offers_a_later_time_instead_of_a_dead_end():
    """`[2026-09-29 사용자 지적]` 「08:00에 여는 식당이 없어요」로 끝내지 않는다 — 늦추면 되는 안을 계산해 **묻는다**."""
    home = _place("원래 식당", "dining", 37.5700, 126.9800)
    nine = _place("9시에 여는 식당", "dining", 37.5705, 126.9805, hours=("09:00", "22:00"))
    breakfast = _at(home, 8, 1)
    palace = _at(_place("경복궁", "activity", 37.5760, 126.9767), 11, 2)
    plan = plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[breakfast, palace],
                                places=[home, nine], item_id=breakfast.item_id, message="다른 데로 바꿔 줘",
                                request_id="r")
    assert isinstance(plan, NoChange) and plan.status == "relaxed", plan
    first = plan.detail["options"][0]
    assert (first["name"], first["relaxed"], first["starts_at"][11:16]) == ("9시에 여는 식당", "time", "09:00")
    assert "09:00으로 늦추면 9시에 여는 식당" in plan.detail["text"] and "답이 없으면 원래 일정을 그대로" in plan.detail["text"]


def test_a_place_near_the_next_stop_is_offered_when_moving_the_time_does_not_help():
    home = _place("원래 식당", "dining", 37.5000, 126.9000)
    near_next = _place("경복궁 옆 식당", "dining", 37.5765, 126.9770, hours=("07:00", "22:00"))
    breakfast = _at(home, 8, 1)
    palace = _at(_place("경복궁", "activity", 37.5760, 126.9767), 10, 2)         # 원래 식당 둘레(8km 밖)엔 늦춰도 없다
    plan = plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[breakfast, palace],
                                places=[home, near_next], item_id=breakfast.item_id, message="다른 데로 바꿔 줘",
                                request_id="r")
    assert isinstance(plan, NoChange) and plan.status == "relaxed", plan
    assert [(o["name"], o["relaxed"]) for o in plan.detail["options"]] == [("경복궁 옆 식당", "near_next")]


def _activity(name, lat, lon, address=None):
    place = _place(name, "activity", lat, lon)
    place["weather_sensitive"] = False
    if address:
        place["attributes"]["address"] = address
    return place


def test_the_same_building_is_not_offered_twice_nor_again_next_to_the_trip():
    """☆`[2026-09-29 ui 세션 지적]` 「K-컬처 스크린(대한민국역사박물관)」과 「대한민국역사박물관」(같은 주소 · 6m)이 바뀐 곳과
    다른 안에 함께 나왔고, 경복궁을 바꾼 뒤 건청궁(경복궁 안)을 바꾸자 이미 든 박물관과 같은 건물이 다시 나왔다."""
    home = _activity("원래 공원", 37.5700, 126.9800)
    screen = _activity("K-컬처 스크린(대한민국역사박물관)", 37.5705, 126.9805, "서울특별시 종로구 세종대로 198 (세종로)")
    museum = _activity("대한민국역사박물관", 37.57051, 126.98051, "서울특별시 종로구 세종대로 198 (세종로)")
    other = _activity("다른 미술관", 37.5720, 126.9830)
    plan = _plan(_item(home, 10), [home, screen, museum, other])
    assert not isinstance(plan, NoChange), plan
    shown = [plan.summary["to"], *plan.notice["other_options"]]
    assert shown.count("대한민국역사박물관") + shown.count("K-컬처 스크린(대한민국역사박물관)") == 1, shown
    assert "다른 미술관" in shown
    # 일정의 다른 활동이 그 박물관이면 같은 건물은 후보가 아니다
    later = replace(_item(museum, 14), seq=2)
    first = _item(home, 10)
    plan = plan_fresh_alternate(trip={"constraints": {}}, trip_version=1, base_version=1, items=[first, later],
                                places=[home, screen, museum, other], item_id=first.item_id,
                                message="다른 데로 바꿔 줘", request_id="r2")
    assert not isinstance(plan, NoChange) and plan.summary["to"] == "다른 미술관", plan
    assert "K-컬처 스크린(대한민국역사박물관)" not in plan.notice["other_options"]


def test_the_planner_keeps_one_of_the_same_site():
    """☆`[2026-09-29 ui 세션 지적]` 일정 짜기가 경복궁(10:10)과 건청궁(13:15, 경복궁 안 · 10m)을 같은 날 따로 넣었다."""
    from app.modules.travel_ops.planner import Cand, distinct_sites

    def cand(name, lat, lon):
        return Cand(key=name, name=name, kind="activity", lat=lat, lon=lon, attributes={}, origin="places")

    kept = distinct_sites([cand("경복궁", 37.5760, 126.9767), cand("건청궁", 37.57608, 126.97674),
                           cand("국립고궁박물관", 37.57659, 126.97497), cand("창덕궁과 후원", 37.5794, 126.9910),
                           cand("창덕궁 다래나무", 37.5830, 126.9920)])
    assert [c.name for c in kept] == ["경복궁", "국립고궁박물관", "창덕궁과 후원"]
