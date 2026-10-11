"""시험 단축 입력의 경계·서울 일정 원문을 검증한다."""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake import test_plans as plans
from app.domains.travel_ops.components.intake.rules import read_plan


@pytest.mark.parametrize("number,count", enumerate((6, 3, 2, 2, 3, 3, 3, 3, 3, 3, 7, 4), start=1))
def test_every_prepared_code_has_dated_readable_stops(monkeypatch, number, count):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: True)
    text, meta = plans.expand(f"  TeSt{number} \n", tenant_id="unit", has_files=False, today=date(2026, 10, 11))
    read = read_plan(text)
    assert len(read.items) == count
    assert read.party_size == 4
    assert all(item.date and item.date >= "2026-10-18" for item in read.items)
    assert meta["code"] == f"test{number}"
    assert meta["mode"] == "prepared_text"
    assert "text" not in meta
    if number == 4:
        assert date.fromisoformat(read.items[0].date).weekday() == 1


@pytest.mark.parametrize("text", ("", "서울 test1 방문", "test1 메모", "test01", "test0", "test 1", "test１"))
def test_ordinary_text_is_not_replaced_or_reads_settings(monkeypatch, text):
    def forbidden(*_):
        raise AssertionError("ordinary text should not read a test setting")
    monkeypatch.setattr(plans, "operator_setting", forbidden)
    assert plans.expand(text, tenant_id="unit", has_files=False) == (text, None)


@pytest.mark.parametrize("text,files,enabled,code", (
    ("test13", False, True, "unknown_test_scenario"),
    ("test1", True, True, "test_scenario_with_files"),
    ("test1", False, False, "test_scenarios_disabled"),
    ("test1rt", False, True, "live_test_not_ready"),
))
def test_reserved_inputs_fail_explicitly(monkeypatch, text, files, enabled, code):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: enabled)
    with pytest.raises(plans.TestPlanRejected) as error:
        plans.expand(text, tenant_id="unit", has_files=files)
    assert error.value.code == code


def test_disabled_catalog_is_empty_and_operator_override_wins(monkeypatch):
    monkeypatch.setattr(plans, "operator_setting", lambda *_: False)
    assert plans.catalog("unit")["scenarios"] == []
    assert plans.catalog("unit")["enabled"] is False
    monkeypatch.setattr(plans, "operator_setting", lambda *_: None)
    assert len(plans.catalog("unit")["scenarios"]) == 12
