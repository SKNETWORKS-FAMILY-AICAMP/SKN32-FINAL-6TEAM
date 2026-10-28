# -*- coding: utf-8 -*-
"""여행 「살펴볼 점」 경고(`trip.warnings` — 밀도 · 품질)와 일정 짜기 거절 `remedy`, 식당 영업 판정 이유의 고객 문장. `[2026-10-28]`

웹 `trip-attention.tsx` 는 `warnings[].reason` · `warnings[].remedy` 를 그대로 그린다. 전에는 이 문장이
반말 평서형(「…같은 곳이다」 「…순서를 바꾼다」)이거나 합니다체 · 내부 말(「연구 보정 프리셋」 「완충시간」 「대기 주석」)이었고,
내부 순번(「항목 3: 시작 시간대 누락」)과 띄어 쓴 조사(「경복궁 와 경복궁 다시 은(는)」 「13.3km 인데」)가 보였다.

고객 문장 규칙(거절 문장 `test_refusal_customer_wording.py` 와 같다): 해요체로 끝난다 · 숫자 · 단위 뒤 조사는 붙여 쓴다 ·
받침에 맞는 조사(`itinerary_checks.particle`) · 내부 자료 이름과 항목 순번을 문장에 넣지 않는다(공개 필드 `items` 는 그대로 둔다).
"""
from __future__ import annotations

import ast
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.itinerary.density import measure_density
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part
from app.domains.travel_ops.components.itinerary.itinerary_quality import quality_warnings
from app.domains.travel_ops.components.planning import planner as planner_module
from app.domains.travel_ops.components.planning.replan import dining_fits

KST = ZoneInfo("Asia/Seoul")
#: 해요체 끝 — 끝에 근거 괄호가 붙을 수 있다
POLITE = re.compile(r"요[.!?]?(\s*\([^)]*\))?$")
#: 숫자 · 단위 뒤에 띄어 쓴 조사 — 「19:00 까지」 「13.3km 인데」 「30분 뿐」
SPACED_PARTICLE = re.compile(r"(\d|km|m|분)\s+(에|에는|까지|부터|이|가|을|를|은|는|으로|로|만|뿐|인데)(?=[\s,.·)]|$)")
#: 겸용 조사 · 한글 뒤에 띄어 쓴 조사 — 「경복궁 와」 「경복궁 다시 은(는)」
#: 영문으로 끝나는 이름 뒤의 겸용 조사(「COEX은(는)」)는 읽는 소리를 몰라 허용한다(`particle` 약속)
MIXED_PARTICLE = re.compile(r"[가-힣](은\(는\)|을\(를\)|이\(가\)|과\(와\))|[가-힣]\s(를|와|과)\s")
BANMAL_END = re.compile(r"(는다|한다|이다|있다|없다|된다|걸린다|넘는다|채운다|바꾼다|줄인다|둔다|앞당긴다|확인한다|받는다|촉박하다)[.)]?$")
#: 내부 자료 · 계산 이름과 항목 순번
INTERNAL = re.compile(r"원장|프리셋|카탈로그|TourAPI|완충|주석|연구 보정|이동 계산기|항목 \d|비이동|가용시간")


def _sentences(text: str) -> list[str]:
    """「 / 」로 이은 이유와 「요. 」로 이은 두 문장을 한 문장씩."""
    return [piece.strip() for piece in re.split(r" / |(?<=요)\.\s+", text) if piece.strip()]


def _assert_customer(text: str) -> None:
    assert text, "빈 문장"
    assert not SPACED_PARTICLE.search(text), text
    assert not MIXED_PARTICLE.search(text), text
    assert not INTERNAL.search(text), text
    for sentence in _sentences(text):
        assert POLITE.search(sentence), sentence
        assert not BANMAL_END.search(sentence), sentence


def _at(hhmm: str, day: int = 23) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime(2026, 9, day, int(hour), int(minute), tzinfo=KST)


def _place(name, *, lat=37.5, lon=127.0, place_id=None, **attributes):
    return {"name": name, "place_id": place_id or name, "latitude": lat, "longitude": lon, "attributes": dict(attributes)}


def _part(seq, title, start, end=None, *, kind="activity", place=None, detail=None, route=None, day=23):
    return Part(seq=seq, kind=kind, title=title, starts_at=_at(start, day), ends_at=_at(end, day) if end else None,
                place=place, route=route, detail=detail)


PLANNED = {"planner": {"day": "2026-09-23"}}
LAST_ORDER_21 = {"hours_week": {"wed": {"open": "11:00", "close": "22:00", "last_entry": "21:00"}}}
BREAK_WITH_LAST_ORDER = {"hours": ["11:00", "22:00"], "break": ["15:00", "17:00"], "last_order_before_break_min": 30}


