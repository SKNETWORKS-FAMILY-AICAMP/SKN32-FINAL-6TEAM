# -*- coding: utf-8 -*-
"""지하철+버스 혼합 후보(환승 1회) — 87번 방(2026-10-01 · 12 전달 + 85 E1 2단).

두 층:
  게이트(데이터 없음) — 작은 역·노선 표로 생성기(candidates.MixedGenerator)와 plan 의 거르기를 잠근다:
    끊는 지점(역 앞 정류장만 · 근접 밖 노선은 못 끊음 · 노선당 N) · 막힌 노선·무정차 역 피하기 · 걸어갈 역은 안 끊음 ·
    공항버스(A 는 공항에서 타는 것만 · 공항행 B 는 no_data 로 이유만) · 가상 정류장 · 규칙 변경안 값 · 두 모양 번갈아 ·
    plan 거르기(앞서는 축 없음 · 허용_소요_배수 · 상한) · 계획 수단은 지하철만·버스만이 있으면 그중에서(혼합은 추가만).
  전체층(실데이터 · mobility_full) —
    83 재생 시나리오(성수 무정차): 잠실→건대입구 → 버스 2016 을 계산기가 낸다 ·
    마지막 성립 출발(_mix_latest)이 판정기 역산(lfd)과 같다 ·
    사고로 걸어갈 역이 모두 막혀도 가장 이른 도착(86)이 혼합으로 답한다 ·
    혼합을 끈 판과 지하철만·버스만 options·계획이 같다(추가만).
회귀 케이스(CLI)는 multi_legs_v1.json 의 MIX-AB-01~09.
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import candidates as CD
from app.domains.travel_ops.instances.mobility.engine import plan as P
from app.domains.travel_ops.instances.mobility.engine.candidates import CandidateGraph, MixedGenerator
from app.domains.travel_ops.instances.mobility.engine.paths import RULES_DIR

RULES = json.loads((RULES_DIR / "rules_v0.3.json").read_text(encoding="utf-8"))


# ── 게이트 — 작은 세계 ────────────────────────────────────────────────────
#   지하철 L1: S1(37.50) — S2(37.51) — S3(37.52) · 경도 127.00 · 간선 2분씩
#   출발점 P(37.535, 127.02) — 어느 역에서도 도보 상한(1,200 m) 밖
#   버스 R1(간선): P 앞 정류장 → 중간 → S3 앞(30 m) → S2 앞(40 m)   — A 의 끊는 지점 둘(S3 · S2)
#   버스 R2(지선): P 앞 정류장 → 멀리(역 없음) 둘                   — 근접 밖(끊는 지점 없음)
#   버스 R3(공항): 「인천공항」 정류장 → S3 앞                         — 공항에서 타는 공항버스
#   버스 R4(공항): P 앞 정류장 → S3 앞                                 — 공항이 아닌 곳에서 타는 공항버스(A 에 안 씀)
P_LAT, P_LNG = 37.535, 127.02


class _LO:
    def __init__(self):
        st = [{"station_nm": n} for n in ("S1", "S2", "S3")]
        self.doc = {"lines": {"L1": {"stations": st, "edges": [
            {"a": "S1", "b": "S2", "travel_min": 2}, {"a": "S2", "b": "S3", "travel_min": 2}]}}}


def _rec(nm, lat):
    return {"station_nm": nm, "line": "L1", "lat": lat, "lng": 127.00, "station_key": f"L1|{nm}"}


class _SC:
    def __init__(self):
        self.by_key = {f"L1|{n}": _rec(n, lat) for n, lat in (("S1", 37.50), ("S2", 37.51), ("S3", 37.52))}

    def phys_key(self, rec):
        return rec["station_nm"]

    def group_lines(self, rec):
        return frozenset({"L1"})

    def resolve(self, nm, lines=None):
        return self.by_key.get(f"L1|{nm}")

    def is_ambiguous(self, nm):
        return False


def _stop(rid, seq, nm, lat, lng, d=100):
    return {"route_id": rid, "seq": seq, "station_nm": nm, "lat": lat, "lng": lng, "sect_dist_m": d,
            "station_id": f"{rid}-{seq}"}


class _Bus:
    def __init__(self, extra=()):
        R = lambda rid, nm, t: SimpleNamespace(route_id=rid, route_nm=nm, route_type_nm=t, term_min=10,  # noqa: E731
                                               first_min=300, last_min=1400)
        self.by_id = {"r1": R("r1", "R1", "간선"), "r2": R("r2", "R2", "지선"),
                      "r3": R("r3", "R3", "공항"), "r4": R("r4", "R4", "공항")}
        self.by_nm = {r.route_nm: r for r in self.by_id.values()}
        self.stops = {
            "r1": [_stop("r1", 1, "P앞", P_LAT, P_LNG), _stop("r1", 2, "중간", 37.53, 127.01),
                   _stop("r1", 3, "S3앞", 37.5203, 127.0001), _stop("r1", 4, "S2앞", 37.5104, 127.0001)],
            "r2": [_stop("r2", 1, "P앞2", P_LAT, P_LNG + 0.0005), _stop("r2", 2, "먼곳", 37.60, 127.10),
                   _stop("r2", 3, "더먼곳", 37.61, 127.11)],
            "r3": [_stop("r3", 1, "인천공항1층", 37.4476, 126.4523), _stop("r3", 2, "영종대교(가상)", 37.52, 127.0),
                   _stop("r3", 3, "S3앞C", 37.5202, 127.0002)],
            "r4": [_stop("r4", 1, "P앞D", P_LAT, P_LNG + 0.0003), _stop("r4", 2, "S3앞D", 37.5202, 127.0003)],
        }
        for rid, rows in extra:
            self.stops[rid] = rows

    def route(self, nm):
        return self.by_nm.get(str(nm))


def _gen(bus=None, **kw):
    cg = CandidateGraph(_LO(), None, RULES, True)
    args = dict(radius_m=500, near_m=500, cuts=3, tlim=3, excluded=["관광", "투어"],
                ride_min=lambda r, x, y: 10.0 * (y["seq"] - x["seq"]), wayfinding=1, walk_speed=1.04, detour=1.4)
    args.update(kw)
    return MixedGenerator(cg, bus or _Bus(), _SC(), None, **args)


def _legs(c):
    return [(l.get("route") or l.get("line"), l["from"], l["to"]) for l in c.legs]


def test_a_cuts_at_station_front_stops_only():
    """A — R1 이 역 앞(S3 · S2)을 지나는 곳에서만 끊는다 · R2 는 역 앞을 안 지나 끊는 지점이 없다(근접 밖)."""
    g = _gen()
    cs = g.bus_to_subway(P_LAT, P_LNG, [("S1", None, 0)], 1200)
    assert {(c.route_nm, c.cut_station) for c in cs} == {("R1", "S3"), ("R1", "S2")}, [(c.route_nm, c.cut_station) for c in cs]
    assert "R2" in g.no_cut, g.no_cut
    c = next(c for c in cs if c.cut_station == "S2")
    assert g.materialize(c)
    assert _legs(c) == [("R1", "P앞", "S2앞"), ("L1", "S2", "S1")]
    assert c.shape == "A" and c.transfers == 1 and c.end_station == "S1" and c.link_m < 500


def test_a_cuts_per_route_cap():
    """노선당 끊는 지점 N — 지하철 쪽 추정이 짧은 순(S2 → S1 이 S3 → S1 보다 짧다)."""
    cs = _gen(cuts=1).bus_to_subway(P_LAT, P_LNG, [("S1", None, 0)], 1200)
    assert [(c.route_nm, c.cut_station) for c in cs] == [("R1", "S2")]


def test_avoid_closed_line_and_skip_station():
    """사고 — 운행 중단 노선은 지하철 쪽에 안 쓰고(후보 없음) · 무정차 역은 그 노선으로 끊지 않는다."""
    assert _gen(avoid_lines={"L1"}).bus_to_subway(P_LAT, P_LNG, [("S1", None, 0)], 1200) == []
    cs = _gen(skip_at={("L1", "S2")}).bus_to_subway(P_LAT, P_LNG, [("S1", None, 0)], 1200)
    assert {c.cut_station for c in cs} == {"S3"}


def test_walkable_cut_station_is_not_cut():
    """끊는 역이 출발점에서 도보 상한 안이면 끊지 않는다(그 역까지 걷는 지하철 후보가 이미 있다)."""
    near_lat = 37.5215                       # S3 에서 약 170 m · S2 에서 약 1.3 km
    cs = _gen().bus_to_subway(near_lat, P_LNG - 0.0199, [("S1", None, 0)], 1200, excl_m=1200)
    assert all(c.cut_station != "S3" for c in cs), [c.cut_station for c in cs]


def test_cut_station_equal_target_is_bus_direct_not_mixed():
    """끊는 역이 도착 역이면 지하철이 없다 — 혼합이 아니라 버스 직행의 몫이라 만들지 않는다."""
    cs = _gen().bus_to_subway(P_LAT, P_LNG, [("S3", None, 0)], 1200)
    assert all(c.cut_station != "S3" for c in cs)


def test_airport_bus_only_from_airport_in_a():
    """공항버스 — A 는 공항 정류장에서 타는 것만(R3) · 공항이 아닌 곳에서 타는 공항버스(R4)는 조용히 뺀다 · 가상 정류장은 안 끊음."""
    g = _gen()
    cs = g.bus_to_subway(37.4476, 126.4523, [("S1", None, 0)], 1200)
    assert {(c.route_nm, c.legs[0]["to"]) for c in cs} == {("R3", "S3앞C")}, [_legs(c) for c in cs]
    assert not any("가상" in c.legs[0]["to"] for c in cs)
    cs2 = g.bus_to_subway(P_LAT, P_LNG, [("S1", None, 0)], 1200)
    assert "R4" not in {c.route_nm for c in cs2} and g.skipped_airport == []


def test_b_shape_and_airport_bound_is_no_data():
    """B — S1 에서 지하철로 S2·S3 까지 가서 R1 을 타고 S2앞·… → 도착점. 도착점이 공항이면(공항행) 공항버스는 만들지 않고 노선만 적는다."""
    bus = _Bus(extra=[("r5", [_stop("r5", 1, "S2앞B", 37.5104, 127.0002), _stop("r5", 2, "목적지앞", 37.545, 127.03)])])
    bus.by_id["r5"] = SimpleNamespace(route_id="r5", route_nm="R5", route_type_nm="지선", term_min=8,
                                      first_min=300, last_min=1400)
    bus.by_nm["R5"] = bus.by_id["r5"]
    g = _gen(bus)
    cs = g.subway_to_bus([("S1", None, 0)], 37.545, 127.03, 1200)
    assert [(c.route_nm, c.cut_station) for c in cs] == [("R5", "S2")]
    assert g.materialize(cs[0]) and _legs(cs[0]) == [("L1", "S1", "S2"), ("R5", "S2앞B", "목적지앞")]
    g2 = _gen()
    g2.subway_to_bus([("S1", None, 0)], 37.5203, 127.0002, 1200)          # S3앞C 근처 — R3 은 공항에서 출발 → 시내
    assert g2.skipped_airport == []
    air = _Bus(extra=[("r6", [_stop("r6", 1, "S2앞C", 37.5104, 127.0002), _stop("r6", 2, "인천공항T1", 37.4476, 126.4523)])])
    air.by_id["r6"] = SimpleNamespace(route_id="r6", route_nm="R6", route_type_nm="공항", term_min=30,
                                      first_min=300, last_min=1400)
    g3 = _gen(air)
    assert g3.subway_to_bus([("S1", None, 0)], 37.4476, 126.4523, 1200) == []
    assert g3.skipped_airport == ["R6"]


def test_transfer_cap_counts_mode_switch():
    """총 환승 상한 = 버스↔지하철 1 + 지하철 안 — 상한 0 이면 혼합을 못 만든다(materialize 거절)."""
    g = _gen(tlim=0)
    cs = g.bus_to_subway(P_LAT, P_LNG, [("S1", None, 0)], 1200)
    assert cs and not any(g.materialize(c) for c in cs)


def test_mix_rule_proposed_and_validation():
    assert CD.mix_rule({"candidates": {}}, "혼합_최대", CD.MIX_MAX_PROPOSED) == 3
    assert CD.mix_rule({"candidates": {"혼합_최대": {"value": 2}}}, "혼합_최대", 3) == 2
    for bad in (0, -1, True, 1.5, "3"):
        with pytest.raises(ValueError):
            CD.mix_rule({"candidates": {"혼합_최대": {"value": bad}}}, "혼합_최대", 3)
    assert CD.MIX_CUTS_PER_ROUTE_PROPOSED == 3 and "혼합_최대" not in RULES["candidates"]   # 변경안 — 규칙 파일은 모아서(규칙 32)


def test_interleave_shapes():
    assert CD.interleave([1, 2, 3], ["a"]) == [1, "a", 2, 3]
    assert CD.interleave([], ["a", "b"]) == ["a", "b"]


# ── 게이트 — plan 거르기 ──────────────────────────────────────────────────
def _opt(eta, tr, walk, start, legs, key):
    return {"eta_min": eta, "_transfers": tr, "_walk_min": walk, "_start": start, "_legs": legs, "_key": key,
            "_route": str(key), "uses": [], "_n": 0}


SUB = [{"line": "02호선", "from": "A", "to": "B"}]
MIXL = [{"mode": "bus", "route": "1", "from": "x", "to": "y"}, {"line": "02호선", "from": "C", "to": "B"}]


def _planner_stub(results):
    """_mixed 만 보는 Planner — 생성기·판정은 가짜(results[i] = 판정 뒤 후보 dict 또는 None)."""
    pl = P.Planner.__new__(P.Planner)
    pl.v = SimpleNamespace(R=RULES, bus=SimpleNamespace(route=lambda nm: None))
    pl.speed, pl.detour, pl.disruptions = 1.04, 1.4, ()
    mcs = [SimpleNamespace(shape="A", est_min=10 + i, transfers=1, walk_in_m=0, walk_out_m=0, link_m=0, sub_walk_min=0,
                           route_nm=f"R{i}", cut_station="C", legs=MIXL) for i in range(len(results))]
    gen = SimpleNamespace(bus_to_subway=lambda *a, **k: mcs, subway_to_bus=lambda *a, **k: [], skipped_airport=[],
                          materialize=lambda c: True)
    pl._mix_gen = lambda party, fv: gen
    pl._phys_set = lambda st: set()
    pl._in_service = lambda mc, lo, hi: True
    pl._mixed_one = lambda mc, i, *a, **k: ((results[i], None) if results[i] is not None
                                            else (None, {"_o": {"_legs": []}, "label": "x", "code": "not_confirmed", "reason": "r"}))
    return pl


def _run_mixed(pl, opts):
    left = []
    got = pl._mixed({"lat": 0, "lon": 0}, {"lat": 0, "lon": 0}, [("A", 10, None)], [("B", 10, None)],
                    None, None, 600, {}, True, "t", 1200, opts, left)
    return got, left


def test_plan_mixed_kept_only_when_ahead_on_an_axis():
    base = [_opt(30, 1, 5, 500, SUB, ("rail", 0, 1))]
    ahead = _opt(25, 1, 6, 505, MIXL, ("mix", 0, 0))          # 소요가 앞선다
    behind = _opt(31, 1, 6, 499, MIXL, ("mix", 0, 1))         # 어느 축도 앞서지 않는다
    too_long = _opt(46, 0, 1, 470, MIXL, ("mix", 0, 2))       # 환승·도보는 앞서지만 30 × 1.5 = 45 를 넘는다
    got, left = _run_mixed(_planner_stub([ahead, behind, too_long]), base)
    assert got == [ahead]
    codes = [e["code"] for e in left]
    assert codes.count("mix_dominated") == 2, left
    assert any("허용_소요_배수" in e["reason"] for e in left), left


def test_plan_mixed_cap_and_no_base():
    """지하철만·버스만 후보가 없으면(사고 등) 비교 없이 싣는다 · 상한(혼합_최대 3)을 넘으면 mix_cap 한 줄."""
    res = [_opt(40 + i, 1, 5, 500, MIXL, ("mix", 0, i)) for i in range(5)]
    pl = _planner_stub(res)
    got, left = _run_mixed(pl, [])
    assert len(got) == P.MIX_VERIFY_MAX == 3
    assert any(e["code"] == "mix_cap" and "2개" in e["label"] for e in left), left


def test_planned_prefers_plain_candidates():
    """GPT 87 #2 — 계획 수단은 앞 판 후보(지하철만·버스만·도보)에서 **앞 판 순서(자격 → nb 재판정)** 를 먼저 다 밟는다. 혼합이 처음부터
    자격이 있어도 기존 후보가 nb 재판정으로 살아나면 그것이 계획. 기존 후보가 하나도 안 살면 그때 혼합."""
    plain = _opt(30, 0, 5, 590, SUB, ("rail", 0, 1))            # nb(600) 보다 이른 역산 출발 — 재판정으로 살아날 수 있다
    mixed = _opt(25, 1, 5, 610, MIXL, ("mix", 0, 0))            # 처음부터 자격
    revived = dict(plain, _start=600)
    got, rv = P.Planner._choose_planned([plain, mixed], 600, lambda o: revived if o is plain else None)
    assert got is revived and rv == [revived]
    got, rv = P.Planner._choose_planned([plain, mixed], 600, lambda o: None)
    assert got is mixed and rv == []
    late_mix = dict(mixed, _start=590)
    got, rv = P.Planner._choose_planned([plain, late_mix], 600, lambda o: None)
    assert got is None and rv == []
    # nb 없음 — 앞 판처럼 가장 늦게 떠나도 되는 기존 후보(혼합이 더 늦어도)
    got, _ = P.Planner._choose_planned([plain, mixed], None, lambda o: None)
    assert got is plain
    assert P._is_mixed({"_legs": MIXL}) and not P._is_mixed({"_legs": SUB})
    assert not P._is_mixed({"_legs": [{"mode": "bus", "route": "1", "from": "a", "to": "b"}]})


def _latest_planner(feasible, lfd_of_verifier, late_from=None):
    """_mix_latest 만 보는 Planner — feasible(t) 가 성립 구간 · 그 밖은 막차 뒤(최악 도착 없음). 판정기 역산(_vc)은 lfd_of_verifier."""
    pl = P.Planner.__new__(P.Planner)
    calls = {"vc": 0, "vcq": 0}

    def vcq(case):
        calls["vcq"] += 1
        t = case["depart_at"]
        if feasible(t):
            return SimpleNamespace(reason="", out={"verdict": "feasible", "eta_min": 30, "slack_min": 0,
                                                   "arrive_worst_min": t + 30, "buffer_min": 0})
        if late_from is not None:           # 늦어서 불가 — 넘친 만큼(최악 도착 + 버퍼 − 목표 600)
            return SimpleNamespace(reason="늦음", out={"verdict": "infeasible", "code": "arrive_late", "reason": "늦음",
                                                     "arrive_worst_min": 600 + (t - late_from), "buffer_min": 0})
        return SimpleNamespace(reason="막차 뒤", out={"verdict": "infeasible", "code": "after_last", "reason": "막차 뒤"})

    def vc(case):
        calls["vc"] += 1
        return SimpleNamespace(reason="", out={"last_feasible_depart_min": lfd_of_verifier})
    pl._vcq, pl._vc = vcq, vc
    return pl, calls


def test_mix_latest_after_last_falls_back_to_verifier():
    """GPT 87 #1 — 추정 출발(580)이 막차 뒤라 도착을 못 내도, 당기면 성립하는 출발(550)을 놓치지 않는다(판정기 역산으로 넘김)."""
    pl, calls = _latest_planner(lambda t: 500 <= t <= 550, 550)
    lfd, r, why = pl._mix_latest({"legs": []}, 600, 20)
    assert lfd == 550 and calls["vc"] == 1, (lfd, why, calls)


