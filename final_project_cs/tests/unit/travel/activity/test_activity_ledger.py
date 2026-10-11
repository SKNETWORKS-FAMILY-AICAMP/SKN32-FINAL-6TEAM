"""활동 원장 판정(`instances/activity/ledger.state`) — 원장 원문 + 방문 시각 → 휴무 · 운영시간. DB 없이(가짜 연결)."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domains.travel_ops.instances.activity import ledger

KST = ZoneInfo("Asia/Seoul")


class _Cursor:
    def __init__(self, row):
        self.row, self.calls = row, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.calls.append(params)

    def fetchone(self):
        return self.row


class _Conn:
    def __init__(self, row):
        self.cur = _Cursor(row)

    def cursor(self):
        return self.cur


def _row(usetime, restdate):
    return ("126508", "경복궁", usetime, restdate)


def test_weekly_closure_day_is_closed():
    # 2026-10-13 은 화요일
    out = ledger.state(_Conn(_row("09:00~18:00", "매주 화요일")), "demo", "p1", datetime(2026, 10, 13, 10, tzinfo=KST))
    assert out["closed"] is True and out["content_id"] == "126508" and out["name"] == "경복궁"
    assert out["source"] == ledger.SOURCE


def test_open_day_within_and_outside_hours():
    conn = _Conn(_row("09:00~18:00", "매주 화요일"))
    inside = ledger.state(conn, "demo", "p1", datetime(2026, 10, 14, 10, tzinfo=KST))
    outside = ledger.state(conn, "demo", "p1", datetime(2026, 10, 14, 20, tzinfo=KST))
    assert (inside["closed"], inside["within_hours"]) == (False, True)
    assert (outside["closed"], outside["within_hours"]) == (False, False)


def test_nth_week_closure_depends_on_the_date():
    conn = _Conn(_row("10:00~17:00", "매월 둘째 주 월요일"))
    second_monday = ledger.state(conn, "demo", "p1", datetime(2026, 10, 12, 11, tzinfo=KST))
    third_monday = ledger.state(conn, "demo", "p1", datetime(2026, 10, 19, 11, tzinfo=KST))
    assert second_monday["closed"] is True and third_monday["closed"] is False


def test_holiday_fact_is_asked_only_for_needed_dates():
    asked: list[date] = []

    def holiday(day):
        asked.append(day)
        return {"is_holiday": True, "holiday_name": "한글날"}

    conn = _Conn(_row("09:00~18:00", "매주 월요일 (단, 월요일이 공휴일인 경우 정상 운영)"))
    out = ledger.state(conn, "demo", "p1", datetime(2026, 10, 12, 10, tzinfo=KST), holiday=holiday)
    assert asked and all(isinstance(d, date) for d in asked)
    assert out["closed"] is False


def test_unparsable_hours_text_is_unknown_not_open():
    out = ledger.state(_Conn(_row("하절기 09:00~19:00, 동절기 09:00~18:00", None)), "demo", "p1",
                       datetime(2026, 10, 14, 10, tzinfo=KST))
    assert out["known"] is False and out["within_hours"] is None and out["closed"] is None


def test_empty_hours_is_marked_empty():
    out = ledger.state(_Conn(_row(None, None)), "demo", "p1", datetime(2026, 10, 14, 10, tzinfo=KST))
    assert out["empty"] is True and out["closed"] is None


def test_not_in_ledger_or_no_time_or_no_place_is_none():
    at = datetime(2026, 10, 14, 10, tzinfo=KST)
    assert ledger.state(_Conn(None), "demo", "p1", at) is None
    assert ledger.state(_Conn(_row("09:00~18:00", None)), "demo", "p1", None) is None
    conn = _Conn(_row("09:00~18:00", None))
    assert ledger.state(conn, "demo", None, at) is None and conn.cur.calls == []
