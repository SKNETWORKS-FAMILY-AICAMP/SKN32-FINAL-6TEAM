# -*- coding: utf-8 -*-
"""확인 화면의 **경로 후보** — 먼저 3개, 목록을 내리면 더 · 고른 경로 다시 세기. 2026-10-23 사용자 지시
(「후보 3개는 먼저 같이 올리고, 선택하고 스크롤을 내리면 더 로딩해서 던져주게」).

· 검사는 구간마다 경로 후보 앞의 3개를 싣는다(`moves[].routes` — 쓰는 경로가 맨 앞 · 같은 계산이라 지연 없음).
· 「조금 일찍 떠나면 닿는」 경로(계산기 `more_options`)도 후보다 — 앞 일정이 끝나기 전에 떠나야 하면 뺀다.
· 고른 경로(`prefer`)는 그 경로의 출발 · 소요로 싣고, 없으면 계산기가 고른 것으로 간다.
· 더 보기(`move_options.routes`)는 검사가 보인 후보 다음부터 `offset` · `limit` 만큼 준다.

DB 없이 도는 시험이다. 이 파일의 이동 계산기는 시험용 mock 계산기다(실제 계산기가 아니다).

재현:

    python -m pytest tests/unit/intake/test_intake_route_candidates_v1.py -v
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.intake import move_options, moves, review

KST = ZoneInfo("Asia/Seoul")
A = {"key": "a", "name": "경복궁", "lat": 37.5796, "lon": 126.9770}
B = {"key": "b", "name": "홍대입구역", "lat": 37.5572, "lon": 126.9254}


def at(hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime(2026, 10, 23, int(h), int(m), tzinfo=KST)


SUB = {"id": "subway_1", "label": "3호선 경복궁→을지로3가 → 2호선 을지로3가→홍대입구", "eta_min": 36, "walk_m": 900, "fare_krw": 1550,
       "uses": ["3호선:경복궁", "2호선:을지로3가"]}
BUS = {"id": "bus_1", "label": "버스 7016", "eta_min": 40, "walk_m": 500, "fare_krw": 1500, "uses": ["버스:7016"]}
EARLY = {"id": "bus_subway_1", "label": "버스 종로11 → 2호선 시청→홍대입구", "eta_min": 38, "walk_m": 700, "fare_krw": 1650,
         "uses": ["버스:종로11", "2호선:시청", "2호선:홍대입구"], "starts_at": at("14:01").isoformat()}
TOO_EARLY = {"id": "subway_2", "label": "3호선 → 4호선 → 2호선", "eta_min": 43, "walk_m": 800, "fare_krw": 1550,
             "uses": ["3호선:경복궁", "4호선:충무로", "2호선:동대문역사문화공원"], "starts_at": at("13:20").isoformat()}


def engine(*more):
    got = {"route": {"planned": "subway_1", "options": [BUS, SUB]}, "starts_at": at("14:03"), "ends_at": at("14:39"), "eta_min": 36,
           "left_out": [{"code": "mix_cap", "label": "그 밖 혼합 후보 3개"}], "more_options": list(more)}
    return lambda *a: (got, None)


def test_rows_put_the_calculators_route_first_then_quicker_ones_and_drop_routes_leaving_before_the_stop_ends():
    leg = moves.leg_between(engine(EARLY, TOO_EARLY), A, B, at("13:30"), at("15:00"))
    keys = [r["key"] for r in leg.routes]
    assert keys[0] == moves.route_key(SUB) and leg.route_key == keys[0]
    assert keys[1:] == [moves.route_key(EARLY), moves.route_key(BUS)]          # 38분 다음 40분 · 13:20 출발은 앞 일정(13:30) 전이라 없다
    early = leg.routes[1]
    assert early["early"] is True and early["depart"] == "14:01" and early["arrive"] == "14:39" and early["slack_min"] == 21
    assert early["lines"] == ["버스 종로11", "2호선"] and early["transfers"] == 1
    assert leg.routes[0]["planned"] is True and leg.routes[0]["early"] is False and leg.routes_capped is True


def test_the_route_key_does_not_depend_on_the_calculators_id():
    assert moves.route_key({**SUB, "id": "subway_7"}) == moves.route_key(SUB) == "u:3호선:경복궁>2호선:을지로3가"
    assert moves.route_key({"id": "walk", "uses": []}) == "walk" and moves.route_key({"id": "taxi", "uses": []}) == "taxi"


def test_a_picked_early_route_leaves_at_its_own_time_and_keeps_its_timetable_context():
    context = {"schema_version": 1, "start_min": 843, "options": {
        "subway_1": {"option_id": "subway_1", "start_min": 843}, "bus_subway_1": {"option_id": "bus_subway_1", "start_min": 841}}}
    got = {"route": {"planned": "subway_1", "options": [SUB]}, "starts_at": at("14:03"), "ends_at": at("14:39"), "eta_min": 36,
           "more_options": [EARLY], "departure_context": context}
    leg = moves.leg_between(lambda *a: (got, None), A, B, at("13:30"), at("15:00"), prefer=moves.route_key(EARLY))
    assert leg.route_key == moves.route_key(EARLY) and leg.verified
    assert (leg.depart, leg.arrive, leg.minutes) == (at("14:01"), at("14:39"), 38)
    assert leg.selected_option_id == "bus_subway_1" and leg.departure_context["start_min"] == 841
    assert list(leg.departure_context["options"]) == ["bus_subway_1"]


def test_a_picked_route_that_is_not_there_falls_back_to_the_calculators():
    leg = moves.leg_between(engine(), A, B, at("13:30"), at("15:00"), prefer="u:없는:경로")
    assert leg.route_key == moves.route_key(SUB) and leg.minutes == 36


def test_the_check_carries_the_first_three_with_the_used_route_first():
    leg = moves.leg_between(engine(EARLY), A, B, at("13:30"), at("15:00"), prefer=moves.route_key(BUS))
    fields = review.route_fields(leg)
    assert [r["key"] for r in fields["routes"]] == [moves.route_key(BUS), moves.route_key(SUB), moves.route_key(EARLY)]
    assert fields["route_key"] == moves.route_key(BUS) and fields["routes_total"] == 3 and fields["routes_more"] is True


def test_an_estimate_leg_has_no_routes():
    fields = review.route_fields(moves.leg_between(None, A, B, at("13:30"), at("15:00")))
    assert fields == {"route_key": None, "routes": [], "routes_total": 0, "routes_more": False}


def test_the_last_route_value_wins_and_an_empty_one_clears_it():
    claims = [{"field": "moves[0-0~0-1].route", "value": "u:a", "method": "customer"},
              {"field": "moves[0-1~0-2].route", "value": "u:b", "method": "customer"},
              {"field": "moves[0-1~0-2].route", "value": None, "method": "customer"},
              {"field": "moves[0-2~0-3].route", "value": "u:c", "method": "llm_agent"}]
    assert review.picked_routes(claims) == {"0-0~0-1": "u:a"}


def _found():
    a = {"id": "0-0", "date": "2026-10-23", "starts_at": "12:00", "ends_at": "13:30",
         "place": {"name": A["name"], "latitude": A["lat"], "longitude": A["lon"]}}
    b = {"id": "0-1", "date": "2026-10-23", "starts_at": "15:00", "ends_at": "16:00",
         "place": {"name": B["name"], "latitude": B["lat"], "longitude": B["lon"]}}
    shown = moves.leg_between(engine(), A, B, at("13:30"), at("15:00"))
    move = {"from": "0-0", "to": "0-1", "status": "keep", **review.route_fields(shown)}
    return {"revision": 4, "items": [a, b], "moves": [move]}


def test_more_routes_start_after_the_ones_the_check_showed_and_page_by_offset():
    found = _found()
    wide = engine(EARLY, {**BUS, "id": "bus_2", "uses": ["버스:272"], "eta_min": 45, "starts_at": at("13:58").isoformat()})
    first = move_options.routes(found, "0-0", "0-1", offset=2, limit=1, engine=wide)
    assert [r["key"] for r in first["routes"]] == [moves.route_key(EARLY)]             # 검사의 2개 다음 = 넓게 센 새 후보 중 빠른 것
    assert first["next_offset"] == 3 and first["has_more"] is True and first["total"] == 4
    rest = move_options.routes(found, "0-0", "0-1", offset=3, limit=5, engine=wide)
    assert [r["key"] for r in rest["routes"]] == ["u:버스:272"] and rest["has_more"] is False


def test_more_routes_say_why_when_the_calculator_had_no_timetable_answer():
    got = move_options.routes(_found(), "0-0", "0-1", offset=3, engine=lambda *a: (None, {"code": "no_data"}))
    assert got["routes"] == [] and got["has_more"] is False and got["why"]


def test_a_route_picked_or_undone_in_this_intake_counts_as_a_changed_leg():
    claims = [{"field": "moves[0-0~0-1].route", "value": "u:a", "method": "customer"},
              {"field": "moves[0-1~0-2].route", "value": None, "method": "customer"},
              {"field": "moves[0-2~0-3].mode", "value": "bus", "method": "trip"},
              {"field": "moves[0-3~0-4].mode", "value": "taxi", "method": "customer"}]
    assert review.customer_mode_pairs(claims) == {"0-0~0-1", "0-1~0-2", "0-3~0-4"}
