# -*- coding: utf-8 -*-
"""「바꿔 줘」의 대상 — 서수 · 날 · 종류를 읽고, 문장이 말한 종류와 다른 항목은 고르지 않는다. `[2026-09-29 ui 세션 지적]`

☆실제 사고: 「첫 활동 다른 걸로 바꿔줘」와 「첫 식당 다른 걸로 바꿔」가 둘 다 화면에서 고른 14:01 활동으로 떨어져,
  「첫 식당」에 **활동** 답이 나갔다(서수를 못 읽었다).
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.conversation.trip_messages import _change_target, asked_kind

KST = ZoneInfo("Asia/Seoul")


def _item(seq, kind, name, day, hour):
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=name, place_id=None,
                starts_at=datetime(2030, 1, day, hour, tzinfo=KST), ends_at=datetime(2030, 1, day, hour, 50, tzinfo=KST),
                place={"place_id": str(uuid4()), "name": name})


TRIP = [_item(1, "dining", "아침집", 1, 8), _item(2, "activity", "경복궁", 1, 10), _item(3, "dining", "점심집", 1, 12),
        _item(4, "activity", "북한산 둘레길", 1, 14), _item(5, "dining", "저녁집", 1, 18),
        _item(6, "dining", "둘째날 아침집", 2, 8), _item(7, "activity", "창덕궁", 2, 10), _item(8, "dining", "둘째날 점심집", 2, 12)]
AT = datetime(2030, 1, 1, 7, tzinfo=KST)
TRAIL = TRIP[3].item_id                         # 화면에서 눌러 둔 14:01 활동


def _pick(text, selected=TRAIL):
    found = _change_target(TRIP, text, selected, AT)
    return found.title if found else None


def test_ordinals_are_read_per_kind_on_the_first_day():
    assert _pick("첫 식당 다른 걸로 바꿔") == "아침집"
    assert _pick("첫 활동 다른 걸로 바꿔줘") == "경복궁"
    assert _pick("두 번째 식당 바꿔 줘") == "점심집"
    assert _pick("마지막 식당 바꿔") == "저녁집"


def test_a_day_word_moves_the_ordinal_to_that_day():
    assert _pick("2일차 첫 식당 바꿔") == "둘째날 아침집"
    assert _pick("둘째 날 두 번째 식당 바꿔 줘") == "둘째날 점심집"
    assert _pick("첫날 활동 바꿔", selected=None) == "경복궁"       # 날만 말하면 그날 첫 항목(종류 안에서)
    assert _pick("2일차 활동 바꿔") == "창덕궁"                     # 고른 것(1일차)은 말한 날과 달라 쓰지 않는다


def test_a_selected_item_of_another_kind_is_never_used_for_a_kind_named_in_the_sentence():
    assert asked_kind("식당 다른 데로 바꿔 줘") == "dining"
    assert _pick("식당 다른 데로 바꿔 줘") is None                  # 고른 것은 활동 — 부르는 쪽이 다음 식당으로
    assert _pick("다른 데로 바꿔 줘") == "북한산 둘레길"            # 문장이 말하지 않으면 고른 것
    assert _pick("활동 다른 걸로 바꿔") == "북한산 둘레길"          # 종류가 같으면 고른 것
