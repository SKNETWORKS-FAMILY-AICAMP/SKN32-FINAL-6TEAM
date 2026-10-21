"""자유문 이해 평가가 조건을 놓친 결과를 성공으로 세지 않는지 확인한다."""
from copy import deepcopy

from app.domains.travel_ops.instances.dining.agent import AgentResult
from eval.runners.dining_freeform import assess, cases, summarize


def answer():
    req = {"request_id": "r1", "attribute": "halal", "required": True, "state": "active", "item_ids": ["lunch", "dinner"]}
    return AgentResult(items=[{"item_id": item, "checks": [
        {"check": "found", "verdict": "ok"}, {"check": "open_at", "verdict": "ok"},
        {"check": "dietary", "required": True, "verdict": verdict, "customer_request": req}]}
        for item, verdict in [("lunch", "bad"), ("dinner", "ok")]], skipped=[], stats={}, requests=[req])


def test_expected_conditions_and_their_verdicts_are_both_required_for_a_pass():
    case, result = cases()[0], answer()
    assert assess(case, result)["pass"] is True
    wrong = deepcopy(result)
    wrong.items[0]["checks"][-1]["verdict"] = "ok"
    scored = assess(case, wrong)
    assert scored["pass"] is False and scored["checks_correct"] == 1


def test_a_manifest_that_skips_one_meal_cannot_pass_on_a_correct_remaining_check():
    case, result = cases()[0], answer()
    result.requests[0]["item_ids"] = ["dinner"]
    scored = assess(case, result)
    assert scored["pass"] is False and scored["request_fn"] == 1


def test_validation_or_missing_inventory_does_not_count_as_a_success():
    case, result = cases()[0], answer()
    result.missing = [{"item_id": "lunch", "check": "_request", "failure": "request_inventory_missing"}]
    assert assess(case, result)["pass"] is False
    result = answer()
    result.items[0]["checks"] = result.items[0]["checks"][2:]
    assert assess(case, result)["availability_ok"] is False


def test_runner_failure_remains_in_the_denominator():
    good = {"case": "one", "slice": "required", "pass": True, "checks_correct": 2, "checks_total": 2,
            "request_tp": 2, "request_fp": 0, "request_fn": 0, "stats": {}}
    bad = {**good, "case": "two", "pass": False, "checks_correct": 0, "request_tp": 0, "request_fn": 2, "failure": "model_error"}
    scored = summarize([good, bad])
    assert scored["cases_passed"] == {"num": 1, "den": 2, "rate": 0.5}
    assert scored["condition_checks"]["num"] == 2 and scored["condition_checks"]["den"] == 4


def test_an_independent_dataset_loads_with_its_own_ids_and_unclear_flags(tmp_path):
    from pathlib import Path
    from eval.runners.dining_freeform import load_rows
    data = load_rows(Path("eval/datasets/dining_freeform_independent_v1.jsonl"))
    assert len(data) == len({c["id"] for c in data}) and all(c["id"].startswith("DI-") for c in data)
    assert len(data) == 96
    assert {c["id"] for c in data if c["expect_unclear"]} == {c["id"] for c in data if c["slice"] == "ambiguous"}
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "X", "slice": "s", "notes": "n", "expected": [["brunch", "halal", true]]}\n', encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        load_rows(bad)
