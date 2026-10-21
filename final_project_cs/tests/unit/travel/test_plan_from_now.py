# -*- coding: utf-8 -*-
"""오늘 시작하는 계획은 지금부터 짠다 — 지금은 요청 입구에서 한 번만 정한다. `[2026-10-21 사용자 지시]`

재현:

    python -m pytest tests/unit/travel/test_plan_from_now.py -v
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.planning import planner
from app.domains.travel_ops.components.planning.planner import PlanRequest, day_bounds

KST = ZoneInfo("Asia/Seoul")
TODAY = date(2026, 10, 21)


def request(start: date = TODAY, constraints=None) -> PlanRequest:
    return PlanRequest(city="서울", start_date=start, days=1, party_size=2, constraints=constraints or {})


def moment(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 10, 21, hour, minute, second, tzinfo=KST)


def test_a_plan_that_starts_today_begins_at_now_rounded_up_to_five_minutes():
    shaped = planner._from_moment(request(), moment(17, 39, 10))
    assert shaped.constraints["day_hours"]["start"] == "17:40"
    assert day_bounds(shaped.constraints)[0].strftime("%H:%M") == "17:40"          # 아래 함수들이 늘 읽는 값이 그대로 바뀐다


def test_an_exact_five_minute_mark_without_seconds_is_kept():
    shaped = planner._from_moment(request(), moment(17, 40))
    assert shaped.constraints["day_hours"]["start"] == "17:40"


def test_another_day_is_left_alone():
    tomorrow = request(date(2026, 10, 22))
    assert planner._from_moment(tomorrow, moment(17, 39)) is tomorrow


def test_before_the_usual_start_the_request_is_left_alone():
    # 아직 하루 시작 전(새벽)이면 평소 시작 시각을 쓴다
    early = request()
    assert planner._from_moment(early, moment(5, 0)) is early


def test_after_the_day_ends_the_request_is_left_alone():
    # 하루 마감(22:00) 뒤에는 억지로 바꾸지 않는다 — 호출하는 쪽이 판단
    late = request()
    assert planner._from_moment(late, moment(22, 30)) is late


def test_the_customers_own_later_start_is_not_moved_earlier():
    wants_late = request(constraints={"day_hours": {"start": "19:00"}})
    shaped = planner._from_moment(wants_late, moment(17, 39))
    assert shaped is wants_late


def test_the_original_request_is_not_changed():
    original = request(constraints={"day_hours": {"end": "21:00"}})
    shaped = planner._from_moment(original, moment(17, 39))
    assert shaped.constraints["day_hours"] == {"end": "21:00", "start": "17:40"}
    assert original.constraints == {"day_hours": {"end": "21:00"}}
