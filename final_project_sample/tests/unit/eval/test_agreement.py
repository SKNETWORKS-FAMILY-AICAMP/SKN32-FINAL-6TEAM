import pytest

from eval.stats.agreement import agreement, cohen_kappa


def rows(values, prefix):
    return [{"case_id": f"{prefix}{i}", "human_intent": v[0], "human_issue_code": v[1], "human_sentiment": v[2], "human_pass": v[3], "human_notes": ""} for i, v in enumerate(values)]


def predictions(values):
    return [{"case_id": f"p{i}", "intent": v[0], "issue_code": v[1], "sentiment": v[2], "judge": {"pass": v[3]}} for i, v in enumerate(values)]


def test_perfect_agreement_has_kappa_one():
    values = [("a", "x", "positive", True), ("b", "y", "negative", False)]
    result = agreement(rows(values, "p"), predictions(values))
    assert all(result[field]["kappa"] == pytest.approx(1.0) for field in ("intent", "issue_code", "sentiment", "pass"))


def test_complete_disagreement():
    human = [("a", "x", "positive", True), ("b", "y", "negative", False)]
    system = [("b", "y", "negative", False), ("a", "x", "positive", True)]
    result = agreement(rows(human, "p"), predictions(system))
    assert result["intent"]["agreement"] == 0.0
    assert result["intent"]["kappa"] == pytest.approx(-1.0)


def test_kappa_can_be_lower_than_exact_match_due_to_chance_agreement():
    left = ["a", "a", "a", "b"]
    right = ["a", "a", "b", "a"]
    assert sum(a == b for a, b in zip(left, right)) / len(left) == pytest.approx(0.5)
    assert cohen_kappa(left, right) < 0.5


def test_case_id_mismatch_is_explicit_error():
    values = [("a", "x", "positive", True)]
    with pytest.raises(ValueError, match="case_id mismatch"):
        agreement(rows(values, "h"), predictions(values))
