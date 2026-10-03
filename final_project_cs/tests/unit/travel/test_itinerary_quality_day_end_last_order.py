# -*- coding: utf-8 -*-
"""일정 품질 경고 두 가지 더 — 체크리스트 T13(하루 마감 22:00) · O4(식당 라스트오더 20분). `[2026-10-03]`

☆왜: 생성기는 하루 마감을 넘기면 거절하고 대체 식당은 라스트오더 20분 규칙으로 거르는데, **받은 일정**(고객 · 외부 에이전트)에는 둘 다 걸리지 않았다 —
밤 11시에 끝나는 저녁도, 라스트오더 5분 전에 도착하는 식사도 아무도 말하지 않았다. 거절은 아니다(일부러 늦게까지 가는 일정 · 급한 식사도 가능은 하다) — 「살펴볼 점」으로 알린다.

★지키려는 것: ①마감(`travel.day_window.default_end`)을 넘겨 끝나면 늦게 끝나는 항목을 이름으로 말한다 ②라스트오더를 **알면** 도착 + 20분이 넘을 때, **모르면** 영업 종료 1시간 안에 식사가 끝날 때
③이미 위반(영업 안 함 · 브레이크)인 것은 여기서 다시 말하지 않는다 ④잡음이 없다(마감 안에 끝남 · 여유 있는 식사 · 식사 아닌 항목).

재현:

    python -m pytest tests/unit/travel/test_itinerary_quality_day_end_last_order.py -v
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary_checks import Part
from app.modules.travel_ops.itinerary_quality import quality_warnings

KST = ZoneInfo("Asia/Seoul")


def _at(hhmm: str, day: int = 23) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 9, day, int(hour), int(minute), tzinfo=KST)


def _part(seq, title, start, end=None, *, kind="activity", attributes=None, day=23):
    place = {"name": title, "place_id": f"p{seq}", "latitude": 37.5, "longitude": 127.0, "attributes": dict(attributes or {})}
    return Part(seq=seq, kind=kind, title=title, starts_at=_at(start, day), ends_at=_at(end, day) if end else None, place=place)


def _codes(found):
    return sorted(w["code"] for w in found)


# ── T13 하루 마감 ───────────────────────────────────────────────

def test_a_day_that_ends_after_the_day_end_is_a_warning_naming_the_late_item():
    found = quality_warnings([_part(1, "경복궁", "10:00", "11:30"), _part(2, "야경 투어", "21:00", "23:00")])
    [warning] = [w for w in found if w["code"] == "past_day_end"]
    assert warning["items"] == [2] and "야경 투어" in warning["reason"] and "23:00" in warning["reason"] and "22:00" in warning["reason"]
    assert warning["date"] == "2026-09-23" and warning["remedy"]


def test_a_day_that_ends_exactly_on_the_day_end_is_fine():
    assert "past_day_end" not in _codes(quality_warnings([_part(1, "경복궁", "10:00", "11:30"), _part(2, "저녁", "20:00", "22:00", kind="dining")]))


def test_every_late_item_is_named_and_each_day_is_judged_on_its_own():
    found = quality_warnings([
        _part(1, "공연", "20:00", "22:30"), _part(2, "야식", "22:30", "23:30", kind="dining"),
        _part(3, "박물관", "10:00", "11:00", day=24),                       # 다음 날은 마감 안에 끝난다
    ])
    late = [w for w in found if w["code"] == "past_day_end"]
    assert len(late) == 1 and late[0]["date"] == "2026-09-23" and late[0]["items"] == [1, 2]


def test_an_item_without_an_end_is_judged_by_its_start():
    assert "past_day_end" in _codes(quality_warnings([_part(1, "심야 영화", "22:30")]))
    assert "past_day_end" not in _codes(quality_warnings([_part(1, "저녁 산책", "21:30")]))


# ── O4 식당 라스트오더 ───────────────────────────────────────────

#: 수요일(2026-09-23)에 21:00 라스트오더인 식당 — 요일별 칸(`hours_week`)에만 라스트오더를 적을 수 있다
WITH_LAST_ORDER = {"hours_week": {"wed": {"open": "11:00", "close": "22:00", "last_entry": "21:00"}}}


def test_arriving_with_less_than_twenty_minutes_before_a_known_last_order_is_a_warning():
    found = quality_warnings([_part(1, "한식당", "20:50", "21:40", kind="dining", attributes=WITH_LAST_ORDER)])
    [warning] = [w for w in found if w["code"] == "last_order_tight"]
    assert warning["items"] == [1] and "한식당" in warning["reason"] and "라스트오더" in warning["reason"] and "20분" in warning["reason"]


def test_arriving_with_twenty_or_more_minutes_before_a_known_last_order_is_fine():
    found = quality_warnings([_part(1, "한식당", "20:30", "21:15", kind="dining", attributes=WITH_LAST_ORDER)])
    assert not {"last_order_tight", "last_order_unknown"} & set(_codes(found))                # 알면 20분으로 판정하고 모르는 경고는 안 한다


def test_an_unknown_last_order_with_the_meal_ending_near_closing_asks_to_confirm():
    found = quality_warnings([_part(1, "한식당", "20:30", "21:30", kind="dining", attributes={"hours": ["11:00", "22:00"]})])
    [warning] = [w for w in found if w["code"] == "last_order_unknown"]
    assert "마지막 주문" in warning["reason"] and warning["items"] == [1]


def test_a_comfortable_meal_is_not_a_warning_and_neither_is_a_non_meal():
    comfortable = _part(1, "한식당", "12:00", "13:00", kind="dining", attributes={"hours": ["11:00", "22:00"]})
    late_activity = _part(2, "전망대", "21:30", "21:55", attributes={"hours": ["10:00", "22:00"]})
    found = quality_warnings([comfortable, late_activity])
    assert not {"last_order_tight", "last_order_unknown"} & set(_codes(found))


def test_a_meal_the_judge_already_rejects_is_not_said_twice():
    """영업을 안 하는 시각(07:00 에 식당)은 위반(`closed`/`before_opening`)이 이미 막는다 — 라스트오더 경고로 또 말하지 않는다."""
    found = quality_warnings([_part(1, "한식당", "07:00", "08:00", kind="dining", attributes={"hours": ["11:00", "22:00"]})])
    assert not {"last_order_tight", "last_order_unknown"} & set(_codes(found))
