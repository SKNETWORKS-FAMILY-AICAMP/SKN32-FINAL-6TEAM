# -*- coding: utf-8 -*-
"""장면 C — 할랄 필수 · 식사 둘만(겹치는 이동 없음) → 판정 뒤 등록까지 가는지."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
live_flow = importlib.import_module("2026-10-18_dining_llmcheck_live_flow")  # noqa: E402

live_flow.PLANS = {
    "C_halal_meals_only": "10월 24일 토요일 서울 하루 여행이에요. 일행 2명, 무슬림이라 할랄 음식만 먹을 수 있어요(꼭 지켜야 해요).\n"
                          "12:00 할랄부산집 점심\n18:00 구르카 저녁",
}
live_flow.main()
