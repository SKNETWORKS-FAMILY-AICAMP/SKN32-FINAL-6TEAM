"""공식 권종별 대여시간과 총요금 경계. 현장 결제 정확도 시험이 아닙니다."""
import json
from pathlib import Path

import pytest

from app.domains.travel_ops.instances.mobility.engine import bike


RULES = Path(bike.__file__).parent / "rules/rules_v0.3.json"


@pytest.mark.parametrize("minutes,won,base", [
    (0, 1000, 60), (60, 1000, 60), (60.01, 1200, 60),
    (80, 1800, 60), (85, 2000, 120), (100, 2000, 120),
    (120, 2000, 120), (120.01, 2200, 120),
    (145, 3000, 180), (180, 3000, 180),
])
def test_official_per_pass_rental_time_and_least_total(minutes, won, base):
    rules = json.loads(RULES.read_text(encoding="utf8"))["bike"]["ddareungi"]["fare"]
    rules["purchase_channel"] = {"value": "standard"}
    # 종일 외국인권의 현 판매·초과조건과 분리해 1/2/3시간 공식 일일권을 검증합니다.
    rules["passes"]["value"] = [p for p in rules["passes"]["value"] if p["minutes"] <= 180]
    result = bike.fare(rules, minutes)
    assert result["total_won"] == won
    assert result["base_ride_min"] == base
    assert result["total_won"] == result["pass_won"] + result["overtime_won"]


def test_explicit_per_rental_limit_takes_precedence_over_validity_minutes():
    rules = {"passes": {"value": [{"name": "day", "minutes": 1440,
             "ride_limit_min": 60, "won": 1000}]},
             "base_ride_min": {"value": 60},
             "overtime": {"value": {"per_min": 5, "won": 200}}}
    assert bike.fare(rules, 100)["total_won"] == 2600


def test_legacy_pass_without_minutes_uses_explicit_common_base():
    rules = {"passes": {"value": [{"name": "legacy", "won": 1000}]},
             "base_ride_min": {"value": 60},
             "overtime": {"value": {"per_min": 5, "won": 200}}}
    assert bike.fare(rules, 61)["total_won"] == 1200


def test_foreigner_menu_does_not_assume_three_hour_purchase_or_day_rental_limit():
    rules = json.loads(RULES.read_text(encoding="utf8"))["bike"]["ddareungi"]["fare"]
    assert rules["purchase_channel"]["value"] == "foreigner"
    assert bike.fare(rules, 180)["pass"] == "2h"
    assert bike.fare(rules, 180)["total_won"] == 4400
    assert bike.fare(rules, 300)["pass"] == "2h"
    assert next(p for p in rules["passes"]["value"] if p["name"] == "24h")["ride_limit_min"] is None


def test_unknown_rental_condition_is_not_silently_turned_into_free_ride():
    rules = {"passes": {"value": [{"name": "unknown", "minutes": 1440,
             "ride_limit_min": None, "won": 1000}]},
             "base_ride_min": {"value": 60},
             "overtime": {"value": {"per_min": 5, "won": 200}}}
    with pytest.raises(ValueError, match="대여조건"):
        bike.fare(rules, 100)
