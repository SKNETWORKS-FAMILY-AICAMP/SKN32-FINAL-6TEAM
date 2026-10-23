# datasets/mobility/scripts/check_road_graph_v1.py — road_graph_v1 검수 (76번 방 · 2026-09-29)
# ① 노드·간선 수 ② 연결 성분(차량 약연결·강연결 / 자전거) — 최대 성분 비율 · 떨어진 섬 목록
# ③ 353 도로 시험 좌표(road_test_expected_v1.csv 양끝)가 차량 간선 200 m 안에 스냅되는지 — 스냅만(경로 계산은 77)
# ④ osm_way_seg_topis_link_v1.csv 의 (way, seg_idx) 가 간선 [sa, sb) 로 이어지는 비율 + 좌표 정렬(osm_way_geom_v1.csv)
# 경로는 계산·저장하지 않는다. 규칙 26: import 는 값만.
# 실행: python datasets/mobility/scripts/check_road_graph_v1.py [--graph <road_graph_v1 폴더>] [--gh-dir <graph 폴더>] [--out <json>]
import argparse, csv, gzip, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "final_project_cs" / "app").is_dir())   # 82: 저장소 루트를 위로 찾는다(자리 datasets/mobility/scripts/)
for _p in (REPO, Path(__file__).resolve().parent):          # 82: 옆 _paths.py 를 부른다
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
SNAP_M = 200


def dec_polyline(s, prec=6):
    f = 10 ** prec; i = lat = lon = 0; out = []
    while i < len(s):
        vals = []
        for _ in range(2):
            sh = r = 0
            while True:
                b = ord(s[i]) - 63; i += 1; r |= (b & 0x1f) << sh; sh += 5
                if b < 0x20:
                    break
            vals.append(~(r >> 1) if r & 1 else r >> 1)
        lat += vals[0]; lon += vals[1]; out.append((lat / f, lon / f))
    return out


