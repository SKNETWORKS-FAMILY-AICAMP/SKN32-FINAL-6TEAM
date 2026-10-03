# -*- coding: utf-8 -*-
"""체크리스트 반영(H3·L2·T13·O4) 적대 검토에서 **실제로 재현된** 결함들. `[2026-10-03 적대 검토 — Claude opus, 코덱스 한도 소진 중]`

☆결함 모음 — 전부 새로 만든 판정이 **입력이 조금만 비뚤어져도** 틀리거나 죽는 것이었다. 여행 화면(`_trip_view`)은 이 계산을 매 조회마다 부르니, 죽으면 그 여행은 **영구히 500** 이다.

①장소의 `break` 값이 비뚤어져도(`"15:00~17:00"` · `["15:00:00","17:00:00"]` · `[null,null]`) 품질 경고가 예외를 내지 않는다 — 규칙 하나가 죽어도 나머지는 나가고, 죽은 것은 **세어서 알린다**
②시간대 없는 시각과 있는 시각이 섞여도 판정기가 `TypeError` 로 죽지 않는다(앞 커밋 메시지는 이를 약속했지만 UTC·서울 섞임만 시험했다)
③자정을 넘기는 일정이 마감·브레이크 검사를 빠져나가지 않는다 — 단 「00:00 에 닫는 곳」은 자정에 끝나는 일정을 거절하지 않는다(자정 마감은 23:59 로 읽는다)
④식당 판정(`dining_fits` · `dining_warnings`)도 서울 시각으로 읽는다 — UTC 로 온 도착 시각에 브레이크·라스트오더가 9시간 어긋나지 않는다
⑤라스트오더 경고의 잡음 — 이미 위반인 식사를 또 말하지 않는다 · 브레이크 앞 라스트오더 값이 **없으면** 라스트오더라고 지어 말하지 않는다 · 자정으로 읽힌 마감(23:59)은 「1시간 안」을 말하지 않는다
⑥끼니 경고는 그 시간대에 **식사할 틈이 1시간도 없을 때만** 낸다 — 일정이 창을 덮어도 사이에 틈이 크면 식사 항목이 없다고 말하지 않는다
⑦하루 마감 경고는 숙소·항공을 세지 않고, 사용자가 하루 시간을 직접 준 여행(`constraints.density`)은 밀도 계산이 이미 말하므로 건너뛴다

재현:

    python -m pytest tests/unit/travel/test_checklist_review_fixes.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.modules.travel_ops import itinerary_quality
from app.modules.travel_ops.itinerary_checks import Part, check_itinerary
from app.modules.travel_ops.itinerary_quality import quality_warnings
from app.modules.travel_ops.replan import dining_fits, dining_warnings

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc


def _at(hhmm: str, day: int = 6, month: int = 10) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, month, day, int(hour), int(minute), tzinfo=KST)


def _part(seq, title, start, end=None, *, kind="activity", attributes=None, day=6, lat=37.5, lon=127.0):
    place = {"name": title, "place_id": f"p{seq}", "latitude": lat, "longitude": lon, "attributes": dict(attributes or {})}
    return Part(seq=seq, kind=kind, title=title, starts_at=_at(start, day), ends_at=_at(end, day) if end else None, place=place)


def _codes(found):
    return sorted(w["code"] for w in found)


# ── ① 비뚤어진 break 값 ──────────────────────────────────────────
MALFORMED_BREAKS = ["15:00~17:00", ["15:00:00", "17:00:00"], [None, None], ["15", "17"], "no", [1500, 1700], ["15:00"]]


@pytest.mark.parametrize("brk", MALFORMED_BREAKS)
def test_a_malformed_break_value_never_breaks_the_quality_warnings(brk):
    found = quality_warnings([_part(1, "한식당", "12:00", "13:00", kind="dining", attributes={"hours": ["11:00", "22:00"], "break": brk})])
    assert isinstance(found, list)


@pytest.mark.parametrize("brk", MALFORMED_BREAKS)
def test_a_malformed_break_value_never_breaks_the_dining_judges(brk):
    place = {"name": "한식당", "attributes": {"hours": ["11:00", "22:00"], "break": brk}}
    fits, _ = dining_fits(place, _at("12:00"), 60)
    assert fits in (True, False, None)
    assert isinstance(dining_warnings(place, _at("12:00"), 60), list)


def test_a_rule_that_dies_is_counted_and_the_other_rules_still_answer(monkeypatch):
    """규칙 하나가 예외를 내도 나머지 경고는 나간다 — 죽은 규칙은 **조용히 빼지 않고** 「일부 점검을 못 했다」로 센다(`RULE` — 조용한 스킵 금지)."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("규칙이 죽었다")

    monkeypatch.setattr(itinerary_quality, "_last_order", boom)
    found = quality_warnings([_part(1, "경복궁", "10:00", "11:00"), _part(2, "야경 투어", "21:00", "23:00")])
    assert "past_day_end" in _codes(found)                                   # 다른 규칙은 그대로
    [skipped] = [w for w in found if w["code"] == "quality_check_skipped"]
    assert "last_order" in skipped["rules"] and skipped["reason"] and "끼니" not in skipped["reason"]


