"""산책 항목의 음식점 우회 회귀 — 실제 장소 조회와 원문 항목 분리를 실행한다.

공용 장소 표·관광공사·요식 원장·로마자 확인이 식사로 바꾸는 경로를 막는다.
외부 소스와 모델 응답만 고정하며 DB·네트워크를 호출하지 않는다.
"""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake.pipeline import read_source
from app.domains.travel_ops.components.intake.places import resolve


def _place(name, *, kind="dining"):
    return {"place_id": "p-" + name, "name": name, "kind": kind,
            "latitude": 37.579, "longitude": 126.970}


def _source_place(name, *, kind="39"):
    return {"matched_title": name, "content_id": "c-" + name,
            "content_type_id": kind, "latitude": 37.579, "longitude": 126.970,
            "address": "서울특별시 종로구"}


class NamedSource:
    def __init__(self, entries):
        self.entries = entries
        self.misses = {}

    def find(self, name, **_):
        return self.entries.get(name)


class Kakao:
    def __init__(self, entries):
        self.entries = entries

    def search(self, query, **_):
        return self.entries.get(query, [])


class Chat:
    def __init__(self, quotes):
        self.quotes = quotes

    def json(self, system, user):
        return {"spans": [{"line": 2, "quote": quote, "role": "place"}
                          for quote in self.quotes]}


def _hit(name, *, group="FD6"):
    return {"id": "k-" + name, "name": name, "category_group": group,
            "category": "음식점 > 한식", "address": "서울특별시 종로구",
            "latitude": 37.579, "longitude": 126.970}


@pytest.mark.parametrize("source", ["our_places", "dining", "tour"])
def test_an_explicit_activity_does_not_take_a_restaurant_branch_from_an_earlier_source(source):
    options = {"our_places": []}
    if source == "our_places":
        options[source] = [_place("서촌 광화문점")]
    else:
        options[source] = NamedSource({"서촌": _source_place("서촌 광화문점")})

    found = resolve("서촌", kind_hint="activity", **options)

    assert found.status == "unresolved" and found.needs_review is True
    assert found.kind != "dining"


@pytest.mark.parametrize("source", ["our_places", "dining", "tour"])
def test_an_explicit_activity_keeps_a_shop_whose_full_name_was_written(source):
    name = "블루보틀 성수점"
    options = {"our_places": []}
    if source == "our_places":
        options[source] = [_place(name)]
    else:
        options[source] = NamedSource({name: _source_place(name)})

    found = resolve(name, kind_hint="activity", **options)

    assert found.status == "resolved" and found.name == name


def test_an_explicit_full_shop_name_wins_over_another_branch_in_our_places():
    found = resolve("블루보틀 성수점", kind_hint="activity",
                    our_places=[_place("블루보틀 성수점"), _place("블루보틀 삼청점")])

    assert (found.status, found.name, found.place_id) == (
        "resolved", "블루보틀 성수점", "p-블루보틀 성수점")


@pytest.mark.parametrize("source", ["our_places", "tour", "dining", "kakao"])
def test_a_parenthesized_restaurant_branch_is_not_the_named_neighbourhood(source):
    name = "서촌(광화문점)"
    options = {"our_places": []}
    if source == "our_places":
        options[source] = [_place(name)]
    elif source == "kakao":
        options[source] = Kakao({"서촌": [_hit(name)]})
    else:
        options[source] = NamedSource({"서촌": _source_place(name)})

    found = resolve("서촌", kind_hint="activity", **options)

    assert found.status == "unresolved" and found.needs_review is True
    assert found.kind != "dining"


@pytest.mark.parametrize("source", ["tour", "dining"])
def test_rechecking_a_kakao_activity_name_does_not_take_a_restaurant(source):
    hit = _hit("서촌 골목", group="")
    hit["category"] = "여행 > 관광,명소"
    found = resolve("서촌", kind_hint="activity", our_places=[],
                    kakao=Kakao({"서촌": [hit]}),
                    **{source: NamedSource({"서촌 골목": _source_place("서촌 골목 밥집")})})

    assert (found.status, found.name, found.kind) == ("resolved", "서촌 골목", "activity")


@pytest.mark.parametrize("source", ["tour", "dining"])
def test_a_romanized_activity_does_not_take_a_confirmed_restaurant(source):
    found = resolve("Seochon", kind_hint="activity", our_places=[],
                    kakao=Kakao({"Seochon": [_hit("서촌닭갈비")]}),
                    **{source: NamedSource({"서촌닭갈비": _source_place("서촌닭갈비")})})

    assert found.status == "unresolved" and found.needs_review is True
    assert found.kind != "dining"


def test_a_romanized_activity_still_takes_a_confirmed_sight():
    found = resolve("Seochon", kind_hint="activity", our_places=[],
                    kakao=Kakao({"Seochon": [_hit("서촌", group="")]}),
                    tour=NamedSource({"서촌": _source_place("서촌", kind="12")}))

    assert (found.status, found.name, found.kind) == ("resolved", "서촌", "activity")


def test_food_search_results_do_not_reclassify_a_confirmed_activity_as_a_meal():
    found = resolve("서촌 골목", kind_hint="activity", our_places=[],
                    kakao=Kakao({"서촌 골목": [_hit("서촌닭갈비"), _hit("서촌만두")]}),
                    tour=NamedSource({"서촌": _source_place("서촌", kind="12")}))

    assert (found.name, found.kind) == ("서촌", "activity")
    assert found.item_kind != "dining"


def test_an_activity_in_a_rule_read_title_does_not_take_a_known_restaurant_branch():
    rows = read_source("2026-10-15\n14:00 서촌 산책", our_places=[_place("서촌 광화문점")],
                       today=date(2026, 10, 14))
    place = next(row for row in rows if row["field"] == "items[0].place")

    assert place["value"] is None and place["needs_review"] is True
    assert not any(row["field"] == "items[0].kind" and row["value"] == "dining" for row in rows)


@pytest.mark.parametrize("sentence,quotes", [
    ("서촌 걷다가 점심은 통인시장 근처에서 해결하고 싶어요", ["서촌", "통인시장"]),
    ("통인시장에서 점심 먹고 서촌 골목 걷자", ["통인시장", "서촌"]),
])
def test_a_meal_and_a_walk_on_the_same_line_keep_their_own_place_kinds(sentence, quotes):
    dining = NamedSource({"서촌": _source_place("서촌닭갈비"),
                          "통인시장": _source_place("통인시장밥집")})
    rows = read_source("2026-10-15\n" + sentence, our_places=[], dining=dining,
                       chat=Chat(quotes), today=date(2026, 10, 14))
    indexes = {row["value"]: row["field"].split(".")[0]
               for row in rows if row["field"].endswith(".title")}
    places = {row["field"]: row for row in rows if row["field"].endswith(".place")}
    walk = places[indexes["서촌"] + ".place"]
    meal = places[indexes["통인시장"] + ".place"]

    assert walk["value"] is None and walk["needs_review"] is True
    assert meal["value"]["name"] == "통인시장밥집" and meal["value"]["kind"] == "dining"
    assert not any(row["field"] == indexes["서촌"] + ".kind" and row["value"] == "dining" for row in rows)
