"""건물 안 장소는 출입구 → 도로 연결선 끝에서 걷기 시작(building_entrances · walk_router, 2026-10-19) — 합성 자료 시험 + 실자료 확인."""
import gzip
import json

import pytest

from app.domains.travel_ops.instances.mobility.engine.bike import BikeRouter
from app.domains.travel_ops.instances.mobility.engine.building_entrances import BuildingEntrances
from app.domains.travel_ops.instances.mobility.engine.car import hav
from app.domains.travel_ops.instances.mobility.engine.graph_router import FOOT_MPS, OPTIMISTIC_ACCESS_M
from app.domains.travel_ops.instances.mobility.engine.walk_router import Boundary, SeoulWalkRouter

Q = 1e6
SEOUL = [[(126.9, 37.5), (127.1, 37.5), (127.1, 37.6), (126.9, 37.6), (126.9, 37.5)]]
# 건물: 가운데 구멍(안뜰)이 있는 네모 — 바깥 126.990~126.992 · 37.550~37.552, 안뜰 126.9905~126.9915 · 37.5505~37.5515
OUTER = [(126.990, 37.550), (126.992, 37.550), (126.992, 37.552), (126.990, 37.552), (126.990, 37.550)]
HOLE = [(126.9905, 37.5505), (126.9915, 37.5505), (126.9915, 37.5515), (126.9905, 37.5515), (126.9905, 37.5505)]
INSIDE = (126.9902, 37.5510)                               # 건물 벽과 안뜰 사이(건물 안)
IN_HOLE = (126.9910, 37.5510)                              # 안뜰 — 건물 밖
FAR_OUT = (126.9950, 37.5510)                              # 건물 밖
ENT, ROAD_END = (126.9900, 37.5510), (126.9899, 37.5510)   # 서쪽 벽 출입구 → 길 쪽 연결선 끝
ENT_BAD, ROAD_BAD = (126.9920, 37.5510), (126.9921, 37.5510)  # 동쪽 벽 출입구(연결선 끝도 길에서 멂)
DEST = (127.0500, 37.5600)


def _ring(pts):
    return [c for p in pts for c in (int(round(p[0] * Q)), int(round(p[1] * Q)))]


