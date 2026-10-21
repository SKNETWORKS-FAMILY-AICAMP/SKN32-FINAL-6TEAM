# -*- coding: utf-8 -*-
"""오늘 시작하는 계획은 지금부터 짠다 — 지금은 요청 입구에서 한 번만 정하고, 고객이 요청한 시각이 먼저다. `[2026-10-21 사용자 지시]`

하루 시작 08:00 · 마감 22:00 은 요청에 시각이 없을 때만 쓰는 기본값이다. 그래서 마감 뒤에 요청해도 그 시각부터 만든다.
첫날만 바뀌고 둘째 날부터는 평소 창이다.

재현:

    python -m pytest tests/unit/travel/test_plan_from_now.py -v
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.planning import planner
from app.domains.travel_ops.components.planning.planner import LAST_MINUTE_OF_DAY, PlanRefused, PlanRequest

KST = ZoneInfo("Asia/Seoul")
TODAY = date(2026, 10, 21)


def request(start: date = TODAY, constraints=None, days: int = 1) -> PlanRequest:
    return PlanRequest(city="서울", start_date=start, days=days, party_size=2, constraints=constraints or {})


def moment(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 10, 21, hour, minute, second, tzinfo=KST)


def window(hour: int, minute: int, second: int = 0, **kw):
    return planner._first_day_window(request(**kw), moment(hour, minute, second))


def test_a_plan_that_starts_today_begins_at_now_rounded_up_to_five_minutes():
    assert window(17, 39, 10) == (time(17, 40), time(22, 0))


def test_an_exact_five_minute_mark_without_seconds_is_kept():
    assert window(17, 40) == (time(17, 40), time(22, 0))


def test_a_request_after_the_default_end_is_still_made_from_that_moment():
    # 22:00 은 요청에 시각이 없을 때의 기본값이다 — 밤 11시 10분에 지금부터 만들어 달라면 그 시각부터 만든다
    assert window(23, 10) == (time(23, 10), LAST_MINUTE_OF_DAY)


def test_the_customers_own_end_is_kept_when_it_is_still_ahead():
    assert window(17, 39, constraints={"day_hours": {"end": "23:00"}}) == (time(17, 40), time(23, 0))


def test_the_customers_own_end_that_has_already_passed_leaves_the_usual_window():
    # 「21시까지」라고 했는데 지금이 22시 반 — 두 요청을 함께 들어줄 수 없어 짐작으로 고르지 않는다
    assert window(22, 30, constraints={"day_hours": {"end": "21:00"}}) is None


def test_the_customers_own_late_hours_are_used_as_they_are():
    # 고객 요청이 명확하면 24시간 어느 시각이든 그대로 — 기본 08:00 · 22:00 은 맡긴 경우에만 쓴다
    wants_night = {"day_hours": {"start": "23:00", "end": "23:59"}}
    assert planner.day_bounds(wants_night) == (time(23, 0), time(23, 59))
    assert window(17, 39, constraints=wants_night) is None            # 지금이 고객이 말한 시작보다 이르다 — 지난 칸이 없으니 고객이 말한 창 그대로
    assert window(23, 10, constraints=wants_night) == (time(23, 10), time(23, 59))        # 말한 창 안에서 지금부터


def test_another_start_day_is_left_alone():
    assert planner._first_day_window(request(date(2026, 10, 22)), moment(17, 39)) is None


def test_before_the_usual_start_nothing_has_passed_so_the_usual_window_is_used():
    assert window(5, 0) is None


def test_the_customers_own_later_start_is_not_moved_earlier():
    assert window(17, 39, constraints={"day_hours": {"start": "19:00"}}) is None


def test_rounding_past_midnight_leaves_the_usual_window():
    assert window(23, 58) is None


def test_the_request_is_never_changed_so_later_days_and_the_saved_trip_keep_their_usual_hours():
    original = request(constraints={"day_hours": {"end": "21:00"}}, days=3)
    planner._first_day_window(original, moment(17, 39))
    assert original.constraints == {"day_hours": {"end": "21:00"}}


def test_overflow_is_judged_by_the_day_end_of_each_day():
    # 지금부터 짠 첫날은 23:59 까지, 다른 날은 평소 마감(22:00)
    late = {"seq": 1, "kind": "activity", "title": "야경", "starts_at": datetime(2026, 10, 21, 23, 0, tzinfo=KST),
            "ends_at": datetime(2026, 10, 21, 23, 40, tzinfo=KST), "detail": {"planner": {"day": "2026-10-21"}}}
    planner._refuse_overflow([late], rounds=0, fixed=[], why="시험", day_ends={"2026-10-21": LAST_MINUTE_OF_DAY})
    with pytest.raises(PlanRefused):
        planner._refuse_overflow([late], rounds=0, fixed=[], why="시험")
