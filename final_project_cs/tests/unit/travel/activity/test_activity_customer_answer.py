# -*- coding: utf-8 -*-
"""고객 답을 재개 때 읽는다 — `[2026-10-13]` 코어 회신 5번.

코어는 고객 답을 이미 `customer_input` 으로 팀에 넘긴다(`TEAM_STATE_KEYS`). 빠진 것은 활동이 그 칸을 읽는 코드였다 —
읽지 않아 재개해도 같은 질문을 되풀이했다. 질문에 선택지(`choices`)를 붙이고, 고객 답이 선택지와 같으면 그 값으로 다시 판정한다.
자유 글을 해석하는 모델은 쓰지 않는다 — 선택지와 같지 않으면 다시 묻는다.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity.team import ASK_OUTDOOR, ASK_PROCEED

from ..helpers import FakeTools, pack, task

ALLOWED = ActivityTeam.manifest.allowed_tools
KST = timezone(timedelta(hours=9))
STARTS = datetime(2026, 11, 10, 14, 0, tzinfo=KST)
OPEN_WEEK = {day: {"open": "09:00", "close": "18:00", "last_entry": "17:00"}
             for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
OPEN_HOURS = {"known": True, "attributes": {"hours_week": OPEN_WEEK}, "source": "tour_api", "why_unknown": None,
              "conditions": [], "usetime_text": "09:00~18:00", "restdate_text": None}
EMPTY_HOURS = {"known": False, "attributes": {}, "source": "tour_api", "why_unknown": "읽지 못했어요", "conditions": [],
               "usetime_text": None, "restdate_text": None}
CLEAR = {"verdict": "clear", "disruptions": [], "advisories": [], "failed_categories": [], "not_connected": [],
         "checks": [{"category": "disaster_msg", "status": "ok", "unclassified": []}]}
HEAT = {"kind": "폭염", "step": "안전안내", "text": "폭염 관련 안내", "created_at": "2026-11-10T12:00:00+09:00",
        "regions": ["서울특별시 종로구"], "serial": "1"}


def _run(*, hours=OPEN_HOURS, sensitive=None, messages=(), answer=None, history=(), pending=None):
    """`pending` 이 직전에 물은 질문(`required_input_schema`), `answer` 가 방금 온 고객 답."""
    state: dict = {}
    if answer is not None:
        state["customer_input"] = {"message": answer}
    if history:
        state["customer_input_history"] = [{"message": h} for h in history]
    if pending is not None:
        state["required_input_schema"] = pending
    values = {"read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": STARTS, "party_size": 2, "capacity": 4},
              "read.policy": [],
              "read.place": {"place_id": "p1", "name": "경복궁", "weather_sensitive": sensitive,
                             "latitude": 37.5796, "longitude": 126.9770},
              "read.place_class": None,
              "read.disruptions": CLEAR,
              "read.disaster": {"for_region": list(messages), "unclassified": [], "covered": True},
              "read.place_hours": hours, "read.holiday": None}
    return asyncio.run(ActivityTeam(FakeTools(values)).execute(
        task("activity", "activity.check_feasible", pack("activity", scope=["activity"], state=state), ALLOWED)))


# ── 실내 · 야외 ────────────────────────────────────────────────

def test_the_outdoor_question_carries_choices():
    result = _run(messages=[HEAT])
    assert result.outcome == "waiting"
    assert [c["message"] for c in result.required_input_schema["choices"]] == ["실내", "야외"]
    assert "1) 실내 2) 야외" in result.answer


def test_an_outdoor_answer_is_used_instead_of_asking_again():
    result = _run(messages=[HEAT], answer="야외", pending=ASK_OUTDOOR)
    assert result.outcome != "waiting"
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL      # 야외 위험형 문자 + 야외 → 막는다(변경 제안)


def test_an_indoor_answer_lets_the_outdoor_hazard_pass_and_is_recorded():
    result = _run(messages=[HEAT], answer="실내", pending=ASK_OUTDOOR)
    assert result.outcome == "completed" and result.next_action is NextAction.RESPOND
    decision = result.decisions[0]
    assert decision["indoor"] == {"value": False, "source": "customer"}
    assert any("고객이 알려 준 값" in w for w in result.warnings)


def test_a_number_answer_picks_the_choice_when_it_was_just_asked():
    result = _run(messages=[HEAT], answer="1번", pending=ASK_OUTDOOR)       # 1번 = 실내
    assert result.outcome == "completed" and result.decisions[0]["indoor"]["value"] is False


def test_a_free_text_answer_asks_again():
    result = _run(messages=[HEAT], answer="글쎄요 잘 모르겠어요", pending=ASK_OUTDOOR)
    assert result.outcome == "waiting"


def test_a_record_of_the_place_wins_over_the_customer_answer():
    result = _run(messages=[HEAT], sensitive=False, answer="야외", pending=ASK_OUTDOOR)
    assert result.decisions[0]["indoor"]["source"] == "place"


# ── 운영 정보 모름 · 그대로 진행 / 다른 장소 ─────────────────────

def test_the_proceed_question_carries_choices():
    result = _run(hours=EMPTY_HOURS, sensitive=False)
    assert result.outcome == "waiting"
    assert [c["proceed"] for c in result.required_input_schema["choices"]] == ["keep", "change"]


def test_keep_answers_feasible_with_a_warning_and_does_not_invent_hours():
    result = _run(hours=EMPTY_HOURS, sensitive=False, answer="그대로 진행", pending=ASK_PROCEED)
    assert result.outcome == "completed"
    decision = result.decisions[0]
    assert decision["feasible"] is True and decision["customer_choice"] == "keep"
    assert any("그대로 진행하기로" in w for w in result.warnings)


def test_change_makes_a_change_proposal_for_approval():
    result = _run(hours=EMPTY_HOURS, sensitive=False, answer="2번", pending=ASK_PROCEED)
    assert result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.decisions[0]["reason"] == "customer_chose_change"


def test_the_outdoor_answer_survives_the_next_question():
    """실내외를 답한 뒤 운영 정보를 또 물으면 — 방금 물은 질문은 proceed 인데 앞의 `야외` 답을 잃지 않는다."""
    result = _run(hours=EMPTY_HOURS, messages=[HEAT], history=["실내"], answer="그대로 진행", pending=ASK_PROCEED)
    assert result.outcome == "completed"
    assert result.decisions[0]["indoor"]["value"] is False


def test_a_number_from_another_question_is_not_read():
    """직전 질문이 proceed 일 때 앞 질문의 번호(실내=1)로 읽지 않는다 — 번호는 방금 물은 질문에만 쓴다."""
    result = _run(hours=EMPTY_HOURS, messages=[HEAT], history=["1번"], answer="글쎄요", pending=ASK_PROCEED)
    assert result.outcome == "waiting"
