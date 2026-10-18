"""요일표 밖 저장된 휴무 조건이 추천에서 사라지지 않는지 확인한다."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from app.domains.travel_ops.components.intake import hours
from app.domains.travel_ops.components.intake.review import _hours_lines

START = datetime(2026, 10, 26, 14, tzinfo=ZoneInfo("Asia/Seoul"))
END = START.replace(hour=15)
WEEK = {day: {"open": "09:00", "close": "18:00"} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
CONDITION = "쉬는 날: 매주 월요일 (단, 월요일이 공휴일인 경우 정상 개장)"
READ = {"conditions": ["하절기 운영시간", CONDITION]}

@pytest.mark.parametrize("origin", ["candidate", "place", "catalog", "reused"])
def test_conditions_reach_review_from_every_stored_hours_path(monkeypatch, origin):
    attrs = {"hours_week": WEEK, "hours_read": READ}
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql, params): self.sql = sql
        def fetchone(self):
            if "FROM catalog_hours" in self.sql: return (WEEK, READ) if origin == "catalog" else None
            return (WEEK, READ)
    class Conn:
        def cursor(self): return Cursor()
    monkeypatch.setattr(hours, "_place_row", lambda *args: (attrs, None))
    monkeypatch.setattr(hours, "_tenants", lambda *args: ["qa"])
    place = {"name": "시험 궁궐"}
    if origin == "candidate": place["_hours"] = attrs
    elif origin == "place": place["place_id"] = "place"
    else: place["content_id"] = "content"
    facts = hours.facts_for(Conn(), "qa", place, "activity", START, END, activity_verdict=False)
    assert facts.conditions == READ["conditions"]
    row = {"date": "2026-10-26", "start": "14:00", "end": "15:00", "place": place}
    _open, closed = _hours_lines(row, facts, [])
    assert closed["result"] == "warn"
    assert CONDITION in closed["text"]
    assert "쉬는 요일이 없어요" not in closed["text"]

def test_conditions_do_not_override_a_confirmed_closed_day():
    facts = hours.HoursFacts(True, {"hours_week": {"mon": "closed"}}, conditions=[CONDITION])
    closed = _hours_lines({"date": "2026-10-26", "start": "14:00", "end": "15:00", "place": {"name": "시험 궁궐"}}, facts, [])[1]
    assert closed["result"] == "bad"

def test_week_without_conditions_keeps_the_known_result():
    facts = hours.HoursFacts(True, {"hours_week": WEEK})
    closed = _hours_lines({"date": "2026-10-26", "start": "14:00", "end": "15:00", "place": {"name": "시험 궁궐"}}, facts, [])[1]
    assert closed["result"] == "ok"
