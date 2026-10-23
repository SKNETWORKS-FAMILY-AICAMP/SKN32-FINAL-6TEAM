"""로딩 중 질문의 직접 입력 · 답 취소 — DB 없이 확인하는 몫. `[2026-10-09]` · `[2026-10-19 묶음 3]`

직접 입력은 묶음 3에서 「누구와」(party)의 「기타」뿐이다. 묶음 2의 직접 입력(이동 수단 「택시 + 버스」)은 이력의 해석 값으로만 읽힌다.
"""
import pytest

from app.domains.travel_ops.components.intake import survey_answers as answers
from app.domains.travel_ops.components.planning.survey import TripSurvey, SURVEY_VERSION
from app.domains.travel_ops.instances.mobility.wiring import modes_from_survey


def test_custom_party_is_kept_word_for_word_and_is_a_valid_survey():
    checked = answers.check({"party": {"custom": "  부모님과 아이 둘 "}})
    assert checked == {"party": "custom:부모님과 아이 둘"}
    survey = answers.to_survey(checked)
    assert survey == {"party": "부모님과 아이 둘", "custom_answers": {"party": "부모님과 아이 둘"}}
    TripSurvey.model_validate({"version": SURVEY_VERSION, **survey})


def test_a_bundle_2_custom_transport_answer_is_still_read_through_its_history():
    """묶음 2에서 저장한 「택시 + 버스」 — 이력의 해석 값(슬롯 preferred_mobility)으로 읽혀 이동 계산기까지 간다."""
    option = "custom:택시 + 버스"
    survey = answers.to_survey({"preferred_mobility": option}, {"preferred_mobility": (option, "preferred_mobility", option)})
    TripSurvey.model_validate({"version": SURVEY_VERSION, **survey})
    assert survey["custom_answers"]["preferred_mobility"] == "택시 + 버스"
    assert modes_from_survey({"survey": survey}) == ["bus", "taxi", "walk"]


def test_clear_is_accepted_only_for_questions_and_does_not_become_an_answer():
    assert answers.check({"party": None}) == {"party": None}
    assert answers.check({"priority": None}) == {"priority": None}
    with pytest.raises(answers.InvalidAnswers):
        answers.check({"on_disruption": None})


@pytest.mark.parametrize("value", [{"custom": " "}, {"custom": "x" * 1001}, {"custom": "혼자", "extra": "x"}, "custom:혼자"])
def test_custom_shape_limits_and_reserved_encoding_cannot_be_bypassed(value):
    with pytest.raises(answers.InvalidAnswers):
        answers.check({"party": value})


@pytest.mark.parametrize("question", ["theme", "pace", "priority", "indoor_outdoor"])
def test_only_the_party_question_takes_free_text(question):
    with pytest.raises(answers.InvalidAnswers):
        answers.check({question: {"custom": "아무거나"}})


def test_custom_and_choice_can_replace_each_other_using_the_saved_meaning():
    custom = answers.check({"party": {"custom": "회사 동료"}})
    shown = next(q for q in answers.questions(custom) if q["id"] == "party")
    assert shown["answer"] is None and shown["custom_answer"] == "회사 동료"
    replaced = answers.to_survey({"party": "family"}, {"party": (custom["party"], "party", custom["party"])})
    assert replaced == {"party": "family"}
