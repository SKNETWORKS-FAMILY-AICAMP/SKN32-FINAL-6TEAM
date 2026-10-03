# -*- coding: utf-8 -*-
"""앞 일정이 늦어지면 **뒤 일정이 아직 성립하는지** 본다 — 체크리스트 L2. `[2026-10-03]`

☆결함: 「N분 늦어요」(`plan_delay`)는 그 뒤 첫 식사 하나만 봤다. 식당이 괜찮으면 「지금 일정 그대로도 괜찮아요」로 끝났다 — 식사가 밀려 **뒤 활동·이동이 겹치거나 밀린 시각에 이미 닫는 곳**이 있어도 말하지 않았다.

★지키려는 것: ①겹치는 뒤 항목만 차례로 밀어 본다(길이 그대로, 이동 항목도 같이, 밀리지 않는 항목에서 멈춘다) ②밀려서 **영업·휴무·브레이크·입장 마감**(`check_itinerary` 와 같은 판정)에 걸리면 알린다
③**예약·고정·잠긴** 일정은 시각을 못 바꾸니 「늦는다」 ④**일정은 바꾸지 않는다** — 알리기만 ⑤괜찮으면 전처럼 `still_fits` ⑥Team(Case) 경로도 문장을 그대로 답으로 낸다.

재현:

    python -m pytest tests/unit/travel/test_delay_knock_on.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.modules.travel_ops.dining import DiningTeam
from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import NoChange, plan_delay
from app.modules.travel_ops.itinerary_delay import delay_knock_on, knock_on_text

from .helpers import FakeTools, pack, task

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 10, 6, 0, 0, tzinfo=KST)


def at(hhmm: str) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return DAY.replace(hour=hour, minute=minute)


def place(name, closes="22:00", opens="09:00"):
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.5, "longitude": 127.0,
            "attributes": {"hours": [opens, closes]}}


def item(seq, kind, title, start, end, *, closes="22:00", **detail):
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=uuid4() if kind != "mobility" else None,
                starts_at=at(start), ends_at=at(end), place=place(title, closes) if kind != "mobility" else None, detail=dict(detail))


def lunch():
    return item(1, "dining", "점심 식사", "12:00", "13:00")


def test_a_later_item_that_still_fits_after_being_pushed_is_not_blamed():
    meal, museum = lunch(), item(2, "activity", "박물관", "13:00", "15:00", closes="17:00")
    assert delay_knock_on([meal, museum], meal, 30) == []                  # 13:30~15:30 — 17:00 에 닫는 곳이라 괜찮다


def test_a_later_item_pushed_past_its_closing_time_is_reported_with_the_reason():
    meal, museum = lunch(), item(2, "activity", "박물관", "13:00", "15:00", closes="15:10")
    [knock] = delay_knock_on([meal, museum], meal, 30)                       # 13:30~15:30 — 15:10 에 닫는다
    assert knock.item is museum and knock.new_start == at("13:30") and knock.new_end == at("15:30")
    assert any("15:10" in reason and "닫는다" in reason for reason in knock.reasons)


def test_the_push_cascades_through_the_move_and_stops_where_nothing_is_pushed():
    meal = lunch()
    move = item(2, "mobility", "점심 → 박물관", "13:00", "13:20")
    museum = item(3, "activity", "박물관", "13:20", "15:00", closes="15:10")
    later = item(4, "activity", "저녁 산책", "19:00", "20:00", closes="20:30")           # 멀리 있어 밀리지 않는다
    knocks = delay_knock_on([meal, move, museum, later], meal, 30)
    assert [k.item.title for k in knocks] == ["박물관"]                                   # 이동은 같이 밀리지만 판정할 장소가 없다
    assert knocks[0].new_start == at("13:50") and knocks[0].new_end == at("15:30")       # 이동 20분이 밀려 13:30~13:50 → 박물관 13:50 시작


def test_a_small_delay_that_does_not_overlap_anything_pushes_nothing():
    meal, museum = lunch(), item(2, "activity", "박물관", "13:30", "15:00", closes="15:10")
    assert delay_knock_on([meal, museum], meal, 10) == []                                # 식사가 13:10 에 끝나 13:30 시작은 그대로다


def test_a_booked_or_pinned_item_cannot_be_moved_so_it_is_late():
    meal = lunch()
    for flag in ({"customer_pinned": True}, {"booking": "BK-1"}):
        booked = item(2, "activity", "예약한 체험", "13:00", "14:00", **flag)
        [knock] = delay_knock_on([meal, booked], meal, 20)
        assert knock.reasons == ["예약·고정한 시각(13:00)에 늦는다"]


def test_the_sentence_says_the_schedule_was_not_changed_and_promises_no_human():
    meal, museum = lunch(), item(2, "activity", "박물관", "13:00", "15:00", closes="15:10")
    text = knock_on_text(meal, 30, delay_knock_on([meal, museum], meal, 30))
    assert "점심 식사은(는) 30분 늦어도 괜찮지만" in text and "박물관(13:30 시작) — 15:30 까지인데 15:10 에 닫는다" in text and "일정은 바꾸지 않았어요" in text
    assert "사람" not in text and "담당자" not in text


# ── plan_delay 에 연결 ─────────────────────────────────────────────

def _trip():
    return {"trip_id": str(uuid4()), "version": 1, "constraints": {}, "party_size": 2}


def test_plan_delay_reports_the_knock_on_instead_of_saying_everything_is_fine():
    meal, museum = lunch(), item(2, "activity", "박물관", "13:00", "15:00", closes="15:10")
    plan = plan_delay(trip=_trip(), items=[meal, museum], places=[meal.place], at=at("11:30"), minutes=30,
                      message="30분 늦어요", request_id=None)
    assert isinstance(plan, NoChange) and plan.status == "knock_on"
    assert "박물관" in plan.detail["text"] and plan.detail["knocked"] and not hasattr(plan, "replacements")


def test_plan_delay_still_says_still_fits_when_nothing_behind_is_hurt():
    meal, museum = lunch(), item(2, "activity", "박물관", "13:00", "15:00", closes="18:00")
    plan = plan_delay(trip=_trip(), items=[meal, museum], places=[meal.place], at=at("11:30"), minutes=30,
                      message="30분 늦어요", request_id=None)
    assert isinstance(plan, NoChange) and plan.status == "still_fits"


@pytest.mark.asyncio
async def test_the_team_answers_with_the_computed_sentence_and_does_not_escalate():
    """Case 경로 — `knock_on` 은 정해진 문장이 아니라 계산 결과의 문장이라 `settle` 이 그대로 답으로 낸다(전에는 목록에 없어 사람에게 넘기는 오류로 떨어졌을 것)."""
    meal, museum = lunch(), item(2, "activity", "박물관", "13:00", "15:00", closes="15:10")
    plan = plan_delay(trip=_trip(), items=[meal, museum], places=[meal.place], at=at("11:30"), minutes=30,
                      message="30분 늦어요", request_id=None)
    team = DiningTeam(FakeTools({}))
    work = task("dining", "dining.itinerary", pack("dining"), DiningTeam.manifest.allowed_tools)
    evidence = team._evidence(work, source_id="read.itinerary", claim="현재 일정 버전", value={"items": 2})
    result = team.settle(work, {"evidence": evidence, "trip": _trip(), "items": [meal, museum], "ref": {}}, plan)
    assert result.outcome == "completed" and result.answer == plan.detail["text"] and not result.action_proposals
    assert result.failure_code is None
