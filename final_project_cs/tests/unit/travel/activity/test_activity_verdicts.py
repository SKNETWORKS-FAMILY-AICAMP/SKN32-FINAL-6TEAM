# -*- coding: utf-8 -*-
"""활동 장소 판정 — 코어 끼움 자리에 꽂을 함수(`verdicts.py`)와 감시 루프의 재난문자 다시 보기. `[2026-10-12]`

같은 판정을 고객 문의 · 계획 검증 · 감시가 쓴다(요식 팀 `dining_ledger` 와 같은 구조 — 2026-10-12 사용자 결정).
여기서는 ① 계산 함수 자체 ② 감시 루프가 공유 점검의 재난문자 이상을 활동 판정으로 거르는지 본다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity.team import _without_cleared_disasters, plan_activity_trigger
from app.domains.travel_ops.instances.activity.verdicts import disaster_verdict, holidays_needed, hours_verdict

from ..helpers import FakeTools, pack, task

KST = timezone(timedelta(hours=9))
TUESDAY = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
WEEK = {d: {"open": "09:00", "close": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def _hours(*, week=WEEK, restdate=None, usetime="09:00~18:00", known=True):
    return {"known": known, "attributes": {"hours_week": week} if week else {}, "source": "tour_api",
            "why_unknown": None, "usetime_text": usetime, "restdate_text": restdate}


# ── 휴무 · 운영시간 ──────────────────────────────────────────────

def test_hours_open_and_within():
    v = hours_verdict(_hours(), TUESDAY)
    assert v["closed"] is False and v["within_hours"] is True and v["empty"] is False


def test_hours_weekday_closed_from_the_week_table():
    v = hours_verdict(_hours(week={**WEEK, "tue": "closed"}), TUESDAY)
    assert v["closed"] is True and v["within_hours"] is None


def test_hours_text_the_week_table_cannot_express():
    """「매월 둘째 주 화요일」 — 요일표는 매주 열지만 원문이 앞선다. 2026-11-10 은 11월 둘째 화요일."""
    v = hours_verdict(_hours(restdate="매월 둘째 주 화요일 휴무"), TUESDAY)
    assert v["closed"] is True and v["quote"]


def test_hours_outside():
    v = hours_verdict(_hours(), TUESDAY.replace(hour=19))
    assert v["closed"] is False and v["within_hours"] is False


def test_hours_empty_is_not_open():
    v = hours_verdict(_hours(week=None, usetime=None, known=False), TUESDAY)
    assert v["empty"] is True and v["closed"] is None and v["within_hours"] is None


def test_hours_unknown_tool_value_is_not_empty():
    v = hours_verdict(None, TUESDAY)
    assert v["empty"] is False and v["closed"] is None


def test_holiday_condition_uses_the_given_lookup():
    """「매주 월요일 휴무, 단 공휴일이면 정상 운영」 — 공휴일 여부는 부르는 쪽이 넘긴다."""
    monday = datetime(2026, 10, 12, 14, 0, tzinfo=KST)
    text = "매주 월요일 휴무 (단, 월요일이 공휴일인 경우 정상 운영)"
    assert holidays_needed(text, monday) == [date(2026, 10, 12)]
    assert hours_verdict(_hours(restdate=text), monday, holiday=lambda d: {"is_holiday": False})["closed"] is True
    assert hours_verdict(_hours(restdate=text), monday, holiday=lambda d: {"is_holiday": True})["closed"] is False
    caveat = hours_verdict(_hours(restdate=text), monday)          # 공휴일을 모르면 휴무로 두고 단서
    assert caveat["closed"] is True and caveat["needs_caveat"] is True


# ── 재난 영향 ─────────────────────────────────────────────────

def _msg(kind, text, created="2026-10-14T05:30:00+09:00"):
    return {"kind": kind, "step": "긴급재난", "text": text, "created_at": created, "category": "disaster_msg"}


def test_disaster_verdict_shapes():
    at = datetime(2026, 10, 14, 14, 0, tzinfo=KST)
    assert disaster_verdict([_msg("산사태", "인왕산 산사태")], outdoor=False, at=at)["blocks"] is True
    assert disaster_verdict([_msg("폭염", "폭염특보")], outdoor=None, at=at)["ask_outdoor"] is True
    assert disaster_verdict([_msg("정전", "정전 복구가 완료되었습니다")], outdoor=False, at=at)["blocks"] is False


# ── 감시 루프 — 공유 점검의 재난문자 이상을 활동 판정으로 다시 본다 ─────────────

def _item(*, sensitive=False, hour=14):
    return SimpleNamespace(kind="activity", starts_at=datetime(2026, 10, 14, hour, 0, tzinfo=KST),
                           place={"place_id": "p1", "name": "여의도한강공원", "weather_sensitive": sensitive})


def _disrupted(*items):
    return {"verdict": "disrupted", "disruptions": list(items), "checks": []}


def test_watch_clears_a_recovery_message():
    report = _without_cleared_disasters(_disrupted(_msg("정전", "[송파구] 정전 복구가 완료되었습니다")), _item())
    assert report["verdict"] == "clear" and report["cleared_by_activity"] == 1


def test_watch_clears_a_message_whose_control_window_has_passed():
    msg = _msg("호우", "[서울시] 한강공원 전면 통제 (10/14 06:00~10/14 12:00)")
    assert _without_cleared_disasters(_disrupted(msg), _item(hour=14))["verdict"] == "clear"
    assert _without_cleared_disasters(_disrupted(msg), _item(hour=10))["verdict"] == "disrupted"


def test_watch_keeps_other_categories_and_unknown_indoor():
    road = {"category": "traffic_control", "kind": "road_closed"}
    heat = _msg("폭염", "폭염특보 발효")
    report = _without_cleared_disasters(_disrupted(road, heat), _item(sensitive=None))
    assert report["verdict"] == "disrupted" and len(report["disruptions"]) == 2   # ★감시에서는 묻지 않고 남긴다


def test_watch_trigger_returns_no_change_when_every_disaster_is_cleared():
    tools = FakeTools({"read.disruptions": _disrupted(_msg("정전", "정전 복구가 완료되었습니다"))})
    team = ActivityTeam(tools)
    t = task("activity", "activity.itinerary", pack("activity", scope=["activity"]), ActivityTeam.manifest.allowed_tools)
    plan = plan_activity_trigger(team, t, {"evidence": [], "seen": set(), "trip": {}}, _item())
    assert isinstance(plan, NoChange) and plan.status == "clear"