def _every_quality_warning():
    found = []
    found += quality_warnings([                                                     # same_place_twice(받침 · 받침 없음)
        _part(1, "남산", "10:00", "11:00", place=_place("남산", place_id="a")),
        _part(2, "남산 다시", "15:00", "16:00", place=_place("남산", place_id="a"))])
    found += quality_warnings([                                                     # meal_missing
        _part(1, "궁", "10:00", "12:00", place=_place("궁")), _part(2, "박물관", "12:30", "16:30", place=_place("박물관"))])
    spots = {"A": 37.50, "B": 37.52, "C": 37.54, "D": 37.56}                        # route_zigzag
    found += quality_warnings([_part(i, name, f"{9 + i}:00", f"{9 + i}:40", place=_place(name, lat=spots[name], place_id=name))
                               for i, name in enumerate("ADBC", 1)])
    found += quality_warnings([_part(1, "궁", "18:00", "19:00", detail=PLANNED, place=_place("궁")),   # past_day_end
                               _part(2, "야경 투어", "21:00", "23:00", detail=PLANNED, place=_place("야경"))])
    found += quality_warnings([_part(1, "한식당", "20:50", "21:40", kind="dining", place=_place("한식당", **LAST_ORDER_21))])
    found += quality_warnings([_part(1, "중식당", "14:20", "14:50", kind="dining", place=_place("중식당", **BREAK_WITH_LAST_ORDER))])
    found += quality_warnings([_part(1, "분식", "20:30", "21:30", kind="dining", place=_place("분식", hours=["11:00", "22:00"]))])
    found += quality_warnings([_part(1, "국밥", "13:30", "14:30", kind="dining", place=_place("국밥", hours=["11:00", "22:00"], **{"break": ["15:00", "17:00"]}))])
    return found


def test_every_quality_warning_on_the_trip_screen_reads_as_a_customer_sentence():
    found = _every_quality_warning()
    codes = {w["code"] for w in found}
    assert {"same_place_twice", "meal_missing", "route_zigzag", "past_day_end", "last_order_tight", "last_order_unknown"} <= codes, codes
    assert sum(w["code"] == "last_order_tight" for w in found) == 2          # 영업 종료 앞 · 브레이크 앞 둘 다
    for warning in found:
        _assert_customer(warning["reason"])
        _assert_customer(warning["remedy"])


def test_the_same_place_sentence_picks_the_particles_by_the_last_syllable():
    found = quality_warnings([_part(1, "남산", "10:00", "11:00", place=_place("남산", place_id="a")),
                              _part(2, "남산 다시", "15:00", "16:00", place=_place("남산", place_id="a"))])
    [warning] = [w for w in found if w["code"] == "same_place_twice"]
    assert warning["reason"].startswith("남산과 남산 다시는 같은 곳이에요")
    assert warning["items"] == [1, 2]                                         # 공개 필드는 그대로
    found = quality_warnings([_part(1, "N서울타워", "10:00", "11:00", place=_place("타워", place_id="t")),
                              _part(2, "서울타워", "15:00", "16:00", place=_place("타워", place_id="t"))])
    [warning] = [w for w in found if w["code"] == "same_place_twice"]
    assert warning["reason"].startswith("N서울타워와 서울타워는 같은 곳이에요")
    found = quality_warnings([_part(1, "Starfield", "10:00", "11:00", place=_place("몰", place_id="m")),
                              _part(2, "COEX", "15:00", "16:00", place=_place("몰", place_id="m"))])
    [warning] = [w for w in found if w["code"] == "same_place_twice"]
    assert warning["reason"].startswith("Starfield과(와) COEX은(는) 같은 곳이에요")      # 영문 끝 — 겸용 표기
    _assert_customer(warning["reason"])


def test_the_zigzag_sentence_keeps_the_distances_and_joins_the_particle():
    spots = {"A": 37.50, "B": 37.52, "C": 37.54, "D": 37.56}
    found = quality_warnings([_part(i, name, f"{9 + i}:00", f"{9 + i}:40", place=_place(name, lat=spots[name], place_id=name))
                              for i, name in enumerate("ADBC", 1)])
    [zigzag] = [w for w in found if w["code"] == "route_zigzag"]
    assert "약 13.3km인데" in zigzag["reason"] and "약 6.7km로" in zigzag["reason"]


# ── 밀도 ─────────────────────────────────────────────────────
def _window(**extra):
    return {"starts_at": _at("10:00").isoformat(), "ends_at": _at("22:00").isoformat(), "buffer_minutes": 0, **extra}


def _density(items, **spec):
    return measure_density(items, {"density": {"days": {"2026-09-23": _window()}, **(spec or {"level": "normal"})}})


@pytest.mark.parametrize("spec", [{"level": "normal"}, {"target_density": 0.3}])
def test_a_day_over_the_chosen_pace_says_so_in_customer_words(spec):
    [warning] = _density([_part(1, "궁", "10:00", "18:00")], **spec)["warnings"]
    assert warning["code"] == "density_exceeded"
    _assert_customer(warning["reason"])
    _assert_customer(warning["remedy"])


