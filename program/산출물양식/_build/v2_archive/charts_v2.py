# -*- coding: utf-8 -*-
"""문서 삽입용 그래프(4차 v2). 검증된 기본 팔레트의 앞 세 칸(파랑·주황·청록)만 쓴다.

지키는 것(dataviz 스킬 기준)
- 한 그래프에 색은 3개 이하. 이름은 색이 아니라 **글로도** 적는다(범례 + 막대 끝 값).
- 막대는 얇게, 바닥선에 붙이고, 격자는 옅게. 값은 막대 끝에 직접 적는다.
- 이중 축을 쓰지 않는다. 분모가 다른 값은 그래프를 나눈다.
"""
from __future__ import annotations

from pathlib import Path

BLUE, ORANGE, AQUA = "#2A78D6", "#EB6834", "#1BAF7A"
INK, MUTED, GRID, GRAY = "#1F2933", "#5B6B7C", "#E3E8EE", "#B8C2CE"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for name in ("Malgun Gothic", "맑은 고딕"):
        if any(f.name == name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _frame(ax, xlabel=None):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRAY)
    ax.tick_params(axis="y", length=0, labelsize=9.5, colors=INK)
    ax.tick_params(axis="x", labelsize=8.5, colors=MUTED, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8.5, color=MUTED, labelpad=6)


