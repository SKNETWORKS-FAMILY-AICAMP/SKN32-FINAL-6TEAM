# -*- coding: utf-8 -*-
"""일정 판정기는 시각을 **서울 시각**으로 읽는다 — 체크리스트 H3. `[2026-10-03]`

☆결함: `check_itinerary` 가 `.date()` · `.time()` 을 받은 그대로 읽었다. 같은 순간을 세계 표준시(UTC)로 보내면(서울 10:00 = UTC 01:00) 「아직 열기 전」 · 「쉬는 날이 어긋남」으로 거절했고,
DB 세션이 UTC 면 DB 에서 다시 읽은 일정(자동 변경 전 일정 전체 재판정이 이 길이다)도 9시간 어긋났다. 장소 영업 판정(`place_hours.fits`)은 2026-09-29 에 고쳤는데 이 판정기는 못 받았다.

★지키려는 것: ①같은 순간이면 어느 시간대로 적어 보내도 판정이 같다(영업 전 · 마감 뒤 · 쉬는 날 · 브레이크 · 입장 마감) ②안내 문장의 시각도 서울 시계다 ③시간대 없는 시각은 서울로 본다(등록 입구가 그렇게 붙인다) — 이 PC 의 시간대로 읽지 않는다
④겹침 · 간격 계산은 시간대가 섞여도 깨지지 않는다.

재현:

    python -m pytest tests/unit/travel/test_itinerary_checks_seoul_time.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary_checks import Part, check_itinerary

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc
TUESDAY = (2026, 10, 6)                    # 화요일


def _seoul(hhmm: str, day=TUESDAY) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    return datetime(*day, hour, minute, tzinfo=KST)


def _as_utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC)


def _part(start: datetime, end: datetime | None = None, *, attributes: dict, seq: int = 1, title: str = "경복궁") -> Part:
    return Part(seq=seq, kind="activity", title=title, starts_at=start, ends_at=end, place={"name": title, "attributes": attributes})


def _codes(parts):
    return sorted(v.code for v in check_itinerary(parts))


HOURS = {"hours": ["09:00", "18:00"]}


def test_the_same_moment_is_judged_the_same_in_utc_and_in_seoul():
    """서울 10:00~11:00 방문(09:00 에 여는 곳). UTC 로는 01:00~02:00 — 전에는 「아직 열기 전」으로 거절했다."""
    seoul = [_part(_seoul("10:00"), _seoul("11:00"), attributes=HOURS)]
    utc = [_part(_as_utc(_seoul("10:00")), _as_utc(_seoul("11:00")), attributes=HOURS)]
    assert _codes(seoul) == _codes(utc) == []


def test_real_violations_are_still_caught_whatever_the_zone_of_the_input():
    early_seoul = _part(_seoul("08:30"), _seoul("09:30"), attributes=HOURS)
    late_seoul = _part(_seoul("17:30"), _seoul("18:30"), attributes=HOURS)
    for zone in (lambda m: m, _as_utc):
        assert _codes([_part(zone(early_seoul.starts_at), zone(early_seoul.ends_at), attributes=HOURS)]) == ["before_opening"]
        assert _codes([_part(zone(late_seoul.starts_at), zone(late_seoul.ends_at), attributes=HOURS)]) == ["after_closing"]


def test_the_closed_day_is_the_day_in_seoul_not_the_day_in_utc():
    """화요일 휴무인 곳에 서울 화요일 08:00(= UTC **월요일** 23:00)을 보냈다 — 날짜가 UTC 로 읽히면 월요일로 보여 휴무를 놓친다."""
    attributes = {"hours_week": {"tue": "closed"}}
    start = _seoul("08:00")
    assert _as_utc(start).date() != start.date()                       # 이 시각은 UTC 로 날짜가 다르다
    assert _codes([_part(start, _seoul("09:00"), attributes=attributes)]) == ["closed_day"]
    assert _codes([_part(_as_utc(start), _as_utc(_seoul("09:00")), attributes=attributes)]) == ["closed_day"]


def test_break_time_and_last_entry_use_seoul_clock_digits():
    lunch = {"hours": ["11:00", "22:00", ], "break": ["15:00", "17:00"]}
    inside = _part(_seoul("15:30"), _seoul("16:30"), attributes=lunch, title="브레이크 식당")
    assert _codes([inside]) == ["break_time"]
    assert _codes([_part(_as_utc(inside.starts_at), _as_utc(inside.ends_at), attributes=lunch, title="브레이크 식당")]) == ["break_time"]


def test_the_message_shows_seoul_times_not_the_zone_it_came_in():
    [violation] = check_itinerary([_part(_as_utc(_seoul("08:30")), _as_utc(_seoul("09:30")), attributes=HOURS)])
    assert "08:30" in violation.reason and "00:30" not in violation.reason            # UTC 시계(23:30 · 00:30)가 안내에 나가지 않는다


def test_a_time_without_a_zone_is_read_as_seoul_not_as_this_pcs_zone():
    naive = [_part(datetime(*TUESDAY, 10, 0), datetime(*TUESDAY, 11, 0), attributes=HOURS)]
    assert _codes(naive) == []
    naive_early = [_part(datetime(*TUESDAY, 8, 30), datetime(*TUESDAY, 9, 30), attributes=HOURS)]
    assert _codes(naive_early) == ["before_opening"]


def test_overlap_and_gap_still_work_when_the_zones_are_mixed():
    first = _part(_seoul("10:00"), _seoul("11:00"), attributes={}, seq=1, title="앞")
    second = _part(_as_utc(_seoul("10:30")), _as_utc(_seoul("11:30")), attributes={}, seq=2, title="뒤")      # 앞 항목은 서울, 뒤 항목은 UTC
    assert _codes([first, second]) == ["overlap"]
    assert _codes([first, _part(_as_utc(_seoul("11:30")), _as_utc(_seoul("12:30")), attributes={}, seq=2, title="뒤")]) == []
