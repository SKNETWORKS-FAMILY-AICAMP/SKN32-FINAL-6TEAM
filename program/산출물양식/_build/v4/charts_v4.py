# -*- coding: utf-8 -*-
"""문서 삽입용 그림(4차 v4). 규격: 폭 6.4인치(=163mm)로 그려 그대로 삽입, 300dpi, 글자 9.5pt 이상.

그림을 삽입 크기와 같은 크기로 그리므로 「삽입 크기 기준 글자 크기」가 그리는 글자 크기와 같다(축소 0).
흐름도는 노드 6개 이하, 노드당 3줄 이하, 2열·3열 배치, 화살표는 도형 연결선이다.
막대그래프는 같은 평가 대상·지표·조건의 값만 같은 축에 그린다.
"""
from __future__ import annotations

from pathlib import Path

BLUE, ORANGE, AQUA = "#2A78D6", "#EB6834", "#1BAF7A"
INK, MUTED, GRID, GRAY = "#1F2933", "#5B6B7C", "#E3E8EE", "#B8C2CE"
NAVY = "#1F3864"
FIG_W = 6.4
DPI = 300
FS = 9.5           # 그림 안 글자 최소 크기(pt)


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
    ax.tick_params(axis="y", length=0, labelsize=FS, colors=INK)
    ax.tick_params(axis="x", labelsize=FS, colors=MUTED, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=FS, color=MUTED, labelpad=6)


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white", dpi=DPI)          # bbox_inches 를 쓰지 않는다: 크기를 6.4인치로 고정
    import matplotlib.pyplot as plt
    plt.close(fig)
    return path


def hbar(path: Path, rows, xmax=None, xlabel=None, fmt="{:.1f}%", target=None, height=None):
    """가로 막대. rows = [(이름, 값, 색 또는 None, 꼬리표(선택))]."""
    plt = _plt()
    n = len(rows)
    fig, ax = plt.subplots(figsize=(FIG_W, height or (0.46 * n + 1.1)), dpi=DPI, layout="constrained")
    top = xmax or max(r[1] for r in rows)
    ys = list(range(n))[::-1]
    for y, row in zip(ys, rows):
        value, color = row[1], (row[2] if len(row) > 2 else None)
        ax.barh(y, value, height=0.55, color=color or BLUE, edgecolor="white", linewidth=1.2, zorder=3)
        tail = row[3] if len(row) > 3 else ""
        ax.text(value + top * 0.012, y, fmt.format(value) + (f"  {tail}" if tail else ""), va="center", ha="left",
                fontsize=FS, color=INK, zorder=5, bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(0, top * 1.30)
    ax.set_xticks([t for t in ax.get_xticks() if 0 <= t <= top * 1.001])
    if target is not None:
        ax.axvline(target[0], color=ORANGE, linewidth=1.3, linestyle=(0, (4, 3)), zorder=2)
        ax.text(target[0], n - 0.35, target[1], color=ORANGE, fontsize=FS, ha="center", va="bottom")
    _frame(ax, xlabel)
    return _save(fig, path)


def grouped(path: Path, groups, series, xmax=1.0, xlabel=None, fmt="{:.3f}", height=None, legend_cols=None):
    """묶음 가로 막대. groups=[이름...], series=[(범례, 색, [값...])]. 같은 그룹 안의 막대는 같은 지표·같은 시험이다."""
    plt = _plt()
    n, k = len(groups), len(series)
    fig, ax = plt.subplots(figsize=(FIG_W, height or (0.36 * n * k + 1.5)), dpi=DPI, layout="constrained")
    band = 0.80
    bar_h = band / k
    for gi in range(n):
        base = n - 1 - gi
        for si, (name, color, values) in enumerate(series):
            y = base + band / 2 - bar_h * (si + 0.5)
            v = values[gi]
            if v is None:
                continue
            ax.barh(y, v, height=bar_h * 0.86, color=color, edgecolor="white", linewidth=1.0, zorder=3, label=name if gi == 0 else None)
            ax.text(v + xmax * 0.012, y, fmt.format(v), va="center", ha="left", fontsize=FS, color=INK, zorder=4)
    ax.set_yticks(list(range(n))[::-1])
    ax.set_yticklabels(groups)
    ax.set_xlim(0, xmax * 1.14)
    ax.set_xticks([t for t in ax.get_xticks() if 0 <= t <= xmax * 1.001])
    _frame(ax, xlabel)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=legend_cols or min(k, 3), frameon=False, fontsize=FS, labelcolor=INK)
    return _save(fig, path)


