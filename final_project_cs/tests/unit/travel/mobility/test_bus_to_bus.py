# -*- coding: utf-8 -*-
"""버스 → 버스 환승 후보(모양 C) — 2026-10-06 구글 대조에서 나온 빈자리.

구글은 17구간 중 3구간에서 「버스+버스」를 골랐는데(북촌→석관동 · 망원시장→연남동 · 성북동→서촌) 우리 후보 생성기에는 그 모양이 없었다.
판정기는 버스↔버스 환승을 이미 판정한다(`_bus_bus_walk`). 여기서는 **후보 생성기**(`MixedGenerator.bus_to_bus`)가 환승점을 맞게 찾는지 본다 — 가짜 노선·정류장으로.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine import candidates as C
from app.domains.travel_ops.instances.mobility.engine import plan as P

A = (37.5800, 126.9800)               # 출발점
B = (37.6100, 127.0100)               # 도착점 — 직선 약 4.2 km


def _route(rid, nm, typ="간선", term=10):
    return SimpleNamespace(route_id=rid, route_nm=nm, route_type_nm=typ, term_min=term)


def _stop(rid, seq, nm, lat, lng, sid=None):
    return {"route_id": rid, "seq": seq, "station_nm": nm, "station_id": sid or f"{rid}-{seq}", "lat": lat, "lng": lng}


class FakeBus:
    def __init__(self, routes, stops):
        self.by_id = {r.route_id: r for r in routes}
        self.stops = {}
        for s in stops:
            self.stops.setdefault(s["route_id"], []).append(s)
        for rows in self.stops.values():
            rows.sort(key=lambda s: s["seq"])


def _gen(bus, ride=lambda r, x, y: float(y["seq"] - x["seq"]) * 3.0, **kw):
    args = dict(radius_m=500, near_m=500, cuts=3, tlim=3, excluded=(), ride_min=ride, wayfinding=1,
                walk_speed=1.04, detour=1.4)
    args.update(kw)
    return C.MixedGenerator(None, bus, None, None, **args)


def _world(**over):
    """R1: A 근처(1) → 중간(2) → 환승점 S(3) / R2: 환승점 근처 T(2) → 도착점 근처 Y(4)."""
    r1, r2 = _route("R1", "1111"), _route("R2", "2222")
    stops = [
        _stop("R1", 1, "가출발", 37.5801, 126.9801),
        _stop("R1", 2, "가중간", 37.5880, 126.9880),
        _stop("R1", 3, "가환승", 37.5950, 126.9950),
        _stop("R2", 1, "나기점", 37.5900, 126.9900),
        _stop("R2", 2, "나환승", 37.5951, 126.9951),            # R1 환승점에서 약 14 m
        _stop("R2", 3, "나중간", 37.6030, 127.0030),
        _stop("R2", 4, "나도착", 37.6101, 127.0101),
    ]
    routes = [r1, r2]
    for fn in over.values():
        routes, stops = fn(routes, stops)
    return FakeBus(routes, stops)


def _legs(c):
    return [(x["route"], x["from"], x["to"]) for x in c.legs]


def test_a_bus_to_bus_candidate_is_found_through_a_nearby_transfer_stop():
    out = _gen(_world()).bus_to_bus(*A, *B, 800)
    assert len(out) == 1
    c = out[0]
    assert c.shape == "C" and c.transfers == 1
    assert _legs(c) == [("1111", "가출발", "가환승"), ("2222", "나환승", "나도착")]
    assert c.route_nm == "1111→2222" and c.cut_station == "가환승" and c.end_station == "나도착"
    assert c.link_m < 30, "환승 정류장 두 곳은 약 14 m"
    assert c.walk_in_m < 30 and c.walk_out_m < 30
    assert c._done is True and c.sub_walk_min == 0.0, "지하철이 없다 — 채울 것이 없다"
    assert c.est_min > 0 and c.grade == "추정"


def test_the_first_route_that_reaches_the_destination_alone_is_left_to_the_direct_bus():
    def r1_reaches_b(routes, stops):
        return routes, stops + [_stop("R1", 4, "가도착", 37.6102, 127.0102)]      # R1 이 도착점 근처까지 간다
    assert _gen(_world(x=r1_reaches_b)).bus_to_bus(*A, *B, 800) == []


def test_a_transfer_stop_beyond_the_link_limit_is_not_used():
    def far_transfer(routes, stops):
        stops = [dict(s, lat=s["lat"] + 0.004) if (s["route_id"], s["seq"]) == ("R2", 2) else s for s in stops]   # 환승점에서 약 440 m
        return routes, stops
    assert _gen(_world(x=far_transfer)).bus_to_bus(*A, *B, 800) == []
    assert _gen(_world(x=far_transfer)).bus_to_bus(*A, *B, 800, link_lim=600), "상한을 넓히면 후보가 된다"


def test_the_second_route_must_pass_the_transfer_stop_before_the_alighting_stop():
    def wrong_order(routes, stops):
        return routes, [dict(s, seq=0) if (s["route_id"], s["seq"]) == ("R2", 4) else s for s in stops]           # 도착 정류장이 환승 정류장보다 앞
    assert _gen(_world(x=wrong_order)).bus_to_bus(*A, *B, 800) == []


def test_a_stop_that_does_not_move_toward_the_destination_is_not_a_transfer_point():
    def away(routes, stops):
        return routes, [dict(s, lat=37.5600, lng=126.9600) if (s["route_id"], s["seq"]) in (("R1", 3), ("R2", 2)) else s for s in stops]
    assert _gen(_world(x=away)).bus_to_bus(*A, *B, 800) == []


def test_a_route_without_a_ride_estimate_is_never_slipped_in():
    assert _gen(_world(), ride=lambda r, x, y: None).bus_to_bus(*A, *B, 800) == []
    assert _gen(_world(), ride=None).bus_to_bus(*A, *B, 800) == []


def test_airport_buses_and_same_named_routes_are_not_transfers():
    def airport(routes, stops):
        return [_route("R1", "1111", typ=C.AIRPORT_TYPE), routes[1]], stops
    assert _gen(_world(x=airport)).bus_to_bus(*A, *B, 800) == []

    def same_name(routes, stops):
        return [routes[0], _route("R2", "1111")], stops
    assert _gen(_world(x=same_name)).bus_to_bus(*A, *B, 800) == []


def test_candidates_are_sorted_by_estimate_and_capped():
    r1, r2, r3 = _route("R1", "1111"), _route("R2", "2222"), _route("R3", "3333")
    stops = [_stop("R1", 1, "가출발", 37.5801, 126.9801), _stop("R1", 3, "가환승", 37.5950, 126.9950),
             _stop("R2", 2, "나환승", 37.5951, 126.9951), _stop("R2", 4, "나도착", 37.6101, 127.0101),
             _stop("R3", 2, "다환승", 37.5952, 126.9952), _stop("R3", 6, "다도착", 37.6101, 127.0102)]       # R3 은 더 오래 탄다
    out = _gen(FakeBus([r1, r2, r3], stops)).bus_to_bus(*A, *B, 800)
    assert [c.route_nm for c in out] == ["1111→2222", "1111→3333"]
    assert out[0].est_min < out[1].est_min
    assert len(_gen(FakeBus([r1, r2, r3], stops)).bus_to_bus(*A, *B, 800, top=1)) == 1


def test_interleave_takes_candidates_from_every_shape_in_turn():
    assert C.interleave(["a1", "a2"], ["b1"], ["c1", "c2", "c3"]) == ["a1", "b1", "c1", "a2", "c2", "c3"]
    assert C.interleave(["a1", "a2"], ["b1"]) == ["a1", "b1", "a2"], "둘만 줘도 종전 동작과 같다"
    assert C.interleave() == []


def test_two_bus_legs_belong_to_the_mixed_group_not_the_single_bus_group():
    bus = {"mode": "bus", "route": "1", "from": "가", "to": "나"}
    sub = {"line": "02호선", "from": "가", "to": "나"}
    assert P._is_mixed({"_legs": [bus, dict(bus, route="2")]}) is True
    assert P._is_mixed({"_legs": [bus]}) is False, "버스 한 노선은 종전 그대로"
    assert P._is_mixed({"_legs": [bus, sub]}) is True and P._is_mixed({"_legs": [sub]}) is False
