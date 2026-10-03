# -*- coding: utf-8 -*-
"""일정 품질 경고 — 체크리스트 v2 의 T7(끼니) · T8(같은 곳 두 번) · T9(왔다 갔다). `[2026-10-03]`

★**거절하지 않는다.** 위반(`check_itinerary`)은 등록을 막지만 이것은 「살펴볼 점」으로 알리기만 한다 —
  같은 곳을 두 번 가는 일정도, 점심을 거르는 일정도 가능은 하다. 그래서 이 파일의 마지막 절은 **경고가 안 나와야 하는 경우**(잡음)를 고정한다.

재현:

    python -m pytest tests/unit/travel/test_itinerary_quality.py -v
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary_checks import Part, check_itinerary
from app.modules.travel_ops.itinerary_quality import quality_warnings

KST = ZoneInfo("Asia/Seoul")


def _at(hhmm: str, day: int = 23) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 9, day, int(hour), int(minute), tzinfo=KST)


def _place(name, *, lat=None, lon=None, place_id=None, address=None, **attributes):
    place = {"name": name, "place_id": place_id or name, "latitude": lat, "longitude": lon,
             "attributes": {**({"address": address} if address else {}), **attributes}}
    return place


def _part(seq, title, start, end=None, *, kind="activity", place=None, detail=None, day=23):
    return Part(seq=seq, kind=kind, title=title, starts_at=_at(start, day), ends_at=_at(end, day) if end else None,
                place=place, detail=detail)


def _codes(found):
    return sorted(w["code"] for w in found)


# ── T8 같은 곳 두 번 ────────────────────────────────────────────
def test_the_same_activity_twice_in_a_day_is_a_warning_with_both_items_named():
    found = quality_warnings([
        _part(1, "경복궁", "10:00", "11:30", place=_place("경복궁", lat=37.5796, lon=126.9770, place_id="a")),
        _part(2, "점심", "12:00", "13:00", kind="dining", place=_place("식당", lat=37.58, lon=126.98)),
        _part(3, "경복궁 다시", "15:00", "16:00", place=_place("경복궁", lat=37.5796, lon=126.9770, place_id="b")),
    ])
    twice = [w for w in found if w["code"] == "same_place_twice"]
    assert len(twice) == 1 and twice[0]["items"] == [1, 3] and twice[0]["date"] == "2026-09-23"
    assert "같은 곳" in twice[0]["reason"] and twice[0]["remedy"]


def test_a_place_inside_another_is_the_same_place_by_the_generators_own_rule():
    """경복궁 · 건청궁(경복궁 안) — 좌표가 약 10m. 생성기가 한 곳으로 치는 규칙(`same_site`)을 그대로 쓴다."""
    found = quality_warnings([
        _part(1, "경복궁", "10:00", "11:00", place=_place("경복궁", lat=37.5796, lon=126.9770, place_id="a")),
        _part(2, "건청궁", "11:30", "12:00", place=_place("경복궁 건청궁", lat=37.5800, lon=126.9771, place_id="b")),
    ])
    assert _codes(found) == ["same_place_twice"]


def test_two_restaurants_in_the_same_building_are_not_the_same_place():
    """식당은 같은 건물에 다른 가게가 흔하다 — 거리로 가르지 않는다(같은 장소 id · 원장 id · 이름만)."""
    found = quality_warnings([
        _part(1, "점심", "12:00", "13:00", kind="dining", place=_place("가게 A", lat=37.5, lon=127.0, place_id="a")),
        _part(2, "저녁", "18:00", "19:00", kind="dining", place=_place("가게 B", lat=37.5, lon=127.0, place_id="b")),
    ])
    assert "same_place_twice" not in _codes(found)


def test_the_same_restaurant_twice_in_a_day_is_a_warning():
    found = quality_warnings([
        _part(1, "점심", "12:00", "13:00", kind="dining", place=_place("가게 A", place_id="a")),
        _part(2, "저녁", "18:00", "19:00", kind="dining", place=_place("가게 A", place_id="a")),
    ])
    assert "same_place_twice" in _codes(found)


def test_the_same_place_on_different_days_is_not_a_warning():
    """단위는 하루다(체크리스트 T8) — 다른 날 다시 가는 것은 이 경고의 몫이 아니다."""
    found = quality_warnings([
        _part(1, "경복궁", "10:00", "11:00", place=_place("경복궁", lat=37.5796, lon=126.9770, place_id="a"), day=23),
        _part(2, "경복궁", "10:00", "11:00", place=_place("경복궁", lat=37.5796, lon=126.9770, place_id="a"), day=24),
    ])
    assert "same_place_twice" not in _codes(found)


def test_a_move_item_never_counts_as_a_place():
    found = quality_warnings([
        _part(1, "경복궁", "10:00", "11:00", place=_place("경복궁", lat=37.5796, lon=126.9770, place_id="a")),
        _part(2, "이동", "11:00", "11:20", kind="mobility"),
        _part(3, "이동", "11:20", "11:40", kind="mobility"),
    ])
    assert found == []


# ── T7 끼니 ──────────────────────────────────────────────────
def _day(*spec, kind="activity"):
    return [_part(i, t, s, e, kind=kind, place=_place(t, place_id=t)) for i, (t, s, e) in enumerate(spec, 1)]


def test_a_day_that_covers_lunch_with_no_meal_is_warned_once_for_lunch():
    # ★`[2026-10-03 적대 검토]` 틈이 1시간 이상 있으면(궁 11:30 끝 · 박물관 13:30 시작) 먹을 시간은 있어 내지 않는다 — 시간대를 **채운** 일정만 알린다(틈 30분)
    found = quality_warnings(_day(("궁", "10:00", "12:00"), ("박물관", "12:30", "16:30")))
    missing = [w for w in found if w["code"] == "meal_missing"]
    assert len(missing) == 1 and "점심" in missing[0]["reason"] and "11:30~14:00" in missing[0]["reason"] and "30분" in missing[0]["reason"]
    assert missing[0]["items"] == [1, 2]            # 그 창과 겹치는 항목 — 창 안에서 끝나는 궁 · 창 안에서 시작하는 박물관


def test_dinner_is_checked_only_when_the_day_runs_through_the_dinner_window():
    short = quality_warnings(_day(("궁", "10:00", "11:30"), ("박물관", "13:30", "17:00")))
    assert all("저녁" not in w["reason"] for w in short)          # 17:00 에 끝나는 하루는 저녁 창(17:30~)을 안 덮는다
    long_day = quality_warnings([
        _part(1, "궁", "09:00", "10:30", place=_place("궁", place_id="a")),
        _part(2, "점심", "12:00", "13:00", kind="dining", place=_place("식당", place_id="b")),
        _part(3, "전망대", "18:00", "21:00", place=_place("전망대", place_id="c")),          # 저녁 창(17:30~20:30)을 틈 30분만 두고 채운다
    ])
    assert [w["reason"].split(" ")[0] for w in long_day if w["code"] == "meal_missing"] == ["저녁"]


def test_a_meal_overlapping_the_window_satisfies_it():
    found = quality_warnings([
        _part(1, "궁", "10:00", "11:00", place=_place("궁", place_id="a")),
        _part(2, "점심", "11:00", "12:00", kind="dining", place=_place("식당", place_id="b")),   # 12:00 에 끝나 창(11:30~)과 겹친다
        _part(3, "박물관", "14:30", "16:00", place=_place("박물관", place_id="c")),
    ])
    assert "meal_missing" not in _codes(found)


def test_a_partial_day_is_not_checked_for_meals():
    """늦게 도착(13:00 시작) · 일찍 끝남 · 항목 하나 — 하루가 창을 통째로 덮지 않으면 끼니를 안 본다(잡음)."""
    assert quality_warnings(_day(("박물관", "13:00", "15:00"), ("시장", "15:30", "17:00"))) == []
    assert quality_warnings(_day(("궁", "10:00", "12:30"))) == []


# ── T9 왔다 갔다 ─────────────────────────────────────────────
def _line(*order):
    """남북으로 늘어선 네 곳(약 2.2km 간격)을 order 순서로 도는 하루."""
    spots = {"A": 37.50, "B": 37.52, "C": 37.54, "D": 37.56}
    return [_part(i, name, f"{9 + i}:00", f"{9 + i}:40", place=_place(name, lat=spots[name], lon=127.0, place_id=name))
            for i, name in enumerate(order, 1)]


def test_a_day_that_crosses_the_map_back_and_forth_is_warned_with_a_better_order():
    found = quality_warnings(_line("A", "D", "B", "C"))
    zigzag = [w for w in found if w["code"] == "route_zigzag"]
    assert len(zigzag) == 1
    assert zigzag[0]["better_order"] in ([1, 3, 4, 2], [2, 4, 3, 1])     # A-B-C-D 의 순서(또는 그 반대)
    assert "13.3km" in zigzag[0]["reason"] and "6.7km" in zigzag[0]["reason"]


def test_a_day_in_geographic_order_is_not_a_zigzag():
    assert "route_zigzag" not in _codes(quality_warnings(_line("A", "B", "C", "D")))
    assert "route_zigzag" not in _codes(quality_warnings(_line("D", "C", "B", "A")))


def test_two_stops_cannot_zigzag_and_stops_without_coordinates_are_left_out():
    assert "route_zigzag" not in _codes(quality_warnings(_line("A", "D")))
    parts = _line("A", "D", "B", "C")
    no_coords = [Part(seq=p.seq, kind=p.kind, title=p.title, starts_at=p.starts_at, ends_at=p.ends_at,
                      place={"name": p.title, "place_id": p.title, "attributes": {}}) if p.seq in (2, 3) else p for p in parts]
    assert "route_zigzag" not in _codes(quality_warnings(no_coords))     # 좌표 있는 곳이 둘뿐이라 못 잰다 — 지어내지 않는다


def test_when_two_stops_are_fixed_by_a_booking_the_order_is_not_ours_to_change():
    parts = _line("A", "D", "B", "C")
    fixed = [Part(seq=p.seq, kind=p.kind, title=p.title, starts_at=p.starts_at, ends_at=p.ends_at, place=p.place,
                  detail={"booking": "K123"} if p.seq in (2, 3) else None) for p in parts]
    assert "route_zigzag" not in _codes(quality_warnings(fixed))
    one_fixed = [Part(seq=p.seq, kind=p.kind, title=p.title, starts_at=p.starts_at, ends_at=p.ends_at, place=p.place,
                      detail={"booking": "K123"} if p.seq == 2 else None) for p in parts]
    assert "route_zigzag" in _codes(quality_warnings(one_fixed))          # 하나만 고정이면 나머지 순서는 바꿀 수 있다


def test_meals_do_not_count_toward_the_zigzag():
    """끼니 시각이 순서를 정하는 일이 흔하다 — 식사를 빼고 활동만으로 길이를 잰다."""
    parts = _line("A", "B", "C")
    lunch = _part(9, "점심", "12:30", "13:30", kind="dining", place=_place("먼 식당", lat=37.9, lon=127.0, place_id="far"))
    assert "route_zigzag" not in _codes(quality_warnings([*parts[:1], lunch, *parts[1:]]))


# ── 거절이 아니다 · 모양 ─────────────────────────────────────
# invariant: INV-CS-ACT-008
def test_a_day_with_every_warning_is_still_accepted_by_the_registration_judge():
    """같은 곳 두 번 · 점심 없음 · 왔다 갔다가 한꺼번에 있어도 **위반은 없다** — 등록은 받는다. 알리기만 한다."""
    parts = [_part(1, "A", "09:00", "09:40", place=_place("A", lat=37.50, lon=127.0, place_id="A")),
             _part(2, "D", "10:00", "10:40", place=_place("D", lat=37.56, lon=127.0, place_id="D")),
             _part(3, "B", "11:00", "13:30", place=_place("B", lat=37.52, lon=127.0, place_id="B")),          # 점심 창(11:30~14:00)을 틈 10분만 두고 채운다
             _part(4, "C", "13:40", "14:10", place=_place("C", lat=37.54, lon=127.0, place_id="C")),
             _part(5, "A 다시", "17:40", "20:40", place=_place("A", lat=37.50, lon=127.0, place_id="A"))]     # 저녁 창(17:30~20:30)도 틈 10분
    assert check_itinerary(parts) == []
    assert _codes(quality_warnings(parts)) == ["meal_missing", "meal_missing", "route_zigzag", "same_place_twice"]


def test_every_warning_has_the_shape_the_trip_screen_reads():
    """화면 「살펴볼 점」이 읽는 칸 — `code` · `date` · `reason` · `remedy`(밀도 경고와 같다) + 가리키는 항목 `items`."""
    parts = _line("A", "D", "B", "C")
    for warning in quality_warnings(parts):
        assert {"code", "date", "reason", "remedy", "items"} <= set(warning)
        assert warning["reason"] and warning["remedy"] and warning["date"] == "2026-09-23"
