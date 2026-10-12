"""카카오 구간 주변의 제품 도로 그래프 간선과 끝점 연결을 본다 — 읽기 전용."""
import json, math, sys
from pathlib import Path
ROOT = Path(r"C:\Users\playdata2\Documents\final_workspace")
sys.path.insert(0, str(ROOT / "final_project_cs"))
from app.domains.travel_ops.instances.mobility.engine import paths as _paths  # noqa: E402
_paths.configure("datasets/mobility/processed")
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, hav, F_FOOT, F_FMAIN, CELL_LAT, CELL_LON  # noqa: E402

probe = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
gr = GraphRouter.default()
gr._load()
inv = {v: k for k, v in gr.nid.items()}
deg = {}
for e in range(len(gr.eu)):
    if gr.eflag[e] & F_FOOT:
        for n in (gr.eu[e], gr.ev[e]):
            deg[n] = deg.get(n, 0) + 1


def seg_d(p, a, b):
    kx = math.cos(math.radians(p[1])) * 111320.0
    ky = 110540.0
    px, py = (p[0] - a[0]) * kx, (p[1] - a[1]) * ky
    dx, dy = (b[0] - a[0]) * kx, (b[1] - a[1]) * ky
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px * dx + py * dy) / L2))
    return math.hypot(px - t * dx, py - t * dy)


for t in probe["targets"]:
    pts = t["kakao_pts"]
    print(f"== {t['od']} seq{t['seq']} {t['ment'][:30]}  kakao {pts[0]} -> {pts[-1]}")
    cand = set()
    for p in pts:
        ci, cj = int(p[1] // CELL_LAT), int(p[0] // CELL_LON)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                cand.update(gr.grid.get((ci + di, cj + dj), ()))
    rows = []
    for e in cand:
        g = gr._geom(e)[0]
        d = min(seg_d(p, g[i], g[i + 1]) for p in pts for i in range(len(g) - 1))
        if d <= 20:
            rows.append((d, e))
    for d, e in sorted(rows):
        u, v = gr.eu[e], gr.ev[e]
        print(f"   d={d:5.1f} way={gr.eway[e]} hw={gr.hw_name[gr.ehw[e]]:<12} foot={int(bool(gr.eflag[e] & F_FOOT))} "
              f"fmain={int(bool(gr.eflag[e] & F_FMAIN))} len={gr.elen[e]:6.1f} u={inv[u]}(deg{deg.get(u,0)}) v={inv[v]}(deg{deg.get(v,0)})")
