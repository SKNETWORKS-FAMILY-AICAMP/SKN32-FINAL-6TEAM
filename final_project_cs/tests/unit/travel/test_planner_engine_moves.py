# -*- coding: utf-8 -*-
"""일정 짜기(planner.add_moves)가 이동 계산기로 이동을 채운다 — 이동 계산기 문제목록(2026-09-29) #27·#42·#43·#46.

가짜 구간 계산기로 갈래를 보고, 작은 가공 자료로 실제 계산기 한 번을 돈다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.travel_ops.mobility import wiring
from app.modules.travel_ops.planner import Cand, add_moves

KST = timezone(timedelta(hours=9))


def _cand(key, lat, lon):
    return Cand(key=key, name=key, kind="activity", lat=lat, lon=lon, attributes={}, origin="places")


PLACES = {"P1": _cand("P1", 37.5001, 127.0001), "P2": _cand("P2", 37.5201, 127.0001)}


def _items(b_start="11:00"):
    day = "2026-10-07"

    def at(hm):
        return datetime.fromisoformat(f"{day}T{hm}:00+09:00")
    return [{"seq": 1, "kind": "activity", "title": "첫", "place": "P1", "starts_at": at("09:00"), "ends_at": at("10:30"),
             "detail": {"planner": {"day": day}}},
            {"seq": 2, "kind": "activity", "title": "둘", "place": "P2", "starts_at": at(b_start), "ends_at": at("12:00"),
             "detail": {"planner": {"day": day}}}]


def _fake(result=None, why=None, late_then=None):
    calls = []

    def leg(a, b, arrive, not_before):
        calls.append((a["key"], b["key"], arrive, not_before))
        if late_then is not None:
            return late_then(arrive, not_before, len(calls))
        return (result(arrive) if result else None), why
    leg.calls = calls
    return leg


def test_27_engine_fills_the_move_with_timetable_route():
    route = {"from": "P1", "to": "P2", "planned": "subway_1",
             "options": [{"id": "subway_1", "label": "01호선 A→C", "eta_min": 9, "uses": ["01호선:A", "01호선:C"]}]}
    eng = _fake(lambda arrive: {"route": route, "starts_at": arrive - timedelta(minutes=19),
                                "ends_at": arrive - timedelta(minutes=10), "eta_min": 9, "left_out": []})
    out, routes, notes = add_moves(_items(), PLACES, engine=eng)
    move = next(it for it in out if it["kind"] == "mobility")
    assert routes[move["route"]]["options"][0]["uses"] == ["01호선:A", "01호선:C"], "탈 노선이 실린다 — 감시가 본다"
    assert move["detail"]["planner"]["transfer_basis"] == "시간표 판정(이동 계산기)" and notes == []


def test_27_unfilled_segment_falls_back_to_labelled_estimate_not_silence():
    eng = _fake(why={"code": "no_data", "reason": "도보 상한 안에 지하철역이 없다"})
    out, routes, notes = add_moves(_items(), PLACES, engine=eng)
    move = next(it for it in out if it["kind"] == "mobility")
    assert routes[move["route"]]["planned"] == "estimate", "대체값(직선 어림)은 추정으로 표시된다"
    assert any("이동 계산기로 못 채움" in n for n in notes), "못 채운 것을 민 내역에 남긴다"


def test_42_arrive_late_shifts_then_rejudges():
    def behave(arrive, not_before, n):
        if n == 1:
            return None, {"code": "arrive_late", "reason": "앞 일정 뒤 출발로는 늦다"}
        if n == 2:                                   # 앞 일정 끝을 푼 계산 — 10:20 에 떠나야 한다(앞 일정은 10:30 끝)
            return {"route": {}, "starts_at": arrive - timedelta(minutes=40), "ends_at": arrive, "eta_min": 30,
                    "left_out": []}, None
        return {"route": {"planned": "x", "options": [{"id": "x", "eta_min": 30, "uses": []}]},
                "starts_at": arrive - timedelta(minutes=40), "ends_at": arrive - timedelta(minutes=10),
                "eta_min": 30, "left_out": []}, None
    eng = _fake(late_then=behave)
    items = _items(b_start="11:00")
    out, _routes, notes = add_moves(items, PLACES, engine=eng)
    second = next(it for it in out if it["title"] == "둘")
    assert second["starts_at"].strftime("%H:%M") == "11:10", "모자란 10분만큼 민다"
    assert len(eng.calls) == 3 and eng.calls[2][2].strftime("%H:%M") == "11:10", "민 시각으로 다시 판정한다"
    assert any("다시 판정했다" in n for n in notes)


def test_46_survey_mobility_preference_becomes_engine_modes():
    assert wiring.modes_from_survey({"survey": {"priority_details": {"mobility": ["public"]}}}) == ["bus", "subway", "walk"]
    assert wiring.modes_from_survey({"survey": {"priority_details": {"mobility": ["walk"]}}}) == ["walk"]
    assert wiring.modes_from_survey({"survey": {"preferred_mobility": ["대중교통"]}}) == ["bus", "subway", "walk"]
    assert wiring.modes_from_survey({"survey": {"priority_details": {"mobility": ["taxi", "car"]}}}) is None, \
        "렌트카·택시만이면 계산기 기본 수단(아직 못 다룬다 — #47)"
    assert wiring.modes_from_survey({}) is None


def test_43_leg_planner_on_mini_data_fills_density_fields(tmp_path, monkeypatch):
    from app.modules.travel_ops.mobility.engine import paths
    from app.modules.travel_ops.mobility.engine import runtime as RT

    from .mobility.test_review_fixes_runtime import _write_mini_data
    before, saved = (paths.SOURCE, paths.DATA_DIR), dict(wiring._STATE)
    monkeypatch.setattr(RT, "_SINGLETON", None)
    try:
        _write_mini_data(tmp_path)
        wiring.configure(data_dir=str(tmp_path), gh_url="", seoul_key="")
        leg = wiring.leg_planner(2, {})
        arrive = datetime(2026, 10, 7, 11, 0, tzinfo=KST)
        got, why = leg(PLACES["P1"].as_place(), PLACES["P2"].as_place(), arrive,
                       datetime(2026, 10, 7, 9, 30, tzinfo=KST))   # 가짜 시간표는 정각 1편 — 10:00 A 발
        assert got is not None, why
        route = got["route"]
        assert route["average_eta_min"] == got["eta_min"] and route["p95_eta_min"] >= route["average_eta_min"]
        assert got["ends_at"] <= arrive
    finally:
        paths._layout(before[1], before[0])
        wiring._STATE.clear()
        wiring._STATE.update(saved)
        RT._SINGLETON = None
