# -*- coding: utf-8 -*-
"""취향을 **팀이 실제로 받아** 대체 후보 순위가 바뀌는가 — `[2026-10-12]` 전달사항 「취향 추천 연결」.

전에는 함수 단위(`preference_of` · `score`)만 시험했다. 여기서는 Case 상태(`current_state`)로 들어온 값이
팀 → `replacement._preference` → `rank_alternatives` 를 지나 `decisions[].alternatives` 순서를 바꾸는지 본다.

받는 값(활동 쪽 — 지금 코드):
    current_state["activity_preference"]  "activity"(활동 중요) · "mobility"(이동 중요) — 먼저 본다
    current_state["survey"]["priority"]     설문 순서에서 먼저 나오는 activity · mobility (`food` 는 건너뛴다)
★코어는 아직 이 둘을 팀에 넘기지 않는다(`Controller.TEAM_STATE_KEYS`) — 마지막 시험이 그 사실을 붙잡아 둔다.
  공통 형식(취향 · 기피 · 가중치)은 코어와 정할 일이다(전달사항 · 협의 메모).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.instances.activity import ActivityTeam

from ..helpers import FakeTools, pack, task
from ._disaster import disaster_from

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": []}
WEEK = {day: {"open": "09:00", "close": "18:00"} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
PLACE = {"place_id": "p1", "name": "경복궁", "weather_sensitive": False, "latitude": 37.5796, "longitude": 126.9770,
         "source_content_id": "origin"}


def _row(cid, l3, *, x, y, closed="연중무휴"):
    return {"contentid": cid, "title": cid, "contenttypeid": "12", "lclsSystm1": "HS", "lclsSystm2": "HS01",
            "lclsSystm3": l3, "mapx": str(x), "mapy": str(y), "closed_days": closed, "business_hours": None,
            "brand": None}


# 같은 소분류는 멀고(약 4.4km), 다른 소분류는 가깝다(약 0.2km) — 취향에 따라 1순위가 갈리는 묶음
POOL = {"origin": _row("origin", "HS010100", x=126.9770, y=37.5796, closed="매주 화요일"),
        "source": "place_catalog", "confirmed_at": "2026-10-12T03:00:00+09:00",
        "candidates": [_row("same_far", "HS010100", x=127.0270, y=37.5796),
                       _row("near_other", "HS010200", x=126.9790, y=37.5800),
                       _row("near_other2", "HS010300", x=126.9800, y=37.5805)]}


def _alternatives(state: dict | None):
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY,
                               "party_size": 2, "capacity": 4},
              "read.policy": [], "read.place": PLACE, "read.disruptions": CLEAR, "read.disaster": disaster_from(CLEAR),
              "read.place_hours": {"known": True, "attributes": {"hours_week": {**WEEK, "tue": "closed"}},
                                   "source": "tour_api", "why_unknown": None, "conditions": [],
                                   "usetime_text": None, "restdate_text": None},
              "read.place_candidates": POOL}
    result = asyncio.run(ActivityTeam(FakeTools(values)).execute(
        task("activity", "activity.check_feasible", pack("activity", scope=["activity"], state=state), ALLOWED)))
    alternatives = result.decisions[0]["alternatives"]
    return [a["contentid"] for a in alternatives["alternatives"]], result.warnings


def test_without_a_preference_only_the_same_class_is_shown():
    order, _ = _alternatives(None)
    assert order == ["same_far"]          # 분류를 풀지 않는다 — 다른 소분류는 더보기에만


def test_activity_first_puts_the_similar_place_first():
    order, _ = _alternatives({"activity_preference": "activity"})
    assert order[0] == "same_far" and set(order) == {"same_far", "near_other", "near_other2"}


def test_mobility_first_puts_the_near_place_first():
    order, _ = _alternatives({"activity_preference": "mobility"})
    assert order[:2] == ["near_other", "near_other2"] and order[-1] == "same_far"


def test_the_survey_priority_is_read_when_there_is_no_explicit_preference():
    order, _ = _alternatives({"survey": {"priority": ["food", "mobility", "activity"]}})
    assert order[0] == "near_other"       # food 는 건너뛰고 mobility


def test_the_explicit_preference_wins_over_the_survey():
    order, _ = _alternatives({"activity_preference": "activity", "survey": {"priority": ["mobility"]}})
    assert order[0] == "same_far"


def test_an_unknown_preference_is_not_guessed_and_is_reported():
    order, warnings = _alternatives({"activity_preference": "cheap"})
    assert order == ["same_far"]          # 없을 때와 같다
    assert any("알 수 없는 선호도 값" in w for w in warnings)


@pytest.mark.xfail(strict=True, reason="코어 Controller.TEAM_STATE_KEYS 가 취향을 팀에 넘기지 않는다 — 코어가 고치면 "
                                       "이 시험이 「예상과 달리 통과」로 알린다(xfail 을 지우고 위 시험들을 실경로로 옮긴다)")
def test_the_core_passes_the_preference_to_the_team():
    from app.application.controller import Controller

    state = Controller._team_state({"state_json": {"activity_preference": "mobility",
                                                   "survey": {"priority": ["mobility"]}}})
    assert state.get("activity_preference") == "mobility" or "survey" in state
