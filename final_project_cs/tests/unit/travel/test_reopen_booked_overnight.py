# -*- coding: utf-8 -*-
"""수정 모드 핫픽스 — ST4F-491 두 건. DB 없이 돈다.

1. 예약번호 없이 「예약 완료」로 등록한 일정(`detail.booking = {declared_by: customer_plan}`)을 다시 열어도 예약 표시가 접수에 실리고, 시각을 고쳐 새 항목이 돼도 예약 표시가 남는다
2. 자정을 넘는 일정은 수정 접수에 넣지 않고 고정으로 둔다(끝 날짜를 접수에 담지 못해 「완료」가 time_order 로 막히던 것)

재현:

    python -m pytest tests/unit/travel/test_reopen_booked_overnight.py -v
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.intake import reopen
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 14, 9, 0, tzinfo=KST)
PLACE = {"place_id": str(uuid4()), "name": "북촌한옥마을", "kind": "activity", "latitude": 37.58, "longitude": 126.98, "attributes": {}}


def _item(starts: str, ends: str | None, *, detail=None, title="북촌한옥마을", kind="activity") -> Item:
    return Item(item_id=uuid4(), seq=1, kind=kind, title=title, place_id=uuid4(), place=dict(PLACE),
                starts_at=datetime.fromisoformat(starts).replace(tzinfo=KST),
                ends_at=datetime.fromisoformat(ends).replace(tzinfo=KST) if ends else None, detail=detail or {})


def _row(origin: Item, **over) -> dict:
    base = {"source_id": "s1", "index": 0, "title": origin.title, "kind": origin.kind, "locked": False, "place": dict(PLACE) | {"place_id": origin.place_id},
            "date": origin.starts_at.date().isoformat(), "start": origin.starts_at.strftime("%H:%M"),
            "end": origin.ends_at.strftime("%H:%M") if origin.ends_at else None,
            "booking_no": None, "booked": None, "provenance": {}, "claims": {"ends_at": {}}}
    return base | over


def _plan(origin: Item, row: dict):
    return reopen.plan_edit(rows=[row], origin_of={("s1", 0): origin.item_id}, base_items=[origin], frozen_ids=set(),
                            intake_id="i1", revision=1, now=NOW)


def test_a_booking_without_a_number_is_carried_into_the_edit_intake():
    item = _item("2026-10-15T10:00", "2026-10-15T11:30", detail={"booking": {"declared_by": "customer_plan"}})
    fields = {name.split(".", 1)[1]: value for name, value, _ in reopen._claims_for(0, item, {})}
    assert fields["booked"] is True and "booking_no" not in fields


def test_a_booking_with_a_number_still_carries_the_number_only():
    item = _item("2026-10-15T10:00", "2026-10-15T11:30", detail={"booking": {"booking_no": "A-1", "declared_by": "customer_plan"}})
    fields = {name.split(".", 1)[1]: value for name, value, _ in reopen._claims_for(0, item, {})}
    assert fields["booking_no"] == "A-1" and "booked" not in fields


def test_no_booking_adds_no_booked_line():
    item = _item("2026-10-15T10:00", "2026-10-15T11:30")
    assert "booked" not in {name.split(".", 1)[1] for name, _, _ in reopen._claims_for(0, item, {})}


def test_changing_the_time_keeps_the_booking_mark_on_the_new_item():
    origin = _item("2026-10-15T10:00", "2026-10-15T11:30", detail={"booking": {"declared_by": "customer_plan"}})
    plan = _plan(origin, _row(origin, start="10:30", end="12:00", booked=True))
    new = next(i for i in plan.items if i.item_id != origin.item_id)
    assert new.replaces_item_id == origin.item_id
    assert new.detail["booking"] == {"declared_by": "customer_plan"}               # 예약번호 없이 예약 표시만


def test_an_untouched_booked_item_is_not_a_change():
    origin = _item("2026-10-15T10:00", "2026-10-15T11:30", detail={"booking": {"declared_by": "customer_plan"}})
    plan = _plan(origin, _row(origin, booked=True))
    assert plan.unchanged and plan.items == [origin]


def test_turning_the_booking_off_is_a_change_and_drops_the_mark():
    origin = _item("2026-10-15T10:00", "2026-10-15T11:30", detail={"booking": {"declared_by": "customer_plan"}})
    plan = _plan(origin, _row(origin, booked=False))
    new = next(i for i in plan.items if i.item_id != origin.item_id)
    assert plan.changed and "booking" not in new.detail


def test_an_item_that_runs_past_midnight_is_frozen_not_editable():
    overnight = _item("2026-10-15T23:00", "2026-10-16T01:00")
    assert reopen._editable(overnight, NOW) is False


def test_a_same_day_item_stays_editable():
    assert reopen._editable(_item("2026-10-15T22:00", "2026-10-15T23:30"), NOW) is True
    assert reopen._editable(_item("2026-10-15T22:00", None), NOW) is True
