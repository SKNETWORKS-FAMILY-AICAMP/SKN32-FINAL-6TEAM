# -*- coding: utf-8 -*-
"""웹 채팅의 담당 팀은 **가리키는 일정의 실제 종류**로 정한다 — 분류기 딱지가 아니라. `[2026-09-29 사용자 지시]`

☆실측(demo): 「무구옥 시간정보 있는 다른 곳으로 바꿔줘」·「첫날 아침 일정 바꿔」 — 둘 다 식사인데 `activity_*` 딱지를 받아
  활동 담당으로 기록됐다. 사용자 지시: 「이런 오분류는 절대 생겨서는 안 된다 — 그래서 코어 DB 를 공유한다」.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.conversation.trip_messages import owner_team

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 9, 30, tzinfo=KST)


def _item(kind, title, hour, place_name=None):
    return Item(item_id=uuid4(), seq=hour, kind=kind, title=title, place_id=None,
                starts_at=DAY + timedelta(hours=hour), ends_at=DAY + timedelta(hours=hour + 1),
                locked=False, booking_id=None, replaces_item_id=None, detail={},
                place={"place_id": str(uuid4()), "name": place_name or title, "kind": kind})


BREAKFAST = _item("dining", "삼거리 순대국", 8)
PALACE = _item("activity", "경복궁 관람", 10, "경복궁")
LUNCH = _item("dining", "무구옥", 12)
MOVE = _item("mobility", "경복궁역 → 광화문역", 11)
ITEMS = [BREAKFAST, PALACE, MOVE, LUNCH]
AT = DAY - timedelta(hours=12)


def test_a_meal_named_in_the_sentence_goes_to_dining_even_with_an_activity_label():
    team, basis = owner_team("activity", items=ITEMS, message="무구옥 시간정보 있는 다른 곳으로 바꿔줘",
                             selected=None, at=AT)
    assert team == "dining"
    assert basis == {"routed_by": "item_kind", "item_id": str(LUNCH.item_id), "item_kind": "dining",
                     "classifier_team": "activity"}


def test_a_meal_word_goes_to_dining():
    team, _ = owner_team("activity", items=ITEMS, message="아침 일정 바꿔", selected=None, at=AT)
    assert team == "dining"


def test_the_item_picked_on_screen_decides_when_the_sentence_names_none():
    team, basis = owner_team("dining", items=ITEMS, message="이거 다른 곳으로 바꿔줘", selected=PALACE.item_id, at=AT)
    assert team == "activity" and basis["item_id"] == str(PALACE.item_id)


def test_a_matching_label_is_kept_and_the_basis_is_recorded():
    team, basis = owner_team("activity", items=ITEMS, message="경복궁 말고 다른 곳", selected=None, at=AT)
    assert team == "activity" and basis["routed_by"] == "item_kind" and "classifier_team" not in basis


def test_non_item_teams_are_left_to_the_classifier():
    """예약·창구 딱지는 일정 종류로 덮지 않는다 — 「경복궁 예약 취소」는 예약 일이다."""
    team, basis = owner_team("booking", items=ITEMS, message="경복궁 예약 취소해 줘", selected=None, at=AT)
    assert team == "booking" and basis == {"routed_by": "classifier"}


def test_when_no_item_is_meant_the_label_stays():
    team, basis = owner_team("activity", items=ITEMS, message="내일 날씨 어때?", selected=None, at=AT)
    assert team == "activity" and basis == {"routed_by": "classifier"}