KINDS = {"입력": ("#EAF2FC", BLUE, "-"), "처리": ("#F4F6F8", MUTED, "-"), "출력": ("#E6F5EE", AQUA, "-"), "검증": ("#FFFFFF", NAVY, (0, (4, 2)))}


def flow(path: Path, nodes, cols=2, snake=True, no_arrow_after=()):
    """흐름도. nodes = [(종류, 글)] 6개 이하, 글은 3줄 이하. 뱀 모양(첫 줄 왼쪽에서 오른쪽, 다음 줄 오른쪽에서 왼쪽)으로 이어 화살표로 잇는다."""
    assert len(nodes) <= 6, "노드는 6개 이하"
    plt = _plt()
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
    n = len(nodes)
    rows = -(-n // cols)
    gap_x = 0.45 if cols == 2 else 0.32
    box_w = (FIG_W - 0.2 - gap_x * (cols - 1)) / cols
    box_h, gap_y = 0.72, 0.30
    legend_h = 0.36
    height = rows * box_h + (rows - 1) * gap_y + 0.2 + legend_h
    fig = plt.figure(figsize=(FIG_W, height), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(0, height)
    ax.axis("off")
    pos = []
    for i in range(n):
        r, c = divmod(i, cols)
        if snake and r % 2 == 1:
            c = cols - 1 - c
        x = 0.1 + c * (box_w + gap_x)
        y = height - 0.1 - box_h - r * (box_h + gap_y)
        pos.append((x, y))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for i, ((kind, text), (x, y)) in enumerate(zip(nodes, pos)):
        fill, edge, ls = KINDS[kind]
        assert text.count("\n") <= 2, f"노드 글 3줄 초과: {text}"
        ax.add_patch(FancyBboxPatch((x, y), box_w, box_h, boxstyle="round,pad=0.01,rounding_size=0.08", linewidth=1.2, edgecolor=edge, facecolor=fill, linestyle=ls))
        t = ax.text(x + box_w / 2 + 0.06, y + box_h / 2, text, fontsize=FS, ha="center", va="center", color=INK, linespacing=1.35)
        bb = t.get_window_extent(renderer)
        if bb.width / DPI > box_w - 0.34:
            raise SystemExit(f"[멈춤] 흐름도 글이 상자를 넘는다({bb.width / DPI:.2f}in > {box_w - 0.34:.2f}in): {text}")
        ax.text(x + 0.12, y + box_h - 0.13, str(i + 1), fontsize=FS, fontweight="bold", color=edge, ha="left", va="center")
    for i in range(n - 1):
        if i in no_arrow_after:
            continue
        (x1, y1), (x2, y2) = pos[i], pos[i + 1]
        if abs(y1 - y2) < 1e-6:                                   # 같은 줄: 옆으로
            if x2 > x1:
                a, b = (x1 + box_w + 0.02, y1 + box_h / 2), (x2 - 0.02, y2 + box_h / 2)
            else:
                a, b = (x1 - 0.02, y1 + box_h / 2), (x2 + box_w + 0.02, y2 + box_h / 2)
        else:                                                      # 줄 바꿈: 아래로
            a, b = (x1 + box_w / 2, y1 - 0.02), (x2 + box_w / 2, y2 + box_h + 0.02)
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=13, color=MUTED, lw=1.4))
    used = [k for k in KINDS if any(kk == k for kk, _ in nodes)]
    handles = [Patch(facecolor=KINDS[k][0], edgecolor=KINDS[k][1], linestyle=KINDS[k][2], label=k) for k in used]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 0.0), ncol=len(handles), frameon=False, fontsize=FS, handlelength=1.4, columnspacing=1.6)
    return _save(fig, path)