def test_mix_latest_step_cap_is_not_reported_as_latest(monkeypatch):
    """GPT 87 #1 — 호출 한도 안에 성립·불성립 이웃을 못 만들면 찾은 성립 출발을 「마지막」이라 하지 않고 판정기 역산으로 넘긴다."""
    monkeypatch.setattr(P, "MIX_LFD_STEPS", 2)
    pl, calls = _latest_planner(lambda t: t <= 560, 560)
    lfd, _r, _why = pl._mix_latest({"legs": []}, 600, 70)        # 530 성립 → 531 성립(여유 0) → 한도
    assert lfd == 560 and calls["vc"] == 1
    monkeypatch.setattr(P, "MIX_LFD_STEPS", 10)
    pl, calls = _latest_planner(lambda t: t <= 560, 999, late_from=560)
    lfd, _r, _why = pl._mix_latest({"legs": []}, 600, 32)        # 568 불가(넘침) → 당김 → 이분으로 560 · 판정기 안 부름
    assert lfd == 560 and calls["vc"] == 0


def test_ride_estimator_cache_is_per_config():
    """GPT 87 #3 — 같은 버스 표라도 속도 규칙(판정기 설정)이 다르면 다른 칸."""
    bus = _Bus()

    def v_with(kmh):
        R = {"bus": {}}
        return SimpleNamespace(bus=bus, bus_prof=None, R=R, bus_speed=lambda r, d: (kmh, "", "추정", []),
                               rv=lambda *a: None)
    r1 = CD.ride_estimator(v_with(10))
    r2 = CD.ride_estimator(v_with(60))
    route = bus.by_id["r1"]
    x, y = bus.stops["r1"][0], bus.stops["r1"][3]                 # 300 m
    assert abs(r1(route, x, y) - 1.8) < 1e-9 and abs(r2(route, x, y) - 0.3) < 1e-9


