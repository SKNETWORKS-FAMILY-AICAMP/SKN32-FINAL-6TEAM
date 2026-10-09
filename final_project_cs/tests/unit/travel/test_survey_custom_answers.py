import pytest

from app.domains.travel_ops.components.intake import survey_answers as answers
from app.domains.travel_ops.components.planning.survey import TripSurvey, SURVEY_VERSION
from app.domains.travel_ops.instances.mobility.wiring import modes_from_survey


def test_custom_transport_is_preserved_and_used_by_the_actual_mobility_adapter():
    checked = answers.check({"preferred_mobility": {"custom": "택시 + 버스"}})
    survey = answers.to_survey(checked)
    TripSurvey.model_validate({"version": SURVEY_VERSION, **survey})
    assert survey["custom_answers"]["preferred_mobility"] == "택시 + 버스"
    assert modes_from_survey({"survey": survey}) == ["bus", "taxi", "walk"]


def test_unrecognized_custom_text_is_kept_without_inventing_a_preference():
    survey = answers.to_survey(answers.check({"priority": {"custom": "아무말 🧳"}}))
    assert survey == {"custom_answers": {"priority": "아무말 🧳"}}
    TripSurvey.model_validate({"version": SURVEY_VERSION, **survey})


def test_clear_is_accepted_only_for_questions_and_does_not_become_an_answer():
    assert answers.check({"preferred_mobility": None}) == {"preferred_mobility": None}
    with pytest.raises(answers.InvalidAnswers):
        answers.check({"on_disruption": None})


@pytest.mark.parametrize("value", [{"custom": " "}, {"custom": "x" * 1001}, {"custom": "taxi", "extra": "x"}, "custom:taxi"])
def test_custom_shape_limits_and_reserved_encoding_cannot_be_bypassed(value):
    with pytest.raises(answers.InvalidAnswers):
        answers.check({"preferred_mobility": value})


def test_custom_and_choice_can_replace_each_other_using_the_saved_meaning():
    custom = answers.check({"preferred_mobility": {"custom": "지하철 + 택시"}})
    shown = answers.questions(custom)[0]
    assert shown["answer"] is None and shown["custom_answer"] == "지하철 + 택시"
    replaced = answers.to_survey({"preferred_mobility": "walk"}, {"preferred_mobility": (custom["preferred_mobility"], "preferred_mobility", custom["preferred_mobility"])})
    assert replaced == {"priority_details": {"mobility": ["walk"]}}
