# -*- coding: utf-8 -*-
"""사고를 계산기 조건으로 옮기고, 저장된 대안이 다 막히면 계산기로 새 경로 — 이동 계산기 문제목록(2026-09-29) #38·#39."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import ItineraryChange, NoChange, plan_route_adjustment
from app.modules.travel_ops.mobility import wiring

T = lambda hm: datetime.fromisoformat(f"2026-10-07T{hm}:00+09:00")  # noqa: E731


def test_39_events_become_engine_disruptions_only_when_meaning_matches():
    out, unmapped = wiring.disruptions_from_events({
        "2호선:잠실": {"effect": "skip_station", "summary": "무정차"},
        "경의중앙선:용산": {"effect": "skip_station"},
        "9호선:*": {"effect": "line_closed"},
        "버스:2224": {"effect": "route_closed"},
        "도로:세종대로": {"effect": "road_control"}})
    kinds = {(d["kind"], d.get("line"), d.get("station"), d.get("route")) for d in out}
    assert ("station_skip", "02호선", "잠실", None) in kinds, "2호선 → 시간표 표기 02호선"
    assert ("station_skip", "경의선", "용산", None) in kinds, "공식명 → 시간표 노선명"
    assert ("line_closed", "09호선", None, None) in kinds and ("route_closed", None, None, "2224") in kinds
    assert unmapped == ["도로:세종대로"], "도로 통제는 뜻이 달라 옮기지 않고 이름으로 돌려준다"


def _place(name, lat, lon):
    return {"place_id": str(uuid4()), "name": name, "latitude": lat, "longitude": lon}


def _scene():
    a = Item(item_id=uuid4(), seq=1, kind="activity", title="잠실", place_id=None, starts_at=T("09:00"),
             ends_at=T("10:40"), place=_place("잠실 타워", 37.512, 127.102))
    route = {"from": "잠실", "to": "성수", "planned": "subway_1",
             "options": [{"id": "subway_1", "label": "2호선 잠실→성수", "eta_min": 13, "uses": ["2호선:잠실", "2호선:성수"]}]}
    move = Item(item_id=uuid4(), seq=2, kind="mobility", title="잠실 → 성수", place_id=None, starts_at=T("10:50"),
                ends_at=T("11:03"), detail={"route_def": route})
    b = Item(item_id=uuid4(), seq=3, kind="activity", title="성수", place_id=None, starts_at=T("11:15"),
             ends_at=T("12:00"), place=_place("성수 쇼룸", 37.5445, 127.056))
    return a, move, b, route


EVENTS = {"2호선:잠실": {"effect": "skip_station", "summary": "2호선 잠실 무정차"}}


def test_38_blocked_everywhere_asks_engine_with_disruptions(monkeypatch):
    a, move, b, route = _scene()
    seen = {}

    def leg_planner(party_size, constraints, *, disruptions=None):
        seen["disruptions"] = disruptions

        def leg(pa, pb, arrive, not_before):
            seen["not_before"] = not_before
            new = {"from": pa["name"], "to": pb["name"], "planned": "bus_2224",
                   "options": [{"id": "bus_2224", "label": "버스 2224", "eta_min": 25, "uses": ["버스:2224"]}]}
            return {"route": new, "starts_at": arrive - timedelta(minutes=35), "ends_at": arrive - timedelta(minutes=10),
                    "eta_min": 25, "left_out": []}, None
        return leg
    monkeypatch.setattr(wiring, "leg_planner", leg_planner)
    plan = plan_route_adjustment(item=move, following=b, route=route, events=EVENTS, now=T("10:30"), previous=a)
    assert isinstance(plan, ItineraryChange), plan
    assert seen["disruptions"][0]["kind"] == "station_skip" and seen["disruptions"][0]["line"] == "02호선"
    assert seen["not_before"] == T("10:40"), "앞 일정이 끝난 뒤부터 떠난다"
    new = next(iter(plan.replacements.values()))
    assert new.detail["route_def"]["options"][0]["uses"] == ["버스:2224"] and "route" not in new.detail
    assert plan.summary["rerouted_by"] == "mobility_engine"


def test_38_engine_off_keeps_old_unresolved(monkeypatch):
    a, move, b, route = _scene()
    monkeypatch.setattr(wiring, "leg_planner", lambda *a, **k: None)
    plan = plan_route_adjustment(item=move, following=b, route=route, events=EVENTS, now=T("10:30"), previous=a)
    assert isinstance(plan, NoChange) and plan.status == "unresolved"