def test_station_cache_is_per_exit_table():
    """GPT 87 #3 — 같은 역 좌표표라도 출구표가 다르면 다른 칸(출구 거리로 역 앞을 정한다)."""
    class _EX:
        def __init__(self, lat):
            self.exits = {"S3": [{"lat": lat, "lng": 127.0, "ref": "1"}]}

        def nearest(self, nm, lat, lng, line=None):
            from app.domains.travel_ops.instances.mobility.engine.geo import meters
            es = self.exits.get(nm, [])
            return min(((meters(lat, lng, e["lat"], e["lng"]), e) for e in es), default=None, key=lambda t: t[0])
    sc, bus, cg = _SC(), _Bus(), CandidateGraph(_LO(), None, RULES, True)
    kw = dict(radius_m=500, near_m=500, cuts=3, tlim=3, ride_min=lambda r, x, y: 1.0)
    row = {"station_id": "z", "lat": 37.5260, "lng": 127.0}       # S3 역 좌표에서 약 670 m
    near = MixedGenerator(cg, bus, sc, _EX(37.5240), **kw)._stations_by(row)      # 출구가 정류장 220 m
    far = MixedGenerator(cg, bus, sc, _EX(37.5200), **kw)._stations_by(row)       # 출구가 정류장 670 m
    assert [r["station_nm"] for _m, r in near] == ["S3"] and far == []


