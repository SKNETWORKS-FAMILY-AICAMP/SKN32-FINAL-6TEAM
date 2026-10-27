# -*- coding: utf-8 -*-
"""범위 옮기기 · 되돌리기가 고객 고정을 바꾸지 않는다. `[2026-10-26 x600 40231a56 · Codex 결정]`

☆왜: 17항목 여행에서 고객이 「이 일정은 고정해 주세요」라고 쓴 국립중앙박물관만 `customer_pinned` 였다.
  ①「일정 전부다 1시간씩 미뤄줘」 → 박물관도 +1시간 옮겨지고 고정이 풀렸다(`split_range` 가 `detail.customer_pinned` 를 보지 않았고,
    옮기는 시각 op 가 자동 표시 풀기 규칙을 탔다). 계약(trip-chat-context 범위 옮기기)은 「고정 … 은 옮기지 않고 그대로 둔 일정」이다.
  ②되돌리기 → 17건 모두 `customer_pinned` — 되살린 항목에 감시용 표시를 같은 칸에 붙여 고친 적 없는 16곳도 「고정」이 됐다.

★지키려는 것
 ①범위 옮기기는 고객 고정 일정을 옮기지 않고 「그대로 둔 일정: …(고정)」으로 보인다 — 나머지만 옮긴다
 ②되돌리기는 옛 판의 고객 고정 값을 그대로 되살리고, 감시용 표시는 따로(`detail.rollback_hold`)
 ③감시 보호(`pending.protected_reason`)는 되살린 항목을 `rollback_hold` 로 본다(고객 고정이 같이 있으면 `customer_pinned` 가 먼저)
 ④되돌린 뒤 다시 「전부 미뤄줘」는 감시용 표시만 있는 일정을 옮긴다(고객 고정이 아니다)
"""
from __future__ import annotations

import copy
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.conversation.chat_edit import shift_range, split_range
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import plan_rollback
from app.domains.travel_ops.components.planning.pending import protected_reason

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2030, 1, 1, 9, tzinfo=KST)


def _stops(pinned=("국립중앙박물관",)):
    names = ["경복궁", "국립중앙박물관", "N서울타워"]
    out = []
    for n, name in enumerate(names):
        place = {"place_id": str(uuid4()), "name": name}
        detail = {"customer_pinned": True} if name in pinned else {}
        out.append(Item(item_id=uuid4(), seq=n + 1, kind="activity", title=name, place_id=place["place_id"], place=place,
                        starts_at=datetime(2030, 1, 2, 9 + 3 * n, tzinfo=KST), ends_at=datetime(2030, 1, 2, 10 + 3 * n, tzinfo=KST),
                        detail=detail))
    return out


def test_a_range_shift_keeps_the_customer_pinned_stop_and_moves_the_rest():
    items = _stops()
    ops, what = shift_range(items, 60, NOW)
    assert [o.item_id for o in ops] == [items[0].item_id, items[2].item_id] and what == "일정 2개 시각 옮기기"
    assert [k for o in ops for k in o.kept] == ["1월 2일(수) 12:00 국립중앙박물관(고정)"]
    targets, kept = split_range(items, NOW)
    assert kept == [items[1]] and items[1] not in targets


def test_a_range_of_only_customer_pinned_stops_is_kept_with_its_reason():
    import pytest

    from app.domains.travel_ops.components.conversation.chat_edit import EditRefused

    items = _stops(pinned=("경복궁", "국립중앙박물관", "N서울타워"))
    with pytest.raises(EditRefused) as caught:
        shift_range(items, 60, NOW)
    assert caught.value.code == "range_kept" and "국립중앙박물관(고정)" in caught.value.message


def _rollback(old, current):
    return plan_rollback(trip_version=2, base_version=2, current_items=current, old_items=copy.deepcopy(old), to_version=1,
                         message="방금 변경을 되돌려줘", request_id="r")


def test_a_rollback_restores_the_old_pins_and_marks_the_watch_hold_separately():
    old = _stops()
    current = [Item(item_id=uuid4(), seq=i.seq, kind=i.kind, title=i.title, place_id=i.place_id, place=i.place,
                    starts_at=i.starts_at.replace(hour=i.starts_at.hour + 1), ends_at=i.ends_at.replace(hour=i.ends_at.hour + 1),
                    replaces_item_id=i.item_id, detail={}) for i in old]
    plan = _rollback(old, current)
    restored = {i.title: i for i in plan.full_items}
    assert {t: bool(i.detail.get("customer_pinned")) for t, i in restored.items()} == {
        "경복궁": False, "국립중앙박물관": True, "N서울타워": False}
    assert all(i.detail.get("rollback_hold") is True for i in restored.values())
    assert protected_reason(restored["경복궁"]) == "rollback_hold"
    assert protected_reason(restored["국립중앙박물관"]) == "customer_pinned"        # 고객 고정이 먼저
    # ④ 되돌린 뒤 다시 「전부 미뤄줘」 — 감시용 표시만 있는 일정은 옮기고, 고객 고정만 그대로 둔다
    ops, _ = shift_range(list(plan.full_items), 60, NOW)
    assert sorted(o.item_id for o in ops) == sorted([restored["경복궁"].item_id, restored["N서울타워"].item_id])
    assert [k for o in ops for k in o.kept] == ["1월 2일(수) 12:00 국립중앙박물관(고정)"]


def test_watch_side_fixed_checks_see_the_rollback_hold():
    from app.domains.travel_ops.components.itinerary import itinerary_delay

    item = _stops(pinned=())[0]
    item.detail = {"rollback_hold": True}
    assert itinerary_delay._fixed(item)
    assert protected_reason(item) == "rollback_hold"
