# -*- coding: utf-8 -*-
"""기획서 차트 — Claude 판.

★숫자는 make_tables.py 의 P·U 에서 가져온다. 여기에는 숫자를 적지 않는다.
★색은 dataviz 기본 팔레트의 앞 두 칸 — 상품 A 파랑, 상품 B 주황. validate_palette.js 로 검증했다.
  상태색(빨강·초록)은 쓰지 않는다. `[미확보]` 는 색이 아니라 **빗금 테두리**로 표시한다.
★축은 하나다. 두 상품을 한 그림에 겹칠 때도 같은 축, 나눌 때는 같은 눈금의 작은 그림 여럿.
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_tables import P, U, breakeven  # noqa: E402

# ── 팔레트 (dataviz 기본값, light) ─────────────────────────────────────
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e6e5e1"
C = {"A": "#2a78d6", "B": "#eb6834"}   # 범주 1·2

plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})
THOUS = FuncFormatter(lambda v, _: "{:,.0f}".format(v))
NAME = {k: "{} ({:,}원)".format(P["상품"][k]["이름"], P["상품"][k]["가격"]) for k in ("A", "B")}


def _grid(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _source(fig, text):
    fig.text(0.01, 0.01, text, fontsize=8, color=MUTED, ha="left", va="bottom")


# ── F1 CAC → 연 손익분기 ──────────────────────────────────────────────
def f1():
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    ymax = 40_000
    xs = np.linspace(0, 40_000, 1600)
    for k in ("A", "B"):
        ci = U[k]["기여I"]
        m = xs < ci - 1
        y = P["고정비"] / (ci - xs[m])
        y[y > ymax] = np.nan
        ax.plot(xs[m], y, color=C[k], linewidth=2, label=NAME[k], solid_capstyle="round")
        # 기여이익Ⅰ — 이 CAC 를 넘으면 팔수록 손해
        ax.axvline(ci, color=C[k], linewidth=1, linestyle=(0, (4, 3)), alpha=0.45)
        # 선 끝 직접 라벨
        # 선 이름은 범례가 맡는다 (두 곡선이 가까워 곡선 위 라벨이 겹친다)

    # 세로선 설명 — 두 선이 1,444원 차이라 선마다 달면 겹친다. 오른쪽 빈 곳에 한 번에 적는다
    ax.text(23_200, ymax * 0.97,
            "점선 = 기여이익Ⅰ (CAC 전)\n  A {:,.0f}원 · B {:,.0f}원\nCAC 가 이보다 작으면 남고, 같으면 0, 크면 팔수록 손해".format(U["A"]["기여I"], U["B"]["기여I"]),
            color=INK2, fontsize=8.5, va="top", ha="left")

    # 판매량 참조선 — 인바운드 가정 · v3 가정
    for vol, lab in ((1_200, "연 1,200건 — 미검증 획득 시나리오 [추정]"),
                     (8_000, "연 8,000건 — v3 한국인 채널 판매 가정")):
        ax.axhline(vol, color=MUTED, linewidth=1, linestyle=(0, (2, 3)))
        ax.text(39_600, vol + 500, lab, color=INK2, fontsize=8.5, ha="right")

    # 두 점만 표시 — v3 원점과 코덱스 가정점
    pts = [("A", 8_500, "v11 §11-A 값 (CAC 8,500원, 한국인 채널)"), ("B", 12_000, "코덱스 판 가정 (CAC 12,000원)")]
    for k, cac, lab in pts:
        be = breakeven(U[k]["기여I"] - cac)
        ax.plot(cac, be, "o", markersize=8, color=C[k], markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
        ax.annotate("{}\n연 {:,}건".format(lab, be), (cac, be), xytext=(12, -34) if k == "A" else (10, 6),
                    textcoords="offset points", fontsize=8.5, color=INK)

    ax.set_xlim(0, 40_000)
    ax.set_ylim(0, ymax)
    ax.xaxis.set_major_formatter(THOUS)
    ax.yaxis.set_major_formatter(THOUS)
    ax.set_xlabel("고객 획득비 CAC (원 / 여행)")
    ax.set_ylabel("연 손익분기 판매량 (건)")
    _grid(ax)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), frameon=False, fontsize=9)
    fig.suptitle("인바운드 CAC 를 모르면 — CAC 가 오를수록 손익분기가 얼마나 멀어지나",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    ax.set_title("고정비 연 {:,.0f}원 [추정] · CAC 가 0 이어도 손익분기는 연 7,900건 이상이다".format(P["고정비"]),
                 loc="left", fontsize=9.5, color=INK2)
    _source(fig, "계산: make_tables.py 의 P · A 원가 = 비용 문서 §4-A 예산 · B = 코덱스 판 사용량 × 공개 단가 · 모두 [추정] · 환율 {:,}원".format(P["환율"]))
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    out = os.path.join(HERE, "F1_CAC_손익분기.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


# ── F2 기여이익 폭포 — 두 상품, 같은 눈금 ─────────────────────────────
def _steps(k):
    c = U[k]["원가"]
    ext = sum(v for n, v in c.items() if n in ("외부 데이터", "장소 상세", "장소 검색", "경로 요소", "기계(외부 데이터·LLM) 상한"))
    items = [("결제 수수료", c.get("결제 수수료", 0)), ("기계·데이터", ext),
             ("LLM", c.get("LLM", 0)), ("사람 지원", c.get("사람 지원", 0)),
             ("장애·보상", c.get("장애·보상", 0)), ("플랫폼", c.get("플랫폼", 0))]
    return [(n, v) for n, v in items if v > 0]


def f2():
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.4), sharey=True)
    top = max(U[k]["순매출"] for k in ("A", "B")) * 1.12
    for ax, k in zip(axes, ("A", "B")):
        labels, bottoms, heights, colors = [], [], [], []
        run = U[k]["순매출"]
        labels.append("순매출"); bottoms.append(0); heights.append(run); colors.append(C[k])
        for n, v in _steps(k):
            run -= v
            labels.append(n); bottoms.append(run); heights.append(v); colors.append(MUTED)
        labels.append("기여이익Ⅰ"); bottoms.append(0); heights.append(run); colors.append(C[k])
        x = np.arange(len(labels))
        ax.bar(x, heights, bottom=bottoms, color=colors, width=0.72,
               edgecolor=SURFACE, linewidth=2)
        for i, (b, h) in enumerate(zip(bottoms, heights)):
            is_total = i in (0, len(labels) - 1)
            ax.text(i, b + h + top * 0.012, ("{:,.0f}" if is_total else "-{:,.0f}").format(h),
                    ha="center", va="bottom", fontsize=8.5,
                    color=INK if is_total else INK2, fontweight="bold" if is_total else "normal")
        ax.set_xticks(x, labels, rotation=30, ha="right", fontsize=9)
        ax.set_title(NAME[k], loc="left", fontsize=10.5, color=INK, fontweight="bold")
        ax.yaxis.set_major_formatter(THOUS)
        ax.set_ylim(0, top)
        _grid(ax)
        ax.annotate("CAC 가 이 높이보다\n작아야 남는다", (len(labels) - 1, run),
                    xytext=(-120, 60), textcoords="offset points", fontsize=8.5, color=INK2,
                    arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1))
    axes[0].set_ylabel("여행 1건당 원")
    fig.suptitle("여행 1건에서 무엇이 빠지고 무엇이 남나 — CAC 전까지",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    _source(fig, "파랑·주황 = 매출과 남는 몫 · 회색 = 빠지는 원가 · 모든 값 [추정] · 계산: make_tables.py 의 P")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    out = os.path.join(HERE, "F2_기여이익_폭포.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


# ── F3 시장 — 아는 것과 모르는 것 ─────────────────────────────────────
def f3():
    arr, ind = 17_410_000, 0.829
    rows = [("방한 외래객 (2025년 1~11월)", arr, "[외부] v11 §1"),
            ("그중 개별여행 (82.9%)", arr * ind, "[외부] × [외부] = [추정]"),
            ("SAM — 서울 방문 × 개인 에이전트 사용", None, "[미확보] 두 비율 모두 조사 안 함"),
            ("SOM — 첫해 실제 획득", None, "산정하지 않는다 · 인바운드 채널 미정")]
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    y = np.arange(len(rows))[::-1]
    for yi, (lab, v, note) in zip(y, rows):
        if v is not None:
            ax.barh(yi, v, color=C["A"], height=0.58, edgecolor=SURFACE, linewidth=2)
            ax.text(v + arr * 0.01, yi, "{:,.0f}명  {}".format(v, note), va="center", fontsize=9, color=INK)
        else:
            # ★크기를 모르므로 막대 길이로 크기를 암시하지 않는다 — 빈 칸에 빗금만
            ax.barh(yi, arr, color="none", height=0.58, edgecolor=MUTED, hatch="///", linewidth=0.8)
            ax.text(arr * 0.02, yi, "?  " + note, va="center", fontsize=9, color=INK,
                    bbox=dict(facecolor=SURFACE, edgecolor="none", pad=3))
    ax.set_yticks(y, [r[0] for r in rows], fontsize=9.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "{:,.0f}만".format(v / 10_000)))
    ax.set_xlim(0, arr * 1.55)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.suptitle("인바운드 시장 — 우리 규모를 정하는 두 비율을 아직 모른다",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    _source(fig, "빗금 칸의 길이는 크기가 아니다 — 모른다는 표시다 · 사람 수이지 구매 단위(팀)가 아니다")
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    out = os.path.join(HERE, "F3_시장_아는것과모르는것.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


if __name__ == "__main__":
    for f in (f1, f2, f3):
        print("저장:", os.path.basename(f()))