# ── ② 시간대 섞임 ────────────────────────────────────────────────
def test_naive_and_aware_times_in_one_itinerary_do_not_crash_the_judge():
    naive_start = datetime(2026, 10, 6, 10, 0)                               # 시간대 없음 — 서울로 본다
    aware_start = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)                   # 서울 21:00
    parts = [
        Part(seq=1, kind="activity", title="경복궁", starts_at=naive_start, ends_at=datetime(2026, 10, 6, 11, 0, tzinfo=KST),
             place={"name": "경복궁", "attributes": {}}),
        Part(seq=2, kind="activity", title="야경", starts_at=aware_start, ends_at=datetime(2026, 10, 6, 13, 0), place={"name": "야경", "attributes": {}}),
    ]
    assert isinstance(check_itinerary(parts), list)                          # 전에는 TypeError


def test_naive_times_are_read_as_seoul_not_as_this_machines_zone():
    attributes = {"hours": ["09:00", "18:00"]}
    part = Part(seq=1, kind="activity", title="궁", starts_at=datetime(2026, 10, 6, 10, 0), ends_at=datetime(2026, 10, 6, 11, 0),
                place={"name": "궁", "attributes": attributes})
    assert check_itinerary([part]) == []


# ── ③ 자정 넘김 ─────────────────────────────────────────────────
def test_an_item_that_runs_past_midnight_does_not_escape_the_closing_check():
    attributes = {"hours": ["10:00", "22:00"]}
    late = Part(seq=1, kind="activity", title="야시장", starts_at=_at("21:00"), ends_at=_at("01:00", day=7), place={"name": "야시장", "attributes": attributes})
    assert "after_closing" in {v.code for v in check_itinerary([late])}


def test_an_item_that_runs_past_midnight_does_not_escape_the_break_check():
    attributes = {"hours": ["10:00", "23:59"], "break": ["15:00", "17:00"]}
    late = Part(seq=1, kind="dining", title="식당", starts_at=_at("14:00"), ends_at=_at("02:00", day=7), place={"name": "식당", "attributes": attributes})
    assert "break_time" in {v.code for v in check_itinerary([late])}


def test_a_place_that_closes_at_midnight_does_not_reject_an_item_ending_at_midnight():
    """자정 마감(24:00)은 23:59 로 읽는다(`place_hours._clock`) — 23:00~00:00 일정을 닫은 뒤라고 거절하지 않는다. 자정을 넘겨 새벽 1시까지면 **알 수 없다**(진짜 닫는 시각이 02:00 일 수도) — 거절하지 않는다."""
    attributes = {"hours": ["08:00", "24:00"]}
    until_midnight = Part(seq=1, kind="activity", title="올리브영", starts_at=_at("23:00"), ends_at=_at("00:00", day=7), place={"name": "올리브영", "attributes": attributes})
    past_midnight = Part(seq=2, kind="activity", title="올리브영", starts_at=_at("23:00"), ends_at=_at("01:00", day=7), place={"name": "올리브영", "attributes": attributes})
    assert "after_closing" not in {v.code for v in check_itinerary([until_midnight])}
    assert "after_closing" not in {v.code for v in check_itinerary([past_midnight])}


# ── ④ 식당 판정의 서울 시각 ─────────────────────────────────────────
def test_the_dining_judges_read_a_utc_arrival_as_seoul():
    """서울 14:30 = UTC 05:30. 브레이크 15:00~17:00 · 브레이크 앞 라스트오더 30분 전(14:30)이라 서울로 읽으면 촉박하다 — 전에는 UTC 시계에 브레이크를 얹어 판정이 어긋났다."""
    place = {"name": "한식당", "attributes": {"hours": ["11:00", "22:00"], "break": ["15:00", "17:00"], "last_order_before_break_min": 30}}
    seoul_ok, seoul_why = dining_fits(place, _at("14:20"), 40)
    utc_ok, utc_why = dining_fits(place, _at("14:20").astimezone(UTC), 40)
    assert (seoul_ok, seoul_why) == (utc_ok, utc_why)
    assert seoul_ok is False and "14:30" in seoul_why                        # 문장의 시각도 서울 시계


