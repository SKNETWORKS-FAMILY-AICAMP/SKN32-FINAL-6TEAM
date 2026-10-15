# -*- coding: utf-8 -*-
"""역·지하상가 안 통로(walk_graph_seoul_v3 — 도로명주소 내부도로 전자지도)를 걷는 길에 쓴다 (2026-10-14).

합성 그래프 시험(자료 없이 돈다):
  · 지상으로 크게 돌아야 하는 두 점을 지하 통로가 짧게 잇는다 → 짧은 길을 고르고 응답에 지하 통로 거리(`indoor.m`)를 싣는다.
  · 지하 통로 간선은 붙임 대상(fmain)이 아니다 → 지하 통로 바로 위 지상 점도 지상 길에 붙는다(지상에서 출구로 들어간다).
  · 서울 도보 그래프 폴더는 v3 가 있으면 v3, 없으면 v2.
자료 시험(v3 가 있을 때만): 승강장 · 요금 구역을 넣지 않았는지, 지하 통로 간선이 붙임 대상이 아닌지.
근거: records/reports/2026-10-14_walk_indoor_v3/REPORT.md
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter

ROOT = Path(__file__).resolve().parents[5]
V3 = ROOT / "datasets/mobility/processed/mobility/walk_graph_seoul_v3"


def _enc(coords, precision=1e6):
    out, plat, plng = [], 0, 0
    for lng, lat in coords:
        for cur, prev in ((round(lat * precision), plat), (round(lng * precision), plng)):
            d = cur - prev
            d = ~(d << 1) if d < 0 else d << 1
            while d >= 0x20:
                out.append(chr((0x20 | (d & 0x1F)) + 63))
                d >>= 5
            out.append(chr(d + 63))
        plat, plng = round(lat * precision), round(lng * precision)
    return "".join(out)


LAT0, LON0 = 37.55, 127.0
#  지상: A(0,0) ─ 북으로 600 m ─ C ─ 동으로 100 m ─ D ─ 남으로 600 m ─ B(0,100 m)   (큰길을 건널 곳이 먼 경우)
#  지하: A ─ 계단 ─ 통로 100 m ─ 계단 ─ B
PTS = {1: (0.0, 0.0), 2: (0.0, 0.00113), 3: (0.0054, 0.0), 4: (0.0054, 0.00113),
       11: (0.00002, 0.0), 12: (0.00002, 0.00113)}


def _node(i):
    dlat, dlon = PTS[i]
    return {"id": i, "lat": LAT0 + dlat, "lon": LON0 + dlon, "r": 1}


def _edge(u, v, way, length, *, indoor=False, st=0):
    a, b = _node(u), _node(v)
    e = {"u": u, "v": v, "way": way, "sa": 0, "sb": 1, "len": length, "ow": 0, "hw": "footway", "ms": None,
         "car": 0, "bike": 0, "bow": 0, "foot": 1, "st": st, "main": 0, "bmain": 0, "fmain": 0 if indoor else 1,
         "g": _enc([(a["lon"], a["lat"]), (b["lon"], b["lat"])])}
    if indoor:
        e.update(src="juso_internal_road_202512", ind=1, kind="corridor")
    return e


def _records(with_indoor=True):
    nodes = [_node(i) for i in PTS]
    edges = [_edge(1, 3, 1, 600.0), _edge(3, 4, 2, 100.0), _edge(4, 2, 3, 600.0)]
    if with_indoor:
        edges += [_edge(1, 11, 10, 6.0, indoor=True, st=1), _edge(11, 12, 11, 100.0, indoor=True),
                  _edge(12, 2, 12, 6.0, indoor=True, st=1)]
    return {"nodes": nodes, "edges": edges}


def _pt(i):
    n = _node(i)
    return (n["lon"], n["lat"])


def test_indoor_passage_shortens_walk_and_is_reported():
    r = GraphRouter(records=_records())
    p = r.route(_pt(1), _pt(2), profile="foot")["paths"][0]
    assert p["distance"] < 200, "지하 통로(약 112 m)가 지상 우회(약 1,300 m)보다 짧다"
    assert p["indoor"]["m"] > 90
    assert p["foot_timing"]["stairs_m"] > 0, "계단 간선은 계단 시간으로 친다"


def test_without_indoor_edges_no_indoor_field():
    r = GraphRouter(records=_records(with_indoor=False))
    p = r.route(_pt(1), _pt(2), profile="foot")["paths"][0]
    assert p["distance"] > 1000
    assert "indoor" not in p


def test_point_above_passage_snaps_to_surface_not_underground():
    """지하 통로 한가운데 바로 위 지상 점 — 붙임은 지상 길(fmain)에만 하므로 지하 통로에 곧장 내려앉지 않는다."""
    r = GraphRouter(records=_records())
    mid = (LON0 + 0.000565, LAT0 + 0.00002)
    p = r.route(mid, _pt(1), profile="foot")["paths"][0]
    assert p["snap_m"][0] > 1.0, "가장 가까운 간선은 지하 통로지만 붙임은 지상 길"


def test_seoul_walk_dir_prefers_v3(tmp_path, monkeypatch):
    from app.domains.travel_ops.instances.mobility.engine import paths, walk_router
    base = tmp_path / "mobility"
    for v in ("walk_graph_seoul_v2", "walk_graph_seoul_v3"):
        (base / v).mkdir(parents=True)
    for f in ("nodes.jsonl.gz", "edges.jsonl.gz"):
        (base / "walk_graph_seoul_v2" / f).write_bytes(b"")
    monkeypatch.setattr(paths, "PROCESSED", tmp_path)
    assert walk_router.seoul_walk_dir().name == "walk_graph_seoul_v2", "v3 파일이 없으면 v2"
    for f in ("nodes.jsonl.gz", "edges.jsonl.gz"):
        (base / "walk_graph_seoul_v3" / f).write_bytes(b"")
    assert walk_router.seoul_walk_dir().name == "walk_graph_seoul_v3"


@pytest.fixture(scope="module")
def v3_indoor_edges():
    if not (V3 / "edges.jsonl.gz").exists():
        pytest.skip("walk_graph_seoul_v3 없음(자료 기기에서만)")
    with gzip.open(V3 / "edges.jsonl.gz", "rt", encoding="utf-8") as f:
        return [e for e in map(json.loads, f) if str(e.get("src") or "").startswith("juso_internal")]


def test_v3_has_no_platform_or_snappable_indoor_edges(v3_indoor_edges):
    assert v3_indoor_edges, "v3 에 지하 통로 간선이 있어야 한다"
    assert not [e for e in v3_indoor_edges if "승강장" in (e.get("name") or "")], "승강장(요금 구역) 통로는 넣지 않는다"
    assert all(e["fmain"] == 0 and e["foot"] == 1 for e in v3_indoor_edges), "지나갈 수는 있지만 붙임 대상은 아니다"
    kinds = {e["kind"] for e in v3_indoor_edges}
    assert {"corridor", "vertical", "surface_link"} <= kinds, "통로 · 오르내림 · 지상 출구 이음이 모두 있다"
