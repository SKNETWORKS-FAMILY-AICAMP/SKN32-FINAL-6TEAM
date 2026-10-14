# -*- coding: utf-8 -*-
"""예약 성립 판정이 **예약이 속한 여행의 설문**으로 대체 후보 순서를 정한다 — `[2026-10-14]` 활동 → 코어 전달 8번 회신.

`wiki/records/reports/2026-10-13_활동_전달8_설문전달_회신.md` 의 흐름:
  1. `read.booking` 의 `trip`(공용 도구가 찾는다) → `read.itinerary` 로 그 여행의 설문
  2. 여행을 기간으로 추정했거나 예약을 추정으로 골랐으면 「추정」이라고 남긴다
  3. 못 찾았고 검증된 후보가 두 곳 이상이면 답변 끝에 설문 문항 하나를 다시 묻는다(지난 답이 있으면 알려 준다) — 안내는 막지 않는다
  4. 고객이 고른 말이 이번 문의 문장에 있으면 그 선택을 쓴다(저장하지 않는다)
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.instances.activity.replacement import REPLY_PHRASES, ask_question, reply_choice

from ..helpers import FakeTools, pack, task
from ._disaster import disaster_from
from .test_activity_preference_received import ALLOWED, CLEAR, PLACE, POOL, TUESDAY, WEEK

TRIP = "7d1f3c4e-0000-4000-8000-000000000001"


def _values(*, trip=None, survey=None, matched_by="case", last=None):
    booking = {"booking_id": "b1", "place_id": "p1", "starts_at": TUESDAY, "party_size": 2, "capacity": 4,
               "matched_by": matched_by, "trip": trip or {"trip_id": None, "matched_by": None, "why_unknown": "not_linked"}}
    values = {"read.booking": booking, "read.policy": [], "read.place": PLACE, "read.disruptions": CLEAR,
              "read.disaster": disaster_from(CLEAR),
              "read.place_hours": {"known": True, "attributes": {"hours_week": {**WEEK, "tue": "closed"}},
                                   "source": "tour_api", "why_unknown": None, "conditions": [],
                                   "usetime_text": None, "restdate_text": None},
              "read.place_candidates": POOL}
    if survey is not None:
        values["read.itinerary"] = {"trip": {"trip_id": TRIP, "constraints": {"survey": survey}}, "items": []}
    if last is not None:
        values["read.last_survey_answer"] = last
    return values


def _run(values, *, state=None, text="이 활동 되나요?"):
    tools = FakeTools(values)
    result = asyncio.run(ActivityTeam(tools).execute(
        task("activity", "activity.check_feasible", pack("activity", scope=["activity"], state=state), ALLOWED,
             input_text=text)))
    alt = result.decisions[0]["alternatives"]
    return result, alt, [a["contentid"] for a in alt["alternatives"]], [name for name, _ in tools.calls]


def test_the_survey_of_the_trip_the_booking_belongs_to_orders_the_candidates():
    result, alt, order, calls = _run(_values(trip={"trip_id": TRIP, "matched_by": "itinerary_item", "why_unknown": None},
                                             survey={"priority": ["mobility", "activity"]}))

    assert order[:2] == ["near_other", "near_other2"]                     # 이동 중요 — 가까운 곳 먼저
    assert alt["preference"] == {"value": "mobility", "from": "survey",
                                 "survey": {"from": "trip", "trip_id": TRIP, "matched_by": "itinerary_item",
                                            "guessed": False}}
    assert "read.itinerary" in calls and "read.last_survey_answer" not in calls
    assert not any("추정" in w for w in result.warnings)
    assert "취향을 알려 주시면" not in result.answer                       # 설문이 있으면 묻지 않는다
    sent = next(e for e in result.evidence if e.source_id == "read.itinerary")
    assert "mobility" not in str(sent.value)                               # 근거에는 설문 칸 이름만


def test_a_trip_found_by_its_dates_is_marked_as_a_guess():
    result, alt, order, _ = _run(_values(trip={"trip_id": TRIP, "matched_by": "trip_period", "why_unknown": None},
                                         survey={"priority": ["mobility"]}))

    assert order[0] == "near_other" and alt["preference"]["survey"]["guessed"] is True
    assert any("추정으로 찾아" in w for w in result.warnings)


def test_a_guessed_booking_makes_the_survey_a_guess_too():
    result, alt, _, _ = _run(_values(trip={"trip_id": TRIP, "matched_by": "itinerary_item", "why_unknown": None},
                                     survey={"priority": ["activity"]}, matched_by="nearest"))

    assert alt["preference"]["survey"]["guessed"] is True and any("추정으로 찾아" in w for w in result.warnings)


def test_without_a_trip_the_question_is_asked_at_the_end_with_the_last_answer():
    last = {"option_id": "mobility", "value": "mobility", "label": "이동이 편한 곳"}
    result, alt, order, calls = _run(_values(last=last))

    assert order == ["same_far"]                                           # 안내는 코드 순서로 먼저 나간다
    asked = alt["preference"]["asked"]
    assert asked["question_id"] == "priority" and asked["last"] == last
    assert [o["id"] for o in asked["options"]] == [o.id for o in ask_question().options]
    assert result.answer.rstrip().endswith("지난번에는 「이동이 편한 곳」을 고르셨어요.")
    assert ask_question().title in result.answer
    assert "read.itinerary" not in calls                                   # 찾은 여행이 없으면 여행을 읽지 않는다
    assert alt["preference"]["survey"] == {"from": None, "why": "not_linked"}


def test_without_a_last_answer_the_question_is_still_asked():
    result, alt, _, _ = _run(_values())

    assert alt["preference"]["asked"]["last"] is None
    assert "지난번에는" not in result.answer and "취향을 알려 주시면" in result.answer


def test_a_trip_without_a_survey_asks_too():
    result, alt, _, _ = _run(_values(trip={"trip_id": TRIP, "matched_by": "itinerary_item", "why_unknown": None},
                                     survey={}))

    assert alt["preference"]["survey"]["why"] == "trip_without_survey" and "asked" in alt["preference"]


def test_the_customer_s_choice_in_this_message_is_used_and_not_asked_again():
    result, alt, order, calls = _run(_values(), text="이동이 편한 곳으로 다시 보여 주세요")

    assert order[0] == "near_other"
    assert alt["preference"]["value"] == "mobility" and alt["preference"]["from"] == "customer_reply"
    assert "asked" not in alt["preference"] and "read.last_survey_answer" not in calls


def test_the_reply_on_resume_comes_from_customer_input():
    _, alt, order, _ = _run(_values(), state={"customer_input": "하고 싶은 활동이 비슷한 곳"},
                            text="원래 요청: 이 활동 되나요?\n추가 답변: 하고 싶은 활동이 비슷한 곳")

    assert alt["preference"]["from"] == "customer_reply" and alt["preference"]["value"] == "activity"
    assert order[0] == "same_far"


def test_the_customer_s_choice_beats_the_old_survey():
    _, alt, order, _ = _run(_values(trip={"trip_id": TRIP, "matched_by": "itinerary_item", "why_unknown": None},
                                    survey={"priority": ["activity"]}), text="이동이 편한 곳이요")

    assert alt["preference"]["from"] == "customer_reply" and order[0] == "near_other"


def test_a_reply_naming_both_choices_is_not_guessed():
    assert reply_choice("활동이 비슷한 곳이랑 이동이 편한 곳 둘 다요") is None
    assert reply_choice("이동이  편한   곳") == "mobility"
    assert reply_choice(None) is None


def test_the_reply_phrases_are_in_the_survey_labels():
    """선택지 글이 바뀌면 고객 답을 못 알아본다 — 여기서 먼저 운다."""
    labels = {o.value: "".join(o.label.split()) for o in ask_question().options}
    assert set(labels) == set(REPLY_PHRASES)
    assert all(REPLY_PHRASES[value] in label for value, label in labels.items())


def test_near_the_tool_limit_the_survey_is_skipped_with_a_warning():
    team = ActivityTeam(FakeTools({}))
    booking = {"trip": {"trip_id": TRIP, "matched_by": "itinerary_item"}}
    seen = {f"x{i}" for i in range(team.manifest.max_steps - 1)}
    t = task("activity", "activity.check_feasible", pack("activity", scope=["activity"]), ALLOWED)

    survey, info, _, warnings = team._survey(t, booking, seen, [], reserve=1)

    assert survey is None and info["why"] == "tool_budget"
    assert any("상한" in w for w in warnings)


def test_the_case_state_survey_is_still_read_first():
    team = ActivityTeam(FakeTools({}))
    t = task("activity", "activity.check_feasible",
             pack("activity", scope=["activity"], state={"survey": {"priority": ["mobility"]}}), ALLOWED)

    survey, info, _, _ = team._survey(t, {"trip": {"trip_id": str(uuid4())}}, set(), [])

    assert survey == {"priority": ["mobility"]} and info == {"from": "case_state"}
