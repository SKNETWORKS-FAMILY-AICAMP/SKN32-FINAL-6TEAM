# -*- coding: utf-8 -*-
"""설문의 여행자 구성 인원(`party_size`) — 계약 칸 · 로딩 설문 입구 · 합치기. `[2026-10-20 사용자 결정 — B안 · ST4F-581]`

계약: `wiki/external/rest-endpoints/trips.md` 「constraints.survey」 · `web-intakes.md` 「설문 질문」 · 등록 규칙(여행 인원이 비었을 때만)은
`tests/e2e/test_intake_survey_questions.py` 가 본다(DB 필요).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domains.travel_ops.components.intake import survey_answers
from app.domains.travel_ops.components.planning.planner import MAX_PARTY
from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION, TripSurvey


@pytest.mark.parametrize("size", [None, *range(1, MAX_PARTY + 1)])
def test_the_survey_takes_a_party_size_inside_the_product(size):
    assert TripSurvey.model_validate({"version": SURVEY_VERSION, "party_size": size}).party_size == size


@pytest.mark.parametrize("size", [0, MAX_PARTY + 1, -1])
def test_the_survey_refuses_a_party_size_outside_the_product(size):
    with pytest.raises(ValidationError):
        TripSurvey.model_validate({"version": SURVEY_VERSION, "party_size": size})


def test_the_loading_survey_entrance_takes_the_size_as_text_and_the_survey_gets_a_number():
    clean = survey_answers.check({"party": "friends", "party_size": "3"})
    assert clean == {"party": "friends", "party_size": "3"}
    assert survey_answers.to_survey(clean) == {"party": "friends", "party_size": 3}
    assert survey_answers.resolve("party_size", str(MAX_PARTY)) == ("party_size", str(MAX_PARTY))
    assert "party_size" not in {question.id for question in survey_answers.QUESTIONS}          # 묻는 문항이 아니다 — 받기만 한다


@pytest.mark.parametrize("value", ["0", str(MAX_PARTY + 1), 3, "셋", {"custom": "3"}])
def test_the_entrance_refuses_a_size_it_does_not_know(value):
    with pytest.raises(survey_answers.InvalidAnswers):
        survey_answers.check({"party_size": value})


def test_the_registration_request_size_wins_over_the_saved_answer():
    merged = survey_answers.merged_survey({"party_size": "4"}, {"version": SURVEY_VERSION, "party_size": 2})
    assert merged["party_size"] == 2
    assert survey_answers.merged_survey({"party_size": "4"}, None)["party_size"] == 4