def test_station_far_exit_found_via_all_records():
    """GPT 87 #6 — 한 물리적 역의 노선 레코드가 여럿이면 대표 하나가 아니라 전부로 찾는다(다른 노선 좌표 쪽 출구 앞 정류장)."""
    sc = _SC()
    sc.by_key["L2|S3"] = dict(_rec("S3", 37.5300), line="L2", station_key="L2|S3")   # 같은 역 다른 노선 좌표(약 1.1 km 북)
    g = MixedGenerator(CandidateGraph(_LO(), None, RULES, True), _Bus(), sc, None, radius_m=500, near_m=500, cuts=3, tlim=3,
                       ride_min=lambda r, x, y: 1.0)
    got = g._stations_by({"station_id": "q", "lat": 37.5320, "lng": 127.0})        # L1 좌표 1.3 km · L2 좌표 220 m
    assert [r["station_nm"] for _m, r in got] == ["S3"]
    assert CD.exit_reach_m(sc, None) == 0.0


def test_mixed_sources_keep_out_of_window_routes_for_waiting():
    """GPT 87 #4 — 가장 이른 도착 목표 생성은 운행 시간 추정 밖 노선을 **거르지 않고 뒤로** 둔다(막차 뒤 → 다음 운행일 첫차 대기)."""
    pl = P.Planner.__new__(P.Planner)
    night = SimpleNamespace(route_id="rn", route_nm="RN", first_min=300, last_min=360, est_min=20, transfers=1,
                            board=None, cut_station="C", legs=MIXL)
    bus = SimpleNamespace(by_id={"rn": SimpleNamespace(route_id="rn", first_min=300, last_min=360)}, stops={"rn": []})
    pl.v = SimpleNamespace(bus=bus)
    gen = SimpleNamespace(bus_to_subway=lambda *a, **k: [night], subway_to_bus=lambda *a, **k: [], materialize=lambda c: True)
    pl._mix_gen = lambda party, fv: gen
    pl._phys_set = lambda st: set()
    got = pl._mixed_sources({"lat": 0, "lon": 0}, {"lat": 0, "lon": 0}, [("A", 1, None)], [("B", 1, None)], 1500, {}, True, 1200)
    assert got == [night]
    assert pl._in_service(night, 1500, 1500 + P.EARLIEST_WAIT_MAX_MIN + 20)      # 다음 운행일 첫차(300 + 1440)