def test_the_dining_warning_reads_a_utc_arrival_as_seoul():
    place = {"name": "한식당", "attributes": {"hours": ["11:00", "22:00"]}}
    assert dining_warnings(place, _at("20:30"), 60) == dining_warnings(place, _at("20:30").astimezone(UTC), 60) != []


# ── ⑤ 라스트오더 경고의 잡음 ──────────────────────────────────────────
def test_a_meal_the_judge_already_rejects_is_not_said_twice_for_a_break_arrival():
    """브레이크 시간 한가운데 도착 — `break_time` 위반이 이미 막는다. 「라스트오더 촉박」으로 또 말하지 않는다."""
    attributes = {"hours": ["11:00", "22:00"], "break": ["15:00", "17:00"], "last_order_before_break_min": 30}
    parts = [_part(1, "한식당", "15:30", "16:30", kind="dining", attributes=attributes)]
    assert "break_time" in {v.code for v in check_itinerary(parts)}
    assert not {"last_order_tight", "last_order_unknown"} & set(_codes(quality_warnings(parts)))


def test_a_break_without_a_known_last_order_is_not_called_a_last_order():
    """브레이크 앞 라스트오더 값이 없는데 「라스트오더(15:00)까지 15분」이라고 지어 말하지 않는다 — 모르면 「마지막 주문을 확인해 주세요」(`last_order_unknown`)뿐이다."""
    attributes = {"hours": ["11:00", "22:00"], "break": ["15:00", "17:00"]}
    found = quality_warnings([_part(1, "한식당", "14:00", "14:50", kind="dining", attributes=attributes)])
    assert "last_order_tight" not in _codes(found) and "last_order_unknown" in _codes(found)


def test_a_midnight_close_is_not_a_one_hour_warning():
    """자정 마감은 23:59 로 읽힌다 — 진짜 닫는 시각을 모르니 「23:59 마감 1시간 안」이라고 말하지 않는다."""
    attributes = {"hours": ["08:00", "24:00"]}
    found = quality_warnings([_part(1, "식당", "22:30", "23:30", kind="dining", attributes=attributes)])
    assert not {"last_order_tight", "last_order_unknown"} & set(_codes(found))


# ── ⑥ 끼니: 식사할 틈 ────────────────────────────────────────────
def test_a_free_gap_of_an_hour_inside_the_lunch_window_is_not_a_missing_meal():
    found = quality_warnings([_part(1, "궁", "10:00", "11:30"), _part(2, "박물관", "13:30", "16:30")])      # 11:30~13:30 비어 있다
    assert "meal_missing" not in _codes(found)


def test_a_lunch_window_packed_with_activities_is_a_missing_meal():
    found = quality_warnings([_part(1, "궁", "10:00", "12:00"), _part(2, "박물관", "12:30", "16:30")])      # 틈 30분(12:00~12:30) · 14:00 까지 이어진다
    assert [w["code"] for w in found if w["code"] == "meal_missing"] == ["meal_missing"]


# ── ⑦ 하루 마감: 숙소·항공 · 사용자가 준 하루 시간 ────────────────────────────
def test_a_hotel_or_a_night_flight_is_not_a_late_item():
    parts = [_part(1, "경복궁", "10:00", "11:00"),
             Part(seq=2, kind="lodging", title="호텔", starts_at=_at("15:00"), ends_at=_at("11:00", day=7), place={"name": "호텔", "attributes": {}}),
             Part(seq=3, kind="flight", title="심야 항공", starts_at=_at("23:30"), ends_at=_at("01:30", day=7), place=None)]
    assert "past_day_end" not in _codes(quality_warnings(parts))


def test_a_hotel_stay_does_not_make_the_day_cover_the_dinner_window():
    """숙소 체크인~다음 날 체크아웃이 하루 끝을 다음 날로 늘려 「저녁 창을 통째로 덮는다」고 오경고했다."""
    parts = [_part(1, "궁", "10:00", "11:00"), _part(2, "점심", "12:00", "13:00", kind="dining"), _part(3, "박물관", "14:00", "16:00"),
             Part(seq=4, kind="lodging", title="호텔", starts_at=_at("15:00"), ends_at=_at("11:00", day=7), place={"name": "호텔", "attributes": {}})]
    assert "meal_missing" not in _codes(quality_warnings(parts))


