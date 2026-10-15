# -*- coding: utf-8 -*-
"""활동 팀이 꽂는 「다른 곳 후보」 자리(`team_hooks.activity_alternatives`) — 미등록 · 답하지 못함은 `None`(모름) 이다. `[2026-10-15 사용자 결정]`

부르는 쪽(확인 화면 `candidates.alternatives`)은 `None` 일 때만 자체 후보 고르기로 간다 — 팀이 「없다」고 답한 빈 목록은 대비책으로 넘어가지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.team_hooks import activity_alternatives as hook
from app.domains.travel_ops.instances.activity import review_alternatives

AT = datetime(2026, 10, 22, 8, 0, tzinfo=timezone(timedelta(hours=9)))


@pytest.fixture(autouse=True)
def clean():
    hook.clear()
    yield
    hook.clear()


def test_without_a_registered_team_the_answer_is_unknown():
    assert hook.is_registered() is False
    assert hook.ranked(None, "t", "126508", AT) is None


def test_an_unknown_origin_or_time_is_unknown_not_an_empty_answer():
    hook.register(rank=lambda *a, **k: {"alternatives": []})
    assert hook.ranked(None, "t", None, AT) is None and hook.ranked(None, "t", "126508", None) is None


def test_a_registered_team_answer_passes_through_even_when_it_is_empty():
    seen = {}

    def rank(conn, tenant, content_id, at, *, exclude_content_ids=(), preference=None):
        seen.update(tenant=tenant, content_id=content_id, exclude=exclude_content_ids)
        return {"alternatives": []}

    hook.register(rank=rank)
    assert hook.ranked(None, "t", "126508", AT, exclude_content_ids={"1", "2"}) == {"alternatives": []}
    assert seen["content_id"] == "126508" and set(seen["exclude"]) == {"1", "2"}


def test_the_activity_adapter_says_unknown_when_the_origin_is_not_in_the_catalog(monkeypatch):
    monkeypatch.setattr(review_alternatives, "find_place_candidates", lambda *a, **k: None)
    assert review_alternatives.rank(object(), "t", "no-such-place", AT) is None
