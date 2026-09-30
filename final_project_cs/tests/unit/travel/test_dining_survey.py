"""설문 → 요식 조건. 조건만 꺼내고, 취향과 모르는 코드는 버리는가."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "..", "..", "..", "app", "modules", "travel_ops", "dining", "survey.py")
spec = importlib.util.spec_from_file_location("dining_survey", PATH)
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


def c(food):
    return {"survey": {"version": "2026-09-24.v1", "priority_details": {"food": food}}}


def test_diet_codes_become_conditions():
    assert survey.conds_from_survey(c(["halal", "vegetarian"])) == ("halal", "vegetarian_menu")


def test_taste_codes_are_not_conditions():
    assert survey.conds_from_survey(c(["taste", "clean", "kindness"])) == ()


def test_unknown_codes_are_dropped():
    assert survey.conds_from_survey(c(["halal", "spicy"])) == ("halal",)


def test_no_survey_means_no_conditions():
    for constraints in (None, {}, {"survey": None}, {"survey": {}}, {"survey": {"priority_details": None}}):
        assert survey.conds_from_survey(constraints) == ()


def test_family_party_does_not_imply_kids():
    got = survey.conds_from_survey({"survey": {"party": "family", "priority_details": {"food": []}}})
    assert "kids_allowed" not in got
