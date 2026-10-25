# -*- coding: utf-8 -*-
"""지난 일정은 기록이다 — 고칠 수 없고(이름 · 장소 · 날짜 · 시각 · 고정 모두) 뺄 수만 있다. 다시 하려면 새 일정으로 추가한다. `[2026-10-26 사용자 확정]`

서버 「완료」(`reopen.plan_edit`)와 채팅 고치기(`chat_edit.ops_for` · 고정 일정 거절)가 같은 규칙을 쓴다. DB · 모델 없이 돈다.
「지났다」 = 끝 ≤ 지금(끝이 없으면 시작). 진행 중(시작 ≤ 지금 < 끝) 일정은 지금 이후 규칙 안에서 고칠 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import chat_edit
from app.domains.travel_ops.components.conversation.chat_edit import EditRefused, ops_for
from app.domains.travel_ops.components.conversation.decision_unit import Decision
from app.domains.travel_ops.components.intake import reopen
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 26, 12, 0, 30, tzinfo=KST)


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=KST)


def _stop(title: str, starts: str, ends: str, kind: str = "activity") -> Item:
    place = {"place_id": str(uuid4()), "name": title, "kind": kind, "latitude": 37.58, "longitude": 126.98, "attributes": {}}
    return Item(item_id=uuid4(), seq=1, kind=kind, title=title, place_id=uuid4(), place=place, starts_at=_at(starts),
                ends_at=_at(ends), detail={})


def _seq(*items: Item) -> list[Item]:
    return [replace(item, seq=n) for n, item in enumerate(items, start=1)]


def _row(origin: Item, index: int = 0, **over) -> dict:
    base = {"source_id": "s1", "index": index, "title": origin.title, "kind": origin.kind, "locked": False,
            "place": dict(origin.place) | {"place_id": origin.place_id}, "date": origin.starts_at.date().isoformat(),
            "start": origin.starts_at.strftime("%H:%M"), "end": origin.ends_at.strftime("%H:%M") if origin.ends_at else None,
            "booking_no": None, "booked": None, "provenance": {}, "claims": {"ends_at": {}}}
    if origin.ends_at and origin.ends_at.date() != origin.starts_at.date():
        base["end_date"] = origin.ends_at.date().isoformat()
    return base | over


def _plan(base, rows, origin_of):
    return reopen.plan_edit(rows=rows, origin_of=origin_of, base_items=base, frozen_ids=set(), intake_id="i1", revision=1, now=NOW)


def _trip():
    return _seq(_stop("창덕궁", "2026-10-26T09:00", "2026-10-26T10:00"),        # 지났다(수정 화면을 연 뒤 끝났다)
                _stop("경복궁", "2026-10-26T11:00", "2026-10-26T13:00"),        # 진행 중
                _stop("남산", "2026-10-27T15:00", "2026-10-27T17:00"))          # 앞으로


def _all_rows(base):
    return [_row(item, n) for n, item in enumerate(base)], {("s1", n): item.item_id for n, item in enumerate(base)}


# ---- 서버 「완료」 -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("change", [{"title": "창덕궁 후원"}, {"locked": True},
                                    {"place": {"place_id": str(uuid4()), "name": "창경궁", "kind": "activity",
                                               "latitude": 37.57, "longitude": 126.99, "attributes": {}}}],
                         ids=["rename", "lock", "place"])
def test_a_past_stop_cannot_be_changed_at_all(change):
    base = _trip()
    rows, origin_of = _all_rows(base)
    plan = _plan(base, [_row(base[0], 0, **change), *rows[1:]], origin_of)
    assert plan.past == ["창덕궁"]                                        # 원래 이름으로 알린다(고친 이름은 쓰이지 않았다)


def test_a_past_stop_can_still_be_removed():
    base = _trip()
    rows, origin_of = _all_rows(base)
    plan = _plan(base, rows[1:], origin_of)
    assert plan.past == [] and plan.removed == ["창덕궁"] and plan.no_upcoming is False


def test_a_running_stop_can_still_be_renamed():
    base = _trip()
    rows, origin_of = _all_rows(base)
    plan = _plan(base, [rows[0], _row(base[1], 1, title="경복궁 야간"), rows[2]], origin_of)
    assert plan.past == [] and plan.changed == ["경복궁 → 경복궁 야간"]


def test_an_overnight_stay_is_running_until_checkout_and_past_after_it():
    staying = _stop("한옥스테이", "2026-10-25T15:00", "2026-10-26T13:00", kind="lodging")
    left = _stop("게스트하우스", "2026-10-25T15:00", "2026-10-26T11:00", kind="lodging")
    for stay, refused in ((staying, []), (left, ["게스트하우스"])):
        base = _seq(stay, _stop("남산", "2026-10-27T15:00", "2026-10-27T17:00"))
        rows, origin_of = _all_rows(base)
        plan = _plan(base, [_row(base[0], 0, title=stay.title + " 별관"), rows[1]], origin_of)
        assert plan.past == refused


def test_lock_only_on_a_past_stay_is_no_change_and_a_stop_without_end_or_ending_now_is_a_record():
    left = _stop("게스트하우스", "2026-10-25T15:00", "2026-10-26T11:00", kind="lodging")
    base = _seq(left, _stop("남산", "2026-10-27T15:00", "2026-10-27T17:00"))
    rows, origin_of = _all_rows(base)
    plan = _plan(base, [_row(base[0], 0, locked=True), rows[1]], origin_of)     # 숙소는 늘 잠금으로 들어온다 — 잠금만으로는 고친 것이 아니다
    assert plan.past == [] and plan.changed == [] and plan.unchanged
    for ends in (None, "2026-10-26T12:00"):                                      # 끝이 없으면 시작으로 · 끝 = 지금(분)도 끝났다
        stop = replace(_stop("창덕궁", "2026-10-26T11:00", "2026-10-26T11:30"), ends_at=_at(ends) if ends else None)
        base = _seq(stop, _stop("남산", "2026-10-27T15:00", "2026-10-27T17:00"))
        rows, origin_of = _all_rows(base)
        plan = _plan(base, [_row(base[0], 0, title="창덕궁 후원"), rows[1]], origin_of)
        assert plan.past == ["창덕궁"]


def test_removing_a_record_from_a_finished_trip_is_not_blocked_by_the_one_upcoming_rule():
    base = _seq(_stop("창덕궁", "2026-10-26T09:00", "2026-10-26T10:00"), _stop("경복궁", "2026-10-26T10:30", "2026-10-26T11:30"))
    rows, origin_of = _all_rows(base)
    plan = _plan(base, rows[1:], origin_of)
    assert plan.past == [] and plan.removed == ["창덕궁"] and plan.no_upcoming is False


def test_commit_refusal_text_says_past_stops_can_only_be_removed():
    from contextlib import nullcontext
    from types import SimpleNamespace

    from app.domains.travel_ops.components.intake import reopen_commit

    plan = reopen.EditPlan(items=[], changed=["창덕궁 → 창덕궁 후원"], past=["창덕궁"])
    store = SimpleNamespace(version_for_request=lambda conn, trip, request: None, latest=lambda conn, trip: ({"version": 4}, []))
    original = reopen.prepare
    reopen.prepare = lambda *a, **k: plan
    try:
        with pytest.raises(reopen_commit.CommitRefused) as caught:
            reopen_commit._commit_locked(store=store, connect=lambda: nullcontext(None), tenant="t", intake_id=uuid4(), revision=2,
                                         reopened={"trip_id": str(uuid4()), "version": 4, "frozen_item_ids": []}, status="review",
                                         built=SimpleNamespace(problems=[]), now=NOW, before_write=None)
    finally:
        reopen.prepare = original
    assert caught.value.code == "item_in_past"
    assert "지난 일정은 고칠 수 없" in caught.value.message and "창덕궁" in caught.value.message
    assert "지난 일정은 고칠 수 없" in chat_edit._refusal("item_in_past", caught.value.message)


# ---- 채팅 ----------------------------------------------------------------------------------------------------------

@dataclass
class Stop:
    item_id: object
    seq: int
    kind: str
    title: str
    starts_at: datetime
    ends_at: datetime | None
    booking_id: object = None
    locked: bool = False
    place: object = None
    detail: dict | None = None


CHAT_NOW = datetime(2030, 1, 2, 11, 0, tzinfo=KST)


def _chat_trip():
    def at(day, hour):
        return datetime(2030, 1, day, hour, 0, tzinfo=KST)
    return [Stop(uuid4(), 1, "activity", "창덕궁", at(1, 10), at(1, 12)),        # 지났다
            Stop(uuid4(), 2, "activity", "경복궁", at(2, 12), at(2, 14)),
            Stop(uuid4(), 3, "activity", "남산", at(3, 15), at(3, 17))]


def _decision(action, item, **raw):
    return Decision(action=action, item=item, change=None, fact="none", minutes=None, question="", raw=raw)


@pytest.mark.parametrize("action,raw", [("replace_named", {"destination_text": "창경궁"}), ("lock_item", {}), ("unlock_item", {}),
                                        ("swap_order", {"anchor_item": "i2"}),
                                        ("change_time", {"anchor_kind": "time", "anchor_time": "16:00", "at_day": "d3"})])
def test_chat_refuses_any_change_to_a_past_stop_and_points_to_adding_a_new_one(action, raw):
    items = _chat_trip()
    with pytest.raises(EditRefused) as caught:
        ops_for(_decision(action, items[0], **raw), items=items, now=CHAT_NOW)
    assert caught.value.code == "item_in_past"
    assert "창덕궁" in caught.value.message and "지난 일정" in caught.value.message and "추가" in caught.value.message


def test_chat_swap_with_a_past_stop_as_the_other_one_is_refused_too():
    items = _chat_trip()
    with pytest.raises(EditRefused) as caught:
        ops_for(_decision("swap_order", items[2], anchor_item="i1"), items=items, now=CHAT_NOW)
    assert caught.value.code == "item_in_past" and "창덕궁" in caught.value.message


def test_chat_can_still_ask_to_remove_a_past_stop_and_change_a_running_or_future_one():
    items = _chat_trip()
    ops, _ = ops_for(_decision("remove_item", items[0]), items=items, now=CHAT_NOW)
    assert [(o.kind, o.item_id) for o in ops] == [("remove", items[0].item_id)]
    ops, _ = ops_for(_decision("replace_named", items[2], destination_text="창경궁"), items=items, now=CHAT_NOW)
    assert ops[0].kind == "place"


def test_chat_frozen_past_stop_gets_its_own_honest_answer():
    items = _chat_trip()
    edit = chat_edit.frozen_refusal(items[0], "place", now=CHAT_NOW)
    assert edit.code == "item_in_past" and "지난 일정" in edit.message and "추가" in edit.message
    removal = chat_edit.frozen_refusal(items[0], "remove", now=CHAT_NOW)
    assert removal.code == "item_in_past" and "아직" in removal.message and "빼" in removal.message
    booked = replace(items[2], booking_id=uuid4()) if hasattr(items[2], "__dataclass_fields__") else items[2]
    other = chat_edit.frozen_refusal(booked, "place", now=CHAT_NOW)
    assert other.code == "frozen_item" and "예약" in other.message