def hbar(path: Path, rows, xmax=None, xlabel=None, fmt="{:.1f}%", title=None, target=None, height=None,
         label_width=None):
    """가로 막대. rows = [(이름, 값, 색 또는 None, 꼬리표(선택))]. 값 단위는 그대로 그린다."""
    plt = _plt()
    n = len(rows)
    fig, ax = plt.subplots(figsize=(7.0, height or (0.42 * n + 1.0)), dpi=250)
    ys = list(range(n))[::-1]
    for y, row in zip(ys, rows):
        name, value, color = row[0], row[1], (row[2] if len(row) > 2 else None)
        ax.barh(y, value, height=0.52, color=color or BLUE, edgecolor="white", linewidth=1.2, zorder=3)
        tail = row[3] if len(row) > 3 else ""
        ax.text(value + (xmax or max(r[1] for r in rows)) * 0.012, y, fmt.format(value) + (f"  {tail}" if tail else ""),
                va="center", ha="left", fontsize=9, color=INK, zorder=5,
                bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    top = xmax or max(r[1] for r in rows)
    ax.set_xlim(0, top * 1.22)
    ticks = [t for t in ax.get_xticks() if 0 <= t <= top * 1.001]
    ax.set_xticks(ticks)
    if target is not None:
        ax.axvline(target[0], color=ORANGE, linewidth=1.3, linestyle=(0, (4, 3)), zorder=2)
        ax.text(target[0], n - 0.35, target[1], color=ORANGE, fontsize=8.5, ha="center", va="bottom")
    _frame(ax, xlabel)
    if title:
        ax.set_title(title, loc="left", fontsize=10.5, color=INK, fontweight="bold", pad=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


def grouped(path: Path, groups, series, xmax=1.0, xlabel=None, fmt="{:.3f}", height=None, title=None, legend_loc="lower right"):
    """묶음 가로 막대. groups=[이름...], series=[(범례, 색, [값...])]."""
    plt = _plt()
    n, k = len(groups), len(series)
    fig, ax = plt.subplots(figsize=(7.0, height or (0.30 * n * k + 1.3)), dpi=250)
    band = 0.78
    bar_h = band / k
    for gi, group in enumerate(groups):
        base = (n - 1 - gi)
        for si, (name, color, values) in enumerate(series):
            y = base + band / 2 - bar_h * (si + 0.5)
            v = values[gi]
            if v is None:
                continue
            ax.barh(y, v, height=bar_h * 0.86, color=color, edgecolor="white", linewidth=1.0, zorder=3,
                    label=name if gi == 0 else None)
            ax.text(v + xmax * 0.012, y, fmt.format(v), va="center", ha="left", fontsize=8.3, color=INK, zorder=4)
    ax.set_yticks(list(range(n))[::-1])
    ax.set_yticklabels(groups)
    ax.set_xlim(0, xmax * 1.16)
    ax.set_xticks([t for t in ax.get_xticks() if 0 <= t <= xmax * 1.001])
    _frame(ax, xlabel)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16 if xlabel else -0.08), ncol=k, frameon=False, fontsize=8.5, labelcolor=INK)
    if title:
        ax.set_title(title, loc="left", fontsize=10.5, color=INK, fontweight="bold", pad=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


def before_after(path: Path, items, xlabel=None, title=None, fmt="{:g}"):
    """전후 비교 — items=[(이름, 전, 후, 분모)]. 같은 분모(퍼센트가 아니라 개수)를 그대로 보인다."""
    plt = _plt()
    n = len(items)
    fig, ax = plt.subplots(figsize=(7.0, 0.62 * n + 1.1), dpi=250)
    for i, (name, before, after, denom) in enumerate(items):
        y = n - 1 - i
        ax.barh(y + 0.17, before, height=0.30, color=GRAY, edgecolor="white", linewidth=1.0, zorder=3, label="전" if i == 0 else None)
        ax.barh(y - 0.17, after, height=0.30, color=BLUE, edgecolor="white", linewidth=1.0, zorder=3, label="후" if i == 0 else None)
        ax.text(before + denom * 0.012, y + 0.17, f"{fmt.format(before)}/{denom}", va="center", fontsize=8.8, color=INK, zorder=4)
        ax.text(after + denom * 0.012, y - 0.17, f"{fmt.format(after)}/{denom}", va="center", fontsize=8.8, color=INK, zorder=4)
    ax.set_yticks(list(range(n))[::-1])
    ax.set_yticklabels([it[0] for it in items])
    ax.set_xlim(0, max(it[3] for it in items) * 1.18)
    _frame(ax, xlabel)
    ax.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK)
    if title:
        ax.set_title(title, loc="left", fontsize=10.5, color=INK, fontweight="bold", pad=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


def flow(path: Path, lanes, note_size=9.0):
    """세로 흐름 그림 — 줄(lane)마다 한 열. 3차 그림과 같은 모양이되 색을 두 가지로 줄였다."""
    plt = _plt()
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    cols, rows = len(lanes), max(len(steps) for _, steps in lanes)
    box_w, box_h, gap_x, gap_y = 3.4, 1.05, 0.7, 0.55
    width = cols * box_w + (cols - 1) * gap_x
    height = rows * box_h + (rows - 1) * gap_y + 1.1
    fig, ax = plt.subplots(figsize=(width * 0.62, height * 0.62), dpi=250)
    ax.set_xlim(-0.1, width + 0.1)
    ax.set_ylim(-0.1, height + 0.1)
    ax.axis("off")
    fills = ("#EAF2FC", "#F4F6F8", "#FDF3E8")
    for c, (lane, steps) in enumerate(lanes):
        x = c * (box_w + gap_x)
        ax.text(x + box_w / 2, height - 0.35, lane.replace("\n", " "), fontsize=10.5, fontweight="bold", ha="center", va="center", color=INK)
        for r, text in enumerate(steps):
            y = height - 1.0 - box_h - r * (box_h + gap_y)
            ax.add_patch(FancyBboxPatch((x, y), box_w, box_h, boxstyle="round,pad=0.02,rounding_size=0.1",
                                        linewidth=1.0, edgecolor=MUTED, facecolor=fills[c % 3]))
            ax.text(x + box_w / 2, y + box_h / 2, text, fontsize=note_size, ha="center", va="center", color=INK, linespacing=1.3)
            if r < len(steps) - 1:
                ax.add_patch(FancyArrowPatch((x + box_w / 2, y - 0.03), (x + box_w / 2, y - gap_y + 0.03),
                                             arrowstyle="-|>", mutation_scale=11, color=MUTED, lw=1.0))
    fig.tight_layout(pad=0.2)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path
