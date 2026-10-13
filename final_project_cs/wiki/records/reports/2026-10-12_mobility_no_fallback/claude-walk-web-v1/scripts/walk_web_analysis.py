"""카카오 웹 도보 관측(W01~W04)과 제품 보행 그래프 대조 — 읽기 전용 진단. 제품 코드를 바꾸지 않는다."""
import json, math, sys, hashlib
from pathlib import Path

ROOT = Path(r"C:\Users\playdata2\Documents\final_workspace")
sys.path.insert(0, str(ROOT / "final_project_cs"))
OBS = ROOT / "datasets/mobility/raw/mobility_walk_web_20261012_v3/kakao-walk-observed-v1.json"
OUT = Path(sys.argv[1])

from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, hav, F_FOOT, F_FMAIN  # noqa: E402

obs = json.loads(OBS.read_text(encoding="utf-8"))

# 1) WCONG → WGS84 국소 아핀(요청점 8개로 최소제곱). 근거: 카카오 화면이 링크의 위경도를 정수 WCONG 로 바꾼 쌍.
pairs = []
for r in obs["rows"]:
    for k in ("from", "to"):
        q = r["request"][k]
        pairs.append((q["wcong"][0], q["wcong"][1], q["lat"], q["lon"]))


def lstsq(rows, ys):
    # 3x3 정규방정식
    n = 3
    A = [[sum(a[i] * a[j] for a in rows) for j in range(n)] for i in range(n)]
    b = [sum(a[i] * y for a, y in zip(rows, ys)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(A[r][i]))
        A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n):
                A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (b[i] - sum(A[i][c] * x[c] for c in range(i + 1, n))) / A[i][i]
    return x


x0, y0 = 500000.0, 1128000.0
rows = [((x - x0) / 1000, (y - y0) / 1000, 1.0) for x, y, _, _ in pairs]
clat = lstsq(rows, [p[2] for p in pairs])
clon = lstsq(rows, [p[3] for p in pairs])


def w2g(x, y):
    a = ((x - x0) / 1000, (y - y0) / 1000, 1.0)
    return (sum(c * v for c, v in zip(clon, a)), sum(c * v for c, v in zip(clat, a)))  # (lng, lat)


resid = [hav(w2g(x, y), (lon, lat)) for x, y, lat, lon in pairs]
# 교차 검증: 한 점씩 빼고 맞춘 뒤 뺀 점의 오차
loo = []
for i in range(len(pairs)):
    pr = [p for j, p in enumerate(pairs) if j != i]
    rr = [((x - x0) / 1000, (y - y0) / 1000, 1.0) for x, y, _, _ in pr]
    a_lat, a_lon = lstsq(rr, [p[2] for p in pr]), lstsq(rr, [p[3] for p in pr])
    x, y, lat, lon = pairs[i]
    a = ((x - x0) / 1000, (y - y0) / 1000, 1.0)
    loo.append(hav((sum(c * v for c, v in zip(a_lon, a)), sum(c * v for c, v in zip(a_lat, a))), (lon, lat)))

report = {"scope": "읽기 전용 진단 — 제품 코드·자료 변경 없음 · 지도 개발자 API 호출 0회",
          "observation_file": str(OBS.relative_to(ROOT)).replace("\\", "/"),
          "observation_sha256": hashlib.sha256(OBS.read_bytes()).hexdigest(),
          "transform": {"method": "요청점 8개 최소제곱 아핀(WCONG→위경도)", "fit_residual_m": [round(v, 2) for v in resid],
                        "leave_one_out_error_m": [round(v, 2) for v in loo]},
          "rows": []}

from app.domains.travel_ops.instances.mobility.engine import paths as _paths
_paths.configure('datasets/mobility/processed')
import os as _os
gr = GraphRouter(Path(_os.environ['GRAPH_DIR'])) if _os.environ.get('GRAPH_DIR') else GraphRouter.default()
gr._load()
report["graph"] = {"dir": str(gr.dir), "source_id": gr.source_id}