# ── 전체층 — 실데이터 ─────────────────────────────────────────────────────
AQUARIUM = {"key": "aquarium", "name": "아쿠아리움", "lat": 37.5131, "lon": 127.1033}
SEONGSU = {"key": "seongsu", "name": "성수동 팝업·향수 쇼룸 거리", "lat": 37.5445, "lon": 127.056}
ARRIVE = datetime.fromisoformat("2026-09-23T11:30:00+09:00")
SKIP_SEONGSU = ({"kind": "station_skip", "line": "02호선", "station": "성수"},)
CLOSED = ({"kind": "line_closed", "line": "02호선"}, {"kind": "line_closed", "line": "수인분당선"})
_RT = None


def _runtime():
    global _RT
    if _RT is None:
        from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
        try:
            _RT = build_verifier(quiet=True)
        except RuntimeError as e:
            _RT = e
    if isinstance(_RT, Exception):
        pytest.skip("시간표 없음(DATA_DIR) — 데이터 축 SKIP")
    return _RT


def _planner(dis=(), **kw):
    pl = P.Planner(_runtime(), stage="planning", **kw)
    pl.disruptions = tuple(dis)
    return pl


@pytest.mark.mobility_full
def test_full_83_skip_gives_konkuk_bus_2016():
    """83 재생 시나리오 A — 성수 무정차에서 사람이 넣던 「건대입구 → 버스 2016」을 계산기가 낸다(계획은 85 의 잠실→뚝섬 그대로 ·
    혼합은 계획 출발 뒤 성립하면 options, 아니면 left_out 에 이유와 함께)."""
    got, why = _planner(SKIP_SEONGSU).leg(AQUARIUM, SEONGSU, ARRIVE, P.party_of(None, {}), True, "aq_to_ss")
    assert got is not None, why
    route, left = got[0], got[4]
    planned = next(o for o in route["options"] if o["id"] == route["planned"])
    assert planned["uses"] == ["2호선:잠실", "2호선:뚝섬"], planned
    labels = [o["label"] for o in route["options"]] + [e["label"] for e in left]
    assert any("2호선 잠실→건대입구" in x and "버스 2016" in x for x in labels), labels


