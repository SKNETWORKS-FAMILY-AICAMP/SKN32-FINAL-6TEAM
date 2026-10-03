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


# ── 적대 검토 보완 `[2026-10-03]` ─────────────────────────────────────

def test_an_item_without_an_end_is_not_reported_as_a_time_order_error():
    """끝 시각이 없는 뒤 항목(전망대 방문 등)을 밀 때 끝=시작인 값을 만들어 `time_order`(끝이 시작보다 빠르다)로 오경고했다 — 모르는 끝은 그대로 모름으로 둔다."""
    meal = lunch()
    open_ended = item(2, "activity", "전망대", "13:00", "13:30", closes="22:00")
    open_ended = Item(item_id=open_ended.item_id, seq=2, kind="activity", title="전망대", place_id=open_ended.place_id,
                      starts_at=at("13:00"), ends_at=None, place=open_ended.place, detail={})
    assert delay_knock_on([meal, open_ended], meal, 30) == []


def test_an_item_without_an_end_still_reports_a_real_closing_problem():
    meal = lunch()
    closes_soon = Item(item_id=uuid4(), seq=2, kind="activity", title="전망대", place_id=uuid4(), starts_at=at("13:00"), ends_at=None,
                       place=place("전망대", "13:10"), detail={})
    [knock] = delay_knock_on([meal, closes_soon], meal, 30)                    # 13:30 시작인데 13:10 에 닫는다
    assert knock.item is closes_soon and any("13:10" in reason for reason in knock.reasons)


def test_a_booked_item_stays_where_it_is_so_the_push_does_not_continue_past_its_original_end():
    """예약 · 고정 일정은 밀리지 않는다 — 늦는 것은 **우리**이고 그 일정은 제 시각에 시작해 제 시각에 끝난다. 뒤로는 그 **원래 끝**(14:00)에서 이어진다.
    전에는 고정 일정도 밀린 것처럼 세어(13:30+60분 = 14:30) 뒤 항목을 14:30 에 닫는 것으로 오경고했다."""
    meal = lunch()
    booked = item(2, "activity", "예약한 체험", "13:00", "14:00", booking="BK-1")
    after = item(3, "activity", "산책", "14:10", "15:00", closes="14:40")          # 원래 끝 14:00 에서 이어지면 14:10 시작 그대로 — 14:40 전에 끝나는 것은 아니지만 밀리지 않는다
    knocks = delay_knock_on([meal, booked, after], meal, 30)
    assert [k.item.title for k in knocks] == ["예약한 체험"]                          # 산책은 밀리지 않으니 걸리지 않는다


def test_the_sentence_for_a_booked_item_does_not_claim_a_new_start_time():
    meal = lunch()
    booked = item(2, "activity", "예약한 체험", "13:00", "14:00", booking="BK-1")
    text = knock_on_text(meal, 20, delay_knock_on([meal, booked], meal, 20))
    assert "예약한 체험 — 예약·고정한 시각(13:00)에 늦는다" in text and "13:20 시작" not in text


def test_the_sentence_offers_only_things_the_service_can_actually_do():
    """채팅이 해 주는 일은 「다른 곳으로 바꿔줘」(대체 찾기)다 — 뒤 일정의 **시각을 밀어 달라**는 말은 처리하는 길이 없어 약속하지 않는다."""
    meal, museum = lunch(), item(2, "activity", "박물관", "13:00", "15:00", closes="15:10")
    text = knock_on_text(meal, 30, delay_knock_on([meal, museum], meal, 30))
    assert "바꿔줘" in text and "박물관" in text
    assert "조정하시거나" not in text and "맞출게요" not in text


def test_the_minutes_prompt_does_not_promise_to_realign_the_later_schedule():
    from app.modules.travel_ops import trip_messages

    source = open(trip_messages.__file__, encoding="utf-8").read()
    assert "뒤 일정을 맞출게요" not in source


def test_plan_delay_reads_the_arrival_in_seoul_time():
    """DB 세션이 UTC 면 일정 시각이 UTC 로 읽힌다 — 알림의 「점심 도착이 HH:MM」과 판정이 서울 시계여야 한다."""
    from datetime import timezone

    meal = item(1, "dining", "점심 식사", "12:00", "13:00")
    meal = Item(item_id=meal.item_id, seq=1, kind="dining", title="점심 식사", place_id=meal.place_id, starts_at=meal.starts_at.astimezone(timezone.utc),
                ends_at=meal.ends_at.astimezone(timezone.utc),
                place={**meal.place, "attributes": {"hours": ["11:00", "22:00"], "break": ["13:00", "17:00"], "last_order_before_break_min": 30}}, detail={})
    plan = plan_delay(trip=_trip(), items=[meal], places=[meal.place], at=at("11:30"), minutes=30, message="30분 늦어요", request_id=None)
    # 12:30 도착 — 서울 시계로 브레이크(13:00~17:00)앞 라스트오더(12:30) 여유가 20분이 안 된다 → 이 식당은 안 된다(`still_fits` 가 아니다)
    assert not (isinstance(plan, NoChange) and plan.status == "still_fits")
