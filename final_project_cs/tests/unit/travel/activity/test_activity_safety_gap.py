# -*- coding: utf-8 -*-
"""활동 성립 판정이 재난 정지와 **같은 기준**으로 막는다 — `[2026-10-09]` 가 방안(사용자 결정).

공유 점검(`read.disruptions`)은 재해구분을 모르는 문자를 `unclassified` 로만 남긴다. 그런데 재난 정지
(`planning/safety.classify`)는 그 문자로 그날 · 여행 전체를 멈춘다 — 성립 판정이 「성립」으로 답하면 둘이 어긋났다.
날씨형 위급재난은 develop 결정대로 정지 대상이 아니다(공유 점검이 실외만 이상으로 센다).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity import failure_codes as fc

from ..helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
STARTS = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
OPEN_HOURS = {"known": True, "attributes": {"hours_week": {"tue": {"open": "09:00", "close": "18:00"}}},
              "source": "tour_api", "why_unknown": None, "conditions": [], "usetime_text": None, "restdate_text": None}


def _report(*unclassified):
    return {"verdict": "clear", "disruptions": [], "advisories": [], "failed_categories": [], "not_connected": [],
            "checks": [{"category": "disaster_msg", "status": "ok", "unclassified": list(unclassified)}]}


def _message(kind, step, text):
    return {"kind": kind, "step": step, "text": text, "created_at": "2026-11-10T12:00:00+09:00",
            "regions": ["서울특별시 종로구"], "serial": "1", "weather": False}


def _run(report):
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": STARTS,
                               "party_size": 2, "capacity": 4},
              "read.policy": [],
              "read.place": {"place_id": "p1", "weather_sensitive": False, "latitude": 37.5, "longitude": 127.0},
              "read.disruptions": report, "read.place_hours": OPEN_HOURS, "read.holiday": None}
    context = pack("activity", scope=["activity"])
    return asyncio.run(ActivityTeam(FakeTools(values)).execute(task("activity", "activity.check_feasible", context, ALLOWED)))


def test_a_critical_message_of_unknown_kind_blocks_like_the_safety_pause():
    """「민방공」은 재해구분 목록에 없고 본문에 공습경보 낱말도 없다 — 공유 점검은 넘겼지만 재난 정지는 여행 전체를 멈춘다."""
    result = _run(_report(_message("민방공", "위급재난", "민방공 상황 발령, 안내에 따라 대피하십시오")))
    decision = result.decisions[0]
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert decision["feasible"] is False and decision["reason"] == "safety_event"
    assert decision["failure_code"] == fc.DISASTER_BLOCKS
    assert decision["safety"]["level"] == "trip" and decision["safety"]["step"] == "위급재난"


def test_a_day_level_event_of_an_unlisted_kind_also_blocks():
    """「원전」 긴급재난 — 재난 정지는 그날 일정을 멈춘다(`day_steps` · `day_kinds`)."""
    result = _run(_report(_message("원전", "긴급재난", "원전 사고, 반경 내 외출 자제")))
    assert result.decisions[0]["reason"] == "safety_event"
    assert result.decisions[0]["safety"]["level"] in ("day", "trip")


def test_an_ordinary_unknown_message_does_not_block():
    result = _run(_report(_message("미지정구분", "안전안내", "건조한 날씨에 화재 예방 바랍니다")))
    assert result.decisions[0]["feasible"] is True


def test_a_drill_message_does_not_block():
    """훈련 문자로 일정이 바뀌면 안 된다(`travel.safety.exclude_keywords`)."""
    result = _run(_report(_message("민방공", "위급재난", "민방위 훈련 — 실제 상황이 아닙니다")))
    assert result.decisions[0]["feasible"] is True


def test_nothing_unclassified_changes_nothing():
    result = _run(_report())
    assert result.decisions[0]["feasible"] is True and "safety" not in result.decisions[0]
