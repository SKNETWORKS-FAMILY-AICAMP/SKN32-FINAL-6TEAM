# -*- coding: utf-8 -*-
"""`chat_edit.spoken_meal_target` — 옮길 곳을 끼니 말(+ 오늘 · 내일 · 모레)로 말한 문장에서 날 · 시각을 읽는다. `[2026-10-15 x600 실서버 확인]`"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation.chat_edit import spoken_meal_target

NOW = datetime(2026, 10, 15, 14, 0, tzinfo=ZoneInfo("Asia/Seoul"))


@pytest.mark.parametrize("text, expected", [
    ("내일 점심을 오늘 저녁으로 옮겨줘", ("2026-10-15", "18:00")),
    ("경복궁을 내일 저녁으로 옮겨줘", ("2026-10-16", "18:00")),
    ("미술관 점심으로 옮겨줘", (None, "12:00")),
    ("저녁 식당을 아침에 가게 바꿔줘", (None, "08:00")),
    ("모레 점심으로 옮겨줘", ("2026-10-17", "12:00")),
])
def test_a_meal_word_the_stop_moves_to_gives_the_day_and_time(text, expected):
    assert spoken_meal_target(text, NOW) == expected


@pytest.mark.parametrize("text", ["점심 30분 늦춰줘", "내일 점심 식당 바꿔줘", "점심을 먹고 싶어", "17시로 옮겨줘"])
def test_a_meal_word_that_is_not_the_destination_is_not_read(text):
    assert spoken_meal_target(text, NOW) is None
