# -*- coding: utf-8 -*-
"""요식 팀이 꽂는 「다른 식당 후보」 자리(`team_hooks.dining_alternatives`) — 미등록 · 답하지 못함은 `None`(모름). `[2026-10-15 사용자 결정]`"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.team_hooks import dining_alternatives as hook

AT = datetime(2026, 10, 22, 12, 30, tzinfo=timezone(timedelta(hours=9)))


@pytest.fixture(autouse=True)
def clean():
    hook.clear()
    yield
    hook.clear()


def test_without_a_registered_team_the_answer_is_unknown():
    assert hook.is_registered() is False
    assert hook.ranked(None, "t", "uid", AT) is None


def test_an_unknown_restaurant_or_time_is_unknown_not_an_empty_answer():
    hook.register(rank=lambda *a, **k: {"alternatives": []})
    assert hook.ranked(None, "t", None, AT) is None and hook.ranked(None, "t", "uid", None) is None


def test_a_registered_team_answer_passes_through_with_the_next_stop_point():
    seen = {}

    def rank(conn, tenant, uid, starts_at, ends_at, *, next_point=None, conditions=()):
        seen.update(uid=uid, next_point=next_point)
        return {"alternatives": []}

    hook.register(rank=rank)
    assert hook.ranked(None, "t", "uid", AT, None, next_point=(37.5, 127.0)) == {"alternatives": []}
    assert seen == {"uid": "uid", "next_point": (37.5, 127.0)}


# ── `[2026-10-18 사용자 지시]` 가게 이름 없는 식사(「점심」 · 「ㅇㅇ 근처 점심」) — 원래 식당 없이 **한 지점** 둘레의 원장 식당 ──

def test_a_nameless_meal_without_a_registered_near_answer_is_unknown():
    hook.register(rank=lambda *a, **k: {"alternatives": []})          # 이름 있는 식당 길만 등록한 팀
    assert hook.near(None, "t", (37.5, 127.0), AT) is None


def test_a_nameless_meal_needs_a_point_and_a_time():
    hook.register(rank=lambda *a, **k: None, near=lambda *a, **k: {"alternatives": []})
    assert hook.near(None, "t", None, AT) is None and hook.near(None, "t", (37.5, 127.0), None) is None


def test_a_registered_near_answer_passes_through_with_the_meal_flag_and_radius():
    seen = {}

    def near(conn, tenant, point, starts_at, ends_at, *, next_point=None, conditions=(), meal=True, radius_m=2000):
        seen.update(point=point, next_point=next_point, meal=meal, radius_m=radius_m, starts_at=starts_at)
        return {"alternatives": []}

    hook.register(rank=lambda *a, **k: None, near=near)
    assert hook.is_registered() and hook.near(None, "t", (37.5, 127.0), AT, None, next_point=(37.6, 127.1),
                                              meal=False, radius_m=800) == {"alternatives": []}
    assert seen == {"point": (37.5, 127.0), "next_point": (37.6, 127.1), "meal": False, "radius_m": 800, "starts_at": AT}
