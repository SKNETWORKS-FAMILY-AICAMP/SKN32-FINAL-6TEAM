"""카카오 최단 도보 경로 vs 제품 경로 + 주변 걸음 그래프 간선을 한 장씩 그린다 — 읽기 전용 진단."""
import json, math, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(r"C:\Users\playdata2\Documents\final_workspace")
sys.path.insert(0, str(ROOT / "final_project_cs"))
from app.domains.travel_ops.instances.mobility.engine import paths as _paths  # noqa: E402
_paths.configure("datasets/mobility/processed")
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter, F_FOOT, F_FMAIN, F_STEPS, CELL_LAT, CELL_LON  # noqa: E402

for f in ("Malgun Gothic", "NanumGothic"):
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams["axes.unicode_minus"] = False

ana = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
import os as _os
gr = GraphRouter(Path(_os.environ['GRAPH_DIR'])) if _os.environ.get('GRAPH_DIR') else GraphRouter.default()
gr._load()

fig, axes = plt.subplots(2, 2, figsize=(14, 13))
for ax, row in zip(axes.flat, ana["rows"]):
    kp = row["kakao_polyline_wgs84"]
    obs = json.loads((ROOT / ana["observation_file"]).read_text(encoding="utf-8"))
    req = next(r for r in obs["rows"] if r["id"] == row["id"])["request"]
    s = (req["from"]["lon"], req["from"]["lat"])
    e = (req["to"]["lon"], req["to"]["lat"])
    resp = gr.route(s, e, "foot")["paths"][0]
    pp = resp["points"]["coordinates"]
    xs = [p[0] for p in kp + pp] + [s[0], e[0]]
    ys = [p[1] for p in kp + pp] + [s[1], e[1]]
    pad = 0.0006
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    cand = set()
    for ci in range(int(y0 // CELL_LAT), int(y1 // CELL_LAT) + 1):
        for cj in range(int(x0 // CELL_LON), int(x1 // CELL_LON) + 1):
            cand.update(gr.grid.get((ci, cj), ()))
    for ed in cand:
        fl = gr.eflag[ed]
        if not fl & F_FOOT:
            continue
        g = gr._geom(ed)[0]
        hw = gr.hw_name[gr.ehw[ed]]
        col = "#c9c9c9" if hw in ("footway", "path", "pedestrian", "steps", "corridor") else "#e6e0d0"
        if fl & F_STEPS:
            col = "#d9a0a0"
        ax.plot([p[0] for p in g], [p[1] for p in g], color=col, lw=1.0 if col != "#e6e0d0" else 2.2, zorder=1)
    ax.plot([p[0] for p in kp], [p[1] for p in kp], color="#1f6feb", lw=3, alpha=0.8, zorder=3,
            label=f"카카오 최단 {row['kakao_shortest_m']}m (웹 관측)")
    ax.plot([p[0] for p in pp], [p[1] for p in pp], color="#d1242f", lw=2, ls="--", zorder=4,
            label=f"제품 {row['product']['distance_m']:.0f}m ({row['product_minus_kakao_pct']:+.1f}%)")
    ax.plot([s[0], kp[0][0]], [s[1], kp[0][1]], color="#1f6feb", lw=1, ls=":", zorder=3)
    ax.plot([e[0], kp[-1][0]], [e[1], kp[-1][1]], color="#1f6feb", lw=1, ls=":", zorder=3)
    ax.scatter([s[0]], [s[1]], marker="o", s=60, color="black", zorder=5)
    ax.scatter([e[0]], [e[1]], marker="s", s=60, color="black", zorder=5)
    ax.annotate("출발", s, xytext=(5, 5), textcoords="offset points")
    ax.annotate("도착", e, xytext=(5, 5), textcoords="offset points")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect(1 / math.cos(math.radians((y0 + y1) / 2)))
    ax.set_title(f"{row['id']} — 같은 출발·도착 좌표", fontsize=12)
    ax.legend(loc="best", fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
fig.suptitle("카카오 웹 최단 도보 경로(파랑) vs 제품 보행 그래프 경로(빨강 점선)\n회색 가는 선 = 그래프의 보행로 · 베이지 굵은 선 = 걸을 수 있는 차도 · 분홍 = 계단", fontsize=13)
_g = Path(_os.environ.get('GRAPH_DIR') or str(gr.dir)).name
_src = ("서울특별시 도보 네트워크(공공누리 1유형, 출처: 서울특별시)" if "seoul" in _g else "OSM 2026-10-03, © OpenStreetMap contributors, ODbL")
fig.text(0.01, 0.005, f"자료: 카카오맵 공개 웹 화면 응답(2026-10-12 관측, API 호출 0) · 제품 그래프 {_g}({_src})", fontsize=8)
fig.tight_layout(rect=(0, 0.02, 1, 0.95))
fig.savefig(out, dpi=110)
print(out)
