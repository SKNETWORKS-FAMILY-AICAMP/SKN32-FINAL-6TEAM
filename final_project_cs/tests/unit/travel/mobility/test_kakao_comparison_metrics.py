from scripts.mobility.compare_kakao_golden import summarise
from scripts.mobility.merge_web_readings import merge
import pytest


def test_wait_before_after_and_percent_have_same_reference():
    row = {"bucket": "short", "ours_transit": {"eta": 30, "eta_without_wait": 24, "wait_min": 6, "min_option_eta": 28},
           "kakao": {"transit": {"best": {"min": 20}, "rec": {"min": 25}}}}
    result = summarise([row])
    assert result["transit_eta_vs_best"]["minutes"]["median"] == 10
    assert result["transit_eta_vs_best"]["percent"]["median"] == 50
    assert result["transit_eta_without_wait_vs_best"]["minutes"]["median"] == 4
    assert result["transit_eta_without_wait_vs_best"]["percent"]["median"] == 20
    assert result["transit_eta_without_wait_vs_rec"]["percent"]["median"] == -4


def test_unknown_wait_and_legacy_api_are_not_treated_as_zero_or_web():
    row = {"bucket": "short", "ours_transit": {"eta": 30, "min_option_eta": 30},
           "ours_taxi": {"eta": 10}, "kakao": {"car": {"duration_s": 600},
           "transit": {"best": {"min": 20}, "rec": {"min": 20}}}}
    result = summarise([row])
    assert result["transit_eta_without_wait_vs_best"]["minutes"]["n"] == 0
    assert result["coverage"]["car_excluded_legacy_api"] == 1
    assert result["taxi_minutes_vs_kakao_car"]["n"] == 0


def test_web_merge_rejects_duplicates_and_bad_lines():
    base = {"_meta": {}, "routes": {}}
    line = "G41 car 24/9.5/12000 rec=43/16/1 best=40/15/2"
    result = merge(base, line)
    assert result["routes"]["G41"]["car"]["source"] == "kakao_map_web"
    assert result["routes"]["G41"]["transit"]["best"]["min"] == 40
    assert base["routes"] == {}
    with pytest.raises(ValueError):
        merge(base, line + "\n" + line)
    with pytest.raises(ValueError):
        merge(base, "G41 car invalid")
