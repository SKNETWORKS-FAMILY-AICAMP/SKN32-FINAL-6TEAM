# -*- coding: utf-8 -*-
"""산출물 문서에 넣을 도표를 만든다.

수치는 전부 team_branch/output/A-COPilot_제출표.xlsx 의 근거출처 41건에서 가져온다.
지어낸 값은 없다. 각 그림 아래에 근거번호를 적는다.

실행: python program/plan/diagram/make_charts.py
결과: program/plan/diagram/charts/ 에 PNG
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# 한글 폰트. 없으면 네모로 나오므로 반드시 지정한다.
for cand in ("Malgun Gothic", "맑은 고딕", "NanumGothic"):
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        rcParams["font.family"] = cand
        break
rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts")
os.makedirs(OUT, exist_ok=True)

INK = "#1f2430"
DIM = "#6b7280"
LINE = "#d7dce5"
BLUE = "#2f5bd8"
RED = "#c0362c"
GREEN = "#0d7a4d"
AMBER = "#b8860b"
PALE = "#e8edf7"


def finish(fig, name, note):
    fig.text(0.012, 0.015, note, fontsize=7.5, color=DIM, ha="left", va="bottom")
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight",
                facecolor="white", pad_inches=0.22)
    plt.close(fig)
    print("  ", name)


def bare(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(axis="both", length=0, labelsize=9.5, colors=INK)
    ax.grid(axis="y", color=LINE, linewidth=0.7)
    ax.set_axisbelow(True)


# 1. 웹 트래픽 구성과 AI 유입 증가 -------------------------------------------
def chart_traffic():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.7),
                                 gridspec_kw={"width_ratios": [1, 1.5]})

    a1.barh([0], [53], color=BLUE, height=0.5, label="자동화(봇, 에이전트)")
    a1.barh([0], [47], left=[53], color=PALE, height=0.5, label="사람")
    a1.text(26.5, 0, "53%", ha="center", va="center", color="white",
            fontsize=15, fontweight="bold")
    a1.text(76.5, 0, "47%", ha="center", va="center", color=INK, fontsize=15)
    a1.set_xlim(0, 100)
    a1.set_ylim(-0.6, 0.9)
    a1.axis("off")
    a1.set_title("전체 웹 트래픽 구성 (2026)", fontsize=11, color=INK, pad=14)
    a1.legend(loc="upper center", bbox_to_anchor=(0.5, 0.22), frameon=False,
              fontsize=8.5, ncol=2, handlelength=1.1)

    names = ["미국 리테일\nAI 유입 방문", "Prime Day\nGenAI 유입", "Black Friday\nAI 유입"]
    vals = [4700, 3300, 805]
    bars = a2.bar(names, vals, color=[BLUE, "#5b7fe0", "#8ea7ea"], width=0.55)
    for b, v in zip(bars, vals):
        a2.text(b.get_x() + b.get_width() / 2, v + 120, "+{:,}%".format(v),
                ha="center", fontsize=10.5, color=INK, fontweight="bold")
    a2.set_ylim(0, 5600)
    a2.set_yticks([0, 1500, 3000, 4500])
    a2.set_yticklabels(["0", "1,500%", "3,000%", "4,500%"])
    a2.set_title("AI 유입 트래픽 전년 대비 증가율", fontsize=11, color=INK, pad=14)
    bare(a2)

    finish(fig, "01_ai_traffic.png",
           "근거 A1(1차, Imperva Bad Bot Report 2026), B1·B2·B3(2차 인용, Adobe Analytics)")


# 2. 도입과 실제 작동의 격차 ---------------------------------------------------
def chart_gap():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.7))

    a1.bar(["AI를 쓴다", "완전히 통합했다"], [88, 25], color=[BLUE, RED], width=0.5)
    for i, v in enumerate([88, 25]):
        a1.text(i, v + 2.5, "{}%".format(v), ha="center", fontsize=13,
                fontweight="bold", color=INK)
    a1.set_ylim(0, 105)
    a1.set_yticks([0, 25, 50, 75, 100])
    a1.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    a1.set_title("콜센터의 AI 도입과 통합", fontsize=11, color=INK, pad=14)
    bare(a1)

    a2.bar(["벤더 데모"], [90], color=BLUE, width=0.45)
    a2.bar(["실제 프로덕션"], [62.5], yerr=[[7.5], [7.5]], color=AMBER, width=0.45,
           capsize=7, error_kw={"ecolor": INK, "elinewidth": 1.2})
    a2.text(0, 93, "90% 이상", ha="center", fontsize=12, fontweight="bold", color=INK)
    a2.text(1, 73, "55~70%", ha="center", fontsize=12, fontweight="bold", color=INK)
    a2.set_ylim(0, 108)
    a2.set_yticks([0, 25, 50, 75, 100])
    a2.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    a2.set_title("자동화율, 데모와 실제", fontsize=11, color=INK, pad=14)
    bare(a2)

    finish(fig, "02_adoption_gap.png",
           "근거 D1(2차), D3(2차). 함께 볼 것: D2 Gartner, 2027년까지 agentic AI 프로젝트 40% 이상 폐기 전망(2차 인용)")


# 3. 시장 규모 ---------------------------------------------------------------
def chart_market():
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    years = [2026, 2027, 2028, 2029, 2030]
    v0, v1 = 151.2, 478.2
    vals = [v0 * (1.258 ** i) for i in range(5)]
    vals[-1] = v1
    ax.plot(years, vals, marker="o", color=BLUE, linewidth=2.4, markersize=7)
    ax.fill_between(years, vals, color=BLUE, alpha=0.10)
    ax.annotate("151.2억 달러", (2026, v0), textcoords="offset points",
                xytext=(6, 12), fontsize=10, color=INK)
    ax.annotate("478.2억 달러", (2030, v1), textcoords="offset points",
                xytext=(-72, -4), fontsize=10, color=INK, fontweight="bold")
    ax.text(2027.9, 250, "연평균 성장률 25.8%", fontsize=10.5, color=BLUE, fontweight="bold")
    ax.set_xticks(years)
    ax.set_ylim(0, 560)
    ax.set_yticks([0, 150, 300, 450])
    ax.set_yticklabels(["0", "150", "300", "450"])
    ax.set_ylabel("억 달러", fontsize=9.5, color=DIM)
    ax.set_title("글로벌 AI 고객서비스 시장 전망", fontsize=11.5, color=INK, pad=14)
    bare(ax)
    finish(fig, "03_market.png",
           "근거 C1(1차 보도자료, MarketsandMarkets), C2(2차 인용). 사이 연도는 CAGR 25.8%로 계산한 값이다. "
           "국내 AICC 수치(C3)는 원출처가 확인되지 않아 넣지 않았다")


# 4. 처리 비용 ---------------------------------------------------------------
def chart_cost():
    fig, ax = plt.subplots(figsize=(7.4, 3.3))
    ax.barh([1], [25 - 15], left=[15], color=RED, height=0.42)
    ax.barh([0], [2.00 - 0.49], left=[0.49], color=GREEN, height=0.42)
    ax.scatter([0.99], [0], color=INK, zorder=5, s=42)
    ax.annotate("Intercom Fin 0.99달러", (0.99, 0), textcoords="offset points",
                xytext=(10, 14), fontsize=9.5, color=INK)
    ax.text(20, 1.32, "사람이 처리, 15~25달러", fontsize=10.5, color=INK, ha="center")
    ax.text(1.2, -0.42, "AI가 처리, 0.49~2.00달러", fontsize=10.5, color=INK, ha="center")
    ax.set_xscale("log")
    ax.set_xlim(0.3, 40)
    ax.set_xticks([0.5, 1, 2, 5, 10, 25])
    ax.set_xticklabels(["0.5", "1", "2", "5", "10", "25달러"])
    ax.set_yticks([])
    ax.set_ylim(-0.8, 1.8)
    ax.set_title("티켓 1건 처리 비용 (가로축은 로그 눈금)", fontsize=11.5, color=INK, pad=14)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(length=0, labelsize=9, colors=INK)
    finish(fig, "04_cost.png",
           "근거 E1·E2·E3(2차). 참고: 해결당 과금은 잘될수록 비싸져 이탈 사유 1위로 지목된다(E5, 2차)")


# 공통 상자 그리기 -------------------------------------------------------------
def box(ax, x, y, w, h, text, fc="white", ec=BLUE, fs=9.2, bold=False, tc=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                linewidth=1.4, edgecolor=ec, facecolor=fc))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", linespacing=1.5)


def arrow(ax, p1, p2, text="", color=DIM, fs=8.4, off=(0, 0.018)):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=13,
                                 color=color, linewidth=1.3,
                                 shrinkA=2, shrinkB=2))
    if text:
        ax.text((p1[0] + p2[0]) / 2 + off[0], (p1[1] + p2[1]) / 2 + off[1], text,
                ha="center", va="bottom", fontsize=fs, color=color)


def canvas(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


# 5. 화면 흐름도 --------------------------------------------------------------
def chart_screen_flow():
    fig, ax = canvas((9.6, 3.4))
    box(ax, 0.03, 0.46, 0.25, 0.30,
        "SCR-01 프로젝트 목록\nGET /", fc=PALE, bold=True)
    box(ax, 0.37, 0.46, 0.25, 0.30,
        "SCR-02 조립 현황\nGET /project", fc=PALE, bold=True)
    box(ax, 0.71, 0.46, 0.26, 0.30,
        "SCR-03 Composer\nGET, POST /composer", fc=PALE, bold=True)
    arrow(ax, (0.28, 0.61), (0.37, 0.61), "프로젝트를 고른다")
    arrow(ax, (0.62, 0.61), (0.71, 0.61), "구성을 바꾼다")
    box(ax, 0.03, 0.08, 0.94, 0.20,
        "상단 메뉴는 세 화면에 늘 있다. 경로가 없으면 뒤의 둘은 비활성으로 보인다.",
        fc="#fbfcfe", ec=LINE, fs=9.4, tc=DIM)
    ax.text(0.5, 0.93, "화면 흐름", ha="center", fontsize=12.5, color=INK, fontweight="bold")
    finish(fig, "05_screen_flow.png", "출처: final_project_ui/console/web.py 의 라우트를 2026-08-28에 실행해 확인")


# 6. Composer 저장 흐름 --------------------------------------------------------
def chart_composer_flow():
    fig, ax = canvas((9.6, 3.6))
    steps = [
        ("1단계\n화면에서 고친다", "브라우저 안의\n후보만 바뀐다", PALE, BLUE),
        ("2단계\n검증", "POST /composer/validate\n저장하지 않는다", "#fff8e6", AMBER),
        ("3단계\n사유 적고 적용", "POST /composer/apply\nrevision 일치할 때만", "#e9f6ef", GREEN),
        ("4단계\n다시 읽기", "새 revision을\n화면에 보여준다", PALE, BLUE),
    ]
    w, gap = 0.215, 0.048
    for i, (title, sub, fc, ec) in enumerate(steps):
        x = 0.02 + i * (w + gap)
        box(ax, x, 0.42, w, 0.30, title, fc=fc, ec=ec, bold=True, fs=9.8)
        ax.text(x + w / 2, 0.34, sub, ha="center", va="top", fontsize=8.6,
                color=DIM, linespacing=1.5)
        if i < 3:
            arrow(ax, (x + w, 0.57), (x + w + gap, 0.57))
    ax.text(0.5, 0.90, "Composer 저장 흐름", ha="center", fontsize=12.5,
            color=INK, fontweight="bold")
    ax.text(0.5, 0.10, "쓰기는 대상 프로세스 안에서 대상의 계약으로 검증한 뒤 실행된다. "
                       "콘솔은 인증된 API를 호출할 뿐 대상 파일을 직접 쓰지 않는다.",
            ha="center", fontsize=9, color=DIM)
    finish(fig, "06_composer_flow.png", "출처: final_project_ui/console/composer.py, console/web.py")


# 7. 저장소 구조 ---------------------------------------------------------------
def chart_storage():
    fig, ax = canvas((9.6, 4.6))
    box(ax, 0.04, 0.78, 0.92, 0.14,
        "A-COP Runtime (코어 1 Case Runtime, 코어 2 Access & Action)",
        fc=PALE, bold=True, fs=10.5)
    cols = [
        (0.04, "PostgreSQL", "업무 상태의 단일 원천\n\ncustomer_cases\ncase_events\nshared_state\nagent_runs\nteam_tasks\noutbox\naction_requests\naction_approvals\naudit_logs", BLUE),
        (0.36, "pgvector", "지식 문서 의미 검색\n\nknowledge_documents\nknowledge_chunks\nembedding(vector)\n\n같은 PostgreSQL 안의\n확장이라 트랜잭션을\n같이 쓴다", GREEN),
        (0.68, "Graph Store (선택)", "관계 조회\n\ncase, issue, policy,\nteam, action 사이의\n관계\n\nPort로 분리해 두고\n채택 기준을 넘을 때만\n켠다", AMBER),
    ]
    for x, title, body, c in cols:
        box(ax, x, 0.12, 0.28, 0.58, "", fc="white", ec=c)
        ax.text(x + 0.14, 0.635, title, ha="center", fontsize=11, color=c, fontweight="bold")
        ax.text(x + 0.14, 0.585, body, ha="center", va="top", fontsize=8.8,
                color=INK, linespacing=1.62)
        arrow(ax, (x + 0.14, 0.78), (x + 0.14, 0.70), color=c)
    ax.text(0.5, 0.965, "저장소 구조", ha="center", fontsize=12.5, color=INK, fontweight="bold")
    ax.text(0.5, 0.045, "업무 상태와 Action 트랜잭션은 PostgreSQL 하나를 단일 원천으로 삼는다. "
                        "Graph Store는 Port와 Adapter로 갈아 끼운다.",
            ha="center", fontsize=9, color=DIM)
    finish(fig, "07_storage.png", "출처: A-COP_구현계획서_v8.md 11절, 9-D절")


# 8. 데이터 파이프라인 ---------------------------------------------------------
def chart_pipeline():
    fig, ax = canvas((9.8, 3.9))
    rows = [
        ("수집", "브라우저 확장,\n공개 데이터셋,\n택배 조회 API", BLUE),
        ("정규화", "스키마 통일,\n개인정보 제거,\n중복 제거", AMBER),
        ("색인", "문서 분할,\n임베딩 생성,\npgvector 적재", GREEN),
        ("사용", "Context Broker가\nContextPack으로\n조합", BLUE),
    ]
    w, gap = 0.215, 0.047
    for i, (title, sub, c) in enumerate(rows):
        x = 0.025 + i * (w + gap)
        box(ax, x, 0.40, w, 0.32, title, fc="white", ec=c, bold=True, fs=11)
        ax.text(x + w / 2, 0.34, sub, ha="center", va="top", fontsize=8.8,
                color=DIM, linespacing=1.6)
        if i < 3:
            arrow(ax, (x + w, 0.56), (x + w + gap, 0.56))
    box(ax, 0.025, 0.05, 0.95, 0.16,
        "raw 와 processed 는 본인의 실제 구매 기록을 담고 있어 git에 올리지 않는다. "
        "스크립트, 스키마, REPORT.md 만 올린다.", fc="#fff8e6", ec=AMBER, fs=9.2)
    ax.text(0.5, 0.92, "데이터 처리 흐름", ha="center", fontsize=12.5, color=INK, fontweight="bold")
    finish(fig, "08_pipeline.png", "출처: datasets/README.md, 각 데이터셋 폴더의 REPORT.md")


# 9. 데이터셋 수집 현황 ---------------------------------------------------------
def chart_dataset_status():
    fig, ax = plt.subplots(figsize=(8.4, 3.5))
    labels = ["네이버 주문\n(건)", "택배 조회\n(건)", "쿠팡 주문\n(건)"]
    got = [68, 13, 0]
    miss = [4, 45, 0]
    ax.bar(labels, got, color=GREEN, width=0.45, label="확보")
    ax.bar(labels, miss, bottom=got, color="#e6b8b4", width=0.45, label="못 가져옴")
    for i, (g, m) in enumerate(zip(got, miss)):
        if g:
            ax.text(i, g / 2, str(g), ha="center", va="center", color="white",
                    fontsize=11, fontweight="bold")
        if m:
            ax.text(i, g + m / 2, str(m), ha="center", va="center", color=INK, fontsize=10)
    ax.text(2, 3, "수치 확정 전", ha="center", fontsize=9.5, color=DIM)
    ax.set_ylim(0, 78)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_title("데이터 수집 현황 (2026-08-28)", fontsize=11.5, color=INK, pad=14)
    bare(ax)
    finish(fig, "09_dataset_status.png",
           "출처: datasets/commerce/*/REPORT.md. 택배는 오래된 송장번호가 6~12개월 뒤 조회가 막혀 이력이 없다")


# 10. Case 상태 전이 -----------------------------------------------------------
def chart_case_states():
    fig, ax = canvas((10.2, 4.8))
    w, h = 0.145, 0.10

    main = [("new", 0.02), ("classifying", 0.20), ("routing", 0.38), ("running", 0.56)]
    for name, x in main:
        box(ax, x, 0.47, w, h, name, fc="white", ec=BLUE, fs=9, tc=BLUE, bold=True)
    for (a, xa), (b, xb) in zip(main, main[1:]):
        arrow(ax, (xa + w, 0.52), (xb, 0.52))
    box(ax, 0.80, 0.47, w, h, "resolved", fc="white", ec=GREEN, fs=9, tc=GREEN, bold=True)
    arrow(ax, (0.56 + w, 0.52), (0.80, 0.52), "처리 완료", off=(0, 0.022))

    waits = [("waiting_input", 0.30), ("waiting_approval", 0.50), ("waiting_external", 0.70)]
    for name, x in waits:
        box(ax, x, 0.80, 0.19, h, name, fc="#fff8e6", ec=AMBER, fs=8.6, tc=AMBER, bold=True)
        arrow(ax, (0.632, 0.57), (x + 0.095, 0.80), color=AMBER)

    box(ax, 0.50, 0.19, 0.19, h, "resuming", fc="#fff8e6", ec=AMBER, fs=9, tc=AMBER, bold=True)
    for name, x in waits:
        arrow(ax, (x + 0.095, 0.80), (0.595, 0.29), color=AMBER)
    arrow(ax, (0.50, 0.24), (0.585, 0.47), color=AMBER)

    ax.text(0.945, 0.855, "보류 상태", fontsize=9.5, color=AMBER, ha="center", fontweight="bold")
    ax.text(0.945, 0.815, "고객 정보 대기,\n승인 대기,\n외부 콜백 대기", fontsize=8.4,
            color=DIM, ha="center", va="top", linespacing=1.6)
    ax.text(0.30, 0.24, "재개는 resume_token\n검증을 통과해야 한다", fontsize=8.6,
            color=DIM, ha="center", va="center", linespacing=1.6)

    box(ax, 0.02, 0.02, 0.96, 0.115,
        "자동 처리 한계에 걸리면 escalated 로 보내 사람이 받는다.  "
        "복구 불가는 failed,  취소는 cancelled 다.  "
        "허용된 다음 상태 표를 벗어나는 전이는 거부한다.",
        fc="#f7f9fc", ec=LINE, fs=9.2, tc=INK)

    ax.text(0.5, 0.965, "Case 상태 전이 (12개 상태)", ha="center", fontsize=12.5,
            color=INK, fontweight="bold")
    finish(fig, "10_case_states.png",
           "출처: A-COP_구현계획서_v8.md 19절. 모든 전이는 case_events 에 추가만 되므로 나중에 그대로 재생할 수 있다")


if __name__ == "__main__":
    print("도표 생성:")
    chart_traffic()
    chart_gap()
    chart_market()
    chart_cost()
    chart_screen_flow()
    chart_composer_flow()
    chart_storage()
    chart_pipeline()
    chart_dataset_status()
    chart_case_states()
    print("완료:", OUT)
