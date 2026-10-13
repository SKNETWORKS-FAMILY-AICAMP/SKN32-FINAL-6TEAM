"""도보 원시 진단은 공개 옵션 제공률이나 제품 시간 오차가 아니다."""
from scripts.mobility import compare_kakao_golden as comparison


def reference():
    return {"walk": {"shortest": {"km": .3, "min": 5}}}


def test_policy_rejected_legacy_diagnostic_is_not_a_product_comparison():
    row = {"bucket": "short", "ours_walk": {"m": 300, "min": 5}, "kakao": reference()}
    got = comparison.summarise([row])
    assert got["walk_minutes_vs_kakao_shortest"]["n"] == 0
    assert got["walk_raw_diagnostic_minutes_vs_kakao_shortest"]["n"] == 1
    assert got["coverage"]["walk_product_missing"] == 0
    assert got["coverage"]["walk_product_unobserved"] == 1


def test_product_duration_is_not_reconstructed_from_distance():
    row = {"bucket": "short", "ours_walk": {"m": 300, "min": 5},
           "ours_walk_product": {"m": 300, "min": 9}, "kakao": reference()}
    got = comparison.summarise([row])
    assert got["walk_minutes_vs_kakao_shortest"]["median"] == 4
    assert got["walk_raw_diagnostic_minutes_vs_kakao_shortest"]["median"] == 0


def test_unselected_public_walk_option_is_preserved():
    result = {"route": {"planned": "rail", "options": [
        {"id": "rail", "eta_min": 3}, {"id": "walk", "eta_min": 9, "walk_m": 300}]}}
    assert comparison._product_walk(result, None) == {"status": "available", "m": 300, "min": 9}
    assert comparison._product_walk(None, {"code": "policy"}) == {"status": "unavailable", "reason": "policy"}
    assert comparison._product_walk(result={"route": {"options": []}}, why=None)["reason"] == "walk_option_not_offered"


def test_diagnostic_uses_internal_duration_and_preserves_reason():
    from types import SimpleNamespace

    def path(*args, evidence):
        evidence.update(source="walking_network", degraded=True)
        return 300, 9, False

    got = comparison._walk_diagnostic(SimpleNamespace(_walk_path=path), {}, {}, 280)
    assert got["min"] == 9
    assert got["evidence"] == {"source": "walking_network", "degraded": True}


def test_diagnostic_failure_is_counted_instead_of_disappearing():
    from types import SimpleNamespace

    def fail(*args, **kwargs):
        raise ValueError("do not expose arbitrary exception content")

    got = comparison._walk_diagnostic(SimpleNamespace(_walk_path=fail), {}, {}, 280)
    assert got == {"status": "error", "error_type": "ValueError"}
    summary = comparison.summarise([{"bucket": "short", "ours_walk_diagnostic": got,
                                    "ours_walk_product": {"status": "unavailable"}, "kakao": reference()}])
    assert summary["coverage"]["pairs"] == 1
    assert summary["coverage"]["walk_diagnostic_errors"] == 1
    assert summary["coverage"]["walk_product_missing"] == 1


def test_zero_reference_distance_is_excluded_without_division_by_zero():
    row = {"bucket": "short", "ours_walk_product": {"m": 300, "min": 9},
           "kakao": {"walk": {"shortest": {"km": 0, "min": 0}}}}
    summary = comparison.summarise([row])
    assert summary["coverage"]["walk_product_offered"] == 1
    assert summary["coverage"]["walk_product_comparisons"] == 0
