# -*- coding: utf-8 -*-
"""되돌리기 답은 고객 말로 — 「버전 1」·이동 항목 제목을 싣지 않고, 장소가 바뀐 자리만 「전 → 후」. `[2026-09-29 ui 세션 지적]`"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import plan_rollback, title_for

KST = ZoneInfo("Asia/Seoul")


def _item(seq, kind, name, hour, day=1):
    place = {"place_id": str(uuid4()), "name": name} if kind != "mobility" else None
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=name, place_id=place and place["place_id"],
                starts_at=datetime(2030, 1, day, hour, tzinfo=KST), ends_at=datetime(2030, 1, day, hour, 50, tzinfo=KST),
                place=place)


def _two_versions():
    palace, move, dinner = _item(1, "activity", "경복궁", 15), _item(2, "mobility", "경복궁 → 일품당프리미엄", 17), \
        _item(3, "dining", "일품당프리미엄", 18)
    new_dinner = dinner.replaced_by(place={"place_id": str(uuid4()), "name": "광화문 세종클럽"},
                                    title=title_for(dinner, "광화문 세종클럽"))
    new_move = move.replaced_by(place=None, title="경복궁 → 광화문 세종클럽")
    return [palace, move, dinner], [palace, new_move, new_dinner]


def test_a_rollback_says_which_slot_went_back_from_what_to_what():
    v1, v2 = _two_versions()
    plan = plan_rollback(trip_version=2, base_version=2, current_items=v2, old_items=v1, to_version=1,
                         message="원래대로", request_id="r")
    text = plan.notice["text"]
    assert text == "1일차 저녁을 광화문 세종클럽에서 일품당프리미엄(으)로 되돌렸어요.", text
    assert "버전" not in text and "→" not in text


def test_applying_an_undone_change_again_says_so():
    v1, v2 = _two_versions()
    plan = plan_rollback(trip_version=3, base_version=3, current_items=v1, old_items=v2, to_version=2,
                         message="다시 진행해 줘", request_id="r", redo=True)
    assert plan.notice["text"] == "요청하신 변경을 다시 적용했어요 — 1일차 저녁 일품당프리미엄 → 광화문 세종클럽."


def test_a_new_title_keeps_the_shape_of_the_old_one():
    plain = _item(3, "dining", "일품당프리미엄", 18)
    assert title_for(plain, "금용문") == "금용문"                                  # 일정 짜기 모양 — 가게 이름만
    shaped = Item(**{**plain.__dict__, "title": "일품당프리미엄 식사"})
    assert title_for(shaped, "금용문") == "금용문 식사"                            # 「○○ 식사」 모양이면 그대로