def pts_of(s):
    return [tuple(map(float, p.split(","))) for p in s.split("|")]


def plen(ll):
    return sum(hav(ll[i], ll[i + 1]) for i in range(len(ll) - 1))


def nearest_foot(lng, lat, radius_cells=2):
    """요청점에서 가장 가까운 걸음 통행 간선(모든 성분)과 최대 성분(fmain) 간선."""
    from app.domains.travel_ops.instances.mobility.engine.graph_router import CELL_LAT, CELL_LON
    ci, cj = int(lat // CELL_LAT), int(lng // CELL_LON)
    kx = math.cos(math.radians(lat)) * 111320.0
    ky = 110540.0
    best_any, best_main = None, None
    seen = set()
    for di in range(-radius_cells, radius_cells + 1):
        for dj in range(-radius_cells, radius_cells + 1):
            seen.update(gr.grid.get((ci + di, cj + dj), ()))
    for e in seen:
        fl = gr.eflag[e]
        if not fl & F_FOOT:
            continue
        pts = gr._geom(e)[0]
        d = min(_seg_d(lng, lat, pts[i], pts[i + 1], kx, ky) for i in range(len(pts) - 1))
        rec = (d, e)
        if best_any is None or d < best_any[0]:
            best_any = rec
        if fl & F_FMAIN and (best_main is None or d < best_main[0]):
            best_main = rec
    return best_any, best_main


def _seg_d(lng, lat, a, b, kx, ky):
    px, py = (lng - a[0]) * kx, (lat - a[1]) * ky
    dx, dy = (b[0] - a[0]) * kx, (b[1] - a[1]) * ky
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px * dx + py * dy) / L2))
    return math.hypot(px - t * dx, py - t * dy)


def edesc(rec):
    if rec is None:
        return None
    d, e = rec
    return {"dist_m": round(d, 1), "way": int(gr.eway[e]), "hw": gr.hw_name[gr.ehw[e]],
            "fmain": bool(gr.eflag[e] & F_FMAIN), "len_m": round(float(gr.elen[e]), 1)}


