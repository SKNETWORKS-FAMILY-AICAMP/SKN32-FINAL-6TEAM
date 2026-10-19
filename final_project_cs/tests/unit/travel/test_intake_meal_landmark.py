# -*- coding: utf-8 -*-
"""시장 · 동네 이름의 식사 — 「광장시장 점심」은 광장시장 **안이나 근처**의 식당이다. `[2026-10-13]`

☆테스트 서버에서 「광장시장 점심」이 용산의 「광장시장 바베큐 용산점」이 됐다 — 이름이 「광장시장」으로 시작할 뿐인 가게를
  앞뒤 일정 근처에서 골랐다. 결함: wiki/records/reports/debugs/2026-10-13_시장_점심이_다른_동네의_같은_이름_가게가_된다.md
★순서: 장소(시장) 좌표를 정한다 → 그 근처 원장 식당 → 없으면 카카오 근처 음식점 → 그래도 없으면 시장 자체를 식사 자리로.
★언제나 확인 필요 — 원문은 가게 이름을 말하지 않았다.
★`[2026-10-19 계획서 진단 포인트 2]` **시장은 구역 그대로**로 바뀌었다 — 시장 끼니는 근처 가게를 고르지 않고 시장이 장소다(삼모녀꼬마김밥 24회).
  근처 식당 고르기(원장 → 카카오 · 간식 가게 거르기)는 시장이 아닌 곳(관광지 · 한옥마을)의 끼니에서 그대로 쓴다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.intake.places import resolve

MARKET = (37.5700, 126.9996)            # 광장시장
YONGSAN = (37.5290, 126.9640)           # 용산 — 동명 가게가 있는 곳


class Tour:
    def __init__(self, known):
        self.known = known

    def find(self, name, area_code=None, **_):
        if name not in self.known:
            return None
        lat, lon, kind = self.known[name]
        return {"matched_title": name, "content_id": "c-" + name, "content_type_id": kind,
                "latitude": lat, "longitude": lon, "address": "서울특별시 종로구"}


class Kakao:
    def __init__(self, hits, around=None):
        self.hits, self.around, self.near_asked = hits, around or {}, []

    def search(self, query, size=5, near=None, **kw):
        if near is not None:
            self.near_asked.append((query, near, kw.get("category_group_code"), kw.get("radius")))
            return self.around.get(query, [])
        return self.hits.get(query, [])


class Ledger:
    """요식 원장 흉내 — 이름으로는 못 찾고(시장은 가게가 아니다), 좌표 근처 식당만 돌려준다."""

    def __init__(self, near_shop=None):
        self.near_shop, self.meal_asked = near_shop, []
        self.misses = {}

    def find(self, name, **_):
        return None

    def find_dish_near(self, text, latitude, longitude):
        return None

    def find_meal_near(self, latitude, longitude):
        self.meal_asked.append((latitude, longitude))
        return self.near_shop


def _hit(name, at, group="", category=""):
    return {"id": name, "name": name, "category": category, "category_group": group, "address": "서울 종로구",
            "latitude": at[0], "longitude": at[1]}


SHOP = {"matched_title": "박가네빈대떡 본점", "content_id": "c-park", "content_type_id": "39",
        "latitude": 37.5701, "longitude": 126.9993, "address": "서울특별시 종로구 종로32길 5",
        "dining_place_uid": "uid-park", "category": "한식", "match": "meal_near", "needs_review": True,
        "note": "「광장시장」 근처 식당", "others": 0}


def test_a_meal_at_a_market_found_in_the_catalog_stays_at_the_market():
    """★`[2026-10-19 계획서 진단 포인트 2]` 시장은 **구역**이다 — 근처 원장 식당 하나로 좁히지 않는다.
    ☆광장시장이 시장 안 가게 하나(삼모녀꼬마김밥)로 24번 좁혀졌다(세 환경 첫 검토판). 전에는 이 시험이 「원장 식당을 고른다」를 지켰다."""
    ledger = Ledger(SHOP)
    found = resolve("광장시장", kind_hint="dining", our_places=[], dining=ledger,
                    tour=Tour({"광장시장": (*MARKET, "38")}))
    assert (found.status, found.name, found.kind, found.item_kind) == ("resolved", "광장시장", "activity", "dining")
    assert ledger.meal_asked == []                          # ★근처 가게를 찾지도 않는다


def test_a_market_named_only_by_kakao_is_the_anchor_not_a_same_named_shop_elsewhere():
    """☆회귀 — 카카오가 「광장시장」(시장)과 「광장시장 바베큐 용산점」(가게)을 함께 돌려줘도 동명 가게를 고르지 않는다. 시장 그대로다."""
    ledger = Ledger(SHOP)
    kakao = Kakao({"광장시장": [_hit("광장시장", MARKET, "", "쇼핑 > 전통시장"),
                               _hit("광장시장 바베큐 용산점", YONGSAN, "FD6", "음식점 > 고기")]})
    found = resolve("광장시장", kind_hint="dining", our_places=[], dining=ledger, kakao=kakao, near=YONGSAN)
    assert (found.name, found.item_kind) == ("광장시장", "dining") and ledger.meal_asked == []


# ── 시장이 아닌 곳(관광지 · 한옥마을)의 끼니 — 그 근처 식당(확인 필요) ─────────────────
#: 「북촌한옥마을 점심」 — 가게가 아니고 시장도 아닌 곳. 끼니는 그 근처 식당이다(위 시장 규칙과 다르다)
BUKCHON = (37.5826, 126.9837)


def _bukchon(around):
    return Kakao({"북촌한옥마을": [_hit("북촌한옥마을", BUKCHON, "", "여행 > 관광,명소 > 한옥마을")]}, around={"북촌한옥마을": around})


def test_without_a_ledger_shop_kakao_restaurants_near_the_landmark_are_used():
    kakao = _bukchon([_hit("북촌손만두", (37.5824, 126.9835), "FD6", "음식점 > 한식")])
    found = resolve("북촌한옥마을", kind_hint="dining", our_places=[], dining=Ledger(None), kakao=kakao)
    assert (found.method, found.name, found.kind, found.needs_review) == ("kakao", "북촌손만두", "dining", True)
    assert kakao.near_asked and kakao.near_asked[0][1] == BUKCHON and kakao.near_asked[0][2] == "FD6"


def test_a_snack_shop_is_not_the_meal_even_when_it_is_the_nearest_restaurant():
    """★`[2026-10-14 테스트 서버 접수 cbd50b1d]` 「점심은 통인시장 근처에서」가 카카오 근처 음식점 중 가장 가까운 「도깨비한과강정」(한과)이 됐다 —
    카카오는 간식 · 제과 · 카페도 음식점으로 묶는다. 원장 길(`ledger.find_meal_near`)처럼 끼니가 아닌 가게는 거른다.
    `[2026-10-19]` 시장은 이제 구역 그대로라 이 규칙은 시장이 아닌 곳의 끼니에서 본다."""
    kakao = _bukchon([_hit("도깨비한과강정", (37.58255, 126.98365), "FD6", "음식점 > 간식 > 떡,한과"),
                      _hit("북촌제과", (37.5825, 126.9836), "FD6", "음식점 > 간식 > 제과,베이커리"),
                      _hit("북촌손만두", (37.5824, 126.9835), "FD6", "음식점 > 한식")])
    found = resolve("북촌한옥마을", kind_hint="dining", our_places=[], dining=Ledger(None), kakao=kakao)
    assert (found.method, found.name, found.kind) == ("kakao", "북촌손만두", "dining")


def test_tteokbokki_is_a_meal_even_though_it_starts_with_tteok():
    """★`[2026-10-14 리뷰]` 「떡」을 부분 문자열로 거르니 「음식점 > 분식 > 떡볶이」도 빠졌다 — 분류 항목 단위로 본다."""
    kakao = _bukchon([_hit("한과집", (37.58255, 126.98365), "FD6", "음식점 > 간식 > 떡,한과"),
                      _hit("마약떡볶이", (37.5825, 126.9836), "FD6", "음식점 > 분식 > 떡볶이")])
    found = resolve("북촌한옥마을", kind_hint="dining", our_places=[], dining=Ledger(None), kakao=kakao)
    assert (found.method, found.name) == ("kakao", "마약떡볶이")


@pytest.mark.parametrize("category", ["음식점 > 떡, 한과", "음식점 > 제과, 베이커리",
                                     "음식점 > 카페 > 커피전문점", "음식점 > 아이스크림"])
def test_snack_category_components_are_excluded_without_a_snack_parent(category):
    kakao = _bukchon([_hit("가까운간식가게", (37.58255, 126.98365), "FD6", category),
                      _hit("북촌떡볶이", (37.5825, 126.9836), "FD6", "음식점 > 분식 > 떡볶이")])
    found = resolve("북촌한옥마을", kind_hint="dining", our_places=[], dining=Ledger(None), kakao=kakao)
    assert (found.method, found.name) == ("kakao", "북촌떡볶이")


def test_when_only_snack_shops_are_around_the_market_itself_is_the_meal_place():
    kakao = Kakao({"광장시장": [_hit("광장시장", MARKET, "", "쇼핑 > 전통시장")]},
                  around={"광장시장": [_hit("도깨비한과강정", (37.57005, 126.99962), "FD6", "음식점 > 간식 > 떡,한과")]})
    found = resolve("광장시장", kind_hint="dining", our_places=[], dining=Ledger(None), kakao=kakao)
    assert found.name == "광장시장" and found.item_kind == "dining"


def test_with_no_restaurant_around_the_market_itself_is_the_meal_place():
    """시장 끼니의 장소는 시장 그대로다 — 원문이 가리킨 곳이 맞으므로 `[2026-10-19]` 부터 확인을 재촉하지 않는다(전에는 확인 필요)."""
    found = resolve("광장시장", kind_hint="dining", our_places=[], dining=Ledger(None), kakao=Kakao({}),
                    tour=Tour({"광장시장": (*MARKET, "38")}))
    assert (found.status, found.name) == ("resolved", "광장시장")
    assert found.item_kind == "dining" and found.needs_review is False


def test_a_market_that_is_not_a_meal_stays_an_activity():
    ledger = Ledger(SHOP)
    found = resolve("광장시장", our_places=[], dining=ledger, tour=Tour({"광장시장": (*MARKET, "38")}))
    assert found.name == "광장시장" and ledger.meal_asked == []


def test_a_restaurant_named_in_the_catalog_is_kept_as_it_is():
    """관광공사 자리가 식당(39)을 찾았으면 그 가게다 — 근처를 다시 찾지 않는다."""
    ledger = Ledger(SHOP)
    found = resolve("토속촌삼계탕", kind_hint="dining", our_places=[], dining=ledger,
                    tour=Tour({"토속촌삼계탕": (37.578, 126.971, "39")}))
    assert found.name == "토속촌삼계탕" and ledger.meal_asked == []


# ── 원장 — 장소 근처 식당 ─────────────────────────────────────────
def _shop(name, at, category="한식"):
    return {"place_uid": "uid-" + name, "name": name, "latitude": at[0], "longitude": at[1], "address": "서울특별시 종로구",
            "category": category, "content_id": None, "key": name, "base": name}


def test_the_ledger_picks_the_nearest_meal_shop_inside_the_radius_and_skips_cafes():
    from app.domains.travel_ops.instances.dining.ledger import find_meal_near

    shops = [_shop("광장커피", (37.57001, 126.99961), "카페디저트"),     # 가장 가깝지만 끼니가 아니다
             _shop("박가네빈대떡 본점", (37.5702, 126.9994)),
             _shop("광장시장 바베큐 용산점", YONGSAN, "양식")]               # 동명이지만 4km 밖
    found = find_meal_near(None, MARKET, shops=shops)
    assert found["matched_title"] == "박가네빈대떡 본점" and found["needs_review"] is True
    assert find_meal_near(None, MARKET, shops=[_shop("광장시장 바베큐 용산점", YONGSAN)]) is None
