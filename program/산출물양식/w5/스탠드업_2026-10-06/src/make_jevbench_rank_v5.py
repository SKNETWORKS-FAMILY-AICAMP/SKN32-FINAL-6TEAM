"""발표 「외부 벤치마크와 모델 순위가 같은 방향입니다」 그림 새 판(v5) — 모든 점에 이름을 단다 (2026-10-07 사용자 질문 「그림에 왜 일부는 이름이 안 적혀 있어?」).

원인(v4): make_assets_v4.py 의 jevbench_rank() 가 `lab` 딕셔너리에 든 모델 8개만 이름을 달았다(중앙 점이 몰려 겹치는 것을 피하려고).
  → 17개 점 중 9개(Jev-Omni · Decider-4B · lev · JevK5 4B · Imajev-4B · Malkuth-4B · Manchego 4B · Decider-35B-A3B · Nimble-9B)에 이름이 없었다.
고침: 모든 점에 이름을 달고, 겹치면 후보 위치 12곳 중 겹침이 가장 적은 곳으로 놓는다. 계산(점 · 순위상관)은 v4 와 같다 — jevbench_rank_check.py.
v4 파일은 건드리지 않고 v5/_assets 에 새로 만든다(전달한 판은 덮어쓰지 않는다).
사용: python make_jevbench_rank_v5.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_assets_v4 as M  # noqa: E402  (테마 T · 글꼴 설정만 쓴다 — 그림 생성 함수는 부르지 않는다)

ROOT = HERE.parent
OUT = ROOT / "v5" / "_assets"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT.parent.parents[1] / "scripts" / "plan_qa_bench"))
import jevbench_rank_check as J  # noqa: E402

T = M.T
SHORT = {
    "Jev 직접 (유료)": "Jev API(유료)",
    "Winnow-12B Q8": "Winnow-12B",
    "Cygnet(얼린 Gemma-4-12B-it 글자 읽기, 8비트)": "Cygnet",
    "Plumb-4B v5 Q8": "Plumb-4B",
    "lev(Interfaze, Qwen3.5-4B + LoRA)": "lev(Qwen3.5-4B)",
    "JevK5 4B v0.3 Q8": "JevK5 4B",
    "Hopper 4B(Qwen3.5-4B + LoRA r16)": "Hopper 4B",
    "Imajev-4B": "Imajev-4B",
    "Malkuth-4B": "Malkuth-4B",
    "Manchego v2.1(4B)": "Manchego 4B",
    "Decider-35B-A3B bf16": "Decider-35B-A3B",
    "Nimble-9B-v3 Q8": "Nimble-9B",
    "Decider-2B": "Decider-2B",
    "Kev-4B Q8": "Kev-4B",
    "Jev-Omni 묶음 읽기(20개 이하씩)": "Jev-Omni(변형 다름)",
    "Decider-4B (자체 라이브러리)": "Decider-4B(판 미확인)",
    "OpenJev 26B Q4_K_M": "OpenJev(변형 다름)",
}


def main(out_dir=None):
    outd = Path(out_dir) if out_dir else OUT
    board, ours = J.load_board(), J.load_ours()
    pairs = {**J.SURE, **J.MAYBE}
    common = None
    for m in pairs:
        if m in ours:
            common = set(ours[m]) if common is None else common & set(ours[m])
    pts = []
    for m, key in pairs.items():
        if m in ours and key in board:
            pts.append((m, float(board[key]["intel"]), 100 * sum(ours[m][q] for q in common) / len(common), m in J.MAYBE))
    same = [p for p in pts if not p[3]]
    rho = J.spearman([p[1] for p in same], [p[2] for p in same])
    lo, hi = J.fisher_ci(rho, len(same))
    missing = [m for m, *_ in pts if m not in SHORT]
    assert not missing, f"이름표가 없는 모델: {missing}"

    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    for m, x, y, maybe in pts:
        if maybe:
            ax.scatter([x], [y], s=60, facecolor="none", edgecolor=T["grey2"], linewidth=1.6, zorder=3)
        else:
            ax.scatter([x], [y], s=70, color=T["primary"], edgecolor="white", linewidth=1.2, zorder=4)
    ax.set_xlim(14, 76)
    ax.set_ylim(66, 100)
    ax.text(0.03, 0.95, f"순위상관 ρ = {rho:+.2f}", transform=ax.transAxes, fontsize=15, fontweight="bold", color=T["primary"], va="top")
    ax.text(0.03, 0.865, f"95% 구간 {lo:+.2f} ~ {hi:+.2f} · 모델 {len(same)}개", transform=ax.transAxes, fontsize=9.5, color=T["muted"], va="top")
    ax.set_xlabel("JevBench v1.6.0 지능 점수 (영어 결정 문제)", fontsize=10, color=T["muted"])
    ax.set_ylabel("우리 시험 정확도 % (한국어 일정 309문제)", fontsize=10, color=T["muted"])
    ax.grid(True, color=T["border"], lw=0.7)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()

    # 이미 놓인 것들의 화면 사각형(픽셀): 점 · 제목 글자
    def box_of(artist):
        return artist.get_window_extent(rend)
    taken = [ax.transAxes.transform((0.03, 0.80)) + (0, 0)]  # 자리 표시(미사용)
    taken = []
    for t in ax.texts:
        taken.append(box_of(t))
    dots = [ax.transData.transform((x, y)) for _, x, y, _ in pts]

    def overlap(a, b):
        return not (a.x1 < b.x0 or b.x1 < a.x0 or a.y1 < b.y0 or b.y1 < a.y0)

    cand = [(7, 0, "left", "center"), (-7, 0, "right", "center"), (0, 9, "center", "bottom"), (0, -9, "center", "top"),
            (7, 7, "left", "bottom"), (7, -7, "left", "top"), (-7, 7, "right", "bottom"), (-7, -7, "right", "top"),
            (16, 12, "left", "bottom"), (16, -12, "left", "top"), (-16, 12, "right", "bottom"), (-16, -12, "right", "top")]
    order = sorted(range(len(pts)), key=lambda i: -sum(1 for j, d in enumerate(dots) if j != i and abs(d[0] - dots[i][0]) < 90 and abs(d[1] - dots[i][1]) < 40))
    placed = {}
    for i in order:
        m, x, y, maybe = pts[i]
        best, best_cost = None, 1e9
        for dx, dy, ha, va in cand:
            t = ax.annotate(SHORT[m], (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=8.8, ha=ha, va=va, color=T["muted"] if maybe else T["text"])
            bb = box_of(t)
            cost = 0.0
            for tb in taken:
                if overlap(bb, tb):
                    cost += 3
            for j, d in enumerate(dots):
                if bb.x0 - 6 <= d[0] <= bb.x1 + 6 and bb.y0 - 6 <= d[1] <= bb.y1 + 6:
                    cost += 2 if j != i else 1
            ab = ax.get_window_extent(rend)
            if bb.x0 < ab.x0 or bb.x1 > ab.x1 or bb.y0 < ab.y0 or bb.y1 > ab.y1:
                cost += 5
            cost += 0.02 * (abs(dx) + abs(dy))
            t.remove()
            if cost < best_cost:
                best, best_cost = (dx, dy, ha, va), cost
        dx, dy, ha, va = best
        t = ax.annotate(SHORT[m], (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=8.8, ha=ha, va=va, color=T["muted"] if maybe else T["text"])
        taken.append(box_of(t))
        placed[m] = best_cost
    over = {k: round(v, 2) for k, v in placed.items() if v >= 2}
    print("겹침이 남은 이름표(비용 2 이상):", over or "없음")
    fig.tight_layout()
    fig.savefig(outd / "jevbench_rank.png", dpi=220, facecolor=fig.get_facecolor())
    print("저장", outd / "jevbench_rank.png", "점", len(pts), "이름표", len(placed))


if __name__ == "__main__":
    main()
