"""활동 판정 평가(5단계) — 골든셋 형식과 지표 계산. 네트워크 없이."""
from __future__ import annotations

import pytest

from app.domains.travel_ops.instances.activity.judge import VALUES
from eval.activity_judge.build import CASES, dataset_text
from eval.activity_judge.metrics import cluster_bootstrap, outcome, summarize
from eval.activity_judge.run import load_cases, to_request


def test_golden_set_matches_manifest_and_has_valid_labels():
    cases = load_cases()                       # ★해시가 다르면 SystemExit
    assert len(cases) == 60 and dataset_text().count("\n") == 60
    assert len({c["case_id"] for c in cases}) == 60
    for case in cases:
        allowed = VALUES[case["kind"]]
        if case["expected"] is None:
            assert case["kind"] == "live_status" and case["acceptable"] == []
            continue
        assert case["expected"] in case["acceptable"] and set(case["acceptable"]) <= set(allowed)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["case_id"])
def test_every_case_builds_a_request(case):
    assert to_request(case).kind == case["kind"]


def test_outcome_splits_dangerous_from_safe():
    assert outcome("closed", ["closed"]) == "correct"
    assert outcome("not_closed", ["closed"]) == "dangerous"
    assert outcome("unknown", ["closed"]) == "safe_unknown"
    assert outcome("unknown", ["closed", "unknown"]) == "correct"


def test_cluster_bootstrap_averages_cases_not_observations():
    """항목 A 는 3회 모두 맞고 B 는 1회 관측에서 틀렸다 — 평균은 관측(3/4)이 아니라 항목(1/2)이다."""
    mean, lo, hi = cluster_bootstrap({"A": [1.0, 1.0, 1.0], "B": [0.0]}, n=2000)
    assert mean == 0.5 and 0.0 <= lo <= mean <= hi <= 1.0


def _row(case_id, llm, rule, acceptable, kind="closure", repeat=1, **extra):
    return {"case_id": case_id, "kind": kind, "repeat": repeat, "labeled": bool(acceptable),
            "acceptable": acceptable, "llm": llm, "rule": rule, **extra}


def test_summarize_counts_with_denominators():
    rows = [
        _row("c1", "closed", "closed", ["closed"], repeat=1),
        _row("c1", "closed", "closed", ["closed"], repeat=2),
        _row("c2", "unknown", "not_closed", ["closed"], repeat=1, failure_code="llm_uncited"),
        _row("c2", "closed", "not_closed", ["closed"], repeat=2),
        _row("l1", "open", "unknown", [], kind="live_status", search_calls=2, input_tokens=1000, output_tokens=100,
             citations=1),
    ]
    s = summarize(rows, n_boot=500)
    closure = s["kinds"]["closure"]
    assert closure["llm_accuracy"]["num"] == 3 and closure["llm_accuracy"]["den"] == 4
    assert closure["rule_accuracy"]["num"] == 1 and closure["rule_accuracy"]["den"] == 2   # 규칙은 항목당 한 번
    assert closure["rule_dangerous"] == {"num": 1, "den": 2}
    assert closure["llm_safe_unknown"] == {"num": 1, "den": 4}
    assert closure["llm_uncited"] == {"num": 1, "den": 4}
    assert closure["consistent_cases"] == {"num": 1, "den": 2}
    assert "llm_accuracy" not in s["kinds"]["live_status"]                 # 라벨 없음 — 정확도를 내지 않는다
    assert s["kinds"]["_labeled_all"]["observations"] == 4
    assert s["cost_usd_total"] == pytest.approx(2 * 0.01 + 1000 * 0.2e-6 + 100 * 1.25e-6)
