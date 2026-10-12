"""D-023: old assets must not return to active execution or fixtures."""
from pathlib import Path
from scripts.check_retired_domain_assets import check_tree

def test_current_runtime_and_business_fixtures_do_not_use_retired_assets():
    assert check_tree(Path(__file__).resolve().parents[2]) == []

def test_guard_detects_a_retired_fixture_but_allows_travel_shopping(tmp_path):
    active = tmp_path / "tests"
    active.mkdir()
    # Negative controls are scanner input, never customer-operation fixtures.
    (active / "test_negative.py").write_text('label = "billing"', encoding="utf-8")
    assert len(check_tree(tmp_path)) == 1
    (active / "test_negative.py").write_text('place = "서울 백화점 쇼핑 활동"; booking_refund = 1000', encoding="utf-8")
    assert check_tree(tmp_path) == []
