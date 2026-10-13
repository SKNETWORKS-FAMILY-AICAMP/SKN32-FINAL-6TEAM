# -*- coding: utf-8 -*-
"""고를 때 숙소 가격 재확인(화면 고르기 앞). `[2026-10-13]` — 판정 · 문장은 숙소 팀 `_recheck` · `_price_note` 와 같다."""
from __future__ import annotations

from app.domains.travel_ops.components.booking.offers.recheck import price_note, recheck_stay

OPTION = {"key": "myrealtrip:12", "name": "둘째 호텔", "price_per_night": 150000, "price_basis": "detail"}


class Source:
    def __init__(self, detail):
        self.detail, self.calls = detail, []

    def stay_detail(self, **kwargs):
        self.calls.append(kwargs)
        return self.detail


def _check(detail, option=OPTION):
    source = Source(detail)
    return recheck_stay(source, option, check_in="2030-11-06", check_out="2030-11-09", adults=2), source


def test_same_changed_gone_and_unreadable():
    same, source = _check({"price_per_night": 150000})
    assert same["status"] == "same" and source.calls == [{"gid": 12, "check_in": "2030-11-06", "check_out": "2030-11-09", "adults": 2}]
    assert price_note(same) == " 지금 가격도 1박 150,000원 그대로예요."
    changed, _ = _check({"price_per_night": 171000})
    assert (changed["status"], changed["now"]) == ("changed", 171000)
    assert price_note(changed) == " 보여 드릴 때 1박 150,000원이던 가격이 지금 1박 171,000원이에요."
    assert _check({"no_rooms": True})[0]["status"] == "gone"
    cooling, _ = _check({"cooldown_seconds": 540})
    assert cooling["status"] == "unchecked" and "다시 확인하지 못했어요" in price_note(cooling)


def test_list_price_against_detail_price_is_said_as_a_basis_difference():
    changed, _ = _check({"price_per_night": 171000}, {**OPTION, "price_basis": "list"})
    assert price_note(changed) == " 목록에서는 1박 150,000원이었는데, 예약 화면 기준으로 지금 1박 171,000원이에요."


def test_other_keys_and_missing_sources_are_not_rechecked():
    other, source = _check({"price_per_night": 1}, {"key": "airbnb:x", "name": "x", "price_per_night": 100000})
    assert other["reason"] == "no_recheck_tool" and source.calls == [] and price_note(other) == ""
    google, source = _check({"price_per_night": 1}, {"key": "google:x", "name": "x", "price_per_night": 100000})
    assert google["reason"] == "source_unavailable" and source.calls == [], "구글 후보는 구글 소스로만 본다(SerpApi 키가 없으면 확인 못 함)"
    assert "다시 확인하지 못했어요" in price_note(google)
    assert recheck_stay(None, OPTION, check_in="2030-11-06", check_out="2030-11-09", adults=2)["reason"] == "source_unavailable"


class Google:
    def __init__(self, detail):
        self.detail, self.calls = detail, []

    def stay_detail(self, **kwargs):
        self.calls.append(kwargs)
        return self.detail


def test_a_google_hotel_is_rechecked_by_its_shown_sellers_lowest_price():
    """`[2026-10-13]` SerpApi 키가 생겨 구글 호텔 후보도 고를 때 다시 본다 — 판매처 최저가끼리(목록에 없는 판매처는 뺀다)."""
    option = {"key": "google:가까운호텔", "name": "가까운 호텔", "price_per_night": 120000, "price_from": 117000, "property_token": "tok-2"}
    google = Google({"sellers": [{"seller": "Vio.com", "price_per_night": 90000}, {"seller": "Agoda", "price_per_night": 125000},
                                 {"seller": "Trip.com", "price_per_night": 131000}]})
    got = recheck_stay(None, option, check_in="2030-11-06", check_out="2030-11-09", adults=2, google=google, keyword="중구")
    assert google.calls == [{"property_token": "tok-2", "keyword": "중구", "check_in": "2030-11-06", "check_out": "2030-11-09", "adults": 2}]
    assert (got["status"], got["before"], got["now"], got["basis"]) == ("changed", 117000, 125000, "sellers"), "Vio.com 은 보여 주는 판매처가 아니다"
    assert price_note(got) == " 보여 드릴 때 1박 117,000원~이던 판매처 최저가가 지금 1박 125,000원~이에요."
    empty = recheck_stay(None, option, check_in="2030-11-06", check_out="2030-11-09", adults=2, google=Google({"sellers": []}), keyword="중구")
    assert empty["status"] == "unchecked" and empty["reason"] == "no_price", "판매처가 없으면 「없어졌다」고 하지 않는다"
    no_key = recheck_stay(None, option, check_in="2030-11-06", check_out="2030-11-09", adults=2, google=None, keyword="중구")
    assert no_key["reason"] == "source_unavailable"


def test_the_seller_list_matches_the_lodging_team():
    from app.domains.travel_ops.components.booking.offers.recheck import SELLER_NAMES
    from app.domains.travel_ops.instances.lodging.team import SELLER_NAMES as TEAM

    assert SELLER_NAMES == TEAM, "재확인과 보여 주기가 같은 판매처끼리 비교해야 한다"


def test_a_google_hotel_is_compared_with_the_sellers_it_showed_not_the_list_price():
    """☆2026-10-13 x600 — 라인 호텔 명동: 「1박 173,845원~」은 구글 목록가였고 판매처 최저는 176,766원 — 그대로인데 「바뀜」으로 나왔다."""
    option = {"key": "google:라인호텔명동", "name": "라인 호텔 명동", "price_per_night": 173845, "price_from": 173845, "property_token": "tok",
              "sellers": [{"name": "클룩", "price_per_night": 176766}, {"name": "트립닷컴", "price_per_night": 178579}]}
    google = Google({"sellers": [{"seller": "Klook", "price_per_night": 176766}, {"seller": "Trip.com", "price_per_night": 178579}]})
    got = recheck_stay(None, option, check_in="2030-11-06", check_out="2030-11-09", adults=2, google=google, keyword="명동")
    assert (got["status"], got["before"], got["now"]) == ("same", 176766, 176766)
