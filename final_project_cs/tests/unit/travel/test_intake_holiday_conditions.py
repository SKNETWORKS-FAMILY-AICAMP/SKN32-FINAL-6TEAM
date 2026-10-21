# -*- coding: utf-8 -*-
"""확인 화면 휴무 줄 — 관광공사 휴무 원문의 공휴일 단서가 상관없는 날까지 「확인해 주세요」로 올리지 않는다. `[2026-10-20]`

재현(x600 서버 실서버 확인, 배포 판 `0057e0ba`): 수요일(10-28) 창덕궁 접수 → 휴무 줄이 「휴무·운영 조건을 확인해 주세요 (매주 월요일 (단, 월요일이
공휴일인 경우 개방하며, 그 다음 첫 번째 평일에 휴관))」. 경위: 창덕궁은 관광공사 장소 「창덕궁과 후원 [유네스코 세계유산]」(127642)로 찾아지고,
운영시간은 관광공사 운영시간 표(`catalog_hours`)에서 온다. 그 행의 읽은 기록(`hours_read.conditions`)에 휴무 원문이 통째로 들어 있어
`hours.facts_for` 가 조건으로 싣고, 확인 화면은 조건이 있으면 요일과 상관없이 경고로 올렸다(대체 후보에서도 「맞는 곳」이 아니게 된다).
활동 원장에는 이 장소가 없다. x600 서버 관광공사 운영시간 2,569곳 중 1,034곳에 조건 문장이 있다.

고침: 활동 팀 휴무 규칙(`closure_rules.read_closure`)에 DB 공휴일 달력을 붙여 조건 문장마다 묻고, 「그날엔 해당 없음」으로 확정된 것만 뺀다.
DB 없이(가짜 연결) 돈다.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import hours as intake_hours
from app.domains.travel_ops.components.intake.review import _hours_lines
from app.domains.travel_ops.components.team_hooks import activity_ledger
from app.domains.travel_ops.instances.activity.closure_rules import read_closure

KST = ZoneInfo("Asia/Seoul")
CHANGDEOK = {"name": "창덕궁과 후원 [유네스코 세계유산]", "content_id": "127642", "source": "tour_api"}
RESTDATE = "매주 월요일 (단, 월요일이 공휴일인 경우 개방하며, 그 다음 첫 번째 평일에 휴관)"
OPEN = {"open": "09:00", "close": "18:00", "last_entry": "17:00"}
WEEK = {day: ("closed" if day == "mon" else dict(OPEN)) for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
#: 한국천문연구원 특일(2026, 일부) — x600 서버 `dining.v_holiday` 와 같은 값
HOLIDAYS_2026 = [(date(2026, 9, 24), "추석"), (date(2026, 9, 25), "추석"), (date(2026, 9, 26), "추석"),
                 (date(2026, 10, 3), "개천절"), (date(2026, 10, 5), "대체공휴일(개천절)"), (date(2026, 10, 9), "한글날")]


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.sql = sql
        self.conn.queries.append(sql)

    def fetchone(self):
        if "FROM catalog_hours" in self.sql:
            return (dict(WEEK), {"source": "tour_api", "method": "llm", "conditions": list(self.conn.conditions)})
        return None

    def fetchall(self):
        return list(self.conn.holidays) if "v_holiday" in self.sql else []


class _Conn:
    def __init__(self, conditions=(RESTDATE,), holidays=HOLIDAYS_2026):
        self.conditions, self.holidays, self.queries = conditions, holidays, []

    def cursor(self):
        return _Cursor(self)

    @contextmanager
    def transaction(self):
        yield


@pytest.fixture(autouse=True)
def _activity_team():
    """활동 팀이 조립 때 꽂는 모양 — 원장에는 창덕궁이 없다(x600 서버와 같다). 휴무 규칙은 진짜 활동 팀 규칙."""
    activity_ledger.register(state=lambda *a, **k: None, state_by_content=lambda *a, **k: None,
                             indoor=lambda *a, **k: None, disaster=lambda messages, **k: None,
                             closure=read_closure)
    yield
    activity_ledger.clear()


def _review(conn, start: datetime):
    end = start.replace(hour=start.hour + 2)
    facts = intake_hours.facts_for(conn, "t", dict(CHANGDEOK), "activity", start, end)
    row = {"date": start.date().isoformat(), "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M"),
           "place": dict(CHANGDEOK), "title": "창덕궁"}
    _hours, closed = _hours_lines(row, facts, [])
    return facts, closed


def test_wednesday_changdeokgung_closed_line_is_normal_with_the_secret_garden_tip():
    """x600 서버 재현 그대로 — 수요일(10-28), 앞 월 · 화가 공휴일이 아니다 → 휴무 원문은 그날과 상관없다."""
    facts, closed = _review(_Conn(), datetime(2026, 10, 28, 10, 0, tzinfo=KST))
    assert facts.source == "tour_api" and facts.conditions == []
    assert closed["result"] == "ok"
    assert closed["text"].startswith("월요일 휴무 · 방문은 수요일")
    assert "후원은 따로 예약해야 들어갈 수 있어요" in closed["text"]          # 관광공사 자료가 있어도 대표 장소 표의 안내는 붙는다


def test_tuesday_is_also_normal_when_monday_was_not_a_holiday():
    """화요일(10-27) 경복궁 휴궁 날 — 창덕궁이 대체 후보에서 「맞는 곳」이 되려면 휴무 줄이 경고가 아니어야 한다(`candidates.assess` 의 `fits`)."""
    facts, closed = _review(_Conn(), datetime(2026, 10, 27, 10, 0, tzinfo=KST))
    assert facts.conditions == [] and closed["result"] == "ok"


def test_the_weekday_after_a_holiday_monday_still_asks_to_check():
    """10-05(월)은 대체공휴일 — 원문대로면 10-06(화)이 휴관일 수 있다. 규칙이 정하지 못하니 지금처럼 「확인해 주세요」."""
    facts, closed = _review(_Conn(), datetime(2026, 10, 6, 10, 0, tzinfo=KST))
    assert facts.conditions == [RESTDATE]
    assert closed["result"] == "warn" and "확인해 주세요" in closed["text"]


def test_without_a_calendar_for_that_year_nothing_is_dropped():
    """달력 표가 비었거나 그해를 모르면 「공휴일 아님」으로 바꾸지 않는다 — 조건을 그대로 둔다."""
    facts, closed = _review(_Conn(holidays=()), datetime(2026, 10, 28, 10, 0, tzinfo=KST))
    assert facts.conditions == [RESTDATE] and closed["result"] == "warn"
    facts, _closed = _review(_Conn(), datetime(2028, 10, 25, 10, 0, tzinfo=KST))
    assert facts.conditions == [RESTDATE]


def test_unregistered_rule_keeps_the_condition():
    activity_ledger.clear()
    facts, closed = _review(_Conn(), datetime(2026, 10, 28, 10, 0, tzinfo=KST))
    assert facts.conditions == [RESTDATE] and closed["result"] == "warn"


def test_only_conditions_settled_as_not_applying_are_dropped():
    """「명절」은 추석 당일엔 남고 평일엔 빠진다. 「홈페이지 참조」 · 「월 1회」는 규칙이 모름으로 읽어 늘 남는다."""
    texts = ("명절", "※ 자세한 사항은 홈페이지 참조", "월 1회")
    weekday, _ = _review(_Conn(conditions=texts), datetime(2026, 10, 28, 10, 0, tzinfo=KST))
    assert weekday.conditions == ["※ 자세한 사항은 홈페이지 참조", "월 1회"]
    chuseok, _ = _review(_Conn(conditions=texts), datetime(2026, 9, 25, 10, 0, tzinfo=KST))
    assert chuseok.conditions == list(texts)


def test_a_date_range_keeps_the_condition_on_every_day_inside_it_and_drops_it_outside():
    """「12월 29일~1월 2일」(x600 서버 자료 1건) — 휴무 규칙이 사이 날짜까지 읽으므로(2026-10-21 고침) 코어가 범위를 따로 빼 두지 않는다.
    양 끝과 사이 날짜(12-30 · 12-31 · 1-1)는 휴무라 「확인해 주세요」로 남고, 범위 밖은 해당 없음으로 빠진다."""
    text = "12월 29일~1월 2일"
    for day in (date(2026, 12, 29), date(2026, 12, 30), date(2026, 12, 31), date(2027, 1, 1), date(2027, 1, 2)):
        facts, closed = _review(_Conn(conditions=(text,)), datetime(day.year, day.month, day.day, 10, 0, tzinfo=KST))
        assert facts.conditions == [text] and closed["result"] == "warn", day
    for day in (date(2026, 12, 28), date(2027, 1, 3), date(2026, 10, 28)):
        facts, closed = _review(_Conn(conditions=(text,)), datetime(day.year, day.month, day.day, 10, 0, tzinfo=KST))
        assert facts.conditions == [], day


def test_a_date_range_whose_end_is_only_a_month_is_kept_because_the_rule_cannot_place_it():
    """「12월 29일~1월 초」 — 끝 날짜를 모르면 규칙이 모름으로 읽고, 코어는 빼지 않는다."""
    text = "12월 29일~1월 초"
    facts, closed = _review(_Conn(conditions=(text,)), datetime(2026, 12, 31, 10, 0, tzinfo=KST))
    assert facts.conditions == [text] and closed["result"] == "warn"


def test_the_calendar_is_not_read_when_the_rule_does_not_ask():
    conn = _Conn(conditions=("※ 자세한 사항은 홈페이지 참조",))
    _review(conn, datetime(2026, 10, 28, 10, 0, tzinfo=KST))
    assert not any("v_holiday" in sql for sql in conn.queries)


def test_the_activity_teams_own_fact_tool_gets_conditions_unsettled():
    """`activity_verdict=False`(활동 팀 자신이 읽는 사실 도구) — 판정하는 쪽에 판정을 섞어 돌려주지 않는다."""
    facts = intake_hours.facts_for(_Conn(), "t", dict(CHANGDEOK), "activity",
                                   datetime(2026, 10, 28, 10, 0, tzinfo=KST), None, activity_verdict=False)
    assert facts.conditions == [RESTDATE]