@pytest.mark.parametrize("items, name", [
    ([Part(1, "activity", "궁", datetime(2026, 9, 23, 10, 0), None)], "궁"),                        # 시간대 없음
    ([_part(1, "궁", "10:00", "11:00", day=24)], "궁"),                                            # 하루 시간 창 밖
    ([_part(1, "박물관", "10:00", None)], "박물관"),                                                 # 끝 시각 없음
    ([_part(1, "박물관", "10:00", "11:00", detail={"queue_minutes": 90})], "박물관"),                # 대기 시간 값이 소요보다 길다
    ([_part(1, "지하철", "10:00", "10:10", kind="mobility", route={"planned": "s", "options": [{"id": "s", "eta_min": 20}]})], "지하철"),
    ([_part(1, "궁", "10:00", "12:00"), _part(2, "시장", "11:00", "13:00")], "궁과 시장"),           # 겹침
    ([_part(1, "궁", "10:00", "12:00", place=_place("궁")), _part(2, "시장", "12:00", "13:00", place=_place("시장"))], "궁에서 시장으로"),
    ([_part(1, "궁", "10:00", "12:00", place=_place("궁")), _part(2, "서울숲", "12:00", "13:00", place=_place("숲"))], "궁에서 서울숲으로"),
    ([_part(1, "궁", "10:00", "12:00", place=_place("궁")), _part(2, "명동길", "12:00", "13:00", place=_place("길"))], "궁에서 명동길로"),   # ㄹ 받침
])
def test_an_unmeasurable_day_names_the_stop_not_its_internal_number(items, name):
    [warning] = _density(items)["warnings"]
    assert warning["code"] == "density_unmeasurable"
    assert name in warning["reason"], warning["reason"]
    _assert_customer(warning["reason"])
    _assert_customer(warning["remedy"])


@pytest.mark.parametrize("days, said", [
    ({"2026-09-23": {"starts_at": "not a time"}}, "읽지 못했어요"),                                   # 형식 오류
    ({"2026-09-23": _window(starts_at=_at("10:00", 24).isoformat(), ends_at=_at("12:00", 24).isoformat())}, "날짜나 길이"),
    ({"2026-09-23": _window(ends_at=_at("01:00", 24).isoformat()),                                    # 날짜 · 길이는 맞고 서로 겹친다
      "2026-09-24": {"starts_at": _at("00:30", 24).isoformat(), "ends_at": _at("10:00", 24).isoformat(), "buffer_minutes": 0}}, "겹쳐요"),
])
def test_an_unreadable_pace_setting_is_said_in_customer_words(days, said):
    [warning] = measure_density([], {"density": {"level": "normal", "days": days}})["warnings"]
    assert warning["code"] == "density_unmeasurable" and said in warning["reason"], warning["reason"]
    _assert_customer(warning["reason"])


# ── 일정 짜기 거절(`PlanRefused`)의 remedy ────────────────────────
def _planner_remedies() -> list[str]:
    tree = ast.parse(Path(planner_module.__file__).read_text(encoding="utf-8"))
    return [kw.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
            for kw in node.keywords if kw.arg == "remedy" and isinstance(kw.value, ast.Constant)]


def test_every_planner_remedy_is_a_customer_sentence():
    remedies = _planner_remedies()
    assert len(remedies) >= 5
    for remedy in remedies:
        _assert_customer(remedy)


# ── 식당 영업 판정 이유(대체 후보 「살펴본 곳」 · 확인 필요 안내 `warnings`) ─────
@pytest.mark.parametrize("place, start, minutes, state", [
    ({"name": "x", "attributes": {}}, "12:00", 60, None),                                               # 영업시간 모름
    ({"name": "x", "attributes": {"hours": ["17:00", "22:00"]}}, "12:00", 60, None),                      # 영업 안 함
    ({"name": "x", "attributes": {"hours": ["11:00", "22:00"], "break": ["15:00", "17:00"]}}, "14:30", 60, None),
    ({"name": "x", "attributes": LAST_ORDER_21}, "20:50", 40, None),                                     # 영업 종료 앞 라스트오더
    ({"name": "x", "attributes": BREAK_WITH_LAST_ORDER}, "14:20", 30, None),                              # 브레이크 앞 라스트오더
    ({"name": "x", "attributes": {}}, "12:00", 60, {"linked": True, "open_at_slot": True, "order_ok": False}),
    ({"name": "x", "attributes": {}}, "12:00", 60, {"linked": True, "open_at_slot": None}),
    ({"name": "x", "attributes": {}}, "12:00", 60, {"linked": True, "open_at_slot": False}),
])
def test_every_dining_fit_reason_is_a_customer_sentence(place, start, minutes, state):
    fits, why = dining_fits(place, _at(start), minutes, state=state)
    assert fits is not True
    _assert_customer(why)