def _write(tmp_path, ents):
    d = tmp_path / "building_entrance_seoul_v1"
    d.mkdir()
    row = {"k": "11110-1", "bb": [*_ring([OUTER[0]]), *_ring([OUTER[2]])], "r": [_ring(OUTER), _ring(HOLE)],
           "e": [[*_ring([en]), *_ring([re]), conn, kind] for en, re, conn, kind in ents]}
    with gzip.open(d / "buildings.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    (d / "MANIFEST.json").write_text(json.dumps({"version": "building_entrance_seoul_v1"}), encoding="utf-8")
    return BuildingEntrances(d)


def test_candidates_only_inside_the_building_not_in_its_courtyard(tmp_path):
    be = _write(tmp_path, [(ENT, ROAD_END, 8.5, "RM")])
    got = be.candidates(*INSIDE)
    assert [c["building"] for c in got] == ["11110-1"] and got[0]["kind"] == "RM" and got[0]["connect_m"] == 8.5
    assert got[0]["inner_m"] == pytest.approx(hav(INSIDE, ENT), abs=0.1)
    assert got[0]["road_end"] == pytest.approx(ROAD_END)
    assert be.candidates(*IN_HOLE) == [] and be.candidates(*FAR_OUT) == []


def test_missing_file_means_unavailable_and_no_candidates(tmp_path):
    be = BuildingEntrances(tmp_path / "없음")
    assert not be.available() and be.candidates(*INSIDE) == []


class Fake:
    """끝점이 길에서 먼지(snap)에 따라 낙관을 내는 합성 라우터 — 받은 끝점을 calls 에 남긴다."""

    def __init__(self, name, snap, dist=500.0):
        self.name, self.snap, self.dist, self.calls = name, snap, dist, []
        self.source_id, self.basis, self.is_local, self.url = f"{name}@x", f"{name}-basis", True, None

    def available(self):
        return True

    def nearest_snap_m(self, profile, lng, lat):
        return self.snap.get((round(lng, 6), round(lat, 6)), 3.0)

    def route(self, s, e, profile="car", via=None):
        self.calls.append((s, e))
        far = max(self.nearest_snap_m(profile, *s), self.nearest_snap_m(profile, *e)) > OPTIMISTIC_ACCESS_M
        return {"paths": [{"distance": self.dist, "time": int(self.dist / FOOT_MPS * 1000),
                           "foot_timing": {"flat_mps": FOOT_MPS, "stairs_m": 0.0, "seconds": self.dist / FOOT_MPS},
                           "quality": {"optimistic": far}}]}


def _router(tmp_path, ents, snap):
    base, seoul = Fake("base", snap, 520.0), Fake("seoul", snap, 500.0)
    return SeoulWalkRouter(base, seoul, Boundary([(SEOUL[0], [])]), entrances=_write(tmp_path, ents)), base, seoul


def test_both_far_then_start_moves_to_the_entrance_road_end_and_adds_inside_and_connector(tmp_path):
    snap = {INSIDE: 80.0, ROAD_END: 4.0, ROAD_BAD: 45.0}
    r, _base, seoul = _router(tmp_path, [(ENT, ROAD_END, 8.5, "RM"), (ENT_BAD, ROAD_BAD, 3.0, "RS")], snap)
    p = r.route(INSIDE, DEST, profile="foot")["paths"][0]
    assert seoul.calls[-1] == (pytest.approx(ROAD_END), DEST), "길에서 먼 출입구(연결선 끝 45 m)는 고르지 않는다"
    extra = hav(INSIDE, ENT) + 8.5
    assert p["distance"] == pytest.approx(500.0 + extra, abs=0.2)
    assert p["foot_timing"]["seconds"] == pytest.approx((500.0 + extra) / FOOT_MPS, abs=0.2)
    assert not p["quality"]["optimistic"]
    be = p["building_entrance"]
    assert be["start"]["building"] == "11110-1" and be["start"]["kind"] == "RM" and be["end"] is None
    assert be["added_m"] == pytest.approx(extra, abs=0.1) and "직선" in be["note"]
    wc = p["walk_candidates"]
    assert wc["chosen"] == "seoul_walk_network" and all(c["optimistic"] for c in wc["first_try"])


def test_entrance_road_end_also_far_keeps_the_original_optimistic_result(tmp_path):
    r, _b, _s = _router(tmp_path, [(ENT_BAD, ROAD_BAD, 3.0, "RS")], {INSIDE: 80.0, ROAD_BAD: 45.0})
    p = r.route(INSIDE, DEST, profile="foot")["paths"][0]
    assert p["quality"]["optimistic"] and "building_entrance" not in p, "거리를 지어내지 않는다 — 플래너가 미검증으로 막는다"


def test_both_ends_in_the_same_building_are_not_routed_out_and_back_in(tmp_path):
    """용산역처럼 장소와 출구가 같은 건물 안이면 출입구로 나갔다 들어오는 거리를 만들지 않는다 — 미검증 그대로."""
    other = (126.9903, 37.5512)                            # 같은 건물 안 다른 점
    r, _b, seoul = _router(tmp_path, [(ENT, ROAD_END, 8.5, "RM")], {INSIDE: 80.0, other: 70.0, ROAD_END: 4.0})
    p = r.route(INSIDE, other, profile="foot")["paths"][0]
    assert p["quality"]["optimistic"] and "building_entrance" not in p
    assert seoul.calls == [(INSIDE, other)], "다시 찾지 않는다"


def test_verified_path_is_used_as_is_without_asking_the_buildings(tmp_path):
    r, _b, seoul = _router(tmp_path, [(ENT, ROAD_END, 8.5, "RM")], {INSIDE: 12.0})
    p = r.route(INSIDE, DEST, profile="foot")["paths"][0]
    assert "building_entrance" not in p and seoul.calls == [(INSIDE, DEST)]


def test_far_point_outside_any_building_is_left_alone(tmp_path):
    r, _b, _s = _router(tmp_path, [(ENT, ROAD_END, 8.5, "RM")], {FAR_OUT: 80.0, ROAD_END: 4.0})
    p = r.route(FAR_OUT, DEST, profile="foot")["paths"][0]
    assert p["quality"]["optimistic"] and "building_entrance" not in p


def test_no_entrance_file_behaves_as_before(tmp_path):
    base, seoul = Fake("base", {INSIDE: 80.0}), Fake("seoul", {INSIDE: 80.0})
    r = SeoulWalkRouter(base, seoul, Boundary([(SEOUL[0], [])]), entrances=BuildingEntrances(tmp_path / "없음"))
    assert r.route(INSIDE, DEST, profile="foot")["paths"][0]["quality"]["optimistic"]


def test_bike_router_carries_the_entrance_evidence(tmp_path):
    r, _b, _s = _router(tmp_path, [(ENT, ROAD_END, 8.5, "RM")], {INSIDE: 80.0, ROAD_END: 4.0})
    got = BikeRouter(r, {}, "2026-10-19").route("foot", INSIDE[1], INSIDE[0], DEST[1], DEST[0])
    assert got["building_entrance"]["start"]["kind"] == "RM" and not got["optimistic"]


# ── 실자료(저장소 processed 자료가 있을 때만) ─────────────────────────────────────────────
def _real():
    from app.domains.travel_ops.instances.mobility.engine import paths
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
    from app.domains.travel_ops.instances.mobility.engine.walk_router import seoul_walk_dir
    paths.load_cli_env()
    d = seoul_walk_dir()
    be = BuildingEntrances(d.parent / "building_entrance_seoul_v1")
    if not be.available() or not (d / "edges.jsonl.gz").exists():
        pytest.skip("서울 보행 그래프 · 건물 출입구 자료 없음")
    return GraphRouter.shared(d), be


def test_real_station_building_place_gets_an_entrance_within_reach():
    """택시 웹 비교 쌍 T05 도착점(여의도 대형 상업 건물 안 · 보행 길까지 약 72 m — 2026-10-19 측정) — 출입구 연결선 끝은 길에서 30 m 안이다."""
    wg, be = _real()
    pt = (126.9284, 37.5259)
    if wg.nearest_snap_m("foot", *pt) <= OPTIMISTIC_ACCESS_M:
        pytest.skip("이 판 보행 그래프에서는 이미 길 가까이 — 시험 전제가 바뀜")
    cands = be.candidates(*pt)
    assert cands, "건물 안 점인데 출입구 후보가 없다"
    assert min(wg.nearest_snap_m("foot", *c["road_end"]) for c in cands) <= OPTIMISTIC_ACCESS_M
