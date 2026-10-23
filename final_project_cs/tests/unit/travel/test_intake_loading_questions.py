# -*- coding: utf-8 -*-
"""로딩 중 질문 — 읽은 칸은 빼고 빈 칸만 묻기(DB 없이 보는 몫). `[2026-10-19 사용자 지시]`

설계 `wiki/records/plans/2026-10-19_로딩설문_읽은칸빼고_빈칸만묻기.md` 「시험」 · 계약 `wiki/external/rest-endpoints/web-intakes.md` 「설문 질문」.
DB 를 거치는 길(접수 조회 · 저장 · 등록)은 `tests/e2e/test_intake_survey_questions.py` · `tests/e2e/test_intake_reading_prefs.py`.

재현:

    python -m pytest tests/unit/travel/test_intake_loading_questions.py -v
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.domains.travel_ops.components.intake import reading_prefs
from app.domains.travel_ops.components.intake import survey_answers as sa
from app.domains.travel_ops.components.planning.survey import ACTIVITY_DETAILS, SURVEY_VERSION, TripSurvey

ALL = ["party", "priority", "indoor_outdoor", "pace"]       # `[2026-10-19]` UI 팀 4문항에 맞춰 여행 테마는 뺐다
ONBOARDING = Path(__file__).resolve().parents[3] / "frontend" / "apps" / "web" / "src" / "features" / "onboarding" / "model.ts"


def _read(*, preferences=(), moves=(), conditions=()):
    """이해 단계 결과 한 원본 → 계획서 읽기 결과(`reading_prefs.proposals`)."""
    return reading_prefs.proposals([{"used": True, "preferences": list(preferences), "moves": list(moves), "conditions": list(conditions)}])


def _plan(found, answered=()):
    return sa.second_plan(sa.first_plan(answered), answered, found)


# ── 문항 집합 ─────────────────────────────────────────────────────
def test_the_four_questions_are_the_start_survey_without_on_disruption():
    assert [q.id for q in sa.QUESTIONS] == ALL
    assert not hasattr(sa, "MAX_QUESTIONS")                                          # 상한 3 을 없앴다
    assert "on_disruption" not in {q.id for q in sa.QUESTIONS} and "on_disruption" in sa.DIRECT   # 항로 지킴이 카드 몫 — 받기만 한다
    assert "theme" not in {q.id for q in sa.QUESTIONS} and "theme" in sa.DIRECT                   # 여행 테마도 문항이 아니다 — 받기만 한다
    assert sa.QUESTION_SET_VERSION == "3"


def test_titles_and_choices_match_the_start_survey_screen():
    """시작 설문 화면(웹 `onboarding/model.ts`)과 같은 문구 · 선택지 글. `[2026-10-20 ST4F-665]` 활동 세부 일곱 코드도 같이 대조한다 — 웹이 같은 일곱 코드를 쓰게 된 뒤로 예외를 뺐다
    (2026-10-19 에는 서버가 먼저 바꿔 웹과 달랐다). 로딩 질문 카드가 시작 설문 카드를 그대로 쓰므로 두 화면의 선택지는 이 대조 하나로 지킨다."""
    if not ONBOARDING.exists():
        pytest.skip("웹 소스가 없는 사본")
    text = ONBOARDING.read_text(encoding="utf-8")
    for question in sa.QUESTIONS:
        assert f'"{question.title}"' in text, question.id
        options = (list(question.options) if question.kind != "priority" else []) + \
            [o for g in question.groups for o in g.options]
        for option in options:
            assert re.search(rf'\["{re.escape(option.id)}", "{re.escape(option.label)}"', text), (question.id, option.id)
        if question.kind == "priority":                                                # 분야 글은 화면의 `areaNames`
            for option in question.options:
                assert f'{option.id}: ["{option.label}"' in text, option.id


def test_activity_details_are_the_seven_tourism_codes():
    priority = next(q for q in sa.QUESTIONS if q.id == "priority")
    activity = next(g for g in priority.groups if g.id == "activity")
    assert [(o.id, o.label) for o in activity.options] == [("EV", "축제/공연/행사"), ("EX", "체험관광"), ("HS", "역사관광"), ("LS", "레저스포츠"),
                                                           ("NA", "자연관광"), ("SH", "쇼핑"), ("VE", "문화관광")]
    assert dict((o.id, o.label) for o in activity.options) == ACTIVITY_DETAILS


def test_sensitive_and_unasked_slots_are_never_questions():
    slots = {q.slot for q in sa.QUESTIONS}
    assert not slots & {"dietary", "accessibility", "domestic", "mobility_ease", "day_hours", "on_disruption"}


# ── 고르는 규칙 · 두 번에 정하기 ──────────────────────────────────────
def test_first_the_two_that_the_plan_rarely_says():
    assert sa.first_plan([])["asked"] == ["party", "priority"]
    assert sa.first_plan(["party"])["asked"] == ["priority"]                 # 이어받은 답은 묻지 않는다


def test_nothing_read_means_all_four_can_be_asked():
    plan = _plan([])
    assert plan["asked"] == ALL and plan["skipped_by_reading"] == [] and plan["phase"] == 2


def test_whole_trip_subway_skips_the_transport_detail_but_one_taxi_ride_does_not():
    said = _plan(_read(moves=[{"mode": "subway", "scope": "all", "quote": "다 지하철로"}]))
    assert said["asked"] == ALL
    assert [(s["question"], s["part"], s["value"]) for s in said["skipped_by_reading"]] == [("priority", "mobility", ["subway"])]
    once = _plan(_read(moves=[{"mode": "taxi", "scope": "all", "quote": "택시로 이동"}]))
    assert once["skipped_by_reading"] == []                                            # 「택시로 이동」 한 구간은 여행 전체가 아니다


@pytest.mark.parametrize("quote, whole", [("다 지하철로", True), ("웬만하면 택시", True), ("이동은 주로 버스", True), ("늘 걸어서", True),
                                          ("모두 택시로", True), ("택시로 이동", False), ("택시로 이동합니다", False), ("다녀와요", False),
                                          ("하루 종일 걸어 다님", False), ("", False), (None, False)])
def test_whole_trip_words(quote, whole):
    assert reading_prefs.whole_trip_said(quote) is whole


def test_rain_indoor_leaves_only_the_dining_part():
    plan = _plan(_read(conditions=[{"code": "if_rain_indoor", "quote": "비 오면 실내로"}]))
    assert "indoor_outdoor" in plan["asked"]
    assert [(s["question"], s["part"], s["value"]) for s in plan["skipped_by_reading"]] == [("indoor_outdoor", "activity", "indoor")]
    shown = next(q for q in sa.questions({}, plan) if q["id"] == "indoor_outdoor")
    assert {p["id"]: (p["read"] or {}).get("value") for p in shown["parts"]} == {"dining": None, "activity": "indoor"}


def test_a_read_pace_drops_the_whole_question():
    plan = _plan(_read(preferences=[{"code": "late_start", "quote": "늦게 일어나서"}]))
    assert "pace" not in plan["asked"]
    assert plan["skipped_by_reading"] == [{"question": "pace", "part": None, "key": "survey.pace", "value": "relaxed",
                                           "text": "여유 있게", "quotes": ["늦게 일어나서"]}]


def test_the_area_order_is_asked_even_when_every_readable_detail_was_read():
    plan = _plan(_read(preferences=[{"code": "prefer_taxi", "quote": "웬만하면 택시"}, {"code": "food_focus", "quote": "맛집 위주"}]))
    assert "priority" in plan["asked"]
    assert {s["part"] for s in plan["skipped_by_reading"] if s["question"] == "priority"} == {"food", "mobility"}


def test_party_hints_never_skip_the_party_question():
    """아이 · 어르신 성향을 읽어도 구성은 추정하지 않는다 — 누구와 문항은 그대로 묻는다(10-05 기획 §7)."""
    plan = _plan(_read(preferences=[{"code": "kid_friendly", "quote": "아이랑"}, {"code": "elderly_friendly", "quote": "부모님 모시고"}]))
    assert "party" in plan["asked"]


def test_an_answered_question_is_neither_asked_nor_listed_as_read():
    found = _read(preferences=[{"code": "slow_pace", "quote": "천천히"}], conditions=[{"code": "if_rain_indoor", "quote": "비 오면 실내"}])
    plan = _plan(found, answered=["pace", "indoor_outdoor"])
    assert plan["asked"] == ["party", "priority"] and plan["skipped_by_reading"] == []


def test_the_second_list_only_appends_and_keeps_the_first_order():
    first = sa.first_plan([])
    second = sa.second_plan(first, ["party"], [])                                     # 첫 조회 뒤에 누구와를 답했다 — 누구와는 남는다
    assert second["asked"][:2] == first["asked"] and second["asked"] == ALL


def test_the_questions_view_follows_the_plan_order_and_shows_answers():
    answers = sa.check({"party": "friends", "priority": {"areas": ["mobility", "food"], "details": {"mobility": ["walk"]}}})
    shown = sa.questions(answers, {"asked": ["party", "priority"], "skipped_by_reading": []})
    assert [q["id"] for q in shown] == ["party", "priority"]
    assert shown[0]["answer"] == "friends" and shown[1]["answer"] == {"areas": ["mobility", "food"], "details": {"mobility": ["walk"]}}


# ── 답 모양 · 설문으로 ─────────────────────────────────────────────
def test_compound_answers_are_stored_as_sorted_json_and_reach_the_survey_shape():
    checked = sa.check({"priority": {"details": {"food": ["nopo"]}, "areas": ["food", "activity"]},
                        "indoor_outdoor": {"activity": "outdoor", "dining": "any"}, "theme": "local", "pace": "moderate"})   # 테마는 받아 두기만 한다
    assert checked["priority"] == '{"areas":["food","activity"],"details":{"food":["nopo"]}}'
    survey = sa.to_survey(checked)
    assert survey == {"priority": ["food", "activity"], "priority_details": {"food": ["nopo"]},
                      "indoor_outdoor": {"dining": "any", "activity": "outdoor"}, "theme": "local", "pace": "moderate"}
    TripSurvey.model_validate({"version": SURVEY_VERSION, **survey})


@pytest.mark.parametrize("answer", [{"areas": ["food"], "details": {"food": ["taste", "taste"]}}, {"areas": ["walk"]},
                                    {"areas": ["food"], "extra": 1}, {"details": {}}, ["food"]])
def test_a_wrong_priority_shape_is_refused(answer):
    with pytest.raises(sa.InvalidAnswers):
        sa.check({"priority": answer})


def test_bundle_2_answers_keep_their_meaning_only_through_history():
    assert sa.resolve("priority", "activity") is None                                 # 옛 단일 답을 새 우선순위로 읽지 않는다
    assert sa.to_survey({"priority": "activity"}, {"priority": ("activity", "priority", "activity")}) == {"priority": ["activity"]}
    assert sa.to_survey({"preferred_mobility": "taxi"}, {"preferred_mobility": ("taxi", "preferred_mobility", "taxi")}) == \
        {"priority_details": {"mobility": ["taxi"]}}


def test_the_replacement_question_for_the_activity_team_stays_as_it_was():
    question = sa.REPLACEMENT_QUESTION
    assert question.id == "priority" and question.kind == "single"
    assert [(o.id, o.label) for o in question.options] == [("activity", "하고 싶은 활동이 비슷한 곳"), ("mobility", "이동이 편한 곳")]
