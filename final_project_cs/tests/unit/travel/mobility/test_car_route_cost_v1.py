"""자동차 길 선택에 TOPIS 시간대 속도를 쓰는 비용(car_route_cost) — 합성 그래프 시험(자료 없이 돈다)."""
import datetime as dt
import types

import pytest

from app.domains.travel_ops.instances.mobility.engine.car_route_cost import BucketCost, TopisRouteCost
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from tests.unit.travel.mobility.test_graph_router import encode_polyline

#   A(0) ── 골목 짧은 길(200 m, residential) ── B(1)
#   A(0) ── 큰길 1(250 m, primary) ── C(2) ── 큰길 2(250 m, primary) ── B(1)
LAT, LON = 37.55, 127.0
NODES = [{"id": 1, "lat": LAT, "lon": LON}, {"id": 2, "lat": LAT, "lon": LON + 0.00226},
         {"id": 3, "lat": LAT + 0.0016, "lon": LON + 0.00113}]


def _edge(u, v, way, hw, length):
    a, b = NODES[u - 1], NODES[v - 1]
    return {"u": u, "v": v, "way": way, "len": length, "hw": hw, "ms": None, "car": 1, "bike": 0, "bow": 0, "ow": 0,
            "main": 1, "bmain": 0, "g": encode_polyline([(a["lon"], a["lat"]), (b["lon"], b["lat"])])}


def _router():
    return GraphRouter(records={"nodes": NODES, "edges": [_edge(1, 2, 10, "residential", 200.0),
                                                          _edge(1, 3, 20, "primary", 250.0), _edge(3, 2, 21, "primary", 250.0)]})


class FakeGraph:
    """CarGraph 의 속도 표 모양만 — TOPIS 링크 L20·L21 은 시각에 따라 속도가 다르다."""

    def __init__(self):
        self.prof = {("L20", "평일", 3): 60.0, ("L21", "평일", 3): 60.0, ("L20", "평일", 18): 8.0, ("L21", "평일", 18): 8.0}
        self.cf = {"주간선도로": {"mean_kmh": {"평일": [25.0] * 24}}}

    def daytype(self, t):
        return "평일"


def _cost(router):
    rc = object.__new__(TopisRouteCost)
    rc.g, rc.router = FakeGraph(), router
    router._load()
    way_link = {20: ("L20", "L20"), 21: ("L21", "L21")}
    rc.elink = [way_link.get(router.eway[e]) for e in range(len(router.eu))]
    rc.version = "car_edge_link_v1"
    rc._w, rc._lock = __import__("collections").OrderedDict(), __import__("threading").Lock()
    return rc


def _ways(doc):
    return [w for _a, _b, w in doc["paths"][0]["details"]["osm_way_id"]]


S, E = (LON + 0.00001, LAT), (LON + 0.00225, LAT)


def test_route_follows_topis_speed_of_departure_hour():
    r = _router()
    rc = _cost(r)
    night = r.route(S, E, "car", car_cost=rc.at(dt.datetime(2026, 10, 13, 3, 0)))
    rush = r.route(S, E, "car", car_cost=rc.at(dt.datetime(2026, 10, 13, 18, 0)))
    assert set(_ways(night)) == {20, 21}, "새벽 큰길 60 km/h — 골목(15 km/h)보다 긴 큰길이 빠르다"
    assert _ways(rush) == [10], "퇴근 큰길 8 km/h — 짧은 골목이 빠르다"
    assert night["paths"][0]["route_cost"] == {"kind": "topis_profile", "day_type": "평일", "hour": 3, "edge_link": "car_edge_link_v1"}


def test_without_cost_router_keeps_static_class_speed():
    r = _router()
    doc = r.route(S, E, "car")
    assert doc["paths"][0]["route_cost"] == {"kind": "static_class_speed"}
    # 고정 속도(골목 15 · 큰길 40 km/h): 200 m 골목 48초 > 500 m 큰길 45초 → 큰길. 시각에 따라 바뀌지 않는다.
    assert set(_ways(doc)) == {20, 21}


def test_speed_fallback_order_matches_compute():
    r = _router()
    rc = _cost(r)
    e_alley = next(e for e in range(len(r.eu)) if r.eway[e] == 10)
    e_main = next(e for e in range(len(r.eu)) if r.eway[e] == 20)
    assert rc.edge_seconds(e_alley, ("평일", 3)) == pytest.approx(200.0 / (15 / 3.6))     # 골목 정적 속도(DEFAULT_KMH)
    assert rc.edge_seconds(e_main, ("평일", 3)) == pytest.approx(250.0 / (60 / 3.6))      # TOPIS 링크
    assert rc.edge_seconds(e_main, ("평일", 12)) == pytest.approx(250.0 / (25 / 3.6))     # 링크 시각 없음 → 도로급 계수


def test_weights_align_with_adjacency_and_are_cached():
    r = _router()
    rc = _cost(r)
    _deg, _to, pe, _w = r._adjacency("car")
    w = rc.weights(("평일", 3))
    assert len(w) == len(pe)
    for k, code in enumerate(pe):
        assert w[k] == pytest.approx(rc.edge_seconds(code >> 1, ("평일", 3)), rel=1e-6)
    assert rc.weights(("평일", 3)) is w


def test_try_load_refuses_non_local_router_and_missing_table(tmp_path):
    got, why = TopisRouteCost.try_load(types.SimpleNamespace(dir=tmp_path / "graph"), object())
    assert got is None and "로컬" in why
    r = _router()
    r.dir = tmp_path / "road"
    got, why = TopisRouteCost.try_load(types.SimpleNamespace(dir=tmp_path / "graph"), r)
    assert got is None and "대응표 없음" in why


def test_bucket_cost_evidence():
    rc = types.SimpleNamespace(version="car_edge_link_v1")
    assert BucketCost(rc, ("휴일", 9)).evidence()["day_type"] == "휴일"