def read_gz(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph"); ap.add_argument("--gh-dir"); ap.add_argument("--out")
    a = ap.parse_args()
    if not (a.graph and a.gh_dir):
        from _paths import PROCESSED
        a.graph = a.graph or str(PROCESSED / "mobility" / "road_graph_v1")
        a.gh_dir = a.gh_dir or str(PROCESSED / "mobility" / "graph")
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    import shapely
    from shapely.geometry import LineString, Point
    g, gh = Path(a.graph), Path(a.gh_dir)
    rep = {}
    nodes = {r["id"]: (r["lat"], r["lon"]) for r in read_gz(g / "nodes.jsonl.gz")}
    edges = list(read_gz(g / "edges.jsonl.gz"))
    rep["counts"] = {"nodes": len(nodes), "edges": len(edges), "car": sum(e["car"] for e in edges),
                     "bike": sum(e["bike"] for e in edges), "hw": dict(Counter(e["hw"] for e in edges).most_common()),
                     "ow": dict(Counter(e["ow"] for e in edges if e["car"]))}
    idx = {n: i for i, n in enumerate(nodes)}
    ids = list(nodes)
    lat0 = 37.55; kx = 111320 * math.cos(math.radians(lat0)); ky = 110540

    def comps(sel, directed):
        us, vs = [], []
        for e in edges:
            if not sel(e):
                continue
            o = e["ow"] if sel is car_sel else e["bow"]
            u, v = idx[e["u"]], idx[e["v"]]
            if not directed or o in (0, 1): us.append(u); vs.append(v)
            if not directed or o in (0, -1): us.append(v); vs.append(u)
        used = set(us) | set(vs)
        n = len(ids)
        M = coo_matrix((np.ones(len(us)), (us, vs)), shape=(n, n)).tocsr()
        k, lab = connected_components(M, directed=directed, connection="strong")
        c = Counter(lab[i] for i in used)
        big = c.most_common(1)[0]
        islands = []
        for comp, sz in c.most_common()[1:]:
            mem = [i for i in used if lab[i] == comp] if sz >= 20 else None
            if mem:
                la = sum(nodes[ids[i]][0] for i in mem) / len(mem); lo = sum(nodes[ids[i]][1] for i in mem) / len(mem)
                islands.append({"nodes": sz, "center": [round(la, 5), round(lo, 5)]})
        return {"used_nodes": len(used), "components": len(c), "largest": big[1],
                "largest_ratio": round(big[1] / len(used), 4),
                "outside_nodes": len(used) - big[1],
                "islands_ge20": islands[:40], "n_islands_ge20": len(islands),
                "size_hist": dict(Counter(min(sz, 20) for _, sz in c.most_common()[1:])),
                }, lab, big[0]

    car_sel = lambda e: e["car"] == 1
    bike_sel = lambda e: e["bike"] == 1
    rep["cc_car_weak"], labw, bw = comps(car_sel, False)
    rep["cc_car_strong"], labs, bs = comps(car_sel, True)
    rep["cc_bike_weak"], _, _ = comps(bike_sel, False)
    print("[성분]", {k: {x: rep[k][x] for x in ("components", "largest_ratio", "outside_nodes", "n_islands_ge20")} for k in ("cc_car_weak", "cc_car_strong", "cc_bike_weak")})

    # ── ③ 353 도로 스냅 ──
    geoms, einfo = [], []
    for e in edges:
        if not e.get("main", e["car"]):          # 77 과 같게: 차량 최대 강연결 성분 간선에만 스냅
            continue
        pts = dec_polyline(e["g"])
        geoms.append(LineString([(lo * kx, la * ky) for la, lo in pts]))
        einfo.append(e)
    tree = shapely.STRtree(geoms)
    ends = {}
    for r in csv.DictReader(open(gh / "road_test_expected_v1.csv", encoding="utf-8-sig")):
        key = (r["road"], r["dir"])
        ends[key] = [(float(r["start_lat"]), float(r["start_lng"])), (float(r["end_lat"]), float(r["end_lng"]))]
    snaps, fails = [], []
    for key, pp in ends.items():
        for tag, (la, lo) in zip(("start", "end"), pp):
            p = Point(lo * kx, la * ky)
            j = tree.nearest(p); d = geoms[j].distance(p)
            in_big_strong = labs[idx[einfo[j]["u"]]] == bs
            snaps.append(d)
            if d > SNAP_M or not in_big_strong:
                fails.append({"road": key[0], "dir": key[1], "end": tag, "dist_m": round(d, 1), "hw": einfo[j]["hw"],
                              "way": einfo[j]["way"], "in_largest_strong": bool(in_big_strong)})
    snaps.sort()
    q = lambda p: round(snaps[min(len(snaps) - 1, int(p * len(snaps)))], 1)
    rep["snap353"] = {"roads": len(ends), "points": len(snaps), "within_200m": sum(d <= SNAP_M for d in snaps),
                      "p50_m": q(.5), "p90_m": q(.9), "p99_m": q(.99), "max_m": round(snaps[-1], 1), "fails_or_offcomp": fails}
    print("[스냅]", {k: v for k, v in rep["snap353"].items() if k != "fails_or_offcomp"}, "예외", len(fails))

    # 랜드마크(좌표는 지도에서 읽은 대략값 · 추정 — 스냅 확인용일 뿐 산출에 안 들어감)
    lm = {"인천공항 T1": (37.4486, 126.4509), "인천공항 T2": (37.4687, 126.4332), "김포공항 국내선": (37.5594, 126.8025),
          "서울역": (37.5547, 126.9707), "강남역": (37.4979, 127.0276), "판교역(성남)": (37.3947, 127.1112),
          "킨텍스(고양)": (37.6688, 126.7456), "서울대공원(과천)": (37.4363, 127.0060), "스타필드 하남": (37.5453, 127.2238),
          "부천역": (37.4843, 126.7827), "광명역": (37.4165, 126.8848), "구리역": (37.6033, 127.1437),
          "김포시청": (37.6153, 126.7156)}
    rep["landmarks"] = {}
    for k, (la, lo) in lm.items():
        p = Point(lo * kx, la * ky); j = tree.nearest(p)
        rep["landmarks"][k] = {"dist_m": round(geoms[j].distance(p), 1), "hw": einfo[j]["hw"]}
    print("[랜드마크]", {k: v["dist_m"] for k, v in rep["landmarks"].items()})

    # 범위 안 노드 기준 성분(여백 3 km 제외)
    if "r" in next(iter(read_gz(g / "nodes.jsonl.gz"))):
        rin = {r["id"] for r in read_gz(g / "nodes.jsonl.gz") if r["r"]}
        cm = set()
        for e in edges:
            if e.get("main"):
                cm.add(e["u"]); cm.add(e["v"])
        carn = set()
        for e in edges:
            if e["car"]:
                carn.add(e["u"]); carn.add(e["v"])
        rep["in_region"] = {"car_nodes": len(carn & rin), "car_main_nodes": len(cm & rin),
                            "car_main_ratio": round(len(cm & rin) / max(1, len(carn & rin)), 4)}
        print("[범위 안]", rep["in_region"])

    # ── ④ TOPIS 링크 연결 ──
    by_way = defaultdict(list)
    for e in edges:
        by_way[e["way"]].append((e["sa"], e["sb"], e))
    link_rows = list(csv.DictReader(open(gh / "osm_way_seg_topis_link_v1.csv", encoding="utf-8-sig")))
    lw = {int(r["osm_way_id"]) for r in link_rows}
    ok_seg = 0; ok_dir = 0; miss_way = Counter()
    for r in link_rows:
        w, s = int(r["osm_way_id"]), int(r["seg_idx"])
        hit = [e for sa, sb, e in by_way.get(w, []) if sa <= s < sb]
        if hit:
            ok_seg += 1
            e = hit[0]
            if e["ow"] == 0 or (e["ow"] == 1 and r["dir"] == "fwd") or (e["ow"] == -1 and r["dir"] == "bwd"):
                ok_dir += 1
        else:
            miss_way[w] += 1
    geo_ok = geo_n = 0; geo_bad = []
    gpath = gh / "osm_way_geom_v1.csv"
    if gpath.exists():
        for r in csv.DictReader(open(gpath, encoding="utf-8-sig")):
            w = int(r["osm_way_id"])
            if w not in by_way:
                continue
            pts = [tuple(map(float, p.split(","))) for p in r["pts"].split(" ")]   # (lon, lat)
            geo_n += 1
            good = True
            for sa, sb, e in by_way[w]:
                gp = dec_polyline(e["g"])
                if sb >= len(pts) or abs(gp[0][0] - pts[sa][1]) > 2e-6 or abs(gp[-1][1] - pts[sb][0]) > 2e-6:
                    good = False; break
            geo_ok += good
            if not good and len(geo_bad) < 10:
                geo_bad.append(w)
    rep["topis_link"] = {"link_ways": len(lw), "ways_in_graph": len(lw & set(by_way)),
                         "way_pct": round(100 * len(lw & set(by_way)) / len(lw), 2),
                         "seg_rows": len(link_rows), "seg_in_edge": ok_seg, "seg_pct": round(100 * ok_seg / len(link_rows), 2),
                         "seg_dir_allowed": ok_dir, "missing_ways": len(miss_way), "missing_way_ids_sample": list(miss_way)[:20],
                         "geom_ways_checked": geo_n, "geom_index_aligned": geo_ok, "geom_misaligned_sample": geo_bad}
    print("[TOPIS]", {k: v for k, v in rep["topis_link"].items() if "sample" not in k})
    outp = Path(a.out) if a.out else g / "check_report.json"
    outp.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→", outp)


if __name__ == "__main__":
    main()
