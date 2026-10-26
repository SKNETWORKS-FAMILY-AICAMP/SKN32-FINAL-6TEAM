# -*- coding: utf-8 -*-
"""확인 화면 휴무 줄 — **구역별 방문 제한시간**을 날짜 휴무와 섞지 않는다. `[2026-10-25 Comment9]`

재현(부모 읽기 전용 DB 확인, 공개 장소 + 고객이 준 방문 날짜·시각만 fixture 로 사용): 방문 2026-11-02 10:00–11:30, 운영시간 줄은 ok
「10:00–17:00 안에 머물러요」인데 휴무 줄이 warn 「휴무·운영 조건을 확인해 주세요 (※ 방문 제한시간(특별관리지역(레드존) 방문 금지) :
17:00~익일 10:00; 쉬는 날: 연중무휴)」였다. 원인: 읽어 둔 조건 문장 둘이 `_settle_stored_conditions` 를 통과하지 못했다.
  ① 「쉬는 날: 연중무휴」 — 앞의 라벨 때문에 휴무 규칙이 「연중무휴」로 못 읽고 모름.
  ② 「방문 제한시간 … 17:00~익일 10:00」 — 휴무가 아니라 시간대 제한인데 휴무 규칙은 「못 읽은 조각」으로 모름 처리.
  `review._hours_and_closed` 는 조건이 하나라도 남으면 앞서 낸 ok 를 warn 으로 덮는다.
고침 범위: 방문 시각과 겹치지 않는다고 **확정**되는 제한시간만 조건에서 빼고 원문은 안내(`tips`)로 보존한다. 겹치거나 읽기 모호하면 그대로 남긴다.
DB 없이(가짜 연결) 돈다.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.intake import hours as intake_hours
from app.domains.travel_ops.components.intake.review import _hours_lines
from app.domains.travel_ops.components.team_hooks import activity_ledger
from app.domains.travel_ops.instances.activity.closure_rules import read_closure

KST = ZoneInfo("Asia/Seoul")
PLACE = {"name": "북촌한옥마을", "content_id": "126537", "source": "tour_api"}
RESTRICT = "※ 방문 제한시간(특별관리지역(레드존) 방문 금지) : 17:00~익일 10:00"
ALWAYS = "쉬는 날: 연중무휴"
OPEN = {"open": "10:00", "close": "17:00", "last_entry": None}
WEEK = {day: dict(OPEN) for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


class _Cursor:
    def __init__(self, conn):
        self.conn, self.sql = conn, ""

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
        return []


class _Conn:
    def __init__(self, conditions=(RESTRICT, ALWAYS)):
        self.conditions, self.queries = conditions, []

    def cursor(self):
        return _Cursor(self)

    @contextmanager
    def transaction(self):
        yield


@pytest.fixture(autouse=True)
def _activity_team():
    activity_ledger.register(state=lambda *a, **k: None, state_by_content=lambda *a, **k: None,
                             indoor=lambda *a, **k: None, disaster=lambda messages, **k: None,
                             closure=read_closure)
    yield
    activity_ledger.clear()


def _at(hhmm: str, day=(2026, 11, 2)) -> datetime:
    hour, minute = (int(x) for x in hhmm.split(":"))
    return datetime(*day, hour, minute, tzinfo=KST)


def _review(conditions, start: str, end: str | None):
    s, e = _at(start), (_at(end) if end else None)
    facts = intake_hours.facts_for(_Conn(conditions), "t", dict(PLACE), "activity", s, e)
    row = {"date": s.date().isoformat(), "start": start, "end": end, "place": dict(PLACE), "title": "산책"}
    hours, closed = _hours_lines(row, facts, [])
    return facts, hours, closed


def test_exact_case_zone_restriction_is_guidance_not_a_closure_warning():
    """11/2(월) 10:00–11:30 — 제한시간(17:00~익일 10:00)과 안 겹치고 연중무휴다. 고객에게 되묻지 않는다."""
    facts, hours, closed = _review([RESTRICT, ALWAYS], "10:00", "11:30")
    assert hours["result"] == "ok" and "10:00–17:00" in hours["text"]
    assert facts.conditions == []
    assert closed["result"] == "ok"
    assert "확인해 주세요" not in closed["text"]
    assert "휴무·운영 조건" not in closed["text"]
    assert RESTRICT in closed["text"]                      # 원문은 안내로 보존
    assert RESTRICT in facts.tips


def test_boundaries_touching_the_window_edge_are_not_overlap():
    for start, end in (("10:00", "17:00"), ("10:00", None), ("12:00", "17:00")):
        facts, _hours, closed = _review([RESTRICT, ALWAYS], start, end)
        assert facts.conditions == [] and closed["result"] == "ok", (start, end)


@pytest.mark.parametrize("start,end", [("16:30", "17:30"), ("17:00", "17:30"), ("17:00", None), ("09:59", "10:30"),
                                       ("09:00", "10:30"), ("20:00", "21:00"), ("02:00", "03:00")])
def test_visit_overlapping_the_restricted_time_keeps_the_condition_unknown(start, end):
    facts, _hours, closed = _review([RESTRICT, ALWAYS], start, end)
    assert facts.conditions == [RESTRICT], (start, end)
    assert closed["result"] == "warn" and RESTRICT in closed["text"]


def test_overnight_window_written_without_next_day_marker_is_still_a_window():
    text = "방문 제한시간(야간 출입통제) : 22:00~06:00"
    clear, _h, _c = _review([text], "06:00", "07:00")
    assert clear.conditions == [] and text in clear.tips
    for start, end in (("23:00", "23:30"), ("05:00", "05:30"), ("21:30", "22:30")):
        hit, _h, _c = _review([text], start, end)
        assert hit.conditions == [text], (start, end)


def test_same_day_window_is_judged_on_the_same_day():
    text = "입장 금지 시간 안내 - 방문 제한시간 12:00~13:00"
    assert _review([text], "10:00", "12:00")[0].conditions == []
    assert _review([text], "12:30", "13:30")[0].conditions == [text]
    assert _review([text], "13:00", "14:00")[0].conditions == []


@pytest.mark.parametrize("text", [
    "방문 제한시간 17:00~17:00",                                  # 시작=끝: 한 시각인지 종일인지 모호
    "방문 제한시간 17:00~익일 19:00",                              # 익일인데 24시간을 넘는다
    "방문 제한시간 09:00~10:00, 17:00~18:00",                      # 구간이 둘
    "평일 방문 제한시간 17:00~익일 10:00",                         # 요일 단서
    "11월 방문 제한시간 17:00~익일 10:00",                         # 달 단서
    "방문 제한시간 25:00~익일 10:00",                             # 읽을 수 없는 시각
    "방문 제한시간 별도 안내",                                     # 시간 없음
    "17:00~익일 10:00",                                           # 제한이라는 말이 없다 — 무엇의 시간인지 모른다
])
def test_ambiguous_or_unreadable_restrictions_stay_unknown(text):
    facts, hours, closed = _review([text], "10:00", "11:30")
    assert facts.conditions == [text]
    assert closed["result"] == "warn"
    assert hours["result"] == "ok"                             # 운영시간 줄은 건드리지 않는다


def test_a_restriction_never_hides_a_real_unresolved_condition():
    """제한시간을 안내로 옮기더라도 다른 해석 불가 조건은 지우지 않는다."""
    other = "※ 자세한 사항은 홈페이지 참조"
    facts, _hours, closed = _review([RESTRICT, other], "10:00", "11:30")
    assert facts.conditions == [other]
    assert closed["result"] == "warn" and other in closed["text"]


def test_restriction_is_not_widened_into_an_all_day_closure():
    facts, hours, closed = _review([RESTRICT], "12:00", "13:00")
    assert closed["result"] == "ok" and hours["result"] == "ok"
    assert "쉬는 날이에요" not in closed["text"] and "휴무예요" not in closed["text"]


def test_rest_day_label_prefix_is_read_by_the_closure_rule():
    assert _review([ALWAYS], "10:00", "11:00")[0].conditions == []
    assert _review(["휴무일 : 연중무휴"], "10:00", "11:00")[0].conditions == []
    # 라벨 뒤가 해당 날 휴무이거나 모름이면 남는다 — 월요일(11/2)
    assert _review(["쉬는 날: 매주 월요일"], "10:00", "11:00")[0].conditions == ["쉬는 날: 매주 월요일"]
    assert _review(["쉬는 날: 홈페이지 참조"], "10:00", "11:00")[0].conditions == ["쉬는 날: 홈페이지 참조"]


def test_values_come_from_the_text_not_from_the_product():
    text = "※ 방문 제한시간(보호구역 방문 금지) : 20:00~익일 09:00"
    facts, _hours, closed = _review([text, ALWAYS], "09:30", "11:00")
    assert facts.conditions == [] and text in closed["text"]
    facts, _hours, _closed = _review([text, ALWAYS], "08:30", "09:30")
    assert facts.conditions == [text]


def test_one_string_holding_both_clauses_is_split_and_judged_separately():
    joined = RESTRICT + "\n" + ALWAYS
    facts, _hours, closed = _review([joined], "10:00", "11:30")
    assert facts.conditions == [] and closed["result"] == "ok" and RESTRICT in closed["text"]
    hit, _h, _c = _review([joined], "16:30", "17:30")
    assert hit.conditions == [RESTRICT]


def test_activity_teams_own_fact_tool_gets_conditions_unsettled():
    facts = intake_hours.facts_for(_Conn(), "t", dict(PLACE), "activity", _at("10:00"), _at("11:30"), activity_verdict=False)
    assert facts.conditions == [RESTRICT, ALWAYS] and facts.tips == []
