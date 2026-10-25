# -*- coding: utf-8 -*-
"""일정 추가 · 수정의 지난 때 규칙(`reopen.plan_edit` — 웹 「일정 수정」과 채팅 고치기가 같은 「완료」를 쓴다). `[2026-10-26 사용자 확정]` DB 없이 돈다.

1. 새로 넣거나 바꾸는 날짜 · 시각은 지금 이후만 — 지난 때에 새 일정을 만들거나(끝이 앞으로여도) 지난 때로 옮기면 `past`
2. 이미 지난 일정은 삭제만 허용한다 — `[2026-10-26 사용자 확정 — 삭제만]` 이름 등 무엇이든 고치면 `past`(앞 규칙 「이름 수정 허용」을 대체, `test_past_stop_delete_only.py`)
3. 진행 중이거나 앞으로 올 일정이 하나는 남아야 한다 — 마지막 하나를 빼거나 지난 때로 옮기면 `no_upcoming`
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import reopen, reopen_commit
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 26, 12, 0, 30, tzinfo=KST)


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=KST)


def _stop(title: str, starts: str, ends: str) -> Item:
    place = {"place_id": str(uuid4()), "name": title, "kind": "activity", "latitude": 37.58, "longitude": 126.98, "attributes": {}}
    return Item(item_id=uuid4(), seq=1, kind="activity", title=title, place_id=uuid4(), place=place, starts_at=_at(starts),
                ends_at=_at(ends), detail={})


def _seq(*items: Item) -> list[Item]:
    return [replace(item, seq=n) for n, item in enumerate(items, start=1)]


def _row(origin: Item, index: int = 0, **over) -> dict:
    base = {"source_id": "s1", "index": index, "title": origin.title, "kind": origin.kind, "locked": False,
            "place": dict(origin.place) | {"place_id": origin.place_id}, "date": origin.starts_at.date().isoformat(),
            "start": origin.starts_at.strftime("%H:%M"), "end": origin.ends_at.strftime("%H:%M") if origin.ends_at else None,
            "booking_no": None, "booked": None, "provenance": {}, "claims": {"ends_at": {}}}
    return base | over


def _new(index: int, date: str, start: str, end: str, title: str = "덕수궁") -> dict:
    return {"source_id": "s1", "index": index, "title": title, "kind": "activity", "locked": False, "place": None, "date": date,
            "start": start, "end": end, "booking_no": None, "booked": None, "provenance": {}, "claims": {"ends_at": {}}}


def _plan(base, rows, origin_of, frozen=()):
    return reopen.plan_edit(rows=rows, origin_of=origin_of, base_items=base, frozen_ids={str(i) for i in frozen},
                            intake_id="i1", revision=1, now=NOW)


def _trip():
    return _seq(_stop("창덕궁", "2026-10-26T09:00", "2026-10-26T10:00"),        # 지났다
                _stop("경복궁", "2026-10-26T11:00", "2026-10-26T13:00"),        # 진행 중
                _stop("남산", "2026-10-27T15:00", "2026-10-27T17:00"))          # 앞으로


def _all_rows(base):
    return [_row(item, n) for n, item in enumerate(base)], {("s1", n): item.item_id for n, item in enumerate(base)}


def test_adding_a_stop_that_started_before_now_is_past_even_if_it_ends_later():
    base = _trip()
    rows, origin_of = _all_rows(base)
    plan = _plan(base, [*rows, _new(3, "2026-10-26", "11:30", "13:30")], origin_of)
    assert plan.past == ["덕수궁"]


def test_adding_a_stop_from_now_on_is_allowed():
    base = _trip()
    rows, origin_of = _all_rows(base)
    plan = _plan(base, [*rows, _new(3, "2026-10-26", "12:00", "13:30")], origin_of)
    assert plan.past == [] and plan.added == ["덕수궁"]


def test_a_past_stop_may_be_removed_but_not_renamed_or_moved():
    base = _trip()
    rows, origin_of = _all_rows(base)
    renamed = _plan(base, [_row(base[0], 0, title="창덕궁 후원"), *rows[1:]], origin_of)
    assert renamed.past == ["창덕궁"]                                    # `[2026-10-26 사용자 확정 — 삭제만]` 이름도 고치지 않는다
    removed = _plan(base, rows[1:], origin_of)
    assert removed.past == [] and removed.removed == ["창덕궁"]
    moved = _plan(base, [_row(base[0], 0, date="2026-10-28", start="09:00", end="10:00"), *rows[1:]], origin_of)
    assert moved.past == ["창덕궁"]                                      # 지난 일정의 날짜 · 시각은 바꾸지 않는다(앞으로 옮기는 것도)


def test_a_running_stop_may_stay_longer_but_not_restart_in_the_past():
    base = _trip()
    rows, origin_of = _all_rows(base)
    longer = _plan(base, [rows[0], _row(base[1], 1, end="14:00"), rows[2]], origin_of)
    assert longer.past == []
    restarted = _plan(base, [rows[0], _row(base[1], 1, start="11:30", end="13:00"), rows[2]], origin_of)
    assert restarted.past == ["경복궁"]
    ended = _plan(base, [rows[0], _row(base[1], 1, end="12:00"), rows[2]], origin_of)
    assert ended.past == ["경복궁"]                                      # 끝을 지금 이전으로 당기면 지난 때로 옮긴 것이다


def test_a_future_stop_cannot_be_moved_into_the_past():
    base = _trip()
    rows, origin_of = _all_rows(base)
    plan = _plan(base, [*rows[:2], _row(base[2], 2, date="2026-10-25")], origin_of)
    assert plan.past == ["남산"]


def test_the_last_running_or_future_stop_cannot_be_removed():
    base = _seq(_stop("창덕궁", "2026-10-26T09:00", "2026-10-26T10:00"), _stop("남산", "2026-10-27T15:00", "2026-10-27T17:00"))
    rows, origin_of = _all_rows(base)
    plan = _plan(base, rows[:1], origin_of)
    assert plan.past == [] and plan.no_upcoming is True
    kept = _plan(base, rows[1:], origin_of)                              # 지난 것을 빼고 앞으로 일정이 남으면 된다
    assert kept.no_upcoming is False


def test_a_frozen_future_stop_counts_as_remaining():
    flight = replace(_stop("김포 출발", "2026-10-28T09:00", "2026-10-28T10:00"), kind="flight")
    base = _seq(_stop("남산", "2026-10-27T15:00", "2026-10-27T17:00"), flight)
    plan = _plan(base, [], {("s1", 0): base[0].item_id}, frozen=[base[1].item_id])
    assert plan.removed == ["남산"] and plan.no_upcoming is False


@pytest.mark.parametrize("plan,code", [(reopen.EditPlan(items=[], removed=["남산"], no_upcoming=True), "no_upcoming_items"),
                                       (reopen.EditPlan(items=[], added=["덕수궁"], past=["덕수궁"]), "item_in_past")])
def test_commit_refuses_before_any_write(monkeypatch, plan, code):
    from contextlib import nullcontext
    from types import SimpleNamespace

    trip_id = uuid4()
    store = SimpleNamespace(version_for_request=lambda conn, trip, request: None, latest=lambda conn, trip: ({"version": 4}, []),
                            append_version=lambda *a, **k: (_ for _ in ()).throw(AssertionError("새 판을 쓰면 안 된다")))
    monkeypatch.setattr(reopen, "prepare", lambda *a, **k: plan)
    with pytest.raises(reopen_commit.CommitRefused) as caught:
        reopen_commit._commit_locked(store=store, connect=lambda: nullcontext(None), tenant="t", intake_id=uuid4(), revision=2,
                                     reopened={"trip_id": str(trip_id), "version": 4, "frozen_item_ids": []}, status="review",
                                     built=SimpleNamespace(problems=[]), now=NOW,
                                     before_write=lambda: (_ for _ in ()).throw(AssertionError("쓰기 전 단계로 가면 안 된다")))
    assert caught.value.status == 422 and caught.value.code == code
