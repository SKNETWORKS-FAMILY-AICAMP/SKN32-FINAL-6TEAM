# -*- coding: utf-8 -*-
"""그림을 그리는 도구. 내용은 make_trace_images.py 에 있다.

원본은 `program/onboarding/trace_refund_case.html` 다. 코드 경로와 데이터는
거기서 가져왔고, 구조 분류는 `final_project_cs/docs/handoff/08_모듈_컴포넌트_목록.md`,
담당은 `program/plan/A-COP_스프린트_에픽_설계.md` 를 따랐다.

★모든 장 위에 같은 진행바를 그린다. 열두 칸 중 지금 어디인지 칠한다.
  이것이 낱장을 하나의 흐름으로 묶는 장치다. 없으면 그냥 그림 여러 장이다.

★각 장 왼쪽에 구조 좌표를 세로로 세운다. 큰 구조에서 이 단계가 어디인지
  (컴포넌트인가 모듈인가 인스턴스인가, 어느 런타임인가, 누가 맡나, 무슨 계약인가)를
  한 자리에서 읽게 한다. 흐름만 보이면 "지금 어디쯤" 을 알 수 없다.

★가운데에 들어온 문서와 나간 문서를 나란히 놓고 바뀐 줄만 색을 준다.
  데이터가 어떻게 가공되는지가 이 자리에서 보여야 한다.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for cand in ("Malgun Gothic", "맑은 고딕", "NanumGothic"):
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        rcParams["font.family"] = cand
        break
rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
os.makedirs(OUT, exist_ok=True)

INK = "#161c28"
DIM = "#6b7488"
FAINT = "#98a1b4"
LINE = "#dbe0ea"
BLUE = "#2f5bd8"      # 코어 1  Case Runtime and Coordination
RED = "#b8442f"       # 코어 2  Access and Action
GREEN = "#0d7a4d"     # 모델    Agent Team
PURPLE = "#6b3fa0"    # 근거 조합
AMBER = "#a8720c"
GREY = "#6b7488"

STEPS = [
    ("신원", RED), ("중복", RED), ("생성", BLUE), ("분류", GREEN),
    ("라우팅", BLUE), ("기능", BLUE), ("근거", PURPLE), ("판단", GREEN),
    ("검토", GREEN), ("반영", BLUE), ("응답", RED), ("기록", GREY),
]

W, H = 13.6, 7.4


def canvas(h=H):
    fig = plt.figure(figsize=(W, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def box(ax, x, y, w, h, fc="white", ec=LINE, lw=1.2, r=0.014, z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.005,rounding_size=%s" % r,
                                facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z))


def arrow(ax, p, q, color=GREY, lw=1.6):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=14,
                                 color=color, linewidth=lw, shrinkA=0, shrinkB=0))


def progress(ax, current):
    n = len(STEPS)
    left, gap = 0.03, 0.005
    w = (1 - 2 * left - gap * (n - 1)) / n
    for i, (name, color) in enumerate(STEPS):
        x = left + i * (w + gap)
        now = i + 1 == current
        done = i + 1 < current
        box(ax, x, 0.933, w, 0.032, fc=color if now else ("#e2e6ee" if done else "#f2f4f8"),
            ec="none", r=0.007)
        ax.text(x + w / 2, 0.949, "%d" % (i + 1), ha="center", va="center", fontsize=8,
                color="white" if now else ("#8f97a8" if done else "#bcc3d0"),
                fontweight="bold" if now else "normal")
        ax.text(x + w / 2, 0.916, name, ha="center", va="top", fontsize=7.4,
                color=color if now else "#aab2c1", fontweight="bold" if now else "normal")


def title(ax, n, text, color):
    ax.text(0.03, 0.862, "%02d" % n, ha="left", va="center", fontsize=25,
            color=color, fontweight="bold")
    ax.text(0.078, 0.866, text, ha="left", va="center", fontsize=17.5,
            color=INK, fontweight="bold")


def coords(ax, rows, color):
    """왼쪽 세로 구조 좌표. rows = [(항목, 값), ...]"""
    box(ax, 0.03, 0.20, 0.205, 0.60, fc="#fbfcfe", ec=color)
    ax.text(0.0425, 0.768, "구조 좌표", ha="left", va="center", fontsize=9.6,
            color=color, fontweight="bold")
    y = 0.712
    for label, value in rows:
        ax.text(0.0425, y, label, ha="left", va="center", fontsize=8.2, color=FAINT)
        for j, line in enumerate(value):
            ax.text(0.0425, y - 0.030 - j * 0.028, line, ha="left", va="center",
                    fontsize=9.1, color=INK)
        y -= 0.030 + 0.028 * len(value) + 0.030


def doc(ax, x, y, w, h, label, lines, ec=LINE, mark=()):
    box(ax, x, y, w, h, fc="#fbfcfe", ec=ec)
    ax.text(x + 0.011, y + h - 0.028, label, ha="left", va="center",
            fontsize=9.4, color=ec if ec != LINE else DIM, fontweight="bold")
    for i, line in enumerate(lines):
        ax.text(x + 0.013, y + h - 0.072 - i * 0.0375, line, ha="left", va="center",
                fontsize=9.0, color=ec if i in mark else INK,
                fontweight="bold" if i in mark else "normal")


def state_badge(ax, x, text, color):
    box(ax, x, 0.223, 0.145, 0.052, fc="white", ec=color)
    ax.text(x + 0.0725, 0.249, text, ha="center", va="center", fontsize=9.6,
            color=color, fontweight="bold")


def footer(ax, code, why, color):
    ax.text(0.255, 0.168, "코드", ha="left", va="center", fontsize=8.6,
            color=FAINT, fontweight="bold")
    ax.text(0.292, 0.168, code, ha="left", va="center", fontsize=9.0, color=DIM)
    box(ax, 0.255, 0.043, 0.715, 0.088, fc="#fffdf6", ec=color)
    ax.text(0.2725, 0.087, why, ha="left", va="center", fontsize=10.2, color=INK)


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=165, facecolor="white",
                bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)
    print("  ", name)


def step(n, head, color, coord_rows, in_label, in_lines, action, out_label, out_lines,
         states, code, why, mark=()):
    fig, ax = canvas()
    progress(ax, n)
    title(ax, n, head, color)
    coords(ax, coord_rows, color)

    doc(ax, 0.255, 0.335, 0.325, 0.465, in_label, in_lines)
    doc(ax, 0.645, 0.335, 0.325, 0.465, out_label, out_lines, ec=color, mark=mark)
    arrow(ax, (0.588, 0.565), (0.638, 0.565), color=color, lw=2.4)

    # ★설명을 두 문서 사이에 두면 오른쪽 문서 제목과 겹친다(첫 시안이 그랬다).
    #   제목줄 오른쪽 빈자리로 올린다.
    for i, line in enumerate(action):
        ax.text(0.968, 0.878 - i * 0.030, line, ha="right", va="center",
                fontsize=9.6, color=INK if i == 0 else DIM,
                fontweight="bold" if i == 0 else "normal")

    for i, (text, c) in enumerate(states):
        state_badge(ax, 0.255 + i * 0.158, text, c)

    footer(ax, code, why, color)
    save(fig, "%02d_%s.png" % (n, head.replace(" ", "_")))