@pytest.mark.mobility_full
def test_full_mix_latest_matches_verifier_lfd():
    """마지막 성립 출발 — 혼합 전용 탐색(_mix_latest · lfd 끈 사본)이 판정기 역산(lfd)과 같은 분을 낸다(A·B 둘 다)."""
    pl = _planner(SKIP_SEONGSU)
    gen = pl._mix_gen({}, True)
    wlim = pl._walk_limit({})
    sa, sb, _ = pl._station_pairs(AQUARIUM, SEONGSU, wlim)
    cands = CD.interleave(gen.bus_to_subway(AQUARIUM["lat"], AQUARIUM["lon"], [(n, l, d) for n, d, l in sb], wlim, wlim),
                          gen.subway_to_bus([(n, l, d) for n, d, l in sa], SEONGSU["lat"], SEONGSU["lon"], wlim, wlim))
    seen = {"A": 0, "B": 0}
    by = 11 * 60 + 25
    for mc in cands:
        if seen[mc.shape] >= 2 or not gen.materialize(mc):
            continue
        r_ = pl.v.bus.route(mc.route_nm)
        if r_ is None or r_.first_min > by or r_.last_min < by - 120:
            continue
        base = {"id": "lfd", "date": "2026-09-23", "stage": "planning", "legs": mc.legs, "arrive_by": by,
                "party": {}, "first_visit": True, "no_alternatives": True}
        ref = (pl._vc(dict(base, depart_at=by - 180)).out or {}).get("last_feasible_depart_min")
        got, _r, _why = pl._mix_latest(base, by, mc.est_min)
        if ref is None:
            continue
        assert got == ref, (mc.legs, got, ref)
        seen[mc.shape] += 1
    assert seen["A"] >= 1 and seen["B"] >= 1, seen


