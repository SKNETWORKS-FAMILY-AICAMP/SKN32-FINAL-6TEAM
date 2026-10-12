"""카카오 경로 띠(폭 ±W m) 안의 보행 간선만으로 이어지는지 보고, 끊기는 자리를 찾는다 — 읽기 전용 진단."""
import json, math, sys
from pathlib import Path
ROOT = Path(r"C:\Users\playdata2\Documents\final_workspace")
sys.path.insert(0, str(ROOT / "final_project_cs"))
from app.domains.travel_ops.instances.mobility.engine import paths as _paths  # noqa: E402
_paths.configure("datasets/mobility/processed")
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, hav, F_FOOT, CELL_LAT, CELL_LON  # noqa: E402

W = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
ana = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
import os as _os
gr = GraphRouter(Path(_os.environ['GRAPH_DIR'])) if _os.environ.get('GRAPH_DIR') else GraphRouter.default()
gr._load()
inv = {v: k for k, v in gr.nid.items()}


def seg_d(p, a, b):
    kx = math.cos(math.radians(p[1])) * 111320.0
    ky = 110540.0
    px, py = (p[0] - a[0]) * kx, (p[1] - a[1]) * ky
    dx, dy = (b[0] - a[0]) * kx, (b[1] - a[1]) * ky
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px * dx + py * dy) / L2))
    return math.hypot(px - t * dx, py - t * dy)


def dist_to_poly(p, poly):
    return min(seg_d(p, poly[i], poly[i + 1]) for i in range(len(poly) - 1))


report = {"width_m": W, "rows": []}
for row in ana["rows"]:
    kp = [tuple(p) for p in row["kakao_polyline_wgs84"]]
    # 5 m 표본
    samples, walked = [], 0.0
    for i in range(len(kp) - 1):
        a, b = kp[i], kp[i + 1]
        L = hav(a, b)
        n = max(1, int(L // 5))
        for k in range(n):
            t = k / n
            samples.append((walked + t * L, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))))
        walked += L
    samples.append((walked, kp[-1]))
    cand = set()
    for _, p in samples:
        ci, cj = int(p[1] // CELL_LAT), int(p[0] // CELL_LON)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                cand.update(gr.grid.get((ci + di, cj + dj), ()))
    corr = []
    for e in cand:
        if not gr.eflag[e] & F_FOOT:
            continue
        g = gr._geom(e)[0]
        # 간선의 꼭짓점·중간점이 모두 띠 안 → 카카오 경로를 따라가는 간선
        pts = list(g)
        for i in range(len(g) - 1):
            pts.append(((g[i][0] + g[i + 1][0]) / 2, (g[i][1] + g[i + 1][1]) / 2))
        if max(dist_to_poly(p, kp) for p in pts) <= W:
            corr.append(e)
    # 띠 안 간선으로 연결 성분
    par = {}

    def f(x):
        while par.setdefault(x, x) != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for e in corr:
        a, b = f(gr.eu[e]), f(gr.ev[e])
        if a != b:
            par[a] = b
    # 표본마다 띠 안 가장 가까운 간선과 그 성분
    seq = []
    for at, p in samples:
        best = None
        for e in corr:
            g = gr._geom(e)[0]
            d = min(seg_d(p, g[i], g[i + 1]) for i in range(len(g) - 1))
            if best is None or d < best[0]:
                best = (d, e)
        if best is None or best[0] > W:
            seq.append({"at_m": round(at, 1), "ll": [round(p[0], 6), round(p[1], 6)], "comp": None,
                        "d": None if best is None else round(best[0], 1)})
        else:
            seq.append({"at_m": round(at, 1), "ll": [round(p[0], 6), round(p[1], 6)], "comp": f(gr.eu[best[1]]),
                        "d": round(best[0], 1), "way": int(gr.eway[best[1]]), "hw": gr.hw_name[gr.ehw[best[1]]]})
    # 끊김 = 성분이 바뀌거나 띠 밖이 된 자리
    breaks, prev = [], None
    for s in seq:
        key = s["comp"]
        if prev is not None and key != prev["comp"]:
            breaks.append({"from": prev, "to": s})
        prev = s
    comps = {}
    for s in seq:
        comps.setdefault(s["comp"], 0)
        comps[s["comp"]] += 1
    report["rows"].append({"id": row["id"], "corridor_edges": len(corr), "samples": len(seq),
                           "components_seen": len([c for c in comps if c is not None]),
                           "samples_outside_band": comps.get(None, 0), "breaks": breaks})
    print(f"== {row['id']} 띠±{W:g}m 간선 {len(corr)} · 표본 {len(seq)} · 성분 {len([c for c in comps if c is not None])} · 띠 밖 표본 {comps.get(None,0)} · 끊김 {len(breaks)}")
    for b in breaks:
        fr, to = b["from"], b["to"]
        print(f"   {fr['at_m']:6.1f}m {fr['ll']} way={fr.get('way')} {fr.get('hw')} → {to['at_m']:6.1f}m {to['ll']} way={to.get('way')} {to.get('hw')} (d={to.get('d')})")
Path(sys.argv[2]).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
