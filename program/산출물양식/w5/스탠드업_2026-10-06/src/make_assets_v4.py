"""5주차 스탠드업 v3 그림 재료 (2026-10-06).

v2 에 대한 사용자 지적: 「디자인 스킬 쓴 거 맞아? 겁나 구린데」 — v2 는 디자인 스킬 없이 손으로 짰다.
v3 원칙(design-critique 진단 → design-system 토큰 → diagram-design 규칙):
- 색 · 글자 · 모서리는 triPilot 사용자 웹 디자인 시스템 토큰(초록 한 가지 + 따뜻한 경고 · 오류 톤, 시스템 글꼴, 큰 모서리)
- 차트는 「하나만 색, 나머지는 회색」 — 장마다 말하려는 막대 하나만 초록
- 흐름도는 diagram-design 원칙(밀도 4/10, 강조 노드 1~2개, 선은 정보가 있을 때만) — 되돌아가는 고리는 흐름 한가운데 실제 화살표로
출력: ../v3/_assets/
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
W5 = ROOT.parent
OUT = ROOT / "v4" / "_assets"
OUT.mkdir(parents=True, exist_ok=True)
CAP = W5 / "화면설계서" / "assets"

# triPilot 디자인 시스템 토큰(사용자 웹 apps/web, 디자인 시스템 아티팩트 tokens.json)
T = {
    "text": "#24392f", "muted": "#6d7c73", "caption": "#526858", "border": "#dce3dd", "surface": "#ffffff",
    "background": "#f3f5f3", "paper": "#f7f9f3", "primary": "#2e6047", "soft": "#e9f2eb", "subtle": "#f6f7f5",
    "warning": "#82693e", "warning_soft": "#faf6ec", "error": "#965640", "error_soft": "#fdf3ed", "dash": "#cbd8cd",
    "grey": "#c9d1cb", "grey2": "#a9b4ad",
}
for f in font_manager.findSystemFonts():
    if "malgun" in f.lower():
        font_manager.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 11,
    "text.color": T["text"], "axes.labelcolor": T["muted"], "xtick.color": T["muted"], "ytick.color": T["text"],
    "axes.edgecolor": T["border"], "figure.facecolor": T["paper"], "axes.facecolor": T["paper"], "savefig.facecolor": T["paper"],
})


def clean(ax, left=False):
    for s in ("top", "right", "bottom") + (() if left else ("left",)):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)


def save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=300, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return p


# ---------------------------------------------------------------- 커밋 (날짜별)
def commits():
    days = ["9/29", "9/30", "10/1", "10/2", "10/3", "10/4", "10/5", "10/6"]
    n = [4, 91, 85, 18, 112, 74, 76, 71]
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    cols = [T["primary"] if v == max(n) else T["grey"] for v in n]
    ax.bar(days, n, color=cols, width=0.62)
    for i, v in enumerate(n):
        ax.text(i, v + 2.5, str(v), ha="center", fontsize=11, color=T["primary"] if v == max(n) else T["muted"], fontweight="bold" if v == max(n) else None)
    clean(ax)
    ax.set_yticks([])
    ax.tick_params(axis="x", labelsize=11, colors=T["muted"])
    ax.set_ylim(0, 125)
    return save(fig, "commits.png")


# ---------------------------------------------------------------- 파인튜닝 결과
def finetune():
    rows = [("Gemma 4 E4B · 파인튜닝 전", 688, "base"), ("Gemma 4 26B-A4B · 파인튜닝 없음", 732, "grey"),
            ("Qwen3.8 27B · 파인튜닝 없음", 749, "grey"), ("Gemma 4 E4B · 파인튜닝 1회차", 750, "ft"),
            ("Winnow-E4B(Jev 계열) · 파인튜닝", 756, "ft"), ("Gemma 4 E4B · 파인튜닝 2회차", 760, "focal")]
    col = {"base": T["grey2"], "grey": T["grey2"], "ft": "#7fa38d", "focal": T["primary"]}
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    for x in range(660, 781, 20):
        ax.axvline(x, color=T["border"], lw=0.8, zorder=0)
    for i, (n, v, k) in enumerate(rows):
        ax.plot([660, v], [i, i], color=T["border"], lw=2, zorder=1)
        ax.scatter([v], [i], s=230 if k == "focal" else 150, color=col[k], zorder=3)
        ax.text(v + 4, i, f"{v}", va="center", fontsize=13, fontweight="bold", color=T["primary"] if k != "base" and k != "grey" else T["muted"])
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=11.5)
    ax.invert_yaxis()
    clean(ax)
    ax.set_xlim(660, 785)
    ax.set_xticks(range(660, 781, 20))
    ax.tick_params(axis="x", labelsize=10.5, colors=T["muted"])
    ax.set_xlabel("맞힌 문제 수 (769문제 중) · 가로축 660부터", fontsize=10.5, color=T["muted"])
    return save(fig, "finetune.png")


# ---------------------------------------------------------------- 출제자 제외 비교 (B 막대 + C 점)
def fair():
    fc = json.loads((W5 / "멀티에이전트_테스트보고서" / "_재료" / "fair_commercial.json").read_text(encoding="utf-8"))
    out = []
    for sub in ("codex_made", "claude_made"):
        rows = fc[sub]
        fig, ax = plt.subplots(figsize=(5.4, 0.62 * len(rows) + 0.5))
        for i, r in enumerate(rows):
            b, c = r["B"] / r["n"] * 100, r["C"] / r["n"] * 100
            name = r["model"].replace("(상용)", "").replace("(파인튜닝 없음, 로컬)", "").replace("(약 4B, 로컬)", "").strip()
            focal = r["kind"] == "local_ft"
            comm = r["kind"] in ("claude", "codex")
            colr = T["primary"] if focal else (T["text"] if comm else T["grey2"])
            ax.plot([86, b], [i, i], color=T["border"], lw=2, zorder=1)
            ax.scatter([b], [i], s=200 if focal else 140, color=colr if (focal or comm) else T["grey2"], zorder=3)
            ax.text(b + 0.55, i, f"{b:.1f}", va="center", fontsize=11.5, fontweight="bold", color=colr if (focal or comm) else T["muted"])
            ax.text(103.6, i, f"{c:.1f}", va="center", ha="right", fontsize=11.5, color=T["primary"] if focal else T["text"], fontweight="bold" if focal else None)
            ax.text(84.6, i, name + (" · 상용" if comm else ""), va="center", ha="right", fontsize=11,
                    color=T["primary"] if focal else T["text"], fontweight="bold" if focal else None)
        for x in (88, 92, 96, 100):
            ax.axvline(x, color=T["border"], lw=0.8, zorder=0)
            ax.text(x, len(rows) - 0.35, str(x), ha="center", va="top", fontsize=10, color=T["muted"])
        ax.text(93, -0.95, "B 채점 (%) · 가로축 86부터", ha="center", fontsize=11.5, color=T["text"], fontweight="bold")
        ax.text(103.6, -0.95, "C (%)", ha="right", fontsize=11.5, color=T["text"], fontweight="bold")
        ax.set_xlim(85, 104)
        ax.set_ylim(len(rows) - 0.1, -1.3)
        ax.set_xticks([])
        ax.set_yticks([])
        clean(ax)
        out.append(save(fig, f"fair_{sub}.png"))
    return out


# ---------------------------------------------------------------- 두 값 비교(덤벨)
def dumbbell(name, rows, lo, hi, fmt="{:.1f}%", good_up=True, w=5.6, h=2.0):
    fig, ax = plt.subplots(figsize=(w, h))
    for i, (lab, a, b) in enumerate(rows):
        c = T["primary"] if (b > a) == good_up else T["error"]
        ax.plot([a, b], [i, i], color=T["border"], lw=4, solid_capstyle="round", zorder=1)
        ax.scatter([a], [i], s=130, color=T["grey2"], zorder=3)
        ax.scatter([b], [i], s=170, color=c, zorder=3)
        ax.text(a, i - 0.3, fmt.format(a), ha="center", fontsize=12, color=T["muted"])
        ax.text(b, i - 0.3, fmt.format(b), ha="center", fontsize=15, fontweight="bold", color=c)
    ax.set_xlim(lo, hi)
    ax.set_ylim(len(rows) - 0.6, -0.75)
    ax.set_yticks([])
    ax.set_xticks([])
    clean(ax)
    return save(fig, name)


# ---------------------------------------------------------------- 규정 검색 기울기 그림
def slope():
    fig, ax = plt.subplots(figsize=(5.4, 3.7))
    lines = [("정답 규정을 보인 질문 (48문제 중)", 21 / 48 * 100, 31 / 48 * 100, "21개", "31개", T["primary"]),
             ("여행 대화에 규정을 잘못 붙임", 22.3, 36.7, "22.3%", "36.7%", T["error"])]
    for lab, a, b, la, lb, c in lines:
        ax.plot([0, 1], [a, b], color=c, lw=3, marker="o", markersize=9)
        ax.text(-0.06, a, la, ha="right", va="center", fontsize=13, color=T["muted"])
        ax.text(1.06, b, lb, ha="left", va="center", fontsize=15, fontweight="bold", color=c)
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(12, 72)
    ax.set_xticks([0, 1], ["지금(본문 인덱싱)", "고객용 문장 인덱싱"], fontsize=11)
    ax.set_yticks([])
    clean(ax)
    return save(fig, "slope.png")


# ---------------------------------------------------------------- 분류: 긴급도 + 나머지
def classify():
    return dumbbell("urgency.png", [("긴급도 정확도 · 400문장", 60.9, 88.4)], 50, 96, w=5.8, h=1.3)


# ---------------------------------------------------------------- 혼합 트래픽
def mixed():
    a = dumbbell("mixed_err.png", [("일정과 무관한 말에 항목을 잘못 고름 (낮을수록 좋음)", 4.5, 3.2)], 2.5, 5.2, good_up=False, w=5.4, h=1.3)
    b = dumbbell("mixed_acc.png", [("전체 정답률", 90.8, 91.9)], 90.2, 92.4, w=5.4, h=1.3)
    # 2026-10-07 생각 모드 끔(서비스 평가 베이스라인 리포트 · 6주차 초안 4.5): 정답률 90.8 → 93.6, 앞단의 오지목 4.4 → 3.7(구간 겹침)
    c = dumbbell("mixed_think.png", [("", 90.8, 93.6)], 89.6, 94.6, w=5.4, h=1.3)
    d = dumbbell("mixed_err2.png", [("", 4.4, 3.7)], 3.0, 5.1, good_up=False, w=5.4, h=1.3)
    return a, b, c, d


# ---------------------------------------------------------------- 화면 캡처: 둥근 모서리 + 테두리
def rounded_shots():
    shots = [("04_trips_new_390.png", "capture_docs"), ("q_read_390.png", "capture_2026-10-06"), ("card_390.png", "capture_2026-10-06"),
             ("day_overview.png", "capture_2026-10-06"), ("09_trip_home_390.png", "capture_docs"), ("safety_top.png", "capture_2026-10-06")]
    out = []
    for f, d in shots:
        im = Image.open(CAP / d / f).convert("RGBA")
        if f == "day_overview.png":  # mock 서버라 지도 타일이 비어 빨갛게 나온다 → 지도는 잘라 내고 일정 시트만 쓴다(화면을 고쳐 그리지 않음)
            im = im.crop((0, 330, im.width, im.height))
        w, h = im.size
        sc = 2
        big = im.resize((w * sc, h * sc), Image.LANCZOS)
        r = 34 * sc
        mask = Image.new("L", big.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, big.size[0] - 1, big.size[1] - 1], r, fill=255)
        canvas = Image.new("RGBA", (big.size[0] + 8, big.size[1] + 8), (0, 0, 0, 0))
        border = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(border).rounded_rectangle([0, 0, canvas.size[0] - 1, canvas.size[1] - 1], r + 4, fill=(220, 227, 221, 255))
        canvas.alpha_composite(border)
        big.putalpha(mask)
        canvas.alpha_composite(big, (4, 4))
        p = OUT / f"shot_{f}"
        canvas.save(p)
        out.append(p)
    return out


# ---------------------------------------------------------------- 흐름도(diagram-design 규칙) — SVG → PNG
def flow_svg():
    W, H = 1200, 430
    s = []
    a = s.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Malgun Gothic, sans-serif">')
    a(f'<rect width="{W}" height="{H}" fill="{T["paper"]}"/>')
    a('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
      f'<path d="M0,0 L10,5 L0,10 z" fill="{T["primary"]}"/></marker>'
      '<marker id="ag" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
      f'<path d="M0,0 L10,5 L0,10 z" fill="{T["muted"]}"/></marker></defs>')
    steps = [("01", "계획 올리기", "글 · 사진 · 파일"), ("02", "검사 · 고객 확인", "시간 겹침 · 이동 가능 여부"),
             ("03", "여행 중 위험 점검", "3분마다 휴관 · 마감 · 날씨"), ("04", "바꿀 안 + 알림", "요식업 · 액티비티 에이전트")]
    bw, bh, y = 236, 118, 60
    xs = [30, 330, 630, 930]
    for i, ((n, t, sub), x) in enumerate(zip(steps, xs)):
        focal = i in (2, 3)
        fill = T["soft"] if focal else T["surface"]
        stroke = T["primary"] if focal else T["border"]
        a(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="18" fill="{fill}" stroke="{stroke}" stroke-width="{2 if focal else 1.5}"/>')
        a(f'<text x="{x + 22}" y="{y + 34}" font-size="13" letter-spacing="1.5" fill="{T["primary"]}" font-weight="700">{n}</text>')
        a(f'<text x="{x + 22}" y="{y + 70}" font-size="23" font-weight="700" fill="{T["text"]}">{t}</text>')
        a(f'<text x="{x + 22}" y="{y + 98}" font-size="15" fill="{T["muted"]}">{sub}</text>')
        if i < 3:
            a(f'<line x1="{x + bw + 8}" y1="{y + bh / 2}" x2="{xs[i + 1] - 10}" y2="{y + bh / 2}" stroke="{T["primary"]}" stroke-width="2.2" marker-end="url(#ar)"/>')
    # 되돌아가는 고리: 04 → 03
    x3, x4 = xs[2] + bw / 2, xs[3] + bw / 2
    yb = y + bh + 62
    a(f'<path d="M{x4},{y + bh + 4} V{yb} H{x3} V{y + bh + 10}" fill="none" stroke="{T["primary"]}" stroke-width="2.6" marker-end="url(#ar)"/>')
    a(f'<rect x="{(x3 + x4) / 2 - 128}" y="{yb - 17}" width="256" height="34" rx="17" fill="{T["paper"]}"/>')
    a(f'<text x="{(x3 + x4) / 2}" y="{yb + 6}" text-anchor="middle" font-size="16" font-weight="700" fill="{T["primary"]}">여행이 끝날 때까지 되풀이</text>')
    # 고객 채팅 입력(점선 = 바깥에서 들어옴)
    cx = xs[3] + bw / 2
    a(f'<rect x="{xs[3] + 10}" y="{H - 92}" width="{bw - 20}" height="64" rx="16" fill="{T["surface"]}" stroke="{T["dash"]}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    a(f'<text x="{cx}" y="{H - 64}" text-anchor="middle" font-size="15" font-weight="700" fill="{T["text"]}">고객 채팅 · 개인 AI 비서</text>')
    a(f'<text x="{cx}" y="{H - 41}" text-anchor="middle" font-size="13" fill="{T["muted"]}">「거기 웨이팅 심해?」</text>')
    a(f'<line x1="{cx + 70}" y1="{H - 92}" x2="{cx + 70}" y2="{y + bh + 8}" stroke="{T["muted"]}" stroke-width="1.6" stroke-dasharray="5 4" marker-end="url(#ag)"/>')
    a('</svg>')
    p = OUT / "flow.svg"
    p.write_text("\n".join(s), encoding="utf-8")
    return p


def funnel_svg():
    W, H = 640, 470
    rows = [(835, "문제 835개 입력", "복수 항목 질의 66개 포함", T["grey"], T["text"]),
            (710, "규칙이 125개를 바로 처리", "「첫 번째」 · 「~말고」 · 같은 장소", T["soft"], T["text"]),
            (674, "ML 사전 필터가 36개를 처리", "일정과 무관한 잡담은 「없음」", T["soft"], T["text"]),
            (674, "파인튜닝 Gemma 4 E4B 호출 674번", "혼자 풀면 835번 → 19% 감소", T["primary"], "#ffffff")]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Malgun Gothic, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="{T["paper"]}"/>']
    y = 10
    for i, (n, t, sub, fill, tc) in enumerate(rows):
        w = 620 - i * 60
        x = (W - w) / 2
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="92" rx="16" fill="{fill}" stroke="{T["primary"] if i == 3 else T["border"]}" stroke-width="1.5"/>')
        s.append(f'<text x="{W / 2}" y="{y + 42}" text-anchor="middle" font-size="22" font-weight="700" fill="{tc}">{t}</text>')
        s.append(f'<text x="{W / 2}" y="{y + 70}" text-anchor="middle" font-size="15" fill="{tc if i == 3 else T["muted"]}">{sub}</text>')
        y += 92 + (24 if i < 3 else 0)
        if i < 3:
            s.append(f'<path d="M{W / 2 - 9},{y - 19} L{W / 2 + 9},{y - 19} L{W / 2},{y - 7} z" fill="{T["grey2"]}"/>')
    s.append("</svg>")
    p = OUT / "funnel.svg"
    p.write_text("\n".join(s), encoding="utf-8")
    return p


def mixbar_svg():
    W, H = 1180, 120
    parts = [("일정 질문", 835, T["primary"], "#ffffff"), ("관광지 질문", 600, "#7fa38d", "#ffffff"), ("일상 대화", 1000, T["grey"], T["text"]), ("구어체 문장", 300, "#e2e7e3", T["text"])]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Malgun Gothic, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="{T["paper"]}"/>']
    x = 0
    for i, (t, n, c, tc) in enumerate(parts):
        w = W * n / 2735
        s.append(f'<rect x="{x + 2}" y="10" width="{w - 4}" height="100" rx="14" fill="{c}"/>')
        s.append(f'<text x="{x + w / 2}" y="54" text-anchor="middle" font-size="20" font-weight="700" fill="{tc}">{t}</text>')
        s.append(f'<text x="{x + w / 2}" y="84" text-anchor="middle" font-size="18" fill="{tc}">{n:,}</text>')
        x += w
    s.append("</svg>")
    p = OUT / "mixbar.svg"
    p.write_text("\n".join(s), encoding="utf-8")
    return p


def render(svgs):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for p in svgs:
            page = b.new_page(device_scale_factor=3)
            page.goto(p.resolve().as_uri())
            page.locator("svg").screenshot(path=str(p.with_suffix(".png")), omit_background=False)
            page.close()
        b.close()


# ---------------------------------------------------------------- 하루 질문 수별 월 비용(손익 분기)
# 근거: program/research/여행일정_질문인식_모델비교_2026-09-29.md §71(API 단가 · 1건 토큰) · §76 · §78(AWS 앱 서버 t3.medium 5.4만원)
#       §80(RunPod 2000 Ada 24.5만원 · 한 대 하루 약 4.2만 건, 캐시 없음 실측) · §86(CPU 4코어 실측 → 2코어는 예상)
BE = {
    # 1건(입력 1,700 + 출력 12 토큰, 1,400원/달러, 생각 토큰 제외). Claude 단가는 RAG 세션이 공식 페이지에서 확인(2026-10-07)
    "api_won": {"Luna": 0.25, "Sol": 4.93, "Claude Opus 5.5": 9.86, "Astra · Claude Fable 5.1": 24.64},
    "app": 5.4,            # API 를 쓰려면 앱 서버가 따로 필요(AWS 서울 t3.medium, 만원/월)
    "runpod": 25.6,        # RunPod RTX A4000 시큐어 $0.25 × 730시간 × 1,400원(16 vCPU · 62GB · 100GB, 앱까지 한 대 — 2026-10-07 사용자 포드), 만원/월
    "runpod_cap": 36200,   # 한 대 하루 처리 — 몰리는 시간 기준: A4000 실측 하루 16.3만(동시 8, RAG 세션 10-07) ÷ 24 × 가동률 80% ÷ 피크 몫 15%
    "oracle_cap": 670,     # 오라클 무료 2코어 ARM · 12GB — 몰리는 시간 기준 하루 약 670건(쉬지 않을 때 약 3,000건, RAG 세션 실측 2026-10-07). scaling_plan.free_only_cap()
}


def breakeven():
    import math
    import numpy as np
    xs = np.logspace(2, 5, 400)
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    col = {"Luna": T["grey2"], "Sol": T["text"], "Claude Opus 5.5": T["warning"], "Astra · Claude Fable 5.1": T["error"]}
    for m, won in BE["api_won"].items():
        ys = BE["app"] + won * 30 * xs / 10000
        ax.plot(xs, ys, color=col[m], lw=2.4, label=f"{m} API + 앱 서버")
    rp = [BE["runpod"] * math.ceil(x / BE["runpod_cap"]) for x in xs]
    ax.plot(xs, rp, color=T["primary"], lw=3, label="RunPod A4000 GPU 서버(앱 포함)")
    ox = xs[xs <= BE["oracle_cap"]]
    ax.plot(ox, [0] * len(ox), color="#7fa38d", lw=5, solid_capstyle="round", label="오라클 무료 서버")
    ax.axvspan(100, BE["oracle_cap"], color=T["soft"], alpha=0.6, zorder=0)
    ax.text(260, 93, "무료 서버만으로\n감당(몰리는 시간 기준)", fontsize=10, color=T["primary"], ha="center", va="top")
    for m, won in BE["api_won"].items():
        x0 = (BE["runpod"] - BE["app"]) * 10000 / (won * 30)
        if 100 <= x0 <= 100000:
            ax.scatter([x0], [BE["runpod"]], s=70, color=col[m], zorder=5, edgecolor="white", linewidth=1.5)
            short = {"Astra · Claude Fable 5.1": "Astra · Fable", "Claude Opus 5.5": "Opus"}.get(m, m)
            off = {"Luna": (0, -40), "Claude Opus 5.5": (8, -44), "Sol": (14, 24), "Astra · Claude Fable 5.1": (-14, 24)}[m]
            ax.annotate(f"{short}\n하루 약 {x0:,.0f}건", (x0, BE["runpod"]), xytext=off,
                        textcoords="offset points", ha="center", fontsize=9.5, color=col[m] if m != "Luna" else T["muted"], fontweight="bold")
    ax.set_xscale("log")
    ax.set_xlim(100, 100000)
    ax.set_ylim(-3, 100)
    ax.set_xticks([100, 300, 1000, 3000, 10000, 30000, 100000], ["100", "300", "1천", "3천", "1만", "3만", "10만"])
    ax.set_xlabel("하루 질문 수 (로그 눈금)", fontsize=10.5, color=T["muted"])
    ax.set_ylabel("월 비용 (만원)", fontsize=10.5, color=T["muted"])
    ax.grid(True, axis="y", color=T["border"], lw=0.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=9.5, bbox_to_anchor=(0.6, 1.0))
    return save(fig, "breakeven.png")


# ---------------------------------------------------------------- 단계별 전환 계획(질문 수마다 가장 싼 조합) — scaling_plan.py 계산
def scaling():
    import numpy as np
    import scaling_plan as SP
    xs = np.unique(np.round(np.logspace(np.log10(300), np.log10(150000), 600)))
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bands = [(300, 700, "⓪", "#f7f9f3"), (700, 40650, "①", "#eef4ef"), (40650, 140450, "②", "#e3ede6"), (140450, 150000, "③", "#d6e5da")]
    for x0, x1, lab, c in bands:
        ax.axvspan(x0, x1, color=c, zorder=0)
        ax.text((x0 * x1) ** 0.5, 57, lab, ha="center", fontsize=15, fontweight="bold", color=T["primary"], fontfamily=["Malgun Gothic", "Segoe UI Symbol"])
    for m, c, ls in (("Luna", T["primary"], "-"), ("Sol", T["text"], (0, (5, 3)))):
        ys = [SP.best(x, SP.API[m])["cost"] / 10000 for x in xs]
        ax.plot(xs, ys, color=c, lw=3, ls=ls, label=f"{'비용 우선' if m == 'Luna' else '품질 우선'}: 넘치는 질문을 {m} API 로")
    ax.set_xscale("log")
    ax.set_xlim(300, 150000)
    ax.set_ylim(-2, 62)
    ax.set_xticks([300, 1000, 3000, 10000, 30000, 100000], ["300", "1천", "3천", "1만", "3만", "10만"])
    ax.set_xlabel("하루 질문 수 (로그 눈금)", fontsize=10.5, color=T["muted"])
    ax.set_ylabel("월 비용 (만원)", fontsize=10.5, color=T["muted"])
    ax.grid(True, axis="y", color="white", lw=1.2)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=10, bbox_to_anchor=(0.0, 0.85))
    return save(fig, "scaling.png")


# ---------------------------------------------------------------- JevBench 순위 ↔ 우리 순위 (2026-10-07 사용자: 「순위가 거의 일치하는 것도 우리 벤치가 이상하지 않다는 근거 아니냐」)
# 계산: program/scripts/plan_qa_bench/jevbench_rank_check.py (mix8 · mix9 공통 309문제, 학습 없는 원본 모델 단독 풀이)
def jevbench_rank():
    # 2026-10-07 사용자: 「이름이 안 적힌 점이 있다」 → 17개 점 모두에 이름을 단 판으로 대체(make_jevbench_rank_v5.py, 계산은 같다).
    #  옛 판(이름표 8개만) 코드는 _backup/*_v4_순위그림교체전/make_assets_v4.py.bak 에 있다.
    import make_jevbench_rank_v5 as V5
    V5.main(OUT)
    return OUT / "jevbench_rank.png"


# ---------------------------------------------------------------- 조합 시험 모음 (2026-10-07 사용자: 「Jev 계열 · 임베딩 · LLM · SLM · ML 조합을 MoE 식으로 구성해 시험한 것도 들어가야」)
# 근거: 연구 문서 §82-5 · §85-3 · §92-4 · §92-6 · §92-9 (같은 769문제, 복수 항목 질의 제외)
COMBOS = [
    ("파인튜닝 Winnow-E4B(Jev 계열) 단독", 756, 756, "solo"),
    ("파인튜닝 Gemma 4 E4B 단독 (시드 1 · 2)", 750, 760, "solo"),
    ("서수 규칙(코드) → 파인튜닝 E4B", 753, 753, "combo"),
    ("규칙 → ML 필터 → 파인튜닝 Winnow-E4B", 752, 752, "combo"),
    ("확신 낮으면 다른 파인튜닝 모델로 넘김", 750, 752, "combo"),
    ("ML 유형 판별기 → 유형별 전문 모델", 751, 751, "combo"),
    ("학습한 ML 라우터 → 두 모델 중 고름", 751, 751, "combo"),
    ("규칙 → ML 필터 → 파인튜닝 E4B", 745, 747, "combo"),
    ("규칙 → 임베딩 게이트 → 파인튜닝 E4B", 743, 747, "combo"),
    ("라우터에 파인튜닝 전 Winnow-E4B", 697, 697, "bad"),
]


def combos():
    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    ax.axvspan(750, 760, color=T["soft"], zorder=0)
    ax.text(755, -0.75, "시드만 바꿔도 생기는 차이", ha="center", va="top", fontsize=8.5, color=T["primary"])
    ax.set_ylim(-1.3, len(COMBOS) - 0.5)
    for i, (name, lo, hi, kind) in enumerate(COMBOS):
        y = len(COMBOS) - 1 - i
        c = {"solo": T["primary"], "combo": T["text"], "bad": T["error"]}[kind]
        if hi > lo:
            ax.plot([lo, hi], [y, y], color=c, lw=3, solid_capstyle="round", zorder=3)
        ax.scatter([lo, hi], [y, y], s=46, color=c, zorder=4, edgecolor="white", linewidth=1)
        ax.text(hi + 1.2, y, f"{lo}" if lo == hi else f"{lo}~{hi}", va="center", fontsize=9.5, color=c, fontweight="bold")
    ax.set_yticks(range(len(COMBOS)), [c[0] for c in COMBOS][::-1], fontsize=9.5)
    ax.set_xlim(694, 768)
    ax.set_xlabel("맞힌 문제 / 769", fontsize=10, color=T["muted"])
    ax.grid(True, axis="x", color=T["border"], lw=0.7)
    clean(ax)
    return save(fig, "combos.png")


def veils():
    from PIL import Image as I
    w, h = 1600, 900
    g = I.new("RGBA", (w, h))
    px = g.load()
    for x in range(w):
        t = x / w
        a = 240 if t < 0.42 else max(0, int(240 * (1 - (t - 0.42) / 0.2))) if t < 0.62 else 0
        for y in range(h):
            px[x, y] = (247, 249, 243, a)
    g.save(OUT / "veil_left.png")
    g2 = I.new("RGBA", (w, h), (247, 249, 243, 228))
    g2.save(OUT / "veil_full.png")


if __name__ == "__main__":
    veils()
    breakeven()
    scaling()
    jevbench_rank(); combos()
    commits(); finetune(); fair(); slope(); classify(); mixed(); rounded_shots()
    render([flow_svg(), funnel_svg(), mixbar_svg()])
    print("assets", len(list(OUT.iterdir())))
