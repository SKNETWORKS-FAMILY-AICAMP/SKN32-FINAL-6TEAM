# -*- coding: utf-8 -*-
"""후보 고르기가 **종류를 지킨다** — 숙소 줄은 숙소 후보를, 분류를 모르는 활동 줄은 쇼핑을 빼고 고른다. `[2026-10-07 사용자 지적]`

사용자 지적(배포 서버의 실제 응답으로 확인): ①「호텔」 줄의 대안이 없다(전에는 카카오로 줬다) ②「경복궁」 대체가 약국이다.
원인: ①숙소 줄의 분류 번호(32)는 제대로 넘어가는데 카탈로그 조회가 **활동 분류(12 · 14 · 28 · 38)만 읽어** 숙박이 늘 0 이었고, 카카오 검색은 숙소 줄에서 막혀 있었다.
②원래 장소가 우리 장소 표의 행이면 분류 값이 비어(활동 522곳 중 194곳만 있다) 거르지 않았고, 카탈로그는 쇼핑(38)이 4,360건으로 가장 많아 가까운 순에 약국 · 편의점이 먼저 나왔다.

★지키려는 것
 ①숙박(32) 분류를 주면 **숙박 후보**가 나온다(관광지 · 쇼핑은 안 섞인다)
 ②분류를 **모르면** 쇼핑(38)은 뺀다 — 관광지의 대체로 약국을 권하지 않는다. 쇼핑을 찾는 줄(분류 38)은 그대로 쇼핑이 나온다
 ③원래 장소의 분류를 모를 때는 **같은 이름의 목록 항목**에서 찾고, 이름이 여러 분류에 걸치거나 목록에 없으면 모른다(지어내지 않는다)
 ④숙소 줄에서 카카오로 찾아도 음식점은 걸러지고 숙소만 남는다

재현:

    python -m pytest tests/e2e/test_intake_candidate_kinds.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.intake import candidates
from app.domains.travel_ops.components.intake.candidates import _catalog_places, _original_type
from app.infrastructure.db.session import get_connection

from .test_intake_review import _catalog, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401

NOW = datetime(2030, 1, 5, 9, 0, tzinfo=timezone(timedelta(hours=9)))
REF = (37.5796, 126.9770)                       # 경복궁 근처
ADDRESS = "서울특별시 종로구 사직로 161"


@pytest.fixture()
def around(rv):  # noqa: F811
    """경복궁 둘레에 숙박 · 쇼핑 · 관광지 · 음식점을 한 곳씩(분류 32 · 38 · 12 · 39) 심는다."""
    _catalog(rv, "920001", "32", "광화문호텔", 37.5790, 126.9772, ADDRESS)
    _catalog(rv, "920002", "38", "우정약국 종로", 37.5797, 126.9771, ADDRESS)            # 쇼핑 — 가장 가깝다
    _catalog(rv, "920003", "12", "북촌한옥마을", 37.5820, 126.9830, ADDRESS)
    _catalog(rv, "920004", "39", "광화문식당", 37.5795, 126.9769, ADDRESS)              # 음식점 — 활동 분류가 아니다
    _catalog(rv, "920005", "12", "경복궁", 37.5796, 126.9770, ADDRESS)                  # 이름으로 분류를 찾을 대상
    yield rv


def _names(rows):
    return [row["name"] for row in rows]


def test_a_lodging_type_reads_lodging_places_and_nothing_else(around):
    with get_connection() as conn:
        found = _catalog_places(conn, around["tenant"], REF, "32", NOW)
    assert _names(found) == ["광화문호텔"] and found[0]["content_type_id"] == "32" and found[0]["kind"] == "activity"   # 숙소 줄은 「활동」 쪽 종류로 거른다(기존 규칙)


def test_an_unknown_type_leaves_shopping_out_but_a_shopping_type_still_finds_shops(around):
    with get_connection() as conn:
        unknown = _catalog_places(conn, around["tenant"], REF, None, NOW)
        shopping = _catalog_places(conn, around["tenant"], REF, "38", NOW)
    assert "우정약국 종로" not in _names(unknown) and {"북촌한옥마을", "경복궁"} <= set(_names(unknown))
    assert {row["content_type_id"] for row in unknown} <= {"12", "14", "28"}                          # 쇼핑 · 숙박 · 음식점이 안 섞인다
    assert _names(shopping) == ["우정약국 종로"]                                                       # 쇼핑을 찾는 줄은 그대로 쇼핑


def test_a_known_type_still_filters_to_that_type(around):
    with get_connection() as conn:
        sights = _catalog_places(conn, around["tenant"], REF, "12", NOW)
    assert {row["content_type_id"] for row in sights} == {"12"} and "우정약국 종로" not in _names(sights)


def test_the_original_type_is_taken_from_the_given_value_then_from_the_same_name_in_the_list(around):
    tenant = around["tenant"]
    with get_connection() as conn:
        assert _original_type(conn, tenant, {"name": "아무개", "content_type_id": "14"}) == "14"          # 준 값이 먼저다
        assert _original_type(conn, tenant, {"name": "경복궁"}) == "12"                                   # 같은 이름의 목록 항목
        assert _original_type(conn, tenant, {"name": "목록에 없는 곳"}) is None                            # 모르면 모른다
        assert _original_type(conn, tenant, None) is None and _original_type(conn, tenant, {"name": " "}) is None


def test_a_name_that_spans_two_types_is_unknown_not_guessed(around):
    _catalog(around, "920006", "38", "경복궁", 37.5801, 126.9775, ADDRESS)                               # 같은 이름이 쇼핑에도 있다
    with get_connection() as conn:
        assert _original_type(conn, around["tenant"], {"name": "경복궁"}) is None


def test_the_untyped_default_names_shopping_only(around):
    assert candidates.UNTYPED_EXCLUDES == ("38",) and candidates.LODGING_TYPE == "32" and candidates.SHOPPING_TYPE == "38"


# ── 웹 입구까지: 호텔 줄이 카카오로 숙소 후보를 받고 음식점은 버린다 ──────────────
class _LodgingKakao:
    """카카오 흉내 — 「숙소」를 찾으면 호텔과 호텔 식당이 같이 나온다(실제 지도 검색이 그렇다)."""
    LODGING = {"id": "21", "name": "광화문스테이호텔", "category": "여행 > 숙박 > 호텔", "category_group": "AD5",
               "address": "서울 종로구 사직로 100", "latitude": 37.5780, "longitude": 126.9760}
    RESTAURANT = {"id": "22", "name": "호텔 뷔페 광화문", "category": "음식점 > 뷔페", "category_group": "FD6",
                  "address": "서울 종로구 사직로 101", "latitude": 37.5781, "longitude": 126.9761}

    def __init__(self):
        self.asked = []

    def search(self, query, size=5, near=None):
        self.asked.append((query, near))
        return [dict(self.LODGING), dict(self.RESTAURANT)] if "숙소" in query else []


def test_a_hotel_breakfast_line_gets_lodging_candidates_from_the_map_and_never_a_restaurant(around):
    from .test_intake_review import _client, _item, _key, _send

    around  # 카탈로그에도 광화문호텔(숙박)이 있다 — 목록 후보와 카카오 후보가 같이 온다
    client, _tour, kakao = _client(kakao=_LodgingKakao())
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n09:00 호텔 조식\n11:00 경복궁")
    hotel = _item(view, "호텔")
    got = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={hotel['source_id']}&index={hotel['index']}"
                     f"&revision={view['revision']}", headers=headers).json()
    names = [c["place"]["name"] for c in got["candidates"]]
    assert "광화문스테이호텔" in names, got                                    # 카카오의 숙박이 후보로 온다(전에는 숙소 줄에서 이 길이 막혀 있었다)
    assert "호텔 뷔페 광화문" not in names                                       # 음식점은 버린다 — 「호텔인데 왜 식당이야」
    assert any(query == "숙소" for query, _near in kakao.asked)                  # 「숙소」로 찾았다(가게 이름처럼 「호텔 조식」을 묻지 않았다)
    _assert_stays_come_with_their_meal(got)


def _assert_stays_come_with_their_meal(got):
    """`[2026-10-07 사용자]` 숙소 후보마다 **같은 숙소 안 식사** 짝이 붙는다 — 이름이 같고 종류만 식사다. 지도의 음식점(호텔 뷔페)은 여전히 안 나온다."""
    stays = [c for c in got["candidates"] if c["basis"] == "lodging"]
    meals = [c for c in got["candidates"] if c["basis"] == "lodging_meal"]
    assert stays and meals, got
    assert all(c["place"]["kind"] == "activity" for c in stays) and all(c["place"]["kind"] == "dining" for c in meals)
    assert {c["place"]["name"] for c in meals} <= {c["place"]["name"] for c in stays}                  # 숙소 이름 그대로(식당 이름을 지어내지 않는다)
    assert "stay_and_meal" in got["notes"]
    assert all(c["reason"].startswith("숙소 후보예요") for c in stays)
    assert all(c["reason"].startswith("이 숙소 안에서 식사하는 경우예요(숙소 안 식당이 있는지는 확인하지 못했어요)") for c in meals)


def test_a_bare_hotel_line_without_breakfast_gets_the_same_two_kinds_of_candidates(around):
    from .test_intake_review import _client, _item, _key, _send

    client, _tour, _kakao = _client(kakao=_LodgingKakao())
    headers = _key(client)
    view = _send(client, headers, "2026-10-15\n09:00 호텔\n11:00 경복궁")
    hotel = _item(view, "호텔")
    assert hotel["kind"] == "activity", hotel                                   # 「조식」이 없는데 식사로 읽지 않는다
    got = client.get(f"/v1/web/trip-intakes/{view['intake_id']}/candidates?source_id={hotel['source_id']}&index={hotel['index']}"
                     f"&revision={view['revision']}", headers=headers).json()
    assert "호텔 뷔페 광화문" not in [c["place"]["name"] for c in got["candidates"]]
    _assert_stays_come_with_their_meal(got)
