import json
from pathlib import Path
from eval.stats.bootstrap import paired_bootstrap_delta
from eval.stats.mcnemar import exact_two_sided, mcnemar_result

ROOT = Path(__file__).resolve().parents[2]

def test_bootstrap_known_input_fixed_seed():
    mean, ci = paired_bootstrap_delta([1.0, 2.0, 3.0], n=1000, seed=7)
    assert mean == 2.0
    assert ci == (1.0, 3.0)

def test_mcnemar_exact_branch_for_small_discordance():
    assert exact_two_sided(3, 1) == 0.625

def test_mcnemar_chi_square_reports_both_statistic_and_bounded_p_value():
    statistic, p_value, method = mcnemar_result(0, 40)
    assert statistic == 38.025
    assert p_value < 1e-8
    assert 0 <= p_value <= 1
    assert method == "chi-square continuity-corrected"

def test_mcnemar_uses_exact_for_small_discordance():
    statistic, p_value, method = mcnemar_result(3, 5)
    assert statistic == 2.0
    assert 0 <= p_value <= 1
    assert method == "exact binomial"

def test_bootstrap_zero_difference_ci_is_not_significant():
    from eval.stats.bootstrap import format_result, paired_bootstrap_delta
    mean, ci = paired_bootstrap_delta([0.0] * 20, n=1000, seed=7)
    assert mean == 0.0 and ci == (0.0, 0.0)
    assert "유의하지 않다" in format_result(mean, ci, "X", "Y", 20)

def test_bootstrap_all_positive_difference_excludes_zero():
    from eval.stats.bootstrap import paired_bootstrap_delta
    mean, ci = paired_bootstrap_delta([1.0] * 20, n=1000, seed=7)
    assert mean == 1.0 and ci == (1.0, 1.0)

def test_dataset_counts_and_allocation_and_disjointness():
    def rows(name): return [json.loads(x) for x in (ROOT / "eval/datasets" / name).read_text(encoding="utf-8").splitlines() if x]
    golden, holdout = rows("golden.jsonl"), rows("holdout.jsonl")
    assert len(golden) == 72 and len(holdout) == 24
    assert {x["case_id"] for x in golden}.isdisjoint({x["case_id"] for x in holdout})
    assert {k: sum(1 for x in golden if x["case_id"].startswith(k)) for k in ("g-order", "g-shipping", "g-return", "g-exchange", "g-response-review")} == {"g-order":15,"g-shipping":15,"g-return":15,"g-exchange":15,"g-response-review":12}
    assert {k: sum(1 for x in holdout if x["case_id"].startswith(k)) for k in ("h-order", "h-shipping", "h-return", "h-exchange", "h-response-review")} == {"h-order":5,"h-shipping":5,"h-return":5,"h-exchange":5,"h-response-review":4}
