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


def _row(usetime, restdate, week=None, read=None):
    return ("126508", "경복궁", usetime, restdate, week, read)


def test_stored_week_is_used_for_text_rules_cannot_read():
    # 규칙 밖 원문을 모델이 미리 펴 둔 경우 — 요청 때는 저장된 표만 본다
    week = {d: {"open": "10:00", "close": "17:00", "last_entry": None} for d in ("mon", "tue", "wed", "thu", "fri")}
    week |= {"sat": "closed", "sun": "closed"}
    conn = _Conn(_row("하절기 09:00~19:00, 동절기 10:00~17:00", None, week, {"method": "llm"}))
    wednesday = ledger.state(conn, "demo", "p1", datetime(2026, 10, 14, 11, tzinfo=KST))
    saturday = ledger.state(conn, "demo", "p1", datetime(2026, 10, 17, 11, tzinfo=KST))
    assert (wednesday["known"], wednesday["within_hours"]) == (True, True)
    assert saturday["closed"] is True


def test_read_but_unparsed_stays_unknown_without_rereading():
    out = ledger.state(_Conn(_row("09:00~18:00", None, None, {"method": "none"})), "demo", "p1",
                       datetime(2026, 10, 14, 10, tzinfo=KST))
    assert out["known"] is False and out["within_hours"] is None


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


def test_until_must_also_be_within_hours():
    # 18시에 닫는 곳 — 17:00 도착이라도 19:00 까지 있는 일정은 밖, 17:50 까지면 안
    conn = _Conn(_row("09:00~18:00", None))
    at = datetime(2026, 10, 14, 17, tzinfo=KST)
    assert ledger.state(conn, "demo", "p1", at)["within_hours"] is True
    assert ledger.state(conn, "demo", "p1", at, datetime(2026, 10, 14, 19, tzinfo=KST))["within_hours"] is False
    assert ledger.state(conn, "demo", "p1", at, datetime(2026, 10, 14, 17, 50, tzinfo=KST))["within_hours"] is True


def test_closing_midway_is_told_apart_from_closed_on_arrival():
    # 19시에 닫는 곳 — 18~20시는 「중간에 닫힘(60분)」, 19~20시는 「도착 때 이미 닫힘」, 18~19시는 문제없음
    conn = _Conn(_row("10:00~19:00", None))
    day = lambda h: datetime(2026, 10, 14, h, tzinfo=KST)  # noqa: E731
    midway = ledger.state(conn, "demo", "p1", day(18), day(20))
    already = ledger.state(conn, "demo", "p1", day(19), day(20))
    fine = ledger.state(conn, "demo", "p1", day(18), day(19))
    assert (midway["within_hours"], midway["cut_short"], midway["closes_at"], midway["usable_minutes"]) == \
        (False, True, "19:00", 60)
    assert (already["within_hours"], already["cut_short"], already["closes_at"]) == (False, False, None)
    assert (fine["within_hours"], fine["cut_short"]) == (True, False)


def test_cut_short_unknown_without_until_or_hours():
    at = datetime(2026, 10, 14, 18, tzinfo=KST)
    assert ledger.state(_Conn(_row("10:00~19:00", None)), "demo", "p1", at)["cut_short"] is None
    unknown = ledger.state(_Conn(_row("하절기 09:00~19:00, 동절기 10:00~17:00", None)), "demo", "p1", at,
                           datetime(2026, 10, 14, 20, tzinfo=KST))
    assert unknown["cut_short"] is None


def test_until_past_midnight_is_outside_and_bad_until_is_ignored():
    conn = _Conn(_row("10:00~22:00", None))
    at = datetime(2026, 10, 14, 21, tzinfo=KST)
    assert ledger.state(conn, "demo", "p1", at, datetime(2026, 10, 15, 0, 30, tzinfo=KST))["within_hours"] is False
    # 끝이 시작보다 앞이거나 같으면 도착 순간만 본다
    assert ledger.state(conn, "demo", "p1", at, datetime(2026, 10, 14, 20, tzinfo=KST))["within_hours"] is True


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
