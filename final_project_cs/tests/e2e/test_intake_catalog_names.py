# -*- coding: utf-8 -*-
"""접수가 이름을 못 찾을 때 우리 장소 목록(`place_catalog`)에서 찾는다 — 표기 차이(공백 · 괄호)로 놓치던 호텔. `[2026-10-15 사용자 지시 — 코어]`

☆왜: x600 서버에서 「더 플라자 호텔 서울 체크인」이 늘 `unresolved` 였다 — 관광공사 검색은 제목이 **글자 그대로** 같아야 받는데 목록의 이름은 「더플라자호텔」(공백 없음)이고, 숙소(분류 32)는
  우리 장소 표(`places`)에도 없다. 게다가 검색은 호출 예산이 바닥나면(`budget_exhausted`) 아무것도 못 찾는다. 그래서 이름 있는 호텔마다 고객이 후보에서 한 번 골라야 했다.

★지키려는 것
 ①공백 · 괄호 · 구분 기호를 무시한 제목이 **정확히 같은 곳이 하나**면 장소로 확정한다(좁혀 찾은 경우처럼 확인 표시는 남는다)
 ②같은 이름이 둘 이상이면 고르지 않는다(지어내지 않는다) · 부분 일치(「경복궁」 ↔ 「경복궁 별빛야행」)는 받지 않는다
 ③관광공사 조회가 찾았으면 그 결과를 쓴다 — 이 길은 **못 찾았을 때만** 돈다
 ④관광공사 조회가 막혀(예산 소진) 있어도 이름 있는 호텔이 확정된다 — 막힘을 이유로 「조회가 막혀 못 찾았다」고 하지 않는다

재현:

    python -m pytest tests/e2e/test_intake_catalog_names.py -v
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.intake.catalog_names import TourThenCatalog

from .test_intake_review import _catalog, _client, _item, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401

PLAN = "2030-11-06\n15:00 {name} 체크인\n17:00 경복궁\n2030-11-07\n11:00 체크아웃"
ADDRESS = "서울특별시 중구 소공로 119"


class _NoTour:
    """관광공사 검색 대역 — 아무것도 못 찾고, 막혔다고 말한다."""

    def __init__(self, blocked=False):
        self.misses = {"budget_exhausted": 1} if blocked else {}
        self.asked = []

    def find(self, name, area_code=None, **_):
        self.asked.append(name)
        return None


@pytest.fixture()
def hotels(rv):  # noqa: F811
    _catalog(rv, "930001", "32", "더플라자호텔", 37.5655, 126.9780, ADDRESS)
    _catalog(rv, "930002", "12", "시험기념관(별칭)", 37.5671, 127.0090, "서울특별시 중구 을지로 281")
    _catalog(rv, "930003", "32", "중복스테이", 37.5700, 126.9900, ADDRESS)
    _catalog(rv, "930004", "32", "중복 스테이", 37.5800, 126.9800, ADDRESS)
    _catalog(rv, "930005", "12", "경복궁 별빛야행", 37.5796, 126.9770, ADDRESS)
    yield rv


def _plan(name, tour=None, plan=PLAN):
    client, _tour, kakao = _client(tour=tour or _NoTour())
    headers = _key(client)
    return _send(client, headers, plan.format(name=name)), _tour, kakao


def test_a_hotel_written_with_other_spacing_is_found_in_our_list(hotels):
    view, tour, _kakao = _plan("더 플라자 호텔")
    stay = _item(view, "더 플라자 호텔")
    assert stay["place_state"] == "found" and stay["place"]["name"] == "더플라자호텔", stay
    assert stay["place"]["content_type_id"] == "32" and stay["kind"] == "lodging", stay


def test_a_bracketed_alias_in_the_list_title_is_the_same_name(hotels):
    # ★`[2026-10-20]` 「체크인」 줄이면 숙소 자료에서만 찾는다(2026-10-19 장소 종류 먼저 판정) — 기념관은 관람 줄로 둔다
    view, _tour, _kakao = _plan("시험 기념관", plan="2030-11-06\n15:00 {name}\n17:00 경복궁")
    spot = next(i for i in view["review"]["items"] if "기념관" in i["title"])
    assert spot["place_state"] == "found" and spot["place"]["name"] == "시험기념관(별칭)", spot      # 괄호 병기와 띄어쓰기를 무시하고 같은 이름


def test_two_places_with_the_same_normalized_name_are_not_guessed(hotels):
    view, _tour, _kakao = _plan("중복스테이")
    stay = _item(view, "중복스테이")
    assert stay["place_state"] == "unresolved", stay                     # 같은 이름이 둘 — 고르지 않는다


def test_a_partial_title_is_not_accepted(hotels):
    view, _tour, _kakao = _plan("경복궁")
    palace = next(i for i in view["review"]["items"] if i["title"] == "경복궁")
    # 「경복궁」은 목록의 「경복궁 별빛야행」으로 가지 않는다(부분 일치 아님) — 우리 장소 표에서 찾거나 못 찾는다
    assert palace["place"] is None or palace["place"]["name"] != "경복궁 별빛야행", palace


def test_the_tour_lookup_wins_when_it_finds_the_place(hotels):
    class Finds(_NoTour):
        def find(self, name, area_code=None, **_):
            self.asked.append(name)
            if name == "더 플라자 호텔":
                return {"matched_title": "더 플라자 호텔 (관광공사)", "content_id": "777", "content_type_id": "32",
                        "latitude": 37.5, "longitude": 126.9, "address": ADDRESS}
            return None

    view, _tour, _kakao = _plan("더 플라자 호텔", tour=Finds())
    stay = _item(view, "더 플라자 호텔")
    assert stay["place"]["name"] == "더 플라자 호텔 (관광공사)", stay          # 목록의 「더플라자호텔」이 아니라 관광공사가 찾은 쪽


def test_a_blocked_tour_lookup_does_not_stop_a_hotel_that_our_list_has(hotels):
    view, tour, _kakao = _plan("더 플라자 호텔", tour=_NoTour(blocked=True))
    stay = _item(view, "더 플라자 호텔")
    assert stay["place_state"] == "found" and stay["place"]["name"] == "더플라자호텔", stay
    assert tour.asked, "관광공사 조회를 먼저 했다"


def test_the_fallback_wrapper_only_asks_our_list_when_the_tour_lookup_found_nothing():
    class Catalog:
        def __init__(self):
            self.asked = []

        def find(self, name, **_):
            self.asked.append(name)
            return {"matched_title": "목록"}

    class Tour:
        misses = {"x": 1}
        images = staticmethod(lambda *a, **k: ["사진"])

        def __init__(self, answer):
            self.answer = answer

        def find(self, name, **_):
            return self.answer

    catalog = Catalog()
    assert TourThenCatalog(Tour({"matched_title": "관광공사"}), catalog).find("a") == {"matched_title": "관광공사"} and catalog.asked == []
    wrapped = TourThenCatalog(Tour(None), catalog)
    assert wrapped.find("b") == {"matched_title": "목록"} and catalog.asked == ["b"]
    assert wrapped.misses == {"x": 1} and wrapped.images("1") == ["사진"], "나머지는 원래 조회에 맡긴다"
    assert TourThenCatalog(None, catalog).find("c") == {"matched_title": "목록"} and TourThenCatalog(None, catalog).misses == {}
