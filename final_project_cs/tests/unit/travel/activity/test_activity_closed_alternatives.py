# -*- coding: utf-8 -*-
"""휴무 · 운영시간 밖이면 변경 제안에 **대체 장소 후보**를 붙인다 — `[2026-10-09]` team 통합 ④(role-activity 판의 대체 장소).

후보 계산은 role-activity 판 그대로(`ReplacementMixin._recommend_alternatives` · `alternatives.rank_alternatives`):
관광공사 목록에서 비슷한 곳 → 가까운 곳, 그 시각에 여는지 확인된 곳만 답변에 싣는다. 제안은 여전히 `booking.change`
(승인 대기)다. 장소를 바꿔도 안 풀리는 사유(재난 정지)와 감시 경로가 맡는 사유(공유 점검 이상)에는 붙이지 않는다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam

from ..helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "checks": [], "failed_categories": [],
         "not_connected": []}
WEEK = {day: {"open": "09:00", "close": "18:00"} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
PLACE = {"place_id": "p1", "name": "경복궁", "weather_sensitive": False, "latitude": 37.5796, "longitude": 126.9770,
         "source_content_id": "origin"}


def _hours(week):
    return {"known": True, "attributes": {"hours_week": week}, "source": "tour_api", "why_unknown": None,
            "conditions": [], "usetime_text": None, "restdate_text": None}


def _row(cid, title, *, closed="연중무휴", x=126.9770, y=37.5796):
    return {"contentid": cid, "title": title, "contenttypeid": "12", "lclsSystm1": "HS", "lclsSystm2": "HS01",
            "lclsSystm3": "HS010100", "mapx": str(x), "mapy": str(y), "closed_days": closed, "business_hours": None,
            "brand": None}


ORIGIN = _row("origin", "경복궁", closed="매주 화요일")
POOL = {"origin": ORIGIN, "source": "place_catalog", "confirmed_at": "2026-10-09T03:00:00+09:00",
        "candidates": [_row("a", "창덕궁", x=126.9910, y=37.5794),
                       _row("b", "덕수궁", x=126.9751, y=37.5658),
                       _row("c", "종묘", closed="매주 화요일", x=126.9941, y=37.5744)]}


def _run(*, week=None, place=PLACE, pool=POOL, report=CLEAR):
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY,
                               "party_size": 2, "capacity": 4},
              "read.policy": [], "read.place": place, "read.disruptions": report,
              "read.place_hours": _hours(week or {**WEEK, "tue": "closed"}),
              "read.place_candidates": pool}
    tools = FakeTools(values)
    result = asyncio.run(ActivityTeam(tools).execute(
        task("activity", "activity.check_feasible", pack("activity", scope=["activity"]), ALLOWED)))
    return result, [name for name, _ in tools.calls]


def test_the_candidates_tool_is_declared():
    assert "read.place_candidates" in ALLOWED


def test_a_closed_day_proposal_carries_ranked_alternatives_open_that_day():
    result, called = _run()
    decision = result.decisions[0]

    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert [p.action_type for p in result.action_proposals] == ["booking.change"]
    assert decision["reason"] == "closed_weekday" and decision["alternatives"]["status"] == "ranked"
    titles = [a["title"] for a in decision["alternatives"]["alternatives"]]
    assert "종묘" not in titles and {"창덕궁", "덕수궁"} <= set(titles)      # ★같은 화요일 휴무는 뺀다
    assert "대체 장소 후보:" in result.answer and "창덕궁" in result.answer
    assert called.count("read.place_candidates") == 1


def test_outside_hours_also_carries_alternatives():
    late = {**WEEK, "tue": {"open": "09:00", "close": "12:00"}}
    result, _ = _run(week=late)
    decision = result.decisions[0]

    assert decision["reason"] == "outside_hours" and decision["alternatives"]["status"] == "ranked"


def test_without_a_tour_id_it_says_so_and_still_proposes():
    result, called = _run(place={**PLACE, "source_content_id": None})
    decision = result.decisions[0]

    assert decision["alternatives"] == {"status": "unknown", "reason": "no_content_id"}
    assert "대체 장소를 찾지 못했습니다" in result.answer
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert "read.place_candidates" not in called


def test_an_unreadable_pool_is_unknown_not_empty():
    result, _ = _run(pool=None)

    assert result.decisions[0]["alternatives"] == {"status": "unknown", "reason": "pool_unavailable"}
    assert "후보를 조회하지 못했습니다" in result.answer


def test_an_open_day_does_not_look_for_alternatives():
    result, called = _run(week=WEEK)

    assert result.decisions[0]["feasible"] is True and "read.place_candidates" not in called


def test_a_shared_check_disruption_does_not_look_for_alternatives():
    """날씨 · 통제는 감시 경로의 대체 계산(`plan_activity_adjustment`)이 맡는다."""
    disrupted = {**CLEAR, "verdict": "disrupted", "disruptions": [{"kind": "호우경보"}]}
    result, called = _run(report=disrupted)

    assert result.decisions[0]["reason"] == "disrupted" and "read.place_candidates" not in called


def test_a_safety_stop_does_not_look_for_alternatives():
    """재난 정지는 그날 · 여행 전체를 멈춘다 — 그날의 다른 장소를 권하지 않는다."""
    message = {"kind": "민방공", "step": "위급재난", "text": "[행정안전부] 공습 대비 민방공 경보 발령",
               "created_at": "2026-11-10T12:00:00+09:00", "regions": ["서울특별시 종로구"], "serial": "1",
               "weather": False}
    report = {**CLEAR, "checks": [{"category": "disaster_msg", "status": "ok", "unclassified": [message]}]}
    result, called = _run(report=report)

    assert result.decisions[0]["reason"] == "safety_event" and "read.place_candidates" not in called