for r in obs["rows"]:
    q = r["request"]
    s_ll, e_ll = (q["from"]["lon"], q["from"]["lat"]), (q["to"]["lon"], q["to"]["lat"])
    g = [x for x in r["shortest_guides"] if "pts" in x]
    poly_w = []
    for x in g:
        for p in pts_of(x["pts"]):
            if not poly_w or poly_w[-1] != p:
                poly_w.append(p)
    poly = [w2g(*p) for p in poly_w]
    acc_s, acc_e = hav(s_ll, poly[0]), hav(e_ll, poly[-1])
    net = plen(poly)
    first_poly = plen([w2g(*p) for p in pts_of(g[0]["pts"])])
    last_poly = plen([w2g(*p) for p in pts_of(g[-1]["pts"])])
    row = {"id": r["id"], "kakao_shortest_m": r["modes"]["SHORTEST"]["length_m"],
           "kakao_shortest_time_s": r["modes"]["SHORTEST"]["time_s"],
           "kakao_guides_sum_m": sum(x["len"] for x in g),
           "kakao_polyline_m": round(net, 1),
           "kakao_access_start_m": round(acc_s, 1), "kakao_access_end_m": round(acc_e, 1),
           "definition_check": {"first_guide_len": g[0]["len"], "first_poly_plus_access_m": round(first_poly + acc_s, 1),
                                "last_guide_len": g[-1]["len"], "last_poly_plus_access_m": round(last_poly + acc_e, 1),
                                "polyline_plus_access_m": round(net + acc_s + acc_e, 1)}}
    try:
        resp = gr.route(s_ll, e_ll, "foot")["paths"][0]
        ways = []
        for a, b, w in resp["details"]["osm_way_id"]:
            if not ways or ways[-1] != w:
                ways.append(w)
        row["product"] = {"distance_m": resp["distance"], "snap_m": resp["snap_m"], "quality": resp["quality"],
                          "network_m": round(resp["distance"] - sum(resp["snap_m"]), 2),
                          "ways": ways}
        row["product_minus_kakao_m"] = round(resp["distance"] - r["modes"]["SHORTEST"]["length_m"], 2)
        row["product_minus_kakao_pct"] = round(100 * (resp["distance"] - r["modes"]["SHORTEST"]["length_m"]) / r["modes"]["SHORTEST"]["length_m"], 2)
    except Exception as ex:  # noqa: BLE001 — 진단 기록
        row["product"] = {"error": f"{type(ex).__name__}: {ex}"}
    # 카카오 경로를 5 m 간격으로 따라가며 가장 가까운 걸음 간선
    samples = []
    walked = 0.0
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]
        L = hav(a, b)
        n = max(1, int(L // 5))
        for k in range(n):
            t = k / n
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            ba, bm = nearest_foot(*p)
            samples.append({"at_m": round(walked + t * L, 1), "lng": round(p[0], 6), "lat": round(p[1], 6),
                            "any": edesc(ba), "main": edesc(bm)})
        walked += L
    gaps = [s for s in samples if (s["any"] is None or s["any"]["dist_m"] > 8)]
    offmain = [s for s in samples if s["any"] and s["any"]["dist_m"] <= 8 and not s["any"]["fmain"]
               and (s["main"] is None or s["main"]["dist_m"] > 8)]
    row["kakao_path_vs_graph"] = {"samples": len(samples), "no_foot_edge_within_8m": len(gaps),
                                  "only_non_main_component_within_8m": len(offmain),
                                  "gap_samples": gaps, "offmain_samples": offmain}
    # 카카오 안내 꺾임점 사이를 제품 그래프로 이어 본다(어느 구간에서 제품이 더 돌아가는지)
    legs = []
    for x in g:
        pp = [w2g(*p) for p in pts_of(x["pts"])]
        a, b = pp[0], pp[-1]
        kl = plen(pp)
        try:
            rr = gr.route(a, b, "foot")["paths"][0]
            legs.append({"seq": x["seq"], "ment": x["ment"], "kakao_poly_m": round(kl, 1), "kakao_len": x["len"],
                         "product_m": rr["distance"], "product_snap_m": rr["snap_m"],
                         "ratio": round(rr["distance"] / kl, 2) if kl > 1 else None})
        except Exception as ex:  # noqa: BLE001
            legs.append({"seq": x["seq"], "ment": x["ment"], "kakao_poly_m": round(kl, 1), "error": f"{type(ex).__name__}: {ex}"})
    row["guide_legs_on_product_graph"] = legs
    row["kakao_polyline_wgs84"] = [[round(p[0], 7), round(p[1], 7)] for p in poly]
    report["rows"].append(row)

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
for row in report["rows"]:
    p = row["product"]
    print(row["id"], "kakao", row["kakao_shortest_m"], "| poly+acc", row["definition_check"]["polyline_plus_access_m"],
          "| first", row["definition_check"]["first_guide_len"], "~", row["definition_check"]["first_poly_plus_access_m"],
          "| last", row["definition_check"]["last_guide_len"], "~", row["definition_check"]["last_poly_plus_access_m"])
    print("   product", p.get("distance_m"), p.get("snap_m"), p.get("quality"), p.get("error", ""),
          "| diff", row.get("product_minus_kakao_m"), row.get("product_minus_kakao_pct"), "%")
    v = row["kakao_path_vs_graph"]
    print("   kakao path samples", v["samples"], "gaps>8m", v["no_foot_edge_within_8m"], "offmain", v["only_non_main_component_within_8m"])
    for lg in row["guide_legs_on_product_graph"]:
        print("     leg", lg["seq"], lg.get("kakao_poly_m"), "->", lg.get("product_m"), lg.get("ratio"), lg.get("error", ""), lg["ment"][:30])
print("transform resid", report["transform"])
