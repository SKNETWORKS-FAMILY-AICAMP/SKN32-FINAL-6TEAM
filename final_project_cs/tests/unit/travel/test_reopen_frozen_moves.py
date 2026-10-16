# -*- coding: utf-8 -*-
"""수정 모드 — 고정 일정(지난 일정 · 항공 · 숙소) 옆 구간의 이동. `[2026-10-15 ST4F-490]` DB 없이 돈다.

1. 이미 끝난 이동은 앞뒤 일정이 바뀌어도 새 판에 남는다(`reopen.plan_edit`)
2. 재검사가 검증한 「고정 ↔ 접수 일정」 구간 이동을 「완료」 때 넣는다 — 구간의 고정 쪽 id 는 여행 일정 id(`registered_moves.fill_edited_moves`)
3. 아침 「고정 숙소 → 그날 첫 일정」 구간(`from_stay`)은 그날 첫 일정 **앞**에 넣고, 이미 그 자리에 이동이 있으면 두지 않는다

재현:

    python -m pytest tests/unit/travel/test_reopen_frozen_moves.py -v
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.intake import reopen
from app.domains.travel_ops.components.intake.registered_moves import fill_edited_moves
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=KST)


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=KST)


def _stop(title: str, starts: str, ends: str, *, kind: str = "activity") -> Item:
    place = {"place_id": str(uuid4()), "name": title, "kind": kind, "latitude": 37.58, "longitude": 126.98, "attributes": {}}
    return Item(item_id=uuid4(), seq=1, kind=kind, title=title, place_id=uuid4(), place=place, starts_at=_at(starts), ends_at=_at(ends), detail={})


def _move(title: str, starts: str, ends: str, **detail) -> Item:
    return Item(item_id=uuid4(), seq=1, kind="mobility", title=title, place_id=None, starts_at=_at(starts), ends_at=_at(ends), detail=dict(detail))


def _seq(*items: Item) -> list[Item]:
    return [replace(item, seq=n) for n, item in enumerate(items, start=1)]


def _row(origin: Item, **over) -> dict:
    base = {"source_id": "s1", "index": 0, "title": origin.title, "kind": origin.kind, "locked": False,
            "place": dict(origin.place) | {"place_id": origin.place_id}, "date": origin.starts_at.date().isoformat(),
            "start": origin.starts_at.strftime("%H:%M"), "end": origin.ends_at.strftime("%H:%M") if origin.ends_at else None,
            "booking_no": None, "booked": None, "provenance": {}, "claims": {"ends_at": {}}}
    return base | over


def _review_move(frm: str, to: str, depart: str, arrive: str, **extra) -> dict:
    return {"from": frm, "to": to, "depart": depart, "arrive": arrive, "mode": "subway", "mode_label": "지하철",
            "minutes": 16, "summary": "지하철 16분", "basis": "timetable", "uses": [], **extra}


def test_a_move_that_is_already_over_stays_even_when_the_stop_after_it_changes():
    past, gone, now_stop = (_stop("경복궁", "2026-10-15T09:00", "2026-10-15T10:30"),
                            _move("경복궁 → 북촌", "2026-10-15T10:30", "2026-10-15T10:50"),
                            _stop("북촌한옥마을", "2026-10-15T11:00", "2026-10-15T13:00"))
    base = _seq(past, gone, now_stop)
    row = _row(base[2], start="11:10", end="13:10")                     # 진행 중 일정의 시각을 고친다
    plan = reopen.plan_edit(rows=[row], origin_of={("s1", 0): base[2].item_id}, base_items=base,
                            frozen_ids={str(base[0].item_id)}, intake_id="i1", revision=1, now=NOW)
    kinds = [(i.kind, i.title) for i in plan.items]
    assert ("mobility", "경복궁 → 북촌") in kinds                         # ★지난 이동은 지나온 기록 — 빼지 않는다
    assert [i.seq for i in plan.items] == list(range(1, len(plan.items) + 1))


def test_a_move_still_ahead_beside_a_changed_stop_is_dropped_for_the_checked_one():
    flight, move, stop = (_stop("김포 도착", "2026-10-16T09:00", "2026-10-16T10:00", kind="flight"),
                          _move("김포공항 → 북촌", "2026-10-16T10:30", "2026-10-16T11:20"),
                          _stop("북촌한옥마을", "2026-10-16T11:30", "2026-10-16T13:00"))
    base = _seq(flight, move, stop)
    plan = reopen.plan_edit(rows=[_row(base[2], start="11:40", end="13:10")], origin_of={("s1", 0): base[2].item_id},
                            base_items=base, frozen_ids={str(base[0].item_id)}, intake_id="i1", revision=1, now=NOW)
    assert [i.kind for i in plan.items] == ["flight", "activity"]       # 아직 안 지난 옛 이동은 빠지고(다시 계산할 대상)
    fixed = str(base[0].item_id)
    review = {"items": [{"id": "0-0", "source_id": "s1", "index": 0}],
              "moves": [_review_move(fixed, "0-0", "10:40", "10:56")]}
    items, picked = fill_edited_moves(plan.items, review, plan.keys, fixed_ids=frozenset({fixed}))
    assert [i.kind for i in items] == ["flight", "mobility", "activity"]   # ★재검사가 검증한 이동이 들어간다
    added = items[1]
    assert (added.starts_at, added.ends_at) == (_at("2026-10-16T10:40"), _at("2026-10-16T10:56"))
    assert added.detail["route_def"]["planned"] == "subway" and picked == []
    # 고정 일정 id 를 모르면(옛 동작) 넣지 않는다 — 이 구간을 잇는 열쇠가 `fixed_ids` 다
    assert [i.kind for i in fill_edited_moves(plan.items, review, plan.keys)[0]] == ["flight", "activity"]


def test_the_morning_move_from_a_fixed_stay_goes_before_the_first_stop_of_that_day_once():
    stay = _stop("롯데호텔 서울", "2026-10-15T15:00", "2026-10-17T11:00", kind="lodging")
    first = _stop("북촌한옥마을", "2026-10-16T10:10", "2026-10-16T11:40")
    items = _seq(stay, first)
    keys = {first.item_id: ("s1", 0)}
    fixed = str(stay.item_id)
    review = {"items": [{"id": "0-0", "source_id": "s1", "index": 0}],
              "moves": [_review_move(fixed, "0-0", "09:40", "09:56", from_stay=True)]}
    out, _ = fill_edited_moves(items, review, keys, fixed_ids=frozenset({fixed}))
    assert [i.kind for i in out] == ["lodging", "mobility", "activity"]
    morning = out[1]
    assert morning.detail.get("from_stay") is True and morning.title == "롯데호텔 서울 → 북촌한옥마을"
    assert morning.starts_at == _at("2026-10-16T09:40")                  # 그날(첫 일정의 날짜) 시각
    # 그 자리에 이미 이동이 있으면 두 번 넣지 않는다(다시 불러도 같다)
    again, _ = fill_edited_moves(out, review, keys, fixed_ids=frozenset({fixed}))
    assert [i.kind for i in again] == ["lodging", "mobility", "activity"]
