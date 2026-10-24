# -*- coding: utf-8 -*-
"""계획 읽기가 읽은 성향 · 조건이 담당 열쇠로 가나 — `intake/reading_prefs.py`. `[2026-10-16 D-025 후속]`

☆왜: 이해 에이전트가 「웬만하면 택시」 · 「천천히」 · 「맛집 위주」 · 「비 오면 실내」 · 「9시까지 숙소」를 읽어도 그 값은 `reading.agent` 값 줄에만 있었고,
  이동 판정 · 일정 짜기 · 식당 고르기 · 활동 대안이 읽는 설문 열쇠는 아무도 채우지 않았다.

★지키려는 것: ①읽은 코드마다 정해진 열쇠로 간다 ②고객이 직접 답한 값은 덮지 않는다 ③채운 것은 「우리가 채움」으로 남고 「직접 답한 문항」이 아니다
  ④담당이 실제로 그 값을 읽는다(이동 수단 · 식당 취향 문장 · 피로 · 하루 마감 · 하루 창) ⑤그림자 · 실패한 읽기는 넘기지 않는다.

재현:

    python -m pytest tests/unit/travel/test_intake_reading_prefs.py -v
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.intake import reading_prefs
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part
from app.domains.travel_ops.components.itinerary.itinerary_quality import quality_warnings
from app.domains.travel_ops.components.planning import meal_pick, planner
from app.domains.travel_ops.components.planning.survey import TripSurvey, apply_survey
from app.domains.travel_ops.instances.activity.alternative_order import preference_inputs
from app.domains.travel_ops.instances.mobility.engine.plan import party_of
from app.domains.travel_ops.instances.mobility.wiring import modes_from_survey

KST = ZoneInfo("Asia/Seoul")
DAY = date(2026, 10, 20)


def _agent(*, preferences=(), conditions=(), moves=(), used=True):
    return {"field": "reading.agent", "value": {"preferences": [{"code": c, "quote": q} for c, q in preferences],
                                                "conditions": [{"code": c, "quote": q} for c, q in conditions],
                                                "moves": list(moves), "used": used}}


def _keys(items):
    return {item["key"]: item["value"] for item in items}


# ── 읽은 코드 → 열쇠 ─────────────────────────────────────────────
def test_every_read_code_goes_to_the_key_its_owner_reads():
    got = _keys(reading_prefs.carry([_agent(
        preferences=[("prefer_taxi", "웬만하면 택시"), ("slow_pace", "천천히요"), ("food_focus", "먹는 게 제일 중요"),
                     ("elderly_friendly", "부모님 모시고")],
        conditions=[("if_rain_indoor", "비 오면 실내로"), ("finish_by:21:00", "9시까지는 숙소")])]))
    assert got["survey.priority_details.mobility"] == ["taxi"]
    assert got["survey.pace"] == "relaxed"
    assert got["survey.indoor_outdoor.activity"] == "indoor"
    assert got["constraints.mobility_ease"] == "needs_rest"
    assert got["constraints.day_hours.end"] == "21:00"
    assert "먹는 게 제일 중요" in got["constraints.meal_preference"]          # 원문 조각을 그대로 싣는다


def test_whole_trip_transport_joins_the_mobility_preference_but_a_segment_does_not():
    got = _keys(reading_prefs.carry([_agent(
        preferences=[("prefer_walking", "걷는 거 좋아해요")],
        moves=[{"mode": "subway", "scope": "all", "quote": "다 지하철로"},
               {"mode": "taxi", "scope": "segment", "quote": "택시로"}])]))
    assert got["survey.priority_details.mobility"] == ["walk", "subway"]


def test_a_shadow_or_failed_reading_is_not_handed_over():
    assert reading_prefs.carry([_agent(preferences=[("prefer_taxi", "택시")], used=False)]) == []
    assert reading_prefs.carry([{"field": "reading.agent", "value": {"error": "Timeout", "used": False}}]) == []


def test_a_start_after_the_end_is_not_guessed_either_way():
    got = _keys(reading_prefs.carry([_agent(conditions=[("start_after:22:00", "10시 이후"), ("finish_by:21:00", "9시까지")])]))
    assert "constraints.day_hours.start" not in got and "constraints.day_hours.end" not in got


def test_several_sources_are_merged_and_quotes_kept():
    items = reading_prefs.carry([_agent(preferences=[("prefer_taxi", "택시 위주")]),
                                 _agent(preferences=[("prefer_transit", "지하철도 괜찮아요"), ("prefer_taxi", "택시 위주")])])
    [mobility] = [i for i in items if i["key"] == "survey.priority_details.mobility"]
    assert mobility["value"] == ["taxi", "public"] and mobility["quotes"] == ["택시 위주", "지하철도 괜찮아요"]


# ── 고객 답이 먼저 · 「우리가 채움」 ──────────────────────────────
def _carried(**kw):
    return {reading_prefs.CARRY_KEY: reading_prefs.carry([_agent(**kw)])}


def test_reading_fills_only_empty_places_and_says_so():
    out = reading_prefs.apply({**_carried(preferences=[("prefer_taxi", "웬만하면 택시"), ("slow_pace", "천천히")]),
                               "survey": {"version": "2026-09-24.v1", "priority_details": {"mobility": ["public"]}}})
    assert out["survey"]["priority_details"]["mobility"] == ["public"]       # 고객이 고른 대중교통 그대로
    assert out["survey"]["pace"] == "relaxed"                                 # 고객이 안 답한 자리는 채운다
    assert [f["key"] for f in out[reading_prefs.FILLED_KEY]] == ["survey.pace"]
    assert out[reading_prefs.FILLED_KEY][0]["by"] == "reading" and out[reading_prefs.FILLED_KEY][0]["quotes"] == ["천천히"]
    assert reading_prefs.CARRY_KEY not in out


def test_a_key_already_in_the_body_is_not_overwritten():
    out = reading_prefs.apply({**_carried(preferences=[("food_focus", "맛집 위주")], conditions=[("finish_by:20:00", "8시까지")]),
                               "meal_preference": "매운 거 빼고", "day_hours": {"end": "22:00"}})
    assert out["meal_preference"] == "매운 거 빼고" and out["day_hours"] == {"end": "22:00"}
    assert reading_prefs.FILLED_KEY not in out


def test_without_a_survey_one_is_made_but_it_is_not_counted_as_answered():
    out = reading_prefs.apply(_carried(preferences=[("prefer_taxi", "택시로 다닐래요"), ("late_start", "아침엔 늦잠")]))
    TripSurvey.model_validate(out["survey"])                                  # 설문 계약 그대로
    done = apply_survey(out, [DAY])
    assert done["survey_answered"] == []                                       # 고객이 직접 답한 문항은 없다
    assert done["density"]["level"]                                            # 그래도 여유(relaxed)는 일정 밀도에 쓰인다


def test_customer_answers_stay_answered_next_to_our_fill():
    out = reading_prefs.apply({**_carried(preferences=[("slow_pace", "느긋하게")]),
                               "survey": {"version": "2026-09-24.v1", "on_disruption": "replace"}})
    assert apply_survey(out, [DAY])["survey_answered"] == ["on_disruption"]


def test_the_review_view_marks_customer_answers_first():
    items = reading_prefs.carry([_agent(preferences=[("prefer_taxi", "택시 위주"), ("slow_pace", "천천히")])])
    shown = {v["key"]: v for v in reading_prefs.view(items, survey={"priority_details": {"mobility": ["public"]}})}
    assert shown["survey.priority_details.mobility"]["status"] == "customer"
    assert shown["survey.pace"]["status"] == "filled" and shown["survey.pace"]["owner"] == "일정 짜기"
    assert shown["survey.pace"]["text"] == "여유 있게" and shown["survey.priority_details.mobility"]["text"] == "택시"


# ── 담당이 실제로 읽는다 ──────────────────────────────────────────
def test_mobility_judgement_reads_the_filled_transport():
    out = reading_prefs.apply(_carried(preferences=[("prefer_taxi", "웬만하면 택시")]))
    assert modes_from_survey(out) == ["taxi", "walk"]


def test_restaurant_picking_reads_the_filled_taste_sentence():
    out = reading_prefs.apply(_carried(preferences=[("nice_restaurants", "분위기 있는 곳")]))
    assert "분위기 있는 곳" in meal_pick.preference_of(out)


def test_walking_trouble_reaches_the_mobility_engine_as_fatigue():
    out = reading_prefs.apply(_carried(preferences=[("avoid_stairs", "계단은 힘들어요")]))
    assert party_of(2, out).get("fatigue_high") is True


def test_rain_indoor_reaches_activity_alternatives_with_the_customer_words():
    out = reading_prefs.apply(_carried(conditions=[("if_rain_indoor", "비 오면 실내 위주로")]))
    picked = preference_inputs(out["survey"], None)
    assert picked["survey"]["indoor_outdoor"] == {"activity": "indoor"}
    assert picked["survey"]["custom_answers"]["indoor_outdoor"] == "비 오면 실내 위주로"


def _part(seq, title, start, end):
    at = lambda hm: datetime(2026, 10, 20, int(hm[:2]), int(hm[3:]), tzinfo=KST)  # noqa: E731
    return Part(seq=seq, kind="activity", title=title, starts_at=at(start), ends_at=at(end),
                place={"name": title, "place_id": f"p{seq}", "latitude": 37.5, "longitude": 127.0, "attributes": {}})


def test_the_day_end_warning_uses_the_read_finish_time():
    out = reading_prefs.apply(_carried(conditions=[("finish_by:20:00", "8시까지는 들어가요")]))
    late = [w for w in quality_warnings([_part(1, "야시장", "19:00", "21:00")], out) if w["code"] == "past_day_end"]
    assert late and "20:00" in late[0]["reason"]
    assert not [w for w in quality_warnings([_part(1, "야시장", "19:00", "21:00")]) if w["code"] == "past_day_end"]


def test_the_planner_starts_and_ends_the_day_inside_the_read_hours():
    out = reading_prefs.apply(_carried(conditions=[("start_after:10:30", "10시 반 이후"), ("finish_by:20:00", "8시까지")]))
    first, last = planner.day_bounds(out)
    assert (first.isoformat(timespec="minutes"), last.isoformat(timespec="minutes")) == ("10:30", "20:00")
    act = planner.Cand(key="k1", name="활동", kind="activity", lat=37.57, lon=126.98, attributes={}, origin="places", rank_hint=0)
    items = planner.build_day(DAY, [act], [], seq_from=1, day_start=first)
    assert items[0]["starts_at"].time() >= first
    assert planner.day_bounds({}) == (planner.DAY_START, planner.DAY_END)
    morning = planner.Cand(key="k2", name="아침", kind="dining", lat=37.57, lon=126.98, attributes={}, origin="places", rank_hint=0)
    late = planner.build_day(DAY, [act], [], seq_from=1, breakfast=morning, day_start=first)
    plain = planner.build_day(DAY, [act], [], seq_from=1, breakfast=morning, day_start=planner.DAY_START)
    assert late[0]["starts_at"].time().isoformat(timespec="minutes") == "09:30"           # 첫 활동 한 시간 앞으로 함께 늦춘다
    assert plain[0]["starts_at"].time() == planner.BREAKFAST_AT                             # 기본은 팀 기본 08:00 그대로


def test_survey_density_window_follows_the_read_hours():
    out = reading_prefs.apply(_carried(preferences=[("slow_pace", "천천히")], conditions=[("finish_by:20:00", "8시까지")]))
    window = apply_survey(out, [DAY])["density"]["days"][DAY.isoformat()]
    assert window["ends_at"].endswith("20:00:00+09:00")
