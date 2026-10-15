# -*- coding: utf-8 -*-
"""수정 모드 — 잠금 일정과 지난 일정을 가른다(ST4F-490 · 2026-10-15 사용자 결정). DB 없이 돈다.

1. 숙소 · 항공 · 업체 예약 표에 묶인 일정은 고정이 아니라 **잠금**으로 접수에 들어온다(풀면 고칠 수 있다)
2. 고정으로 남는 일정에는 이유가 있다 — `past` · `overnight` · `no_place` · `kind`(화면은 `past` 만 「지난 일정」이라 부른다)
3. 정책 잠금은 풀기만 해서는 바뀐 것이 아니고, 고치면 업체 예약 연결 · 같은 곳의 세부를 이어받는다

재현:

    python -m pytest tests/unit/travel/test_reopen_locked_items.py -v
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.intake import reopen
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 15, 9, 0, tzinfo=KST)


def _place(name="김포공항"):
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.56, "longitude": 126.80, "attributes": {}}


def _item(kind: str, starts: str, ends: str | None, *, detail=None, booking_id=None, place=None, title="김포 도착") -> Item:
    place = place or _place()
    return Item(item_id=uuid4(), seq=1, kind=kind, title=title, place_id=place["place_id"], place=place,
                starts_at=datetime.fromisoformat(starts).replace(tzinfo=KST),
                ends_at=datetime.fromisoformat(ends).replace(tzinfo=KST) if ends else None,
                detail=detail or {}, booking_id=booking_id)


def _fields(item: Item) -> dict:
    return {name.split(".", 1)[1]: value for name, value, _ in reopen._claims_for(0, item, {})}


def _row(origin: Item, **over) -> dict:
    ends = origin.ends_at
    base = {"source_id": "s1", "index": 0, "title": origin.title, "kind": origin.kind, "locked": True,
            "place": dict(origin.place) | {"place_id": origin.place_id},
            "date": origin.starts_at.date().isoformat(), "start": origin.starts_at.strftime("%H:%M"),
            "end": ends.strftime("%H:%M") if ends else None,
            "end_date": ends.date().isoformat() if ends and ends.date() != origin.starts_at.date() else None,
            "booking_no": None, "booked": True if origin.booking_id else None, "provenance": {}, "claims": {"ends_at": {}}}
    return base | over


def _plan(origin: Item, row: dict):
    return reopen.plan_edit(rows=[row], origin_of={("s1", 0): origin.item_id}, base_items=[origin], frozen_ids=set(),
                            intake_id="i1", revision=1, now=NOW)


def test_tomorrows_flight_stay_and_vendor_booking_are_not_fixed():
    assert reopen.fixed_reason(_item("flight", "2026-10-16T09:00", "2026-10-16T10:00"), NOW) is None
    assert reopen.fixed_reason(_item("lodging", "2026-10-15T15:00", "2026-10-17T11:00"), NOW) is None      # 여러 날 묵어도
    assert reopen.fixed_reason(_item("lodging", "2026-10-14T15:00", "2026-10-16T11:00"), NOW) is None      # 묵는 중이어도
    assert reopen.fixed_reason(_item("activity", "2026-10-16T10:00", "2026-10-16T11:00", booking_id=uuid4()), NOW) is None


def test_fixed_items_say_why():
    assert reopen.fixed_reason(_item("flight", "2026-10-14T09:00", "2026-10-14T10:00"), NOW) == "past"
    assert reopen.fixed_reason(_item("lodging", "2026-10-13T15:00", "2026-10-15T09:00"), NOW) == "past"    # 체크아웃이 지났다
    assert reopen.fixed_reason(_item("activity", "2026-10-15T23:00", "2026-10-16T01:00"), NOW) == "overnight"
    assert reopen.fixed_reason(_item("flight", "2026-10-15T23:00", "2026-10-16T01:00"), NOW) == "overnight"
    no_coords = {**_place(), "latitude": None, "longitude": None}
    assert reopen.fixed_reason(_item("activity", "2026-10-16T10:00", "2026-10-16T11:00", place=no_coords), NOW) == "no_place"
    assert reopen.fixed_reason(_item("event", "2026-10-16T10:00", "2026-10-16T11:00"), NOW) == "kind"


def test_policy_locked_items_enter_locked_with_what_the_screen_needs():
    flight = _fields(_item("flight", "2026-10-16T09:00", "2026-10-16T10:00"))
    assert flight["locked"] is True and flight["kind"] == "flight" and "end_date" not in flight
    stay = _fields(_item("lodging", "2026-10-16T15:00", "2026-10-18T11:00", title="롯데호텔 서울"))
    assert stay["locked"] is True and (stay["date"], stay["ends_at"], stay["end_date"]) == ("2026-10-16", "11:00", "2026-10-18")
    vendor = _fields(_item("activity", "2026-10-16T10:00", "2026-10-16T11:00", booking_id=uuid4(), title="북촌한옥마을"))
    assert (vendor["locked"], vendor["vendor_booking"], vendor["booked"]) == (True, True, True)
    plain = _fields(_item("activity", "2026-10-16T10:00", "2026-10-16T11:00", title="북촌한옥마을"))
    assert "locked" not in plain and "vendor_booking" not in plain


def test_frozen_entries_read_old_and_new_shapes():
    old, new = str(uuid4()), str(uuid4())
    assert reopen.frozen_entries([old]) == [{"item_id": old, "reason": None}]             # 이유를 담기 전에 연 접수
    assert reopen.frozen_entries([{"item_id": new, "reason": "past"}]) == [{"item_id": new, "reason": "past"}]
    assert reopen.frozen_entries(None) == []


def test_unlocking_a_flight_alone_is_not_a_change():
    origin = _item("flight", "2026-10-16T09:00", "2026-10-16T10:00")
    plan = _plan(origin, _row(origin, locked=False))
    assert plan.unchanged and plan.items == [origin]


def test_an_untouched_stay_with_its_checkout_day_is_not_a_change():
    origin = _item("lodging", "2026-10-16T15:00", "2026-10-18T11:00", title="롯데호텔 서울")
    plan = _plan(origin, _row(origin))
    assert plan.unchanged and plan.items == [origin]


def test_moving_a_flight_keeps_its_detail_and_writes_no_customer_pin():
    origin = _item("flight", "2026-10-16T09:00", "2026-10-16T10:00", detail={"flight_no": "KE1234", "customer_pinned": True})
    plan = _plan(origin, _row(origin, start="10:00", end="11:00"))
    new = next(i for i in plan.items if i.item_id != origin.item_id)
    assert new.replaces_item_id == origin.item_id and new.detail["flight_no"] == "KE1234"
    assert "customer_pinned" not in new.detail                                             # 다시 열면 늘 잠금이다


def test_a_vendor_booked_stop_keeps_its_booking_when_its_time_changes():
    booking = uuid4()
    origin = _item("activity", "2026-10-16T10:00", "2026-10-16T11:00", booking_id=booking, title="북촌한옥마을")
    plan = _plan(origin, _row(origin, start="10:30", end="11:30", locked=False))
    new = next(i for i in plan.items if i.item_id != origin.item_id)
    assert new.booking_id == booking and "booking" not in new.detail                      # 연결 유지 · 예약 표시를 지어 붙이지 않는다


def test_moving_a_stay_to_another_hotel_does_not_carry_the_old_hotels_detail():
    origin = _item("lodging", "2026-10-16T15:00", "2026-10-18T11:00", title="롯데호텔 서울", detail={"price_per_night": 200000})
    other = _place("신라호텔")
    plan = _plan(origin, _row(origin, title="신라호텔", place=other, locked=False))
    new = next(i for i in plan.items if i.item_id != origin.item_id)
    assert new.replaces_item_id == origin.item_id and "price_per_night" not in new.detail
    assert new.ends_at == datetime(2026, 10, 18, 11, 0, tzinfo=KST)                       # 체크아웃 날 그대로
