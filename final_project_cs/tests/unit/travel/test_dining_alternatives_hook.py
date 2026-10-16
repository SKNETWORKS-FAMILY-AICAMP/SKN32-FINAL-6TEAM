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
