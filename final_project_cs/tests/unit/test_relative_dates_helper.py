"""`tests/helpers/relative_dates.py` — 시험 자료 날짜를 실행 날 기준으로 옮기는 helper 의 계약."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from tests.helpers import relative_dates as rd


def _clock(monkeypatch, moment: datetime) -> None:
    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)

    monkeypatch.setattr(rd, "datetime", Fixed)


@pytest.mark.parametrize("now", [
    datetime(2026, 10, 28, 3, 40, tzinfo=rd.KST),     # 평일 새벽
    datetime(2026, 12, 31, 23, 59, tzinfo=rd.KST),    # 연말 자정 직전
    datetime(2027, 2, 28, 23, 59, tzinfo=rd.KST),     # 월말
    datetime(2028, 2, 29, 0, 0, tzinfo=rd.KST),       # 윤일 자정
])
@pytest.mark.parametrize("anchor", ["2026-08-17", "2026-09-23", "2026-10-15", "2030-11-08"])
def test_weeks_ahead_keeps_the_weekday_and_lands_after_the_margin(monkeypatch, now, anchor):
    _clock(monkeypatch, now)
    days = rd.weeks_ahead(anchor)
    moved = date.fromisoformat(anchor).toordinal() + days
    moved = date.fromordinal(moved)
    assert days % 7 == 0
    assert moved.weekday() == date.fromisoformat(anchor).weekday()
    floor = now.date().toordinal() + 7
    assert floor <= moved.toordinal() < floor + 7       # 여유 뒤 첫 같은 요일 — 너무 멀리 보내지 않는다


def test_today_is_seoul_not_utc(monkeypatch):
    _clock(monkeypatch, datetime(2026, 10, 27, 15, 30, tzinfo=rd.ZoneInfo("UTC")))   # 서울은 10-28 00:30
    assert rd.today() == date(2026, 10, 28)
    assert rd.relative_day(3) == date(2026, 10, 31)


def test_shifted_moves_only_whole_iso_values_and_keys():
    data = {"date": "2026-09-23", "from": "2026-09-23T08:50:00+09:00", "matched_hour": "2026-09-23T10:00",
            "dataTime": "2026-09-23 08:00", "version": "2026-09-24.v1", "note": "2026-09-23 에 간다",
            "days": {"2026-09-23": {"at": "2026-09-23T10:00:00+09:00"}}, "n": 2026, "list": ["2026-09-30"]}
    out = rd.shifted(data, 7)
    assert out == {"date": "2026-09-30", "from": "2026-09-30T08:50:00+09:00", "matched_hour": "2026-09-30T10:00",
                   "dataTime": "2026-09-30 08:00", "version": "2026-09-24.v1", "note": "2026-09-23 에 간다",
                   "days": {"2026-09-30": {"at": "2026-09-30T10:00:00+09:00"}}, "n": 2026, "list": ["2026-10-07"]}
    assert data["date"] == "2026-09-23"                    # 원본은 그대로


def test_shift_text_moves_inline_iso_dates_across_month_and_year_ends():
    assert rd.shift_text("1일차 2026-12-31 · 2일차 2027-01-01(판 2026-09-24.v1)", 1) == \
        "1일차 2027-01-01 · 2일차 2027-01-02(판 2026-09-25.v1)"
    assert rd.shift_text("전화 010-2026-1015", 7) == "전화 010-2026-1015"


@pytest.mark.parametrize("now", [datetime(2026, 10, 28, 3, 40, tzinfo=rd.KST), datetime(2027, 1, 31, 23, 59, tzinfo=rd.KST)])
def test_epoch_shift_moves_every_fixture_date_by_one_width_and_keeps_it_for_the_run(monkeypatch, now):
    monkeypatch.setattr(rd, "_SESSION", {})
    _clock(monkeypatch, now)
    width = rd.epoch_shift()
    assert width % 7 == 0 and width == rd.weeks_ahead(rd.FIXTURE_EPOCH)
    for written in ["2026-08-17", "2026-09-23", "2026-10-15", "2026-11-02"]:
        moved = date.fromisoformat(rd.day(written))
        assert moved.weekday() == date.fromisoformat(written).weekday()
        assert moved >= now.date() + timedelta(days=7)
    assert rd.moved(date(2026, 10, 5)) == date.fromisoformat(rd.day("2026-10-05"))
    _clock(monkeypatch, now + timedelta(days=1, minutes=2))   # 자정을 넘겨도 한 실행의 폭은 같다
    assert rd.epoch_shift() == width


def test_clock_class_follows_the_given_clock_and_keeps_isinstance():
    moment = {"now": datetime(2026, 12, 30, 9, 0, tzinfo=rd.KST)}
    clocked = rd.clock_class(lambda: moment["now"])
    assert clocked.now(rd.ZoneInfo("UTC")) == datetime(2026, 12, 30, 0, 0, tzinfo=rd.ZoneInfo("UTC"))
    moment["now"] = datetime(2026, 12, 30, 10, 0, tzinfo=rd.KST)
    assert clocked.now(rd.KST).hour == 10 and clocked.now().tzinfo is None
    assert isinstance(datetime(2020, 1, 1), clocked)          # 바꿔 끼운 모듈의 isinstance(at, datetime) 판정 불변
    assert not isinstance(date(2020, 1, 1), clocked)
    assert clocked.fromisoformat("2026-12-30T09:00:00+09:00") == moment["now"].replace(hour=9)


def test_epoch_shift_has_the_exact_width_for_a_known_day(monkeypatch):
    """폭 계산을 helper 와 독립된 값으로 고정한다 — 2026-10-28(수) 새벽이면 기준일 2026-08-01(토)을 11-04 이후 첫 토요일 11-07 로."""
    monkeypatch.setattr(rd, "_SESSION", {})
    _clock(monkeypatch, datetime(2026, 10, 28, 3, 40, tzinfo=rd.KST))
    assert rd.epoch_shift() == 98
    assert rd.day("2026-09-23") == "2026-12-30" and rd.day("2026-10-15") == "2027-01-21"
