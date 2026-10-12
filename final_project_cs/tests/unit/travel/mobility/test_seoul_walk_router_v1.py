"""서울 안 걸음은 서울시 도보 그래프와 기존 라우터로 함께 찾아 검증된 짧은 길을 고르는 중계 라우터(walk_router) — 합성 자료 시험."""
import json

import pytest

from app.domains.travel_ops.instances.mobility.engine.bike import BikeRouter
from app.domains.travel_ops.instances.mobility.engine.car import RouterDown
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from app.domains.travel_ops.instances.mobility.engine.walk_router import (
    SEOUL_WALK_BASIS, Boundary, SeoulWalkRouter, wrap_with_seoul_walk)

SQUARE = [[(126.9, 37.5), (127.1, 37.5), (127.1, 37.6), (126.9, 37.6), (126.9, 37.5)]]
IN_A, IN_B, OUT = (126.95, 37.55), (127.05, 37.56), (127.2, 37.55)


class Fake:
    def __init__(self, name, fail=False, dist=100.0, optimistic=False):
        self.name, self.fail, self.calls, self.dist, self.optimistic = name, fail, [], dist, optimistic
        self.source_id, self.basis, self.is_local, self.url = f"{name}@x", f"{name}-basis", True, None

    def available(self):
        return True

    def route(self, s, e, profile="car", via=None):
        self.calls.append((s, e, profile))
        if self.fail:
            raise RouterDown("no_path: 합성")
        return {"paths": [{"distance": self.dist, "time": 72000, "quality": {"optimistic": self.optimistic}}]}


def _router(seoul_fail=False, seoul=100.0, base=150.0, seoul_opt=False, base_opt=False, base_fail=False):
    b, sw = Fake("base", fail=base_fail, dist=base, optimistic=base_opt), Fake("seoul", fail=seoul_fail, dist=seoul, optimistic=seoul_opt)
    return SeoulWalkRouter(b, sw, Boundary([(SQUARE[0], [])])), b, sw


def test_foot_inside_seoul_asks_both_and_picks_shorter_verified():
    r, base, seoul = _router(seoul=100.0, base=150.0)
    p = r.route(IN_A, IN_B, profile="foot")["paths"][0]
    assert len(seoul.calls) == 1 and len(base.calls) == 1
    assert p["source_id"] == "seoul@x" and p["basis"] == SEOUL_WALK_BASIS
    wc = p["walk_candidates"]
    assert wc["chosen"] == "seoul_walk_network" and [c["distance_m"] for c in wc["candidates"]] == [100.0, 150.0]
    r, base, seoul = _router(seoul=180.0, base=150.0)
    p = r.route(IN_A, IN_B, profile="foot")["paths"][0]
    assert p["source_id"] == "base@x" and p["walk_candidates"]["chosen"] == "base"


def test_optimistic_candidate_is_not_preferred():
    r, _b, _s = _router(seoul=90.0, seoul_opt=True, base=150.0)
    p = r.route(IN_A, IN_B, profile="foot")["paths"][0]
    assert p["walk_candidates"]["chosen"] == "base", "접근 미검증(낙관) 경로는 짧아도 고르지 않는다"
    r, _b, _s = _router(seoul=90.0, seoul_opt=True, base=150.0, base_opt=True)
    p = r.route(IN_A, IN_B, profile="foot")["paths"][0]
    assert p["quality"]["optimistic"], "둘 다 낙관이면 낙관 표시 그대로 — 플래너가 막는다"


@pytest.mark.parametrize("s,e,profile", [(IN_A, OUT, "foot"), (OUT, IN_A, "foot"), (IN_A, IN_B, "car"), (IN_A, IN_B, "bike")])
def test_outside_or_not_foot_uses_base(s, e, profile):
    r, base, seoul = _router()
    doc = r.route(s, e, profile=profile)
    assert base.calls == [(s, e, profile)] and not seoul.calls
    assert doc["paths"][0]["source_id"] == "base@x" and "walk_candidates" not in doc["paths"][0]


def test_one_source_failing_is_recorded_and_both_failing_raises():
    r, _base, _seoul = _router(seoul_fail=True)
    p = r.route(IN_A, IN_B, profile="foot")["paths"][0]
    c = p["walk_candidates"]["candidates"]
    assert p["walk_candidates"]["chosen"] == "base" and c[0]["source"] == "seoul_walk_network" and "RouterDown" in c[0]["error"]
    r, _base, _seoul = _router(seoul_fail=True, base_fail=True)
    with pytest.raises(RouterDown):
        r.route(IN_A, IN_B, profile="foot")


