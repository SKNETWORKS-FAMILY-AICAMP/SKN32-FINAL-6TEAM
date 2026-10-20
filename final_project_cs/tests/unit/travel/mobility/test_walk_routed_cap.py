# -*- coding: utf-8 -*-
"""접근 걷기 길 거리 상한 — 2026-10-06 도입 · ☆2026-10-18 끔(사용자 결정).

도로 그래프(OSM)에 지하 통로·역 복합시설 연결이 없어 길 거리가 직선의 수 배로 나오던 자리를 막으려고 길 거리를 직선의 2배로 상한했다
(서울역 1호선 출구 73 m → 1,502 m · 롯데월드→잠실역 195 m → 699 m). 2026-10-18 점검에서 그 자리들은 다른 출구 고르기 · 서울시 도보 그래프 ·
역 연결 건물 목록으로 풀렸고, 상한이 실제로 하는 일은 남산 산길처럼 진짜 먼 길을 짧게 보이게 하는 것뿐이라 껐다
(records/reports/2026-10-18_walk_cap_off_and_taxi_receipts/REPORT.md). 아래 시험은 「꺼져 있다 · 길 거리를 그대로 쓴다 · 기록을 안 남긴다」를 본다.
"""
from __future__ import annotations

import logging
import math
from types import SimpleNamespace

from app.domains.travel_ops.instances.mobility.engine import plan as P

DETOUR, SPEED = 1.4, 1.04


class FakeBike:
    def __init__(self, meters, optimistic=False):
        self.router = SimpleNamespace(is_local=True)
        self.meters, self.optimistic, self.last_error = meters, optimistic, None

    def available(self):
        return True

    def route(self, prof, la1, lo1, la2, lo2):
        return {"distance_m": self.meters, "optimistic": self.optimistic}


def _planner(meters, optimistic=False):
    p = object.__new__(P.Planner)
    p.detour, p.speed, p._eff_cache = DETOUR, SPEED, {}
    p.v = SimpleNamespace(bike_router=FakeBike(meters, optimistic), R={}, bus=None, sc=None, ex=None)
    return p


def _eff(p, straight):
    return p._eff(37.57, 126.98, 37.5736, 126.98, straight)


def test_the_cap_is_off():
    assert P.WALK_ROUTED_CAP_PROPOSED is None, "2026-10-18 사용자 결정으로 껐다 — 켜려면 근거와 함께 다시 정한다"


def test_an_inflated_routed_distance_is_used_as_is_and_not_recorded(caplog):
    p = _planner(699.0)                                   # 직선 195 m 인데 길 699 m (3.6배) — 이제 깎지 않는다
    with caplog.at_level(logging.INFO):
        got = _eff(p, 195)
    assert math.isclose(got, 699.0 / DETOUR), "길 거리를 우회계수로 나눈 직선 환산 값 그대로"
    assert getattr(p, "walk_capped", []) == []
    assert not any("접근 걷기 상한" in r.getMessage() for r in caplog.records)


def test_a_real_long_walk_keeps_its_length():
    p = _planner(1624.0)                                  # 남산(N서울타워) → 정류장: 직선 473 m · 산길 1,624 m
    assert p._walk(_eff(p, 473)) == math.ceil(1624.0 / SPEED / 60) == 27


def test_a_normal_detour_is_left_alone():
    p = _planner(300.0)
    assert math.isclose(_eff(p, 195), 300.0 / DETOUR)
    assert getattr(p, "walk_capped", []) == []


def test_the_optimistic_floor_still_applies():
    p = _planner(100.0, optimistic=True)                  # 길 밖 접근이 길어 짧게 나온 값 — 직선×우회계수 와 큰 쪽(종전 규칙)
    assert math.isclose(_eff(p, 195), 195 * DETOUR / DETOUR) and getattr(p, "walk_capped", []) == []


# ── 같은 역의 다른 출구를 길 거리로 따진다(2026-10-06) ────────────────────────────────────────────────────