@pytest.mark.mobility_full
def test_full_earliest_uses_mixed_when_stations_blocked():
    """86 가장 이른 도착 — 걸어갈 역이 모두 막히고 앞 일정 끝 뒤로는 늦을 때, 목표 생성이 혼합도 본다(혼합이 계획 수단이 되는 구간)."""
    nb = datetime.fromisoformat("2026-09-23T10:45:00+09:00")
    got, why = _planner(CLOSED).leg(AQUARIUM, SEONGSU, ARRIVE, P.party_of(None, {}), True, "aq_to_ss",
                                    not_before_dt=nb, earliest_on_late=True)
    if got is not None:                       # 앞 일정 끝 뒤에 떠나도 맞는 혼합이 있으면 그대로 계획(가장 이른 도착이 필요 없다)
        planned = next(o for o in got[0]["options"] if o["id"] == got[0]["planned"])
        assert planned["id"].startswith("subway_bus"), planned
        return
    e = why.get("earliest") or {}
    assert e.get("status") == "found", why
    assert any(u.startswith("버스:") for u in e["uses"]) and any(not u.startswith("버스:") for u in e["uses"]), e


@pytest.mark.mobility_full
def test_full_plain_options_unchanged_by_mixed():
    """혼합은 **추가만** — 혼합을 끈 판(_mixed → [])과 계획 수단·출발·지하철만/버스만 options 가 같다(사고 없는 다섯 구간)."""
    legs = [(AQUARIUM, SEONGSU, ARRIVE),
            ({"key": "a", "name": "명동", "lat": 37.5609, "lon": 126.9862}, {"key": "b", "name": "경복궁", "lat": 37.5796, "lon": 126.977},
             datetime.fromisoformat("2026-09-23T10:00:00+09:00")),
            ({"key": "a", "name": "신용산", "lat": 37.5292, "lon": 126.968}, {"key": "b", "name": "남성", "lat": 37.4847, "lon": 126.971},
             datetime.fromisoformat("2026-09-23T15:00:00+09:00")),
            ({"key": "a", "name": "홍대", "lat": 37.5572, "lon": 126.9245}, {"key": "b", "name": "잠실", "lat": 37.5133, "lon": 127.1001},
             datetime.fromisoformat("2026-09-23T18:30:00+09:00")),
            ({"key": "a", "name": "선바위", "lat": 37.4517, "lon": 127.0021}, {"key": "b", "name": "숭실대", "lat": 37.4963, "lon": 126.9537},
             datetime.fromisoformat("2026-09-23T09:00:00+09:00"))]
    for a, b, arr in legs:
        on, _ = _planner().leg(a, b, arr, {}, True, "on")
        off_pl = _planner()
        off_pl._mixed = lambda *x, **k: []
        off, _ = off_pl.leg(a, b, arr, {}, True, "off")
        assert (on is None) == (off is None), (a["name"], b["name"])
        if on is None:
            continue
        assert (on[0]["planned"], on[1], on[2]) == (off[0]["planned"], off[1], off[2]), (a["name"], b["name"])
        plain = [o for o in on[0]["options"] if not ("subway" in o["id"] and "bus" in o["id"])]
        strip = lambda o: {k: v for k, v in o.items() if k != "label"}       # noqa: E731 — 축별 사실 문구는 실린 후보끼리 비교라 바뀔 수 있다
        assert [strip(o) for o in plain] == [strip(o) for o in off[0]["options"]], (a["name"], b["name"])