def test_bike_router_records_per_route_source():
    r, _base, _seoul = _router()
    br = BikeRouter(r, {}, "2026-09-18")
    got = br.route("foot", IN_A[1], IN_A[0], IN_B[1], IN_B[0])
    assert got["source_id"] == "seoul@x" and got["basis"] == SEOUL_WALK_BASIS and got["walk_candidates"]["chosen"] == "seoul_walk_network"
    got = br.route("foot", IN_A[1], IN_A[0], OUT[1], OUT[0])
    assert got["source_id"] == "base@x"
    r2, _b, _s = _router(seoul_fail=True, base_fail=True)
    br2 = BikeRouter(r2, {}, "2026-09-18")
    assert br2.route("foot", IN_A[1], IN_A[0], IN_B[1], IN_B[0]) is None
    assert br2.last_error["kind"] == "router_down", "실패는 근거와 함께 드러난다"


def test_boundary_hole_and_bbox():
    hole = [(126.99, 37.54), (127.01, 37.54), (127.01, 37.56), (126.99, 37.56), (126.99, 37.54)]
    b = Boundary([(SQUARE[0], [hole])])
    assert b.contains(*IN_A) and not b.contains(127.0, 37.55) and not b.contains(*OUT)


def test_wrap_needs_graph_and_boundary(tmp_path):
    base = Fake("base")
    got, why = wrap_with_seoul_walk(base, tmp_path / "missing")
    assert got is base and "없음" in why
    d = tmp_path / "walk_graph_seoul_v2"
    d.mkdir()
    for fn in ("nodes.jsonl.gz", "edges.jsonl.gz"):
        (d / fn).write_bytes(b"")
    got, why = wrap_with_seoul_walk(base, d)
    assert got is base and "경계 파일 없음" in why, "경계 없이는 서울 안을 가를 수 없다 — 그래프를 쓰지 않고 이유를 낸다(멈추지 않는다)"
    (d / "seoul_boundary.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": SQUARE}}]}), encoding="utf-8")
    got, why = wrap_with_seoul_walk(base, d)
    assert isinstance(got, SeoulWalkRouter) and why is None


def test_seoul_graph_source_id_from_manifest(tmp_path):
    (tmp_path / "MANIFEST.json").write_text(json.dumps(
        {"version": "walk_graph_seoul_v2", "work_dates": ["2026-10-12"], "osm_data_at": "2026-10-03T20:20:50Z"}), encoding="utf-8")
    assert GraphRouter(tmp_path).source_id == "seoul_walk_network@2026-10-12+osm_steps@2026-10-03"


def _enc(pts):
    out, plat, plon = [], 0, 0
    for lat, lon in pts:
        a, b = int(round(lat * 1e6)), int(round(lon * 1e6))
        for v in (a - plat, b - plon):
            v = ~(v << 1) if v < 0 else (v << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1f)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = a, b
    return "".join(out)


def test_stairs_edge_in_seoul_format_adds_stairs_time():
    """서울시 도보 그래프 형식(걸음 전용 · st 칸) 그대로 — 계단 간선은 계단 시간으로 친다."""
    n = [{"id": 1, "lat": 37.55, "lon": 126.95}, {"id": 2, "lat": 37.55, "lon": 126.951}, {"id": 3, "lat": 37.55, "lon": 126.952}]
    def edge(u, v, st):
        a, b = next(x for x in n if x["id"] == u), next(x for x in n if x["id"] == v)
        return {"u": u, "v": v, "way": u, "len": 88.0, "hw": "footway", "ms": None, "car": 0, "bike": 0, "bow": 0, "ow": 0,
                "foot": 1, "fmain": 1, "st": st, "g": _enc([(a["lat"], a["lon"]), (b["lat"], b["lon"])])}
    flat = GraphRouter(records={"nodes": n, "edges": [edge(1, 2, 0), edge(2, 3, 0)]})
    stair = GraphRouter(records={"nodes": n, "edges": [edge(1, 2, 0), edge(2, 3, 1)]})
    s, e = (126.95, 37.55), (126.952, 37.55)
    pf = flat.route(s, e, "foot")["paths"][0]
    ps = stair.route(s, e, "foot")["paths"][0]
    assert ps["foot_timing"]["stairs_m"] > 80 and pf["foot_timing"]["stairs_m"] == 0
    assert ps["foot_timing"]["seconds"] > pf["foot_timing"]["seconds"]
    assert abs(ps["distance"] - pf["distance"]) < 0.01, "거리는 같고 시간만 계단만큼 늘어난다"
