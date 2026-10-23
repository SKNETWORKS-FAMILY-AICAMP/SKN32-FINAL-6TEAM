import pytest

from app.domains.travel_ops.components.intake.hours import HoursFacts
from app.domains.travel_ops.components.intake.review import _hours_lines


@pytest.mark.parametrize("order_ok,end,expected", [(None,"21:30",True),(False,"21:30",False),(None,"22:30",False)])
def test_only_uncertain_last_order_can_be_acknowledged(order_ok, end, expected):
    facts = HoursFacts(True, {"hours": ["11:00", "22:00"]}, "dining_ledger",
                       open_at_slot=True, order_ok=order_ok, needs_check=True)
    row = {"date":"2026-10-28", "start":"21:00", "end":end, "place":{"name":"라멘집"}}
    from app.domains.travel_ops.components.itinerary.itinerary_checks import Violation
    violations = [] if end == "21:30" else [Violation("after_closing", (0,), "late", "move")]
    line, _ = _hours_lines(row, facts, violations)
    assert bool(line.get("can_acknowledge")) is expected
    assert line["result"] == "warn"
