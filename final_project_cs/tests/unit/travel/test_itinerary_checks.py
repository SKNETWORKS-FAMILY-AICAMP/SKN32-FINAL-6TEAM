# -*- coding: utf-8 -*-
"""일정을 받을 때의 판정 — v11 §12 DoD-2(코드로 판정) · DoD-3(이유와 완화 조건을 붙여 거절).

★**모르면 판정하지 않는다**(결정 15). 영업시간·결제·예산·경로 소요가 **보낸 값에 없으면** 그 항목은
  위반으로 세지 않는다 — 그 자리는 감시 루프가 실제 소스로 본다. 아래 마지막 절이 그것을 고정한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary_checks import Part, check_itinerary

KST = ZoneInfo("Asia/Seoul")


def _at(hhmm: str) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 9, 23, int(hour), int(minute), tzinfo=KST)


def _part(seq, title, start, end=None, *, kind="activity", place=None, route=None):
    return Part(seq=seq, kind=kind, title=title, starts_at=_at(start),
                ends_at=_at(end) if end else None, place=place, route=route)


def _place(name, **attributes):
    return {"name": name, "attributes": attributes}


def _codes(violations):
    return sorted(v.code for v in violations)


ROUTE = {"planned": "subway", "options": [{"id": "subway", "label": "2호선 직통", "eta_min": 13},
                                          {"id": "bus", "label": "버스", "eta_min": 25}]}


# ── 잡아야 하는 것 ─────────────────────────────────────────────
def test_an_item_that_ends_before_it_starts():
    found = check_itinerary([_part(1, "전망대", "10:00", "09:30")])
    assert _codes(found) == ["time_order"] and "끝나는 시각" in found[0].reason


def test_two_items_that_overlap():
    found = check_itinerary([_part(1, "전망대", "10:00", "11:00"), _part(2, "점심", "10:30", "11:30")])
    assert _codes(found) == ["overlap"]
    assert found[0].seq == (1, 2) and "11:00 뒤로" in found[0].remedy    # 앞 항목이 끝나는 시각


def test_a_move_shorter_than_the_planned_option():
    found = check_itinerary([_part(1, "전망대", "10:00", "10:45"),
                             _part(2, "잠실 → 성수", "10:50", "10:55", kind="mobility", route=ROUTE)])
    assert _codes(found) == ["move_too_short"]
    assert "13분" in found[0].reason and "13분 이상" in found[0].remedy


def test_zero_minutes_between_two_districts():
    found = check_itinerary([_part(1, "전망대", "10:00", "11:00", place=_place("잠실", district="송파구")),
                             _part(2, "쇼핑", "11:00", "12:00", place=_place("성수", district="성동구"))])
    assert _codes(found) == ["no_transfer_time"]


def test_outside_opening_hours_and_inside_the_break():
    lunch = _place("성수 식당", hours=["11:00", "21:00"], break_=None)
    found = check_itinerary([_part(1, "이른 방문", "10:00", "10:30", place=lunch),
                             _part(2, "늦은 방문", "21:30", "22:00", place=lunch)])
    assert _codes(found) == ["after_closing", "before_opening"]
    assert "11:00" in found[0].remedy

    breaking = _place("브레이크 있는 식당", hours=["11:00", "21:00"], **{"break": ["15:00", "17:00"]})
    found = check_itinerary([_part(1, "늦은 점심", "14:40", "15:20", place=breaking)])
    assert _codes(found) == ["break_time"] and "17:00 이후" in found[0].remedy


def test_a_place_that_does_not_take_the_agreed_payment():
    cash_only = _place("현금만", payment=["cash"])
    found = check_itinerary([_part(1, "저녁", "18:00", "19:00", place=cash_only)],
                            constraints={"payment": "card"})
    assert _codes(found) == ["payment_not_accepted"] and "card" in found[0].remedy


def test_a_plan_over_the_budget_counts_heads():
    pricey = _place("전망대", price_krw=31000)
    found = check_itinerary([_part(1, "전망대", "10:00", "11:00", place=pricey)],
                            constraints={"budget_krw": 50000}, party_size=2)
    assert _codes(found) == ["over_budget"]
    assert "62,000원" in found[0].reason and "12,000원" in found[0].remedy


def test_every_violation_carries_a_reason_and_a_remedy():
    """★고칠 방법을 안 주면 거절이 벽이 된다(DoD-3)."""
    found = check_itinerary([_part(1, "전망대", "10:00", "09:30"),
                             _part(2, "점심", "09:00", "10:30", place=_place("식당", hours=["11:00", "21:00"]))])
    assert found and all(v.reason and v.remedy for v in found)


# ── 잡지 말아야 하는 것 ────────────────────────────────────────
def test_the_confirmed_scenario_day_passes_as_submitted():
    """확정 시나리오 하루는 그대로 받아야 한다 — 이 판정이 운영을 막으면 안 된다."""
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parents[3] / "app" / "modules" / "travel_ops" /
                       "scenarios" / "seoul_day_taiwan_friends.json").read_text(encoding="utf-8"))
    places = {place["key"]: {"name": place["name"], "attributes": place["attributes"]}
              for place in data["places"]}
    parts = [Part(seq=it["seq"], kind=it["kind"], title=it["title"], starts_at=_at(it["start"]),
                  ends_at=_at(it["end"]), place=places.get(it.get("place")),
                  route=data["routes"].get(it.get("route")))
             for it in data["items"]]
    assert check_itinerary(parts, constraints=data["trip"]["constraints"],
                           party_size=data["trip"]["party_size"]) == []


def test_what_we_do_not_know_is_not_a_violation():
    """영업시간·결제·예산·경로 소요를 **모르면** 판정하지 않는다 — 지어내지 않는다(결정 15)."""
    bare = _place("이름만 아는 곳")
    parts = [_part(1, "어딘가", "03:00", "04:00", place=bare),
             _part(2, "이동", "04:00", "04:01", kind="mobility",
                   route={"planned": "walk", "options": [{"id": "walk", "label": "걷기"}]}),
             _part(3, "다른 곳", "04:01", "05:00", place=_place("다른 곳"))]
    assert check_itinerary(parts, constraints={"payment": "card", "budget_krw": None} | {}) == []


def test_zero_minutes_inside_one_district_is_fine():
    same = [_part(1, "쇼핑", "11:15", "13:00", place=_place("성수", district="성동구")),
            _part(2, "점심", "13:00", "13:50", place=_place("성수 식당", district="성동구"))]
    assert check_itinerary(same) == []
