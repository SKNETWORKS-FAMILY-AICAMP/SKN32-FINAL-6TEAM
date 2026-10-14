"""택시 후보의 `uses` 에 지나는 도로 구간 번호(`링크:`)를 싣는다 — 실제 이동 자료가 있을 때만 돈다(없으면 건너뜀).

☆`[2026-10-14]` 번호 체계를 TOPIS 대응표에서 **전국 표준 링크**(경찰청 UTIC 원문과 같은 체계)로 바꿨다 — 서울 실경보 28건의 원문 번호 133개 중
TOPIS 대응표에는 20개, 표준 링크 대응표(stdlink_v1)에는 128개가 있다(records/reports/2026-10-14_road_event_direction_stdlink/REPORT.md).
☆같은 날 v2: 경로 계산 도로망의 큰길·연결로 전체 + 일방통행 길은 갈 수 있는 방향만(records/reports/2026-10-14_road_event_direction_stdlink_v2/REPORT.md)."""
import datetime as dt
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "datasets/mobility/processed"
ENGINE = ROOT / "final_project_cs/app/domains/travel_ops/instances/mobility/engine"


@pytest.fixture(scope="module")
def svc():
    if (not (DATA / "mobility/graph/osm_way_seg_topis_link_v1.csv").exists() or not (DATA / "mobility/road_graph_v2/edges.jsonl.gz").exists()
            or not (DATA / "mobility/stdlink_v2/osm_way_seg_stdlink_v2.csv.gz").exists()):
        pytest.skip("이동 자료(graph · road_graph_v2 · stdlink_v2) 없음")
    from app.domains.travel_ops.instances.mobility.engine import paths
    paths.configure(DATA, source="test_taxi_link_uses")
    from app.domains.travel_ops.instances.mobility.engine.car import CarGraph, CarService
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    graph = CarGraph.load(DATA / "mobility/graph", read(ENGINE / "rules/holidays_2026_2027.json")["holidays"])
    return CarService(graph, GraphRouter.default(), read(ENGINE / "rules/rules_v0.3.json"))


DEPART = dt.datetime(2026, 10, 14, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
# 세종대로 위 두 점(광화문 앞 ↔ 시청 앞) — 양방향 큰길
A, B = (126.97690, 37.57170), (126.97795, 37.56620)


def test_std_link_ids_are_real(svc):
    go = svc.leg(A, B, DEPART, taxi=True)
    known = {lk for tab in svc.g.std.values() for lk in tab.values()}
    assert go["std_link_source"] == "stdlink_v2"
    assert go["std_link_ids"], "세종대로는 표준 링크가 붙은 큰길이다"
    assert set(go["std_link_ids"]) <= known, "대응표에 없는 번호를 지어내지 않는다"


def _way_with_both_directions(g):
    for way, tab in g.std.items():
        if way not in g.wayinfo:
            continue
        for (k, d), lk in tab.items():
            other = tab.get((k, "bwd" if d == "fwd" else "fwd"))
            if d == "fwd" and other and other != lk and k + 1 < len(g.wayinfo[way][1]):
                return way, k, lk, other
    pytest.skip("양방향 표준 링크가 다른 조각을 찾지 못했다")


def test_same_segment_gets_direction_specific_std_link(svc):
    """같은 도로 조각을 정방향으로 지나면 fwd 표준 링크, 거꾸로 지나면 bwd 표준 링크 — 반대 방향 사건 오탐을 막는 핵심."""
    g = svc.g
    way, k, fwd_link, bwd_link = _way_with_both_directions(g)
    pts = g.wayinfo[way][1][k:k + 2]
    def route(p):
        return {"paths": [{"points": {"coordinates": p}, "details": {"osm_way_id": [[0, len(p) - 1, way]]}, "distance": 0}]}
    forward = g.compute(route(pts), DEPART)["std_link_ids"]
    backward = g.compute(route(list(reversed(pts))), DEPART)["std_link_ids"]
    assert forward == [fwd_link] and backward == [bwd_link]


def _route(way, p):
    return {"paths": [{"points": {"coordinates": p}, "details": {"osm_way_id": [[0, len(p) - 1, way]]}, "distance": 0}]}


def _way_outside_topis_geom(g):
    for way, (_, pts) in g.std_geom.items():
        tab = g.std.get(way, {})
        for (k, d), lk in sorted(tab.items()):
            if k + 1 < len(pts):
                return way, k, d, lk, pts
    pytest.skip("v1 형상 밖 way 의 표준 링크를 찾지 못했다")


def test_way_outside_topis_geometry_gets_std_link(svc):
    """TOPIS 속도 자료가 없는 큰길(고가 연결로 등)도 표준 번호가 실린다 — v1 은 이런 길이 비어 내부순환도로 연결로 사건을 못 잡았다."""
    g = svc.g
    way, k, d, link, pts = _way_outside_topis_geom(g)
    assert way not in g.wayinfo
    seg = pts[k:k + 2] if d == "fwd" else list(reversed(pts[k:k + 2]))
    assert g.compute(_route(way, seg), DEPART)["std_link_ids"] == [link]


def test_std_geometry_does_not_change_duration(svc):
    """표준 번호용 형상은 번호만 찾는다 — 같은 경로의 소요 시간·속도 근거는 형상이 있든 없든 같다."""
    g = svc.g
    way, k, d, _, pts = _way_outside_topis_geom(g)
    seg = pts[k:k + 2] if d == "fwd" else list(reversed(pts[k:k + 2]))
    with_geom = g.compute(_route(way, seg), DEPART)
    saved, g.std_geom = g.std_geom, {}
    try:
        without = g.compute(_route(way, seg), DEPART)
    finally:
        g.std_geom = saved
    assert without["std_link_ids"] == []
    assert {k: v for k, v in with_geom.items() if k != "std_link_ids"} == {k: v for k, v in without.items() if k != "std_link_ids"}


def test_std_link_ids_follow_first_traversal_order_without_duplicates(svc):
    got = svc.leg(A, B, DEPART, taxi=True)
    assert len(got["std_link_ids"]) == len(set(got["std_link_ids"]))
