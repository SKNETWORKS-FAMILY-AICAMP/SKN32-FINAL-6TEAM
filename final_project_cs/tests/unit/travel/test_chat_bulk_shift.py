# -*- coding: utf-8 -*-
"""`[2026-10-26 x600 6152ae77]` 「일정 전부다 1시간씩 미뤄줘」 — 기준 없는 following + 검증된 범위(query)는 범위 이동이다.

실서비스 기록의 해석 원출력(모델 호출 없음)을 그대로 넣는다: action=change_time · target/anchor 없음 · minutes=60 ·
query={day:all,…} · time_edit={shift, following, cascade}. 전에는 `edit_intent.time_ops` 가 기준을 되물어(need_target) 아무것도 옮기지 않았다.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation.chat_edit import EditOp, EditRefused, done_text, ops_for
from app.domains.travel_ops.components.conversation.decision_unit import Decision
from app.domains.travel_ops.components.itinerary.itinerary import Item

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, 0, tzinfo=KST)
ALL = {"day": "all", "kind": "all", "period": "all", "position": "all"}
#: x600 case 6152ae77 의 time_edit 원출력
X600_EDIT = {"time": "", "scope": "following", "cascade": True, "boundary": "shift",
             "evidence": "일정 전부다 1시간씩 미뤄줘", "duration_minutes": 0, "continue_previous": False}


def stop(name, day, start, end, seq, kind="activity", **kw):
    place = {"place_id": uuid4(), "name": name, "kind": kind, "latitude": 37.57, "longitude": 126.98, "attributes": {}}
    base = NOW + timedelta(days=day)
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=name, place_id=place["place_id"], place=place,
                starts_at=base.replace(hour=start), ends_at=base.replace(hour=end), **kw)


def recorded(query=ALL, minutes=60, anchor="none", item=None, edit=X600_EDIT):
    raw = {"action": "change_time", "target_item": "none", "anchor_item": anchor, "anchor_kind": "none", "at_day": "none",
           "minutes": minutes, "query": query, "time_edit": edit}
    return Decision(action="change_time", item=item, change=None, fact="none", minutes=minutes, question="", raw=raw,
                    query=query)


def trip():
    return [stop("인사동", 0, 13, 14, 1), stop("점심", 0, 14, 15, 2, kind="dining"), stop("남산", 0, 16, 18, 3),
            stop("경복궁", 1, 10, 12, 4)]


def test_x600_all_schedule_shift_moves_every_future_stop_by_the_same_minutes():
    items = trip()
    ops, what = ops_for(recorded(), items=items, now=NOW, message="일정 전부다 1시간씩 미뤄줘")
    moved = {op.item_id: (op.date, op.starts_at, op.ends_at) for op in ops}
    assert set(moved) == {i.item_id for i in items}, what
    assert moved[items[0].item_id][1:] == ("14:00", "15:00") and moved[items[3].item_id] == ("2030-01-02", "11:00", "13:00")
    assert what == "일정 4개 시각 옮기기"


def test_following_without_anchor_and_without_range_still_asks_for_the_anchor():
    with pytest.raises(EditRefused) as caught:
        ops_for(replace(recorded(), query=None), items=trip(), now=NOW, message="뒤 일정 1시간 미뤄줘")
    assert caught.value.code == "need_target"


def test_following_with_an_explicit_anchor_keeps_the_same_day_following_contract():
    items = trip()
    ops, _ = ops_for(recorded(anchor="i1"), items=items, now=NOW, message="인사동 뒤 일정 다 1시간 미뤄줘")
    assert [op.item_id for op in ops] == [items[1].item_id, items[2].item_id]       # 기준 자신과 다음 날은 제외


def test_plain_shift_without_target_or_range_asks_which_stop():
    """「1시간씩 늦춰줘」 — 대상도 범위도 없으면(화면 선택 없음) 되묻는다."""
    plain = recorded(query=None, edit={**X600_EDIT, "scope": "item", "evidence": "1시간씩 늦춰줘"})
    with pytest.raises(EditRefused) as caught:
        ops_for(plain, items=trip(), now=NOW, message="1시간씩 늦춰줘")
    assert caught.value.code == "need_target"


def test_plain_shift_with_a_selected_stop_moves_only_that_stop():
    items = trip()
    plain = recorded(query=None, item=items[1], edit={**X600_EDIT, "scope": "item", "evidence": "1시간씩 늦춰줘"})
    ops, _ = ops_for(plain, items=items, now=NOW, message="1시간씩 늦춰줘")
    assert [(op.item_id, op.starts_at) for op in ops] == [(items[1].item_id, "15:00")]


def test_locked_booked_and_started_stops_stay_and_are_reported():
    items = trip()
    items[1] = replace(items[1], locked=True)
    items[2] = replace(items[2], booking_id=uuid4())
    started = stop("아침 산책", 0, 8, 10, 0)
    ops, _ = ops_for(recorded(), items=[started, *items], now=NOW, message="일정 전부다 1시간씩 미뤄줘")
    assert {op.item_id for op in ops} == {items[0].item_id, items[3].item_id}
    kept = ops[0].kept
    assert any("점심" in k and "고정" in k for k in kept) and any("남산" in k and "예약" in k for k in kept)
    assert any("아침 산책" in k and "이미 시작" in k for k in kept)


def test_range_of_only_protected_stops_is_refused_without_moving():
    items = [replace(stop("인사동", 0, 13, 14, 1), locked=True)]
    with pytest.raises(EditRefused) as caught:
        ops_for(recorded(), items=items, now=NOW, message="일정 전부다 1시간씩 미뤄줘")
    assert caught.value.code == "range_kept"


def test_range_shift_that_crosses_midnight_is_refused_as_a_whole():
    items = [stop("인사동", 0, 13, 14, 1), stop("야경", 0, 22, 23, 2)]
    with pytest.raises(EditRefused) as caught:
        ops_for(recorded(minutes=90), items=items, now=NOW, message="일정 전부 1시간 30분씩 미뤄줘")
    assert caught.value.code in ("crosses_midnight",)


def test_range_pull_into_the_past_is_refused_as_a_whole():
    items = [stop("인사동", 0, 10, 11, 1), stop("남산", 0, 16, 18, 2)]
    with pytest.raises(EditRefused) as caught:
        ops_for(recorded(minutes=-120), items=items, now=NOW, message="오늘 일정 전부 2시간 당겨줘")
    assert caught.value.code == "time_in_past"


def test_done_text_lists_every_moved_stop_and_the_kept_ones():
    items = trip()
    ops = [EditOp("time", item_id=items[0].item_id, kept=("1월 1일 14:00 점심(고정)",)),
           EditOp("time", item_id=items[2].item_id)]
    plan = SimpleNamespace(changed_ids=[items[0].item_id, items[2].item_id], added_ids=[], removed=[])
    text = done_text(ops, items_after=items, plan=plan)
    assert "인사동" in text and "남산" in text and "· 그대로 둔 일정: 1월 1일 14:00 점심(고정)" in text
