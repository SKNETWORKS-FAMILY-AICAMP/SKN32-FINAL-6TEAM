import copy
import json
from pathlib import Path

import pytest

from scripts.mobility import calibrate_taxi_budget as B


POLICY = {"minimum_reserve_won": {"value": 1000}, "round_unit_won": {"value": 100}}


def examples():
    return [{"id": f"travel-{i}", "bucket": "short", "reference_fare": 9000,
             "time_basis": {"read_completed_at": "2026-10-07T14:00:00+09:00"},
             "estimate": {"fare_kind": "중형", "meter_won": 8000, "toll_won": 0}}
            for i in range(25)]


def test_validation_values_cannot_change_the_fitted_reserve():
    rows = examples()
    original = B.calibrate(rows, POLICY)
    altered = copy.deepcopy(rows)
    for row in altered:
        if row["id"] in original["validation_ids"]:
            row["reference_fare"] = 50000
    result = B.calibrate(altered, POLICY)
    assert result["reserve_rate"] == original["reserve_rate"]
    assert result["training_ids"] == original["training_ids"]
    assert result["validated"] is False


def test_missing_time_and_duplicate_pairs_fail_instead_of_shrinking_the_sample():
    rows = examples()
    with pytest.raises(ValueError, match="중복"):
        B.calibrate(rows + [rows[0]], POLICY)
    rows[0].pop("time_basis")
    with pytest.raises(ValueError, match="시각"):
        B.calibrate(rows, POLICY)
    with pytest.raises(ValueError, match="git 밖"):
        B.raw_path(Path(__file__).with_suffix(".json"))


@pytest.mark.live
def test_current_medium_budget_passes_reserved_paths_and_matches_calibration():
    source = B.RAW / "kakao_golden/taxi_time_aligned_v1.json"
    if not source.exists():
        pytest.skip("로컬 시각 복원 비교 자료를 확보한 기기에서 실행합니다")
    rules = Path(__file__).resolve().parents[4] / "app/domains/travel_ops/instances/mobility/engine/rules/rules_v0.3.json"
    policy = json.loads(rules.read_text(encoding="utf-8"))["taxi"]["planning_budget"]
    result = B.calibrate(json.loads(source.read_text(encoding="utf-8"))["rows"], policy)
    assert policy["reserve_rate_by_kind"]["value"]["중형"] == result["reserve_rate"]
    assert set(result["training_ids"]).isdisjoint(result["validation_ids"])
    assert result["validated"], result["validation"]
    assert len(result["excluded"]) + result["training"]["n"] + result["validation"]["n"] == 200