def test_a_trip_with_its_own_day_window_is_left_to_the_density_calculation():
    parts = [_part(1, "경복궁", "10:00", "11:00"), _part(2, "야경 투어", "21:00", "23:00")]
    assert "past_day_end" in _codes(quality_warnings(parts))                                       # 하루 시간을 안 줬으면 22:00 기본값
    with_window = {"density": {"level": "balanced", "days": {"2026-10-06": {"starts_at": "2026-10-06T08:00:00+09:00",
                                                                                "ends_at": "2026-10-06T23:30:00+09:00", "buffer_minutes": 0}}}}
    assert "past_day_end" not in _codes(quality_warnings(parts, with_window))                      # 사용자가 23:30 까지로 줬다 — 밀도 계산이 창 밖을 말한다


# ── ui 검증 세션이 짚은 것 ────────────────────────────────────────
def test_the_unresolved_notice_does_not_leak_a_code_name_into_the_customer_sentence():
    """새벽 확인이 만든 원인에는 `type=closed_on_day` 뿐이라 알림 문장에 코드 이름이 그대로 들어갔다."""
    from uuid import uuid4

    from app.modules.travel_ops.itinerary import Item
    from app.modules.travel_ops.pending import unresolved_notice

    item = Item(item_id=uuid4(), seq=1, kind="dining", title="점심 식당", place_id=None, starts_at=_at("12:00"), ends_at=_at("13:00"), place=None, detail={})
    cause = {"category": "place_closed", "type": "closed_on_day", "source": "google", "detail": "휴무", "evidence": "새벽 확인"}
    for recheck in (True, False):
        text = unresolved_notice(item=item, causes=[cause], recheck_failed=recheck)["text"]
        assert "closed_on_day" not in text and "place_closed" not in text and "쉬는 곳" in text
    assert "일정에 문제가 생겼어요" in unresolved_notice(item=item, causes=[{"category": "some_new_code"}])["text"]    # 모르는 코드도 새지 않는다
    assert "호우경보" in unresolved_notice(item=item, causes=[{"category": "weather_warning", "kind": "호우경보"}])["text"]


def test_the_mcp_error_text_carries_the_field_positions():
    from app.modules.travel_ops.mcp_server import McpApiError

    error = McpApiError(422, "validation_error", "필수 칸이 비었어요", {"fields": [{"loc": ["body", "items", 0, "title"], "type": "missing"}]})
    assert "fields" in error.text() and "title" in error.text()


# ── 동선 점검의 비용 ──────────────────────────────────────────────
def test_the_zigzag_check_of_a_full_day_of_eight_stops_is_cheap():
    """`max_stops`(8)곳이면 순서를 모두 세는 방식은 4만 가지 — 여행 화면을 열 때마다(그날마다) 약 1.1초가 들었다. 같은 답을 내되 값싸게(동적 계획법) 센다."""
    import time as clock

    zigzag = [(37.50, 127.00), (37.58, 127.00), (37.51, 127.00), (37.57, 127.00), (37.52, 127.00), (37.56, 127.00), (37.53, 127.00), (37.55, 127.00)]
    parts = [_part(i, f"곳{i}", f"{9 + i}:00", f"{9 + i}:40", lat=lat, lon=lon) for i, (lat, lon) in enumerate(zigzag, 1)]
    began = clock.perf_counter()
    found = quality_warnings(parts)
    took = clock.perf_counter() - began
    assert [w for w in found if w["code"] == "route_zigzag"], "지그재그가 잡혀야 한다"
    assert took < 0.4, f"동선 점검이 {took:.2f}초 걸렸다"


def test_the_cheap_shortest_path_equals_the_exhaustive_one():
    """DP 로 구한 가장 짧은 열린 경로의 길이는 모든 순서를 세어 본 값과 같다."""
    from itertools import permutations
    import random

    from app.modules.travel_ops.itinerary_quality import _shortest_open_path

    rng = random.Random(7)
    for count in (2, 3, 5, 6):
        points = [(rng.random(), rng.random()) for _ in range(count)]
        dist = [[((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for b in points] for a in points]
        order = _shortest_open_path(dist)
        length = lambda o: sum(dist[a][b] for a, b in zip(o, o[1:]))  # noqa: E731
        assert sorted(order) == list(range(count))
        assert abs(length(order) - min(length(o) for o in permutations(range(count)))) < 1e-9