class _RouteByTarget:
    """목적지 위도마다 길 거리를 돌려주는 가짜 라우터 — 어느 출구로 갔는지 호출 기록으로 본다."""
    def __init__(self, by_lat):
        self.router = SimpleNamespace(is_local=True)
        self.by_lat, self.calls, self.last_error = by_lat, [], None

    def available(self):
        return True

    def route(self, prof, la1, lo1, la2, lo2):
        self.calls.append(round(la2, 4))
        return {"distance_m": self.by_lat[round(la2, 4)], "optimistic": False}


class _EX:
    def __init__(self, exits):
        self.exits = exits

    def exits_of(self, nm, line=None):
        return self.exits

    def nearest(self, nm, lat, lng, line=None):
        from app.domains.travel_ops.instances.mobility.engine.geo import meters
        best = min(self.exits, key=lambda e: meters(lat, lng, e["lat"], e["lng"]))
        return (meters(lat, lng, best["lat"], best["lng"]), best)


def _exit_planner(by_lat, exits):
    p = object.__new__(P.Planner)
    p.detour, p.speed, p._eff_cache = DETOUR, SPEED, {}
    p.v = SimpleNamespace(bike_router=SimpleNamespace(router=SimpleNamespace(is_local=True), available=lambda: True,
                                                      route=_RouteByTarget(by_lat).route), R={}, bus=None, sc=None, ex=_EX(exits))
    p._rt = p.v.bike_router.route.__self__
    return p


PLACE = {"lat": 37.5700, "lon": 126.9800}
NEAR = {"lat": 37.5712, "lng": 126.9800}          # 직선 ≈ 133 m — 가장 가까운 출구(큰 도로 건너편이라 길이 멀다)
FAR_OK = {"lat": 37.5720, "lng": 126.9800}        # 직선 ≈ 222 m — 길이 곧다


def test_a_better_exit_is_taken_when_the_nearest_one_needs_a_long_way_round():
    p = _exit_planner({round(NEAR["lat"], 4): 900.0, round(FAR_OK["lat"], 4): 260.0}, [NEAR, FAR_OK])
    straight_near = 133.4
    d_eff = 900.0 / DETOUR                              # 가장 가까운 출구의 직선 환산(상한 안이라고 가정)
    got = p._better_exit(PLACE, "시청", "01호선", d_eff, (NEAR["lat"], NEAR["lng"]))
    assert math.isclose(got, 260.0 / DETOUR), "길 거리가 더 짧은 출구로 바꾼다"
    assert p.exit_switched == [{"station": "시청", "from_routed_m": 900, "to_routed_m": 260}], "조용한 보정이 아니다 — 기록이 남는다"
    assert straight_near > 0


def test_the_nearest_exit_is_kept_when_no_other_exit_is_shorter():
    p = _exit_planner({round(NEAR["lat"], 4): 400.0, round(FAR_OK["lat"], 4): 600.0}, [NEAR, FAR_OK])
    got = p._better_exit(PLACE, "시청", "01호선", 400.0 / DETOUR, (NEAR["lat"], NEAR["lng"]))
    assert math.isclose(got, 400.0 / DETOUR) and getattr(p, "exit_switched", []) == []


def test_without_an_exit_table_with_exits_of_nothing_changes():
    p = _exit_planner({}, [])
    p.v.ex = SimpleNamespace(nearest=lambda *a, **k: None)            # exits_of 가 없는 출구표(옛 모양)
    assert p._better_exit(PLACE, "시청", None, 123.0, (0, 0)) == 123.0


def test_other_exits_are_not_routed_unless_the_nearest_looks_wrong():
    """정상(길이 직선의 1.5배 안)이면 다른 출구는 라우팅하지 않는다 — 호출을 아낀다."""
    sc = SimpleNamespace(stations_near=lambda la, lo, m: [(150.0, {"station_nm": "가", "line": "1", "lat": 37.5712, "lng": 126.98})],
                         group_lines=lambda rec: {rec["line"]})
    p = _exit_planner({round(NEAR["lat"], 4): 160.0, round(FAR_OK["lat"], 4): 100.0}, [NEAR, FAR_OK])
    p.v.sc = sc
    p._station_k = lambda: 3
    p._blocked_station = lambda rec: False
    out = p._near_stations(PLACE, 1000)
    assert out and p._rt.calls == [round(NEAR["lat"], 4)], "가장 가까운 출구 한 번만"
