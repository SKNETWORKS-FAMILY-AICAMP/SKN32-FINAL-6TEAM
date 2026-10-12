from datetime import date, datetime, timezone
from types import SimpleNamespace
import pytest
from app.domains.travel_ops.components.conversation.summary_request import decide_summary
from app.domains.travel_ops.components.conversation import read_requests

ITEMS = [SimpleNamespace(kind="activity", starts_at=datetime(2031,3,10,15,30,tzinfo=timezone.utc))]

@pytest.mark.parametrize("message",["2031-03-11 하루 일정을 요약해 주세요.","Summarize the itinerary for 2031-03-11."])
def test_explicit_button_date_uses_seoul_calendar(message):
    decision=decide_summary(date(2031,3,11),message=message,items=ITEMS)
    assert decision.action=="answer_fact" and decision.fact=="schedule"
    assert decision.query["day"]=="d1" and decision.raw["model_called"] is False

@pytest.mark.parametrize("day,message",[(date(2031,3,12),"2031-03-12 하루 일정을 요약해 주세요."),
    (date(2031,3,11),"2031-03-12 하루 일정을 요약해 주세요."),
    (date(2031,3,11),"2031-03-11 하루 일정을 요약해 주세요. 그리고 식당 바꿔"),
    ("2031-03-11","2031-03-11 하루 일정을 요약해 주세요.")])
def test_invalid_or_conflicting_summary_is_rejected(day,message):
    with pytest.raises(ValueError):decide_summary(day,message=message,items=ITEMS)

def test_gapped_trip_days_preserve_calendar_offset():
    items=ITEMS+[SimpleNamespace(kind="activity", starts_at=datetime(2031,3,13,tzinfo=timezone.utc))]
    d=decide_summary(date(2031,3,13),message="2031-03-13 하루 일정을 요약해 주세요.",items=items)
    assert d.query["day"]=="d3"
