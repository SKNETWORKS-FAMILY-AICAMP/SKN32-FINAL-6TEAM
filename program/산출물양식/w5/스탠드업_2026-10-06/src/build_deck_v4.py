"""5주차 스탠드업 v4 — v3 에 2026-10-07 요청 반영(피크 기준 비용 · A4000 · 외부 벤치마크 대조 · 조합 시험 · 이동 · 에이전트 · 배포 · 유스케이스 · 아키텍처 · 검토 수정 · 에이전트 이름 통일).

(v3 머리말)

v2 진단(design-critique): 장마다 같은 무게의 연두 · 베이지 상자가 가득해 눈이 갈 곳이 없음 · 오피스 기본 차트 ·
본문 10~11pt 로 작음 · 「이 장의 말」 칸이 반쯤 비어 있음 · 흐름도 선이 엇갈림.
v3 규칙(design-system = triPilot 사용자 웹 토큰, diagram-design = 밀도 4/10 · 강조 1~2개):
- 바탕 color-paper, 글 color-text, 강조는 color-primary 하나. 경고 · 오류만 따뜻한 톤
- 장마다 주인공 하나(큰 숫자 · 그림 · 화면), 나머지는 작고 조용하게. 상자는 꼭 필요할 때만, 모서리 크게
- 제목 위 영어 대문자 눈썹 문구(디자인 시스템의 Eyebrow), 숫자 아래 작은 글씨로 출처
재료: ../v3/_assets (make_assets_v3.py) · ../_재료/주간_사실.md · ../_재료/쉬운말_재료_v2.md
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
W5 = ROOT.parent
V3 = ROOT / "v4"
A = V3 / "_assets"
OUT = V3 / "[발표] triPilot_진행경과_2026-10-06_Claude_v4.pptx"
SCENE = Path(r"C:/Users/playdata2/Documents/final_workspace/final_project_cs/frontend/apps/web/public/images")
THUMB_SRC = ROOT / "v2" / "_thumbs"


def rgb(h):
    return RGBColor.from_string(h.lstrip("#"))


TEXT, MUTED, CAPTION = rgb("#24392f"), rgb("#6d7c73"), rgb("#526858")
BORDER, SURFACE, PAPER = rgb("#dce3dd"), rgb("#ffffff"), rgb("#f7f9f3")
PRIMARY, SOFT, SUBTLE = rgb("#2e6047"), rgb("#e9f2eb"), rgb("#f6f7f5")
WARN, WARN_SOFT, WARN_B = rgb("#82693e"), rgb("#faf6ec"), rgb("#e5d9c1")
ERR, ERR_SOFT, ERR_B = rgb("#965640"), rgb("#fdf3ed"), rgb("#ecd2c7")
GREY = rgb("#c9d1cb")
WHITE = rgb("#ffffff")
FONT = "맑은 고딕"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
SCRIPT = []
L, CW = 0.75, 11.83  # 왼쪽 여백 · 본문 폭


import re as _re


def g4(t):
    """2026-10-07 사용자 지시: E4B 는 「Gemma 4 E4B」로 제대로 적는다(Winnow-E4B 는 다른 모델이라 그대로)."""
    return _re.sub(r"(?<![\w-])(?<!Gemma 4 )E4B", "Gemma 4 E4B", t)


def text(s, x, y, w, h, runs, size=14, color=TEXT, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=0, spacing=None, line=None):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    lines = runs if isinstance(runs, list) and runs and isinstance(runs[0], list) else [runs]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if space:
            p.space_after = Pt(space)
        if line:
            p.line_spacing = line
        for t, o in ([(ln, {})] if isinstance(ln, str) else ln):
            r = p.add_run()
            r.text = g4(t)
            f = r.font
            f.name = FONT
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.color.rgb = o.get("color", color)
            sp = o.get("spacing", spacing)
            if sp is not None:
                r._r.get_or_add_rPr().set("spc", str(int(sp * 100)))
    return tb


def box(s, x, y, w, h, fill=SURFACE, line=BORDER, r=0.2, lw=1.0, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(lw)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = min(0.5, r / min(w, h))
    sh.shadow.inherit = False
    return sh


def alpha(sh, a):
    sf = sh.fill._xPr.find(qn("a:solidFill"))
    el = etree.SubElement(sf[0], qn("a:alpha"))
    el.set("val", str(int(a * 100000)))


def hline(s, x, y, w, color=BORDER, lw=1.0):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x), Inches(y), Inches(x + w), Inches(y))
    c.line.color.rgb = color
    c.line.width = Pt(lw)


def pic(s, path, x, y, w=None, h=None):
    iw, ih = Image.open(path).size
    if w and h:
        sc = min(w / iw, h / ih)
        pw, ph = iw * sc, ih * sc
        return s.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))
    if w:
        return s.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w))
    return s.shapes.add_picture(str(path), Inches(x), Inches(y), height=Inches(h))


def bg(s, color=PAPER):
    f = s.background.fill
    f.solid()
    f.fore_color.rgb = color


CHAPTERS = ["서비스", "모델", "비용", "검증", "남은 일"]
CH = None  # 지금 장의 파트 번호(1~5). None 이면 표시하지 않는다(표지 · 순서 · 부록)


def tracker(s):
    """2026-10-07 사용자: 「챕터 나눠서 지금 발표하는 부분이 어떤 파트인지 같이 알려줘」 — 장마다 오른쪽 위에 다섯 파트를 두고 지금 파트만 초록."""
    if not CH:
        return
    x = 13.333 - 0.75
    for k in range(len(CHAPTERS), 0, -1):
        t = f"{k:02d} {CHAPTERS[k - 1]}"
        w = 0.42 + len(CHAPTERS[k - 1]) * 0.17
        x -= w
        on = k == CH
        box(s, x, 0.4, w - 0.06, 0.3, fill=PRIMARY if on else SURFACE, line=None if on else BORDER, r=0.15, lw=0.75)
        text(s, x, 0.4, w - 0.06, 0.3, t, size=9.5, bold=on, color=WHITE if on else MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def head(s, eyebrow, title, sub=None):
    tracker(s)
    text(s, L, 0.5, CW, 0.3, eyebrow, size=10.5, bold=True, color=PRIMARY, spacing=2)
    size = 30 if len(title) <= 24 else 26
    text(s, L, 0.82, CW, 0.75, title, size=size, bold=True, color=TEXT, spacing=-0.5)
    if sub:
        text(s, L, 1.5, CW, 0.4, sub, size=13, color=MUTED)


def foot(s, t):
    text(s, L, 6.9, CW, 0.45, t, size=10.5, color=CAPTION, line=1.1)


def notes(s, t):
    t = g4(t)
    s.notes_slide.notes_text_frame.text = t
    SCRIPT.append(t)


def new(eyebrow=None, title=None, sub=None):
    s = prs.slides.add_slide(BLANK)
    bg(s)
    if eyebrow:
        head(s, eyebrow, title, sub)
    return s


def mark(s, x, y, d=0.62):
    b = box(s, x, y, d, d, fill=PRIMARY, line=None, r=d * 0.31)
    text(s, x, y - 0.02, d, d, "t", size=d * 44, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return b


def stat(s, x, y, w, big, label, how, color=PRIMARY, big_size=34):
    text(s, x, y, w, 0.7, big, size=big_size, bold=True, color=color, spacing=-0.5)
    text(s, x, y + big_size / 72 * 1.25 + 0.02, w, 0.35, label, size=13, bold=True)
    text(s, x, y + big_size / 72 * 1.25 + 0.36, w, 0.5, how, size=10, color=CAPTION)


def chip(s, x, y, t, fill=SOFT, color=PRIMARY, size=11.5, w=None):
    w = w or (0.28 + len(t) * size / 72 * 0.92)
    box(s, x, y, w, 0.36, fill=fill, line=None, r=0.18)
    text(s, x, y, w, 0.36, t, size=size, bold=True, color=color, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return w


def bubble(s, x, y, w, t, who, mine=False, h=0.62):
    box(s, x, y, w, h, fill=SOFT if mine else SURFACE, line=None if mine else BORDER, r=0.22)
    text(s, x + 0.2, y + 0.07, w - 0.4, 0.22, who, size=9, bold=True, color=PRIMARY if mine else MUTED)
    text(s, x + 0.2, y + 0.27, w - 0.4, h - 0.3, t, size=13)


def rounded(path, out, r=26, border=(220, 227, 221)):
    im = Image.open(path).convert("RGBA")
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.size[0] - 1, im.size[1] - 1], r, fill=255)
    c = Image.new("RGBA", (im.size[0] + 4, im.size[1] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(c).rounded_rectangle([0, 0, c.size[0] - 1, c.size[1] - 1], r + 2, fill=border + (255,))
    im.putalpha(m)
    c.alpha_composite(im, (2, 2))
    c.save(out)
    return out


# ================================================================ 1 표지
s = new()
pic(s, SCENE / "tripilot-home-02-paper-seoul.png", 0, 0, w=13.333)
pic(s, A / "veil_left.png", 0, 0, w=13.333)
mark(s, L, 1.25)
text(s, L + 0.78, 1.3, 4, 0.55, "triPilot", size=26, bold=True, spacing=-0.5)
text(s, L, 2.55, 6.4, 0.3, "WEEK 5 STANDUP  ·  SKN32 6팀 A-COPilot", size=11, bold=True, color=PRIMARY, spacing=2)
text(s, L, 2.95, 6.4, 1.0, "5주차 진행 경과", size=50, bold=True, spacing=-1.5)
text(s, L, 4.2, 6.0, 1.0, "자유여행자가 올린 여행 계획을\n여행이 끝날 때까지 지켜 주는 서비스", size=19, color=CAPTION, line=1.25)
text(s, L, 6.55, 6, 0.35, "2026.09.29 ~ 10.06", size=13, bold=True, color=MUTED)
notes(s, "triPilot 5주차 진행 경과를 말씀드리겠습니다. triPilot 은 자유여행자가 이미 짠 여행 계획을 받아서, 여행이 끝날 때까지 문제가 생기지 않는지 지켜보고 바꿔 주는 서비스입니다.")

# ================================================================ 1-2 순서
s = new("AGENDA", "오늘은 다섯 파트로 말씀드립니다")
parts = [("01", "서비스", "하는 일 · 유스케이스 · 아키텍처 · 한 주 규모 · 화면 · 서버 · 이동 · 에이전트 · 배포"),
         ("02", "모델", "모델이 푸는 문제 · 파인튜닝 방법과 검증 · 시험 A · B · C · D"),
         ("03", "비용", "상용 모델과 비교 · 손익 분기 · 단계별 전환 계획"),
         ("04", "검증", "여러 단계 잇기 · 혼합 트래픽 · 분류 · 규정 검색 · 사람 검수 · 측정 방법"),
         ("05", "남은 일", "해결한 것과 남은 것 · 다음 주")]
for k, (n, t, d) in enumerate(parts):
    yy = 1.8 + k * 0.98
    box(s, L, yy, CW, 0.82, fill=SURFACE, line=BORDER, r=0.2)
    text(s, L + 0.3, yy, 0.9, 0.82, n, size=26, bold=True, color=PRIMARY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 1.3, yy, 2.2, 0.82, t, size=18, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 3.5, yy, 8.0, 0.82, d, size=12.5, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "오늘은 서비스, 모델, 비용, 검증, 남은 일의 다섯 파트로 말씀드리겠습니다. 장마다 오른쪽 위에 지금 어느 파트인지 표시해 두었습니다.")

CH = 1
# ================================================================ 2 흐름
s = new("HOW IT WORKS", "계획을 받아 여행이 끝날 때까지 지킵니다")
pic(s, A / "flow.png", L - 0.05, 1.75, w=CW + 0.1)
y = 6.1
text(s, L, y - 0.42, 3, 0.3, "이번 주에 손댄 곳", size=11, bold=True, color=MUTED, spacing=1)
xs = [(L, "화면 12개를 cs 프로젝트 서버에 연결"), (L + 4.05, "실시간 진행 표시 · 개인 AI 입구"), (L + 8.1, "고객 말 → 일정 항목 매칭 모델")]
for x, t in xs:
    box(s, x, y + 0.1, 0.12, 0.12, fill=PRIMARY, line=None, r=0.06, shape=MSO_SHAPE.OVAL)
    text(s, x + 0.22, y, 3.7, 0.35, t, size=13, bold=True)
for x, t in ((L, "계획 올리기부터 재난 시 일정 정지까지"), (L + 4.05, "오래 걸리는 일의 단계 표시 · 본인 여행만"), (L + 8.1, "파인튜닝 시험 중 · 제품 미연결")):
    text(s, x + 0.22, y + 0.33, 3.7, 0.3, t, size=10.5, color=CAPTION)
foot(s, "「아키텍처 한눈에 v26」 그림 1 · 4 를 줄인 흐름입니다. 알림은 디스코드 등으로 보내고, 바뀐 내용은 로그인 없이 열리는 여행계획서 링크에도 반영됩니다.")
notes(s, "고객이 계획을 올리면 코드가 시간 겹침과 이동 가능 여부를 검사하고 고객이 확인합니다. 등록하면 여행 중 3분마다 휴관, 마감, 날씨 위험을 점검하고, 문제가 생기면 요식업 · 액티비티 에이전트가 바꿀 안을 만들어 알립니다. 이 점검과 수정은 여행이 끝날 때까지 되풀이됩니다. 이번 주에는 화면 연결, 실시간 진행 표시와 개인 AI 입구, 고객 말을 일정 항목에 매칭하는 모델을 다뤘습니다.")

# ================================================================ 2-2 유스케이스 · 아키텍처 (2026-10-07 사용자: 「아키텍처랑 유스케이스 그림이 없어」)
# 그림은 새로 그리지 않고 완성된 산출물 그림을 그대로 쓴다: w5/유스케이스/v7 · w5/AI시스템아키텍처/그림(그림2 컨테이너도 · 그림3 에이전트아키텍처)
W5DIR = Path(__file__).resolve().parents[2]
s = new("USE CASES", "고객 목표 12개와 공통 하위 기능 2개로 정리했습니다")
pic(s, W5DIR / "유스케이스" / "v7" / "triPilot_유스케이스_다이어그램_v7.png", L - 0.05, 1.55, h=5.25)
x = L + 6.15
ucs = [("누가 쓰나", "여행자 · 개인 AI 비서 앱(같은 일을 함) · 동행자(계획서 링크만) · 시간(3분마다 점검) · 운영자(장애 알림)"),
       ("무엇을 하나", "계획으로 여행 등록 · 일정 짜 달라 · 여행 중에 묻기 · 일정 바꿔 달라 · 생긴 문제 알림 · 다른 안 고르기 · 되돌리기"),
       ("공통 하위 기능", "일정을 다시 맞추고 알린다 · 바꾸기 전에 묻는다(보호 일정 · 「먼저 물어봐」일 때)"),
       ("하지 않는 것", "고객 건을 사람 상담원에게 넘기는 유스케이스는 없습니다")]
for k, (a_, b_) in enumerate(ucs):
    yy = 1.68 + k * 1.22
    if k:
        hline(s, x, yy - 0.14, 5.7)
    text(s, x, yy, 5.7, 0.3, a_, size=12.5, bold=True, color=PRIMARY)
    text(s, x, yy + 0.34, 5.7, 0.8, b_, size=11, color=TEXT, line=1.2)
foot(s, "유스케이스 명세 v7(22쪽, 10-03) · 처리 단계는 명세의 시나리오에 적었습니다. 실선 = 참여, 점선 = 포함 · 확장.")
notes(s, "유스케이스입니다. 쓰는 사람은 여행자와, 여행자 대신 일하는 개인 AI 비서 앱, 계획서 링크만 보는 동행자, 그리고 3분마다 일정을 점검하는 시간과 장애 알림을 받는 운영자입니다. 고객 목표는 계획으로 여행 등록하기부터 일정 바꾸기, 생긴 문제 알림, 다른 안 고르기까지 12개이고, 여러 유스케이스가 함께 쓰는 하위 기능이 둘 있습니다. 고객 건을 사람 상담원에게 넘기는 유스케이스는 일부러 두지 않았습니다.")

s = new("SYSTEM ARCHITECTURE", "두 입구가 API 하나로 모이고, 워커가 3분마다 일정을 지킵니다")
pic(s, W5DIR / "AI시스템아키텍처" / "그림" / "그림2_컨테이너도_v1.png", L - 0.05, 1.6, w=8.6)
x = L + 8.8
pts = [("입구 둘", "고객 웹(Next.js) · 고객의 개인 AI(MCP)"), ("API 하나", "FastAPI 안에 오케스트레이터 · 요식업 · 액티비티 에이전트 · 이동 판정"),
       ("워커", "1분마다 돌며 3분마다 외부 정보 6종 조회 · 알림 발송"), ("모델 · 저장", "Ollama gemma4:12b · 임베딩 / PostgreSQL + pgvector")]
for k, (a_, b_) in enumerate(pts):
    yy = 1.68 + k * 1.2
    if k:
        hline(s, x, yy - 0.14, 3.0)
    text(s, x, yy, 3.0, 0.3, a_, size=12.5, bold=True, color=PRIMARY)
    text(s, x, yy + 0.34, 3.0, 0.8, b_, size=10.5, color=TEXT, line=1.15)
foot(s, "AI 시스템 아키텍처 문서(28쪽 · 그림 10장)의 그림 2. 컨테이너 4개(웹 · API · 워커 · DB)가 x600 서버에서 돌고 있습니다.")
notes(s, "시스템 구성입니다. 고객은 웹이나 자기 AI 비서로 들어오고, 둘 다 API 하나로 모입니다. API 안에 오케스트레이터와 요식업 · 액티비티 에이전트, 이동 판정이 있습니다. 워커는 3분마다 날씨 · 교통 같은 외부 정보 6종을 확인해 일정이 깨졌는지 보고, 알림을 보냅니다. 모델은 Ollama 의 gemma4:12b 와 임베딩을 쓰고, 저장은 PostgreSQL 과 pgvector 입니다. 이 네 컨테이너가 지금 x600 서버에서 돌고 있습니다.")

s = new("AGENT ARCHITECTURE", "오케스트레이터는 코드로 맡기고 검증하며, 두 에이전트는 초안만 냅니다")
pic(s, W5DIR / "AI시스템아키텍처" / "그림" / "그림3_에이전트아키텍처_v1.png", L - 0.05, 1.6, w=8.6)
x = L + 8.8
pts = [("오케스트레이터", "언어 모델을 쓰지 않는 코드 · 일을 맡기고 결과는 늘 여기로"), ("에이전트 2개", "요식업 · 액티비티 · 일정마다 바꿀 초안 최대 3개"),
       ("검증 · 반영", "체크리스트 · 이동 판정으로 다시 본 뒤 저장 · 알림"), ("이동 판정", "에이전트가 아닌 공용 도구 · 앞뒤 일정 시간표 판정")]
for k, (a_, b_) in enumerate(pts):
    yy = 1.68 + k * 1.2
    if k:
        hline(s, x, yy - 0.14, 3.0)
    text(s, x, yy, 3.0, 0.3, a_, size=12.5, bold=True, color=PRIMARY)
    text(s, x, yy + 0.34, 3.0, 0.8, b_, size=10.5, color=TEXT, line=1.15)
foot(s, "AI 시스템 아키텍처 문서의 그림 3. 에이전트끼리는 서로 부르지 않고, 읽기 도구는 한 번에 최대 12번까지 씁니다.")
notes(s, "에이전트 구성입니다. 가운데 오케스트레이터는 언어 모델을 쓰지 않는 코드라서 같은 입력이면 늘 같은 순서로 움직입니다. 요식업 에이전트와 액티비티 에이전트는 일정마다 바꿀 초안을 세 개까지 내기만 하고, 그 초안은 다시 오케스트레이터로 돌아와 체크리스트와 이동 판정으로 검증된 뒤에 저장되고 알림이 나갑니다. 이동 판정은 에이전트가 아니라 모두가 부르는 공용 도구입니다.")

# ================================================================ 3 한 주
s = new("THIS WEEK", "한 주 동안 커밋 531건을 쌓았습니다")
text(s, L, 1.75, 4, 1.3, "531", size=96, bold=True, color=PRIMARY, spacing=-3)
text(s, L + 0.05, 3.2, 4, 0.35, "커밋 · 모든 브랜치(팀원 포함)", size=13, bold=True)
text(s, L + 0.05, 3.52, 4, 0.3, "작업 브랜치만 세면 402건", size=10.5, color=CAPTION)
pic(s, A / "commits.png", L, 4.0, w=6.1, h=2.8)
kpis = [("12", "고객 웹 화면 연결", "계획 올리기부터 재난 시 일정 정지까지"),
        ("4,245 / 4,251", "자동 시험 통과 (99.9%)", "10-06 18:09, 실제 모델 시험 238개 제외"),
        ("688 → 760", "일정 항목 매칭, 769문제 중", "약 4B 모델 파인튜닝 전 → 후(2회차)"),
        ("22쪽 · 28쪽", "유스케이스 · AI 시스템 아키텍처 완성", "유스케이스 v7 · 아키텍처는 양식 6절 · 그림 10장 · 코드 대조 20건")]
x0 = 7.6
for i, (big, lab, how) in enumerate(kpis):
    yy = 1.8 + i * 1.28
    if i:
        hline(s, x0, yy - 0.16, 4.98)
    text(s, x0, yy, 4.98, 0.6, big, size=30, bold=True, color=PRIMARY, spacing=-0.5)
    text(s, x0, yy + 0.55, 4.98, 0.3, lab, size=13, bold=True)
    text(s, x0, yy + 0.84, 4.98, 0.3, how, size=10, color=CAPTION)
foot(s, "git log 2026-09-29 ~ 10-06. 막대 진한 색은 가장 많은 날(10/3, 112건).")
notes(s, "한 주 규모입니다. 모든 브랜치를 합쳐 커밋 531건이었고 10월 3일이 112건으로 가장 많았습니다. 고객 웹 화면 12개를 연결했고, 자동 시험은 4,251개 중 4,245개를 통과했습니다. 일정 항목 매칭 모델은 파인튜닝으로 688개에서 760개까지 맞혔고, 산출물은 6종을 만들었습니다.")

# ================================================================ 4 화면
s = new("CUSTOMER WEB", "고객이 지나가는 여섯 단계를 이어 붙였습니다")
shots = [("shot_04_trips_new_390.png", "계획 올리기", "글 · 사진 · 파일"), ("shot_q_read_390.png", "계획 읽는 중", "기다리는 동안 취향 질문"),
         ("shot_card_390.png", "항로 지킴이", "먼저 바꿀지 고르는 스위치"), ("shot_day_overview.png", "계획 확인", "날짜별 일정 · 수정"),
         ("shot_09_trip_home_390.png", "여행 화면", "일정 · 지도 · 채팅 · 알림"), ("shot_safety_top.png", "재난 시 일정 정지", "안전 안내 · 119 · 대피 장소")]
SW, SG = 1.78, 0.23
for i, (f, t, sub) in enumerate(shots):
    x = L + i * (SW + SG)
    pic(s, A / f, x, 1.72, w=SW, h=3.95)
    text(s, x, 5.82, SW, 0.25, f"0{i + 1}", size=10, bold=True, color=PRIMARY, align=PP_ALIGN.CENTER, spacing=1)
    text(s, x - 0.1, 6.08, SW + 0.2, 0.3, t, size=13.5, bold=True, align=PP_ALIGN.CENTER)
    text(s, x - 0.1, 6.4, SW + 0.2, 0.3, sub, size=10.5, color=CAPTION, align=PP_ALIGN.CENTER)
foot(s, "mock 서버 시험 397/402(화면 반응). 실서버 확인(10-07): x600 서버의 cs 프로젝트 서버 응답 · 웹 경로 55개 · 재난 뒤 패널 문구까지. 로그인 · 여행 만들기 흐름은 아직입니다.")
notes(s, "고객은 계획을 붙여 넣고, 읽는 동안 취향 질문에 답하고, 항로 지킴이를 켤지 고릅니다. 항로 지킴이는 문제가 생기면 서비스가 먼저 바꿔 두고 알릴지, 먼저 물어볼지를 정하는 스위치입니다. 계획을 확인한 뒤 여행 중에는 일정, 지도, 채팅을 쓰고, 재난 문자가 오면 남은 일정을 멈추고 안전 안내를 보여 줍니다. mock 서버로 화면 반응을 확인했고, 10월 7일에 x600 서버에서 서버 응답과 웹 경로 55개, 재난 뒤 패널 문구까지 확인했습니다. 로그인과 여행 만들기 흐름은 아직 확인하지 않았습니다.")

# ================================================================ 5 서버
s = new("SERVER", "AI 비서 입구와 실시간 진행 표시가 생겼습니다")
for j, x in enumerate((L, L + 6.07)):
    box(s, x, 1.75, 5.76, 3.9, fill=SURFACE, line=BORDER, r=0.22)
x = L + 0.35
text(s, x, 1.98, 5, 0.3, "개인 AI 입구", size=15, bold=True)
pills = [("고객의 AI 비서", SUBTLE), ("triPilot 입구", SOFT), ("본인 여행만", SOFT)]
px = x
for k, (t, f) in enumerate(pills):
    w = 1.5
    box(s, px, 2.5, w, 0.58, fill=f, line=PRIMARY if k == 1 else None, r=0.29)
    text(s, px, 2.5, w, 0.58, t, size=12, bold=True, color=PRIMARY if k else TEXT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if k < 2:
        text(s, px + w, 2.5, 0.27, 0.58, "→", size=14, bold=True, color=MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    px += w + 0.27
text(s, x, 3.35, 5, 0.6, [[("읽기  ", {"bold": True}), ("일정 · 위험 점검 결과 · 이동 판정  ", {"color": MUTED}), ("켜짐", {"bold": True, "color": PRIMARY})],
                         [("고치기  ", {"bold": True}), ("일정 수정 · 신고  ", {"color": MUTED}), ("기본 꺼짐", {"bold": True, "color": ERR})]], size=12, space=4)
stat(s, x, 4.2, 4.8, "15 / 15", "자동 시험 통과", "10-02 · 본인 여행만 열리는지 · 꺼진 고치기가 막히는지", big_size=30)
x = L + 6.42
text(s, x, 1.98, 5, 0.3, "실시간 진행 표시", size=15, bold=True)
steps = ["받았어요", "일정 읽기", "장소 · 운영시간", "정리 완료"]
for k, t in enumerate(steps):
    cx = x + 0.15 + k * 1.5
    done = k < 2
    box(s, cx, 2.6, 0.34, 0.34, fill=PRIMARY if done else SURFACE, line=PRIMARY, r=0.17, shape=MSO_SHAPE.OVAL, lw=1.75)
    if k < 3:
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(cx + 0.38), Inches(2.77), Inches(cx + 1.46), Inches(2.77))
        c.line.color.rgb = PRIMARY if k < 1 else GREY
        c.line.width = Pt(2.5)
    text(s, cx - 0.5, 3.02, 1.34, 0.28, t, size=10.5, color=TEXT if done else MUTED, align=PP_ALIGN.CENTER)
text(s, x, 3.48, 5.1, 0.7, "수십 초 걸리는 일(계획 읽기 · 일정 짜기 · 채팅) 동안 지금 몇 단계인지와 3초마다 「살아 있음」 신호를 보냅니다.", size=12, color=MUTED, line=1.15)
stat(s, x, 4.2, 4.8, "21 / 21", "자동 시험 통과", "10-02 · 채팅 · 일정 짜기 · 계획 읽기", big_size=30)
for k, (big, lab, how) in enumerate((("10 / 10", "에이전트 다시 고르기", "맡을 에이전트가 없을 때 한 번 더 고름 · mock 서버 시험"),
                                     ("517 / 517", "요식업 에이전트 시험", "팀원 정세환 · 10-06"))):
    xx = L + k * 6.07
    text(s, xx, 5.95, 1.9, 0.5, big, size=22, bold=True, color=PRIMARY)
    text(s, xx + 1.95, 5.97, 3.9, 0.3, lab, size=12.5, bold=True)
    text(s, xx + 1.95, 6.26, 3.9, 0.3, how, size=10, color=CAPTION)
foot(s, "개인 AI 입구는 MCP 서버입니다. 디스코드 · 텔레그램 연결과 여행 삭제는 코드에 들어갔지만 x600 서버 반영과 실제 연결은 아직 확인하지 않았습니다.")
notes(s, "서버 쪽은 두 가지가 컸습니다. 고객이 평소 쓰는 AI 비서가 triPilot 에 들어와 본인 여행만 읽을 수 있고, 고치는 기능은 기본으로 꺼 두었습니다. 오래 걸리는 일을 하는 동안에는 몇 단계인지와 살아 있다는 신호를 3초마다 보내서, 고객이 멈췄는지 기다리는 중인지 알 수 있게 했습니다.")

# ================================================================ 5-2 이동 판정 (2026-10-07 사용자: 이동 모듈 개선이 안 담겼다)
# 근거: final_project_cs/wiki/records/reports/2026-10-06_이동_엔진_구글대조_걷기모델_점검.md · 2026-10-04_0400_이동_파이썬_길찾기_서버없이_리포트.md ·
#       2026-10-06_버스_버스_환승_후보_설계.md · 커밋 dcb6bc92 · ab61caf9 · 6b0d8e5b · fcf937fa
s = new("MOBILITY", "이동 판정을 구글 · 카카오 길찾기와 맞춰 보며 차이를 줄였습니다")
text(s, L, 1.68, 5.6, 0.3, "이번 주에 넣은 것", size=12.5, bold=True, color=MUTED, spacing=0.5)
adds = [("10-01", "가장 이른 도착 계산", "앞 일정이 끝난 뒤 출발해서 되는 가장 이른 도착 · 시험 45건"),
        ("10-01", "지하철 ↔ 버스 섞기", "환승 1회 · 80구간 중 6구간에서 새 선택지, 기존 80/80 그대로"),
        ("10-06", "걷기 거리 상한", "직선의 2배까지만 · 멀리 도는 출구 대신 다른 출구"),
        ("10-06", "버스 → 버스 환승 후보", "구글이 고른 3구간에서 후보 생성 · 작업 중"),
        ("10-06", "역과 지하로 이어진 건물", "126개 역 · 216개 통로 · 작업 중")]
for k, (d, a_, b_) in enumerate(adds):
    yy = 2.08 + k * 0.84
    if k:
        hline(s, L, yy - 0.12, 5.6)
    chip(s, L, yy + 0.02, d, w=0.78)
    text(s, L + 0.95, yy - 0.02, 4.6, 0.3, a_, size=13, bold=True)
    text(s, L + 0.95, yy + 0.3, 4.65, 0.3, b_, size=10, color=CAPTION)
cards = [("대중교통 · 구글 Routes 17구간", "+3.5 → +3.0분", "구글보다 긴 정도(중앙값) · 절대오차 5.7 → 5.3분"),
         ("걷기 거리 부풀림 · 83곳", "8 → 3곳", "직선의 2배 넘는 걷기 · 예: 남대문시장 → 시청 4,065m → 824m"),
         ("택시 · 카카오 미래 길찾기 12쌍", "0.92 · 1.08 · 0.96", "거리 · 시간 · 요금 비율(우리 ÷ 카카오) · 요금은 ODsay 와 9/9 같음")]
for k, (lab, big, how) in enumerate(cards):
    yy = 1.68 + k * 1.58
    box(s, L + 6.15, yy, 5.68, 1.42, fill=SOFT if k == 0 else SURFACE, line=PRIMARY if k == 0 else BORDER, r=0.2)
    text(s, L + 6.4, yy + 0.12, 5.2, 0.3, lab, size=11, bold=True, color=MUTED)
    text(s, L + 6.4, yy + 0.42, 5.2, 0.6, big, size=26, bold=True, color=PRIMARY, spacing=-0.5)
    text(s, L + 6.4, yy + 0.98, 5.3, 0.35, how, size=10, color=CAPTION)
foot(s, "카카오는 대중교통 길찾기 공개 API 가 없고 도보는 권한 거부라, 대중교통은 구글과 · 택시는 카카오와 대조했습니다. 17구간은 작아 「나아졌다」보다 「방향이 맞다」로 읽습니다. 작업 중 2건은 커밋 전.")
notes(s, "이동 판정은 일정과 일정 사이를 제때 갈 수 있는지 보는 공용 기능입니다. 이번 주에는 앞 일정이 끝난 뒤 출발해서 되는 가장 이른 도착을 계산하게 했고, 지하철과 버스를 섞은 경로를 만들게 했습니다. 실제 길찾기 서비스와 맞춰 보니, 대중교통은 구글보다 중앙값 3.5분 길게 나왔고, 원인은 걷는 속도가 아니라 걷는 거리였습니다. 도로를 따라 재다 보니 출구에서 멀리 돌아가는 경우가 있어, 걷기 거리를 직선의 두 배까지로 막고 다른 출구를 쓰게 했더니 3.0분으로 줄었습니다. 택시는 카카오 미래 길찾기와 12쌍을 비교해 거리 0.92, 시간 1.08, 요금 0.96 배로 거의 맞았습니다. 카카오는 대중교통 공개 API 가 없어서 대중교통은 구글과 비교했습니다.")

# ================================================================ 5-3 담당 AI (2026-10-07 사용자: 각 에이전트 작업이 안 담겼다)
# 근거: final_project_cs/wiki/records/reports/2026-10-05_0500_요식팀_최신작업_점검과_병합_리포트.md · 2026-10-01_Activity_develop_반영_리포트.md ·
#       2026-09-28_계획읽기_평가셋60_리포트.md · 커밋 622639f4 · 6974654a · 5e02cbc1 · 1c7a9a2f · 563bca5a · c9498b83 · 82cedbb1
s = new("AGENTS", "요식업 · 액티비티 에이전트는 팀 작업을 합치고 데이터를 늘렸습니다")
agents = [("요식업 에이전트", "990 → 1,599곳", "서울 음식점 목록", ["팀 작업 합침: 파일 66/66 · 시험 2,525 + 496 통과", "사업자 등록 영업 15만 곳 적재(좌표 오차 중앙 6m)", "폐업 판정에는 안 씀 — 사람 확인 46곳 중 22곳 불일치"]),
          ("액티비티 에이전트", "2,454 / 2,455", "자동 시험 통과", ["팀 작업 중 나은 것 4/4 반영", "다른 브랜치 83줄 판정: 반영 2 · 일부 8 · 제외 73", "같은 브랜드 매장 364행 추가"]),
          ("오케스트레이터", "10 + 847", "다시 고르기 시험 · 흐름 시험 통과", ["맡을 에이전트가 없으면 등록된 에이전트 안에서 한 번 더 고름", "그 뒤 Case 가 죽던 결함 수정(10-07)", "AI 비서 입구에 읽기 도구 2개 · 시험 60건"]),
          ("계획 읽기", "90.2 → 97.0%", "일정 항목을 빠짐없이 읽은 비율(336항목)", ["근거 없는 값 0 / 1,828", "사진 · 스캔 글자 오독 12/350 — 고치는 중", "읽는 동안 진행 알림 · 추천 미리 보기"])]
for k, (name, big, lab, items) in enumerate(agents):
    xx = L + (k % 2) * 5.98
    yy = 1.68 + (k // 2) * 2.48
    box(s, xx, yy, 5.78, 2.3, fill=SURFACE, line=BORDER, r=0.2)
    text(s, xx + 0.28, yy + 0.15, 5.2, 0.3, name, size=12.5, bold=True, color=MUTED)
    text(s, xx + 0.28, yy + 0.45, 3.0, 0.6, big, size=24, bold=True, color=PRIMARY, spacing=-0.5)
    text(s, xx + 0.28, yy + 0.98, 5.2, 0.3, lab, size=10.5, bold=True)
    text(s, xx + 0.28, yy + 1.32, 5.3, 0.9, [[("· " + t, {})] for t in items], size=10, color=CAPTION, space=2)
foot(s, "숫자는 각 담당 세션의 리포트 · 자동 시험 기준입니다. x600 서버에서 실제 고객 흐름까지 확인한 것은 아닙니다. 팀원 작업은 「팀 작업」으로 적었습니다.")
notes(s, "에이전트별로 이번 주 일입니다. 요식업 에이전트는 팀원 작업을 합치면서 서울 음식점 목록을 990곳에서 1,599곳으로 늘렸고, 사업자 등록 자료 15만 곳을 이름 찾기에 쓰게 넣었습니다. 다만 사업자 자료는 실제 폐업과 절반 가까이 어긋나서 폐업 판정에는 쓰지 않습니다. 액티비티 에이전트도 팀 작업 중 나은 것을 반영했고 시험 2,454개를 통과했습니다. 오케스트레이터는 맡을 에이전트가 없을 때 한 번 더 고르게 했고, 그 뒤에 생긴 결함도 고쳤습니다. 계획 읽기는 일정 항목을 빠짐없이 읽는 비율이 97%까지 올랐고, 남은 것은 사진 글자 오독입니다.")

# ================================================================ 5-4 배포 · 서버 (2026-10-07 사용자: CI/CD · x600 자동 배포 · 서버 확보가 안 담겼다)
# 근거: 저장소 .github/workflows/ci-develop.yml · ci-main.yml · final_project_cs/deploy/(auto_deploy.sh · tripilot-autodeploy.timer) ·
#       커밋 53184c94 · 1d87ae34 · 551e804c · final_project_cs/wiki/log.md 10-07. 접속 정보는 적지 않는다.
s = new("DEPLOY · INFRA", "올리면 x600 서버에 자동 반영되고, 실패하면 이전 판으로 돌아갑니다")
box(s, L, 1.68, 5.75, 1.0, fill=SUBTLE, line=BORDER, r=0.18)
text(s, L + 0.25, 1.76, 5.3, 0.3, "시험 · GitHub Actions (09-24~)", size=12, bold=True)
text(s, L + 0.25, 2.08, 5.3, 0.55, "develop · main 에 올리면 린트 · 구조 · 단위 · 보안 시험, main 은 전체 시험 + Docker 빌드까지", size=10, color=CAPTION, line=1.1)
text(s, L, 2.85, 5.6, 0.3, "배포 · x600 서버 자동 반영 (10-03~)", size=12, bold=True)
flow = [("1", "5분마다 새 커밋 확인", "팀 저장소 작업 브랜치 · 올린 뒤 2~10분 안에 반영"),
        ("2", "바뀐 부분만 이미지 빌드", "커밋 번호로 이름 · 이전 판 3개 보관"),
        ("3", "DB 변경 → 새 판 띄움", "DB 변경은 앞으로만 적용"),
        ("4", "30초 지켜봄", "컨테이너 4개 · 재시작 0 이면 성공")]
for k, (n, a_, b_) in enumerate(flow):
    yy = 3.22 + k * 0.62
    box(s, L, yy, 0.42, 0.42, fill=PRIMARY, line=None, r=0.21, shape=MSO_SHAPE.OVAL)
    text(s, L, yy, 0.42, 0.42, n, size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 0.6, yy - 0.04, 2.4, 0.3, a_, size=12, bold=True)
    text(s, L + 0.6, yy + 0.24, 5.1, 0.3, b_, size=9.5, color=CAPTION)
box(s, L, 5.75, 5.75, 0.95, fill=ERR_SOFT, line=ERR_B, r=0.18)
text(s, L + 0.25, 5.8, 5.3, 0.3, "실패하면 이전 판으로 되돌리고 그 커밋은 다시 안 씀", size=11.5, bold=True, color=ERR)
text(s, L + 0.25, 6.12, 5.3, 0.55, "실제로 10-06 DB 변경 교착으로 실패 → 서비스는 이전 판으로 계속 → 고친 커밋으로 반영. 지금 판 9a3521b5(10-07) · 상태 확인 200", size=9.5, color=CAPTION, line=1.1)
x = L + 6.15
text(s, x, 1.68, 5.6, 0.3, "확보한 서버", size=12, bold=True)
servers = [("x600 서버", "팀 기계 · 12GB GPU · Docker", "공개 서비스(DB · API · 워커 · 웹) + 모델 2개"),
           ("오라클 무료 서버", "ARM 2코어 · 12GB · 0원", "적은 질문 운영 후보 · CPU 추론 실측"),
           ("RunPod GPU A", "RTX 2000 Ada 16GB", "모델 20여 종 채점"),
           ("RunPod GPU B", "RTX A4000 · 16 vCPU · 62GB", "파인튜닝 · 모델 변환"),
           ("RunPod GPU C", "RTX 4000 Ada 20GB", "E2E 파이프라인 테스트 · 10-06 반납"),
           ("경유 서버", "고정 IP", "IP 에 묶인 도로 통제 API 호출")]
for k, (n, spec, use) in enumerate(servers):
    yy = 2.0 + k * 0.6
    if k:
        hline(s, x, yy - 0.06, 5.68)
    text(s, x, yy, 1.85, 0.3, n, size=12, bold=True, color=PRIMARY)
    text(s, x + 1.9, yy, 3.8, 0.3, spec, size=11, bold=True)
    text(s, x + 1.9, yy + 0.3, 3.8, 0.3, use, size=9.5, color=CAPTION)
box(s, x, 5.7, 5.68, 1.08, fill=SOFT, line=PRIMARY, r=0.18)
pic(s, A / "qr_tripilot.png", x + 0.12, 5.76, w=0.96)
text(s, x + 1.25, 5.8, 4.3, 0.3, "지금 x600 서버에서 돌고 있는 서비스", size=11, bold=True, color=PRIMARY)
text(s, x + 1.25, 6.12, 4.3, 0.4, "https://tripilot.devroro.click", size=15, bold=True, color=TEXT)
text(s, x + 1.25, 6.47, 4.3, 0.3, "QR 로 휴대폰에서 바로 열 수 있습니다", size=9.5, color=CAPTION)
foot(s, "자동 반영은 x600 서버가 스스로 새 커밋을 확인하는 방식(웹훅 아님). GitHub Actions 는 시험만 하고 배포는 하지 않습니다. AWS 는 확보하지 않고 비용 비교만 했습니다.")
notes(s, "배포와 서버입니다. 코드를 올리면 GitHub Actions 가 린트와 구조, 단위, 보안 시험을 돌립니다. 배포는 따로 돕니다. x600 서버가 5분마다 팀 저장소의 새 커밋을 확인해서, 바뀐 부분만 새 이미지로 만들고, DB 를 바꾼 뒤 새 판을 띄우고, 30초 동안 지켜봅니다. 컨테이너 넷이 멀쩡하면 성공이고, 아니면 이전 판으로 되돌립니다. 실제로 10월 6일에 DB 변경이 교착으로 실패했지만 서비스는 이전 판으로 계속 돌았고, 고친 커밋으로 다시 반영됐습니다. 서버는 공개 서비스를 돌리는 x600, 무료로 쓰는 오라클 서버, 학습과 채점용 RunPod GPU 세 대, 그리고 IP 에 묶인 도로 통제 API 를 부르기 위한 경유 서버를 확보했습니다. 지금 돌고 있는 서비스는 화면의 주소나 QR 로 바로 열어 보실 수 있습니다.")

CH = 2
# ================================================================ 6 모델 과제
s = new("THE MODEL TASK", "고객 말이 일정표의 몇 번 항목인지 찾습니다")
box(s, L, 1.75, 4.3, 3.0, fill=SURFACE, line=BORDER, r=0.22)
text(s, L + 0.3, 1.95, 3.8, 0.3, "금요일 일정  ·  2027-11-05", size=11, bold=True, color=MUTED, spacing=0.5)
rows = [("23", "13:30", "대림미술관 전시 관람", False), ("24", "15:30", "호텔 체크인", False), ("25", "16:30", "피크닉 전시 보기", True)]
for k, (n, tm, t, hi) in enumerate(rows):
    yy = 2.38 + k * 0.72
    box(s, L + 0.25, yy, 3.8, 0.6, fill=SOFT if hi else SUBTLE, line=PRIMARY if hi else None, r=0.16, lw=1.5)
    text(s, L + 0.45, yy, 0.6, 0.6, n, size=15, bold=True, color=PRIMARY if hi else MUTED, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 1.0, yy, 0.8, 0.6, tm, size=12, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 1.8, yy, 2.2, 0.6, t, size=13, bold=hi, anchor=MSO_ANCHOR.MIDDLE)
bx = L + 4.75
bubble(s, bx, 1.75, 3.6, "금요일에 전시 뭐 봐?", "고객", mine=True)
bubble(s, bx + 0.6, 2.5, 4.5, "13:30 대림미술관, 16:30 피크닉 전시가 있어요.", "triPilot")
bubble(s, bx, 3.25, 3.6, "뒤에 거 예매해야 돼?", "고객", mine=True)
text(s, bx + 3.8, 3.33, 0.5, 0.5, "→", size=22, bold=True, color=PRIMARY)
box(s, bx + 4.35, 3.25, 2.7, 0.62, fill=PRIMARY, line=None, r=0.31)
text(s, bx + 4.35, 3.25, 2.7, 0.62, "정답  25번", size=17, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
bubble(s, bx, 4.12, 3.6, "남산타워 몇 시에 올라가?", "고객", mine=True)
text(s, bx + 3.8, 4.2, 0.5, 0.5, "→", size=22, bold=True, color=MUTED)
box(s, bx + 4.35, 4.12, 2.7, 0.62, fill=SURFACE, line=BORDER, r=0.31)
text(s, bx + 4.35, 4.12, 2.7, 0.62, "정답  없음", size=17, bold=True, color=TEXT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s, bx + 4.35, 4.8, 2.7, 0.3, "일정에 없는 곳은 지어내지 않음", size=10, color=CAPTION, align=PP_ALIGN.CENTER)
hline(s, L, 5.4, CW)
cols = [("769문제", "시험 세트 mix8~12 835문제에서\n한 문장에 두 항목을 묻는 66문제를 뺀 주 지표"),
        ("11가지", "헷갈리게 만든 유형: 「거기」 · 비슷한 이름 ·\n「~말고」 · 오타 · 잡담 · 없는 일정 등"),
        ("AI 합성", "Codex · Claude 가 쓴 문제.\n처음 문제 · 체크리스트는 사람이 쓰고 일부 검수")]
for k, (big, t) in enumerate(cols):
    xx = L + k * 3.98
    text(s, xx, 5.58, 3.8, 0.5, big, size=22, bold=True, color=PRIMARY)
    text(s, xx, 6.1, 3.8, 0.7, t, size=10.5, color=CAPTION, line=1.15)
notes(s, "모델이 푸는 문제는 하나입니다. 고객이 한 말이 일정표의 몇 번 항목을 가리키는지 찾습니다. 금요일 전시를 물은 뒤 「뒤에 거 예매해야 돼」라고 하면 정답은 25번 피크닉 전시이고, 일정에 없는 남산타워를 물으면 정답은 없음입니다. 이걸 맞혀야 그 장소의 영업시간이나 예약을 확인하고 바꿀 수 있습니다.")

# ================================================================ 7 파인튜닝
s = new("FINE-TUNING", "4B 모델을 파인튜닝하니 27B 로컬 모델만큼 맞혔습니다")
text(s, L, 1.62, 7.6, 0.3, "같은 769문제 · 맞힌 문제 수", size=11, bold=True, color=MUTED, spacing=0.5)
pic(s, A / "finetune.png", L - 0.1, 1.95, w=7.9)
x = 9.0
text(s, x, 1.75, 3.6, 0.3, "파인튜닝 전 → 후", size=12, bold=True, color=MUTED)
text(s, x, 2.05, 3.6, 1.0, [[("688", {"color": GREY}), ("  →  ", {"size": 30, "color": MUTED}), ("750", {"color": PRIMARY})]], size=58, bold=True, spacing=-1.5)
text(s, x, 3.15, 3.9, 0.9, "시드 1 기준 갈린 문제 69 : 7 (p=6.4e-14).\n시드 3개 750 · 760 · 748 (평균 752.7) —\n12문제가 흔들려 4B 모델끼리 순위는 안 매김.", size=11, color=CAPTION, line=1.2)
hline(s, x, 4.3, 3.6)
stat(s, x, 4.5, 3.9, "0.24초", "GPU 한 장(RTX 2000 Ada)", "이어지는 질문 · 새 일정 첫 질문 1.1초 · CPU 4코어는 4.55초", big_size=30)
foot(s, "학습 자료: 연습문제 1,760개(처음 문제 · 체크리스트는 사람이 쓰고 Claude 가 늘림). CPU 실행본(8비트 · 756/769)을 4비트로 줄여도 756/769 로 같음. Winnow-E4B 는 Jev 계열 결정 모델을 같은 방법으로 파인튜닝한 값.")
notes(s, "약 4B 크기의 Gemma 4 E4B 를 우리 연습문제로 파인튜닝하니 688개에서 750개, 다시 학습하면 760개를 맞혔습니다. 파인튜닝하지 않은 26B, 27B 로컬 모델이 732개, 749개라서, 작은 모델로 큰 모델만큼 맞힌 셈입니다. 다만 같은 방법으로 두 번 학습해도 10문제쯤 흔들리기 때문에 4B 모델끼리 순위는 매기지 않습니다. CPU 만으로도 이어지는 질문은 평균 4.5초에 답합니다.")

# ================================================================ 7-2 파인튜닝 방법 · 검증
# 근거: 멀티 에이전트 보고서 3.2(학습 설정 표) · 연구 문서 §69 · §86 (2026-10-07 사용자: 「파인튜닝은 뭐로 어떻게 했고 검증 어떻게 했는지 없네」)
s = new("HOW WE FINE-TUNED", "Gemma 4 E4B 를 이렇게 가르치고 이렇게 검증했습니다")
flow = [("사람", "처음 문제 · 체크리스트 작성"), ("Claude", "여행자 10명 일정 +\n연습문제 1,760개"), ("별도 풀이", "정답 1,760/1,760 일치"),
        ("겹침 제거", "시험 문제와 같거나\n비슷한 122개 뺌"), ("나누기", "학습 1,313 · 여행자 8명\n검증 325 · 다른 2명")]
bw, gap = 2.18, 0.23
for k, (t1, t2) in enumerate(flow):
    xx = L + k * (bw + gap)
    box(s, xx, 1.72, bw, 1.25, fill=SOFT if k == 4 else SURFACE, line=PRIMARY if k == 4 else BORDER, r=0.2, lw=1.5 if k == 4 else 1.0)
    text(s, xx + 0.18, 1.82, bw - 0.36, 0.3, t1, size=11, bold=True, color=PRIMARY)
    text(s, xx + 0.18, 2.12, bw - 0.36, 0.8, t2, size=12, bold=True, line=1.1)
    if k < 4:
        text(s, xx + bw, 1.72, gap, 1.25, "→", size=14, bold=True, color=MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
box(s, L, 3.25, 5.75, 3.45, fill=SURFACE, line=BORDER, r=0.22)
text(s, L + 0.3, 3.42, 5.2, 0.3, "학습 설정 (평가를 보기 전에 하나로 고정)", size=13, bold=True)
rows = [("기초 모델", "google/gemma-4-E4B-it · 4비트 NF4"), ("방법", "QLoRA · LoRA rank 16 · alpha 32 · 선형층 7종"),
        ("최적화", "AdamW · 학습률 2e-4 · 2 epoch · 유효 배치 8"), ("손실", "정답 토큰에만"),
        ("장비 · 시간", "GPU 서버 B RTX A4000 16GB · 148.7분 · 최대 10.6GB")]
for k, (a_, b_) in enumerate(rows):
    yy = 3.85 + k * 0.53
    if k:
        hline(s, L + 0.3, yy - 0.07, 5.15)
    text(s, L + 0.3, yy, 1.35, 0.4, a_, size=11, bold=True, color=MUTED)
    text(s, L + 1.65, yy, 3.9, 0.45, b_, size=11.5)
x = L + 6.07
box(s, x, 3.25, 5.76, 3.45, fill=SURFACE, line=BORDER, r=0.22)
text(s, x + 0.3, 3.42, 5.2, 0.3, "검증", size=13, bold=True)
checks = [("320/325", "검증 세트(학습에 없는 여행자 2명)", "파인튜닝 전 265 → 후 320"),
          ("750/769", "시험지 mix8~12 · 사전 등록 기준 통과", "전 688 → 후 750 · 갈린 문제 69 : 7 (p=6.4e-14) · 기준 +3%p · p<0.05"),
          ("760/769", "시드만 바꿔 다시 학습", "흔들림 10문제 → 모델끼리 순위는 시드 3개 이상"),
          ("748/769", "8비트 파일로 바꿔 CPU 4코어에서", "배포용 변환 뒤에도 구분 안 됨")]
for k, (big, lab, how) in enumerate(checks):
    yy = 3.85 + k * 0.7
    if k:
        hline(s, x + 0.3, yy - 0.08, 5.16)
    text(s, x + 0.3, yy, 1.45, 0.5, big, size=17, bold=True, color=PRIMARY)
    text(s, x + 1.8, yy, 3.8, 0.3, lab, size=11.5, bold=True)
    text(s, x + 1.8, yy + 0.29, 3.8, 0.35, how, size=9.5, color=CAPTION)
foot(s, "시험지 mix8~12 는 학습 자료와 겹침을 뺀 별도 문제(AI 합성). 학습 자료와 mix12 를 같은 Claude 가 만들어 mix12 는 유리할 수 있습니다. 코드: program/scripts/plan_qa_bench/server/qlora_train.py")
notes(s, "파인튜닝은 이렇게 했습니다. 사람이 처음 문제와 체크리스트를 쓰고, Claude 가 이를 바탕으로 여행자 10명의 일정과 연습문제 1,760개를 만들었습니다. 별도 풀이로 정답이 모두 일치하는지 확인하고, 시험 문제와 같거나 비슷한 122개를 뺀 뒤, 여행자 8명 몫 1,313개로 학습하고 다른 2명 몫 325개로 검증했습니다. Gemma 4 E4B 를 4비트로 올려 QLoRA 로 2 epoch 학습했고, 설정은 평가를 보기 전에 하나로 고정했습니다. 검증 세트에서 265개에서 320개로, 시험지에서 688개에서 750개로 올라 미리 정한 기준을 통과했고, 시드만 바꿔 다시 학습한 760개, CPU 용 8비트 파일로 바꾼 748개도 확인했습니다.")

# ================================================================ 7-3 시험 A · B · C · D 와 모델 점수 (2026-10-07 사용자 지시)
# 근거: program/scripts/plan_qa_bench/results/c_scoring_all.txt · 멀티 에이전트 보고서 _재료/c_scoring_new.json ·
#       서비스 평가 베이스라인 리포트 §3(혼합 트래픽). A·B·C 는 같은 835문제의 세 채점, D 는 무관한 말을 섞은 2,735문제.
s = new("BENCHMARKS", "같은 문제를 네 가지 기준으로 재고 모델마다 점수를 냈습니다")
defs = [("A", "835문제 · 먼저 말한 항목 하나만 정답", "둘을 묻는 66문제는 먼저 말한 항목 하나를 맞혀야 정답"),
        ("B", "835문제 · 하나라도 맞으면 정답", "둘을 묻는 질문은 둘 중 하나만 맞혀도 정답 (주 채점)"),
        ("C", "835문제 · 둘 다 맞혀야 정답", "낸 항목 묶음이 정답 묶음과 같아야 정답 (가장 엄격, 사전 등록)"),
        ("D", "2,735문제 · 채팅처럼 섞음", "835 + 관광지 질문 600 + 일상 대화 1,000 + 구어체 300")]
for k, (t, a_, b_) in enumerate(defs):
    xx = L + k * 2.98
    box(s, xx, 1.65, 2.82, 1.25, fill=SOFT if t == "D" else SURFACE, line=PRIMARY if t == "D" else BORDER, r=0.2)
    text(s, xx + 0.2, 1.72, 0.5, 0.5, t, size=22, bold=True, color=PRIMARY)
    text(s, xx + 0.7, 1.74, 2.05, 0.55, a_, size=10.5, bold=True, line=1.0)
    text(s, xx + 0.2, 2.36, 2.5, 0.5, b_, size=9, color=CAPTION, line=1.05)
hdr = ["모델", "769", "A /835", "B /835", "C /835", "D /2,669"]
cw = [4.35, 1.2, 1.5, 1.5, 1.5, 1.78]
rows = [("Gemma 4 E4B · 파인튜닝 전", "688", "736", "750", "688", "안 잼", False),
        ("Gemma 4 E4B · 파인튜닝 (시드 1)", "750", "816", "816", "750", "93.6% (시드 1)", True),
        ("Gemma 4 E4B · 파인튜닝 (시드 2)", "760", "825", "826", "760", "90.1% (시드 3개 평균)", True),
        ("Winnow-E4B(Jev 계열) · 파인튜닝", "756", "821", "821", "756", "안 잼", True),
        ("Gemma 4 26B-A4B · 파인튜닝 없음", "732", "780", "797", "732", "안 잼", False),
        ("Qwen3.8 27B · 파인튜닝 없음", "749", "793", "814", "749", "못 잼 · 큰 GPU 필요", False),
        ("Claude Opus 5.5 · 상용", "759", "823", "825", "819", "안 잼", False),
        ("Claude Fable 5.1 · 상용", "762", "825", "828", "821", "안 잼", False),
        ("Codex Sol · Astra · Luna · 상용", "760 · 766 · 741", "", "", "814 · 823 · 793", "안 잼", False)]
y = 3.1
xx = L
for c, w in zip(hdr, cw):
    text(s, xx, y, w - 0.1, 0.3, c, size=10.5, bold=True, color=MUTED, align=PP_ALIGN.LEFT if c == "모델" else PP_ALIGN.RIGHT)
    xx += w
for k, (name, *vals, hi) in enumerate(rows):
    yy = 3.42 + k * 0.37
    if hi:
        box(s, L - 0.08, yy - 0.03, CW + 0.16, 0.35, fill=SOFT, line=None, r=0.08)
    hline(s, L, yy - 0.04, CW, lw=0.5)
    xx = L
    text(s, xx, yy, cw[0] - 0.1, 0.3, name, size=10.5, bold=hi, color=PRIMARY if hi else TEXT)
    xx += cw[0]
    for v, w in zip(vals, cw[1:]):
        text(s, xx, yy, w - 0.1, 0.3, v or "없음", size=10.5, bold=hi, color=(PRIMARY if hi else TEXT) if v else MUTED, align=PP_ALIGN.RIGHT)
        xx += w
foot(s, "769 = 둘을 묻는 66문제를 뺀 주 지표. 우리 모델은 항목을 하나만 내는 구조라 C 에서 66문제를 놓칩니다. D 는 둘을 묻는 질문을 뺀 2,669문제를 생각 모드를 끄고 채점(지금은 파인튜닝 Gemma 4 E4B 만 잼 · 나머지는 RAG 세션이 재는 중). 상용은 CLI 실행 · 출제자 편향으로 공정 비교 아님, Codex 의 A · B 는 기록 없음.")
notes(s, "시험은 네 가지입니다. A, B, C 는 같은 835문제를 채점 기준만 바꾼 것입니다. 한 문장에 일정 둘을 묻는 질문을, A 는 먼저 말한 항목만, B 는 하나라도 맞으면, C 는 둘 다 맞혀야 정답으로 봅니다. D 는 실제 채팅처럼 일정 질문 사이에 관광지 질문, 일상 대화, 구어체를 섞은 2,735문제입니다. 파인튜닝한 Gemma 4 E4B 는 769문제 750~760개, B 채점 816~826개로 26B, 27B 로컬 모델보다 높았고, C 에서는 항목을 하나만 내는 구조라 상용 모델보다 낮습니다. D 는 지금 우리 모델만 쟀고 다른 모델은 측정을 맡겨 두었습니다.")

# ================================================================ 7-4 외부 벤치마크와 순위 대조 (2026-10-07 사용자 지시)
# 계산: program/scripts/plan_qa_bench/jevbench_rank_check.py → results/jevbench_rank_check.txt
s = new("EXTERNAL CHECK", "외부 벤치마크와 모델 순위가 같은 방향입니다")
pic(s, A / "jevbench_rank.png", L - 0.1, 1.6, w=6.6)
x = L + 6.9
pts = [("무엇을 했나", "학습 없는 원본 모델 14개를 우리 한국어 일정 시험(같은 309문제)으로 잰 순위와 공개 결정 벤치마크 JevBench v1.6.0(10-05 채점)의 순위를 견줬습니다."),
       ("무엇을 말하나", "지능 점수와 순위상관 +0.92(95% 구간 +0.75~+0.98). 바깥 벤치마크와 모델 순서가 같다는 뜻으로, 우리 시험이 엉뚱한 것을 재지 않는다는 외부 근거 하나입니다(수렴 타당도). 측정 대상을 확정하지는 못합니다."),
       ("무엇은 말하지 않나", "점수 크기는 이어지지 않습니다 — 보드 4B 상위 모델이 우리 시험에서는 78~84%. 속도 · 비용을 섞은 보드 헤드라인 점수와는 +0.66 으로 약합니다.")]
for k, (a_, b_) in enumerate(pts):
    yy = 1.7 + k * 1.35
    if k:
        hline(s, x, yy - 0.15, 5.0)
    text(s, x, yy, 5.0, 0.3, a_, size=12.5, bold=True, color=PRIMARY)
    text(s, x, yy + 0.36, 5.0, 0.95, b_, size=11, color=TEXT, line=1.2)
foot(s, "속이 빈 점 = 보드와 양자화 · 판이 다를 수 있는 모델(넣으면 지능 +0.93, n=17). 보드는 영어, 우리 시험은 한국어 · AI 합성 문제. 파인튜닝한 모델은 보드에 없어 대조하지 않았습니다.")
notes(s, "우리가 만든 시험이 제대로 된 것인지 바깥 기준과 대조해 봤습니다. 공개 결정 모델 벤치마크인 JevBench 와 우리 시험에 같이 나오는 원본 모델 14개의 순위를 비교하니 순위상관이 0.92였습니다. 바깥 벤치마크에서 잘하는 모델이 우리 시험에서도 잘했다는 뜻이라, 우리 시험이 엉뚱한 것을 재고 있지 않다는 근거가 됩니다. 다만 점수 크기는 다릅니다. 영어 보드의 4B 상위 모델이 우리 한국어 시험에서는 80% 안팎이라, 보드 점수만 보고 모델을 고르면 안 되고 우리 시험으로 다시 재야 합니다.")

CH = 3
# ================================================================ 8 출제자 제외 + 운영 비용
# 2026-10-07 사용자 지시: 출제자 제외 비교 옆에 상용 API 비용 문제를 함께 말한다. 비용 숫자는 사용자 진술(아래 각주),
# 무료 서버 처리량은 RAG 세션이 dr-a2 에서 재는 중 — 결과가 오면 「측정 중」을 숫자로 바꾼다.
s = new("FAIR COMPARISON · COST", "점수는 상용 모델이 가장 높지만, 운영 비용이 문제입니다")
text(s, L, 1.62, 5.6, 0.3, "Codex 가 쓴 659문제  ·  Codex 모델 제외", size=12.5, bold=True)
pic(s, A / "fair_codex_made.png", L, 1.95, w=5.6, h=2.85)
text(s, L + 6.2, 1.62, 5.6, 0.3, "Claude 가 쓴 176문제  ·  Claude 모델 제외", size=12.5, bold=True)
pic(s, A / "fair_claude_made.png", L + 6.2, 1.95, w=5.6, h=2.85)
text(s, L, 5.0, 4, 0.3, "운영 비용 (한 달)", size=12, bold=True, color=MUTED, spacing=0.5)
costs = [("상용 API 만 쓸 때", "+5~10만원", "상위 모델 사용량 과금 · 서버는 따로 필요", WARN, WARN_SOFT, WARN_B),
         ("RunPod GPU 서버", "25.6만원", "A4000 · 16 vCPU · 62GB · 앱도 같이 · 월 고정", TEXT, SURFACE, BORDER),
         ("오라클 무료 서버", "0원", "2 CPU · 12GB · 몰리는 시간 기준 하루 약 700건", PRIMARY, SOFT, PRIMARY)]
for k, (lab, big, how, c, f, b) in enumerate(costs):
    xx = L + k * 3.98
    box(s, xx, 5.35, 3.8, 1.42, fill=f, line=b, r=0.2, lw=1.5 if k == 2 else 1.0)
    text(s, xx + 0.25, 5.45, 3.4, 0.3, lab, size=12, bold=True, color=c if k != 1 else TEXT)
    text(s, xx + 0.25, 5.72, 3.4, 0.6, big, size=28, bold=True, color=c, spacing=-0.5)
    text(s, xx + 0.25, 6.28, 3.4, 0.45, how, size=10, color=CAPTION, line=1.1)
foot(s, "B: 둘 다 묻는 질문은 하나라도 맞으면 정답 · C: 묶음이 정답과 같아야 정답. 비용은 사용자 제공(10-07), 무료 서버 처리량은 측정 중.")
notes(s, "상용 모델 점수는 자기가 낸 문제까지 푼 것이라, Codex 가 쓴 문제에서는 Codex 를, Claude 가 쓴 문제에서는 Claude 를 빼고 다시 셌습니다. 그래도 상용 모델이 가장 높았습니다. 문제는 비용입니다. 서버는 어차피 우리가 확보해야 하는데, 상용 API 를 쓰면 한 달 5~10만원이 더 들고, RunPod A4000 은 25.6만원 고정입니다. 오라클 무료 서버는 2 CPU, 12GB, 월 10TB 트래픽까지 0원이라, 파인튜닝한 작은 모델을 여기서 얼마나 감당할 수 있는지 지금 재고 있습니다.")

# ================================================================ 8-2 손익 분기
# 근거: 연구 문서 §71 · §76 · §78 · §80 · §86 (2026-10-07 사용자: 「저 금액대는 어떻게 나왔고, 트래픽-금액대 별 손익 분기가 원래 있었는데 없네」)
s = new("COST BREAK-EVEN", "하루 질문 수에 따라 가장 싼 방식이 바뀝니다")
pic(s, A / "breakeven.png", L - 0.1, 1.62, w=7.4, h=4.6)
x = L + 7.55
text(s, x, 1.7, 4.3, 0.3, "금액은 이렇게 나왔습니다", size=13, bold=True)
calc = [("API 1건", "입력 1,700 + 출력 12토큰 × 공식 단가 × 1,400원/달러\nLuna 0.25 · Sol 4.93 · Opus 5.5 9.86 · Astra · Fable 5.1 24.64원"),
        ("앱 서버", "API 를 써도 서버는 필요 · AWS 서울 t3.medium 월 5.4만원"),
        ("RunPod", "A4000 $0.25 × 730시간 = 월 25.6만원(앱 포함)\n하루 약 3.6만 건 · 3 · 6개월 선불 약정 할인"),
        ("오라클 무료", "2코어 ARM · 12GB · 월 10TB = 0원 · 트래픽은 약 12억 건\n실측: 이어지는 질문 7.7초 · 새 일정 112.5초 · 몰리는 시간 기준 하루 약 700건")]
for k, (a_, b_) in enumerate(calc):
    yy = 2.12 + k * 1.0
    if k:
        hline(s, x, yy - 0.1, 4.28)
    text(s, x, yy, 1.05, 0.3, a_, size=11, bold=True, color=PRIMARY)
    text(s, x + 1.08, yy, 3.2, 0.9, b_, size=10.5, color=TEXT, line=1.12)
box(s, L, 6.27, CW, 0.55, fill=SOFT, line=None, r=0.2)
text(s, L + 0.25, 6.27, CW - 0.5, 0.55, [[("읽는 법  ", {"bold": True, "color": PRIMARY}),
                                         ("한 가지 방식만 쓸 때의 비교입니다. 실제로는 섞어 쓰며, 질문 수별 가장 싼 조합은 다음 장에 있습니다.", {})]],
     size=12, anchor=MSO_ANCHOR.MIDDLE)
foot(s, "단가: Claude · OpenAI 공식 가격 페이지(10-07 확인), 생각 토큰 · 캐시는 뺀 값. 「API 만 쓰면 월 5~10만원」은 Luna + 앱 서버 하루 1천~5천 건(6.1~9.1만원)과 맞습니다. 트래픽은 CPU 보다 한참 뒤에 막힙니다.")
notes(s, "금액은 이렇게 나왔습니다. API 한 건은 질의 1,700토큰과 답 12토큰에 공개 단가를 곱한 값으로 Luna 0.25원, Sol 4.93원, Astra 24.64원이고, API 를 써도 앱 서버가 필요해 월 5.4만원이 더해집니다. RunPod 은 지금 쓰는 A4000 포드 기준 월 25.6만원 고정이고, 16 vCPU 와 62GB 메모리가 있어 앱 서버까지 같이 올립니다. 3개월이나 6개월을 미리 내면 할인되고, 1년 약정은 RunPod 에 없습니다. 오라클 무료 서버는 0원이고 몰리는 시간 기준 하루 약 700건까지 받습니다. 그 위로는 Sol 기준 하루 약 1,400건, Astra 기준 약 270건부터 GPU 서버가 API 보다 쌉니다.")

# ================================================================ 8-3 단계별 전환 계획 (2026-10-07 사용자: 최적 전환 시기와 조합)
# 계산: src/scaling_plan.py — 하루 질문 수마다 GPU 대수와 API 몫을 바꿔 가며 월 비용이 가장 작은 조합을 고른다.
s = new("SCALING PLAN", "몰리는 시간 기준: 무료 서버만 → +API → GPU → 증설")
pic(s, A / "scaling.png", L - 0.1, 1.6, w=6.7, h=3.75)
x = L + 6.75
text(s, x, 1.65, 5.1, 0.3, "비용 우선 경로 (넘치는 질문은 Luna API)", size=12.5, bold=True)
st = [("⓪", "~700", "무료 서버만", "몰리는 시간까지 무료 서버가 다 받음 · 일정은 미리 읽음", "0원"),
      ("①", "700~4.1만", "무료 서버 + API", "몰리는 시간에 넘치는 몫만 Luna API · 한가한 시간은 무료 서버", "0~25.7만원"),
      ("②", "4.1만~14.0만", "GPU 1대 + API", "API 비용이 GPU 월세를 넘는 지점에서 GPU · 피크 넘침은 API", "25.8~66.9만원"),
      ("③", "14.0만~", "GPU 2대 → 반복", "하루 약 10만 건 늘 때마다 GPU 1대 추가", "66.9만원~")]
for k, (n, rng, combo, how, cost) in enumerate(st):
    yy = 2.05 + k * 0.8
    if k:
        hline(s, x, yy - 0.08, 5.08)
    text(s, x, yy, 0.35, 0.4, n, size=13, bold=True, color=PRIMARY)
    text(s, x + 0.38, yy, 1.25, 0.3, rng, size=10, bold=True, color=MUTED)
    text(s, x + 1.6, yy, 2.4, 0.3, combo, size=11, bold=True)
    text(s, x + 4.0, yy, 1.08, 0.3, cost, size=10, bold=True, color=PRIMARY, align=PP_ALIGN.RIGHT)
    text(s, x + 1.6, yy + 0.22, 3.5, 0.26, how, size=8.5, color=CAPTION)
box(s, L, 5.5, CW, 1.25, fill=SURFACE, line=BORDER, r=0.2)
text(s, L + 0.3, 5.6, 3.6, 0.3, "품질 우선 경로 (Sol API)", size=12, bold=True)
text(s, L + 0.3, 5.93, 3.6, 0.8, "⓪ 하루 700건까지 무료 서버만(0원)\n① 5.9천 건까지 + Sol · ② 그 위로 GPU 1대(25.6만원)\n③ 3.9만 건부터 약 3.8만 건마다 GPU 1대 추가", size=10.5, color=MUTED, line=1.15)
text(s, L + 4.2, 5.6, 7.4, 0.3, "성능 · 응답 시간", size=12, bold=True)
text(s, L + 4.2, 5.93, 7.4, 0.8, "우리 모델(무료 서버 · GPU) 97.3~97.5% · Luna 96.4% · Sol 98.8% (769문제, 상용은 공정 비교 아님)\n응답: 무료 서버 이어지는 질문 7.7초 · GPU(파인튜닝 모델) 0.24초 · 새 일정 첫 질문 1.1초\n→ Luna 경로가 클수록 쌈(하루 2만 건 월 약 15만 · 10만 건 약 32만원 차이) · API 몫 정확도 약 1%p 낮음", size=10.5, color=MUTED, line=1.15)
foot(s, "가정: 가장 몰리는 한 시간 = 하루 질문의 15%(콜센터 계획 기본값) · 그 시간 가동률 80% · 새 일정 첫 질문 20% · GPU = RunPod A4000 월 25.6만원 · 처리량 A4000 실측(파인튜닝 전 E4B · 동시 8) · 30일. 장애 시 API 로 넘기는 장치는 cs 개발 세션에 맡김.")
notes(s, "결론입니다. 서버 대수는 하루 평균이 아니라 가장 몰리는 한 시간을 기준으로 정했습니다. 그 한 시간에 하루 질문의 15%가 몰린다고 보고, 그때도 서버를 80%까지만 쓰게 했습니다. 이 기준으로 무료 서버만으로는 하루 약 700건까지 버팁니다. 그 위로는 몰리는 시간에 넘치는 몫만 Luna API 로 보내고, 한가한 시간에는 무료 서버가 다 받습니다. API 비용이 GPU 월세를 넘는 하루 약 4.1만 건에서 GPU 서버를 붙이고, 그 뒤로는 약 10만 건마다 한 대씩 늘립니다. 품질을 우선해 Sol 을 쓰면 하루 5.8천 건에서 바로 GPU 로 넘어갑니다. 서버가 죽었을 때 API 로 넘기는 장치는 cs 개발 세션에 맡겼습니다.")

CH = 4
# ================================================================ 9 E2E
s = new("PIPELINE TEST", "앞단을 두어도 점수는 구분되지 않았고 호출은 19% 줄었습니다")
pic(s, A / "funnel.png", L - 0.05, 1.7, w=6.2)
x = 7.55
text(s, x, 1.75, 5, 0.3, "맞힌 문제 / 769", size=12, bold=True, color=MUTED)
res = [("748", "파인튜닝 E4B 혼자", "기준", PRIMARY), ("745", "앞에 규칙 + ML 사전 필터 추가", "혼자와 구분 안 됨 (갈린 문제 3 : 6, p=0.51)", PRIMARY),
       ("697", "라우터에 Winnow-E4B 추가", "Jev 계열 · 파인튜닝 전이라 공정 비교 아님.\n사후 수정 버전 (미리 고정한 버전 472)", ERR)]
for k, (big, lab, how, c) in enumerate(res):
    yy = 2.15 + k * 1.42
    if k:
        hline(s, x, yy - 0.18, 5.03)
    text(s, x, yy, 1.5, 0.8, big, size=38, bold=True, color=c, spacing=-1)
    text(s, x + 1.6, yy + 0.1, 3.45, 0.4, lab, size=13, bold=True)
    text(s, x + 1.6, yy + 0.48, 3.45, 0.7, how, size=10.5, color=CAPTION, line=1.15)
foot(s, "E2E 파이프라인 테스트: 단계를 실제로 이어 붙여 문제마다 처음부터 끝까지 호출(GPU 서버 C, 10-06). 같은 방법으로 파인튜닝한 두 모델을 섞은 구조는 747~752 로 혼자와 구분 안 됨.")
notes(s, "모델을 여러 단계로 이어 붙이면 좋아지는지 실제로 돌려 봤습니다. 835문제를 넣으면 정해 둔 말 패턴의 규칙이 125개를 바로 처리하고, 작은 분류 모델이 잡담 36개를 걸러서 큰 모델은 674번만 부르면 됩니다. 점수는 혼자 풀 때와 같고 호출은 19% 줄었습니다. 파인튜닝하지 않은 Jev 계열 모델을 라우터로 넣으면 697로 떨어졌지만 학습 조건이 달라 공정한 비교는 아닙니다.")

# ================================================================ 9-2 조합 시험 모음 (2026-10-07 사용자 지시)
# 근거: 연구 문서 §82-5 · §85-3 · §90 · §92-4 · §92-6 · §92-8 · §92-9
s = new("COMBINATIONS", "조합 여덟 가지 모두 단독 최고를 넘지 못했고, 이득은 호출 절감입니다")
pic(s, A / "combos.png", L - 0.1, 1.6, w=6.7)
x = L + 6.95
text(s, x, 1.65, 5.0, 0.3, "파트별로 맞는 모델을 붙인 지금 구성", size=12.5, bold=True)
parts = [("고객 말 분류", "학습한 인코더 · 의도 98 · 감정 95 · 긴급도 91 · 대상 95%"),
         ("일정 항목 매칭", "파인튜닝 E4B · 서수 · 상대 위치는 규칙이 먼저"),
         ("규정 검색", "임베딩(bge-m3) · 제품 Recall@3 62.5% → 재순위 92.6%(제품 반영 전)"),
         ("잡담 · 무관한 말", "규칙 → ML 필터 · 호출 −19~23%")]
for k, (a_, b_) in enumerate(parts):
    yy = 2.05 + k * 0.62
    if k:
        hline(s, x, yy - 0.08, 5.0)
    text(s, x, yy, 1.6, 0.5, a_, size=11, bold=True, color=PRIMARY)
    text(s, x + 1.6, yy, 3.4, 0.55, b_, size=10, color=TEXT, line=1.1)
box(s, x, 4.65, 5.0, 1.2, fill=SURFACE, line=BORDER, r=0.2)
text(s, x + 0.2, 4.72, 4.6, 0.3, "Jev 계열을 어디에 쓸 수 있나", size=11, bold=True)
text(s, x + 0.2, 5.05, 4.6, 1.1, "인코더형(Laya · OpenDecider-nano)은 분류 46~81%로 못 씀. LLM형 Winnow-E4B 는 파인튜닝 전에도 의도 94.5 · 감정 91.0 · 대상 92.1% 지만 긴급도 63.5%. 파인튜닝하면 항목 매칭 756(E4B 시드 2 의 760 과 구분 안 됨)", size=9.5, color=CAPTION, line=1.15)
foot(s, "같은 769문제. 조합의 문턱 · 라우터는 한 세트를 빼고 고른 값. 두 파인튜닝 모델이 다른 답을 낸 문제가 12개뿐이라 고를 여지가 작았습니다. 분류 · 매칭 · 검색을 한 흐름으로 이은 시험은 아직 없습니다(맡김).")
notes(s, "규칙, ML, 임베딩, Jev 계열 모델, 소형 LLM 을 여러 방식으로 조합해 봤습니다. 앞에서 거르기, 자신 없으면 다른 모델로 넘기기, 질문 유형에 따라 전문 모델로 보내기, 학습한 라우터로 고르기까지 여덟 가지입니다. 어느 조합도 단독 최고 모델을 넘지 못했고, 파인튜닝 전 모델을 라우터로 넣은 조합은 오히려 크게 떨어졌습니다. 같은 모델을 시드만 바꿔 다시 학습해도 10문제가 달라지는데, 조합 사이 차이는 그보다 작았습니다. 조합의 이득은 정확도가 아니라 비용입니다. 규칙과 ML 필터가 앞에서 쉬운 문제를 닫아 큰 모델 호출이 19에서 23% 줄었습니다. 그래서 지금 구성은 한 모델에 모두 맡기지 않고, 기능마다 가장 잘하는 것을 붙인 파트별 구성입니다. 고객 말 분류는 학습한 인코더, 항목 매칭은 파인튜닝 E4B, 규정 검색은 임베딩과 재순위, 잡담은 규칙과 ML 필터입니다. 이 넷을 한 흐름으로 이어 재는 시험은 아직이라 맡겨 두었습니다.")

# ================================================================ 10 혼합 트래픽 (2026-10-07 생각 모드 끔 결과 반영)
# 근거: 서비스 평가 베이스라인 리포트 · 6주차 초안 4.5 (Wilson 95% 구간 · McNemar 정확검정)
s = new("MIXED TRAFFIC", "빈 답은 사라졌지만, 시드에 따라 85.6~93.7%로 흔들립니다")
text(s, L, 1.68, CW, 0.3, "실제 채팅처럼 섞은 2,735문제", size=12, bold=True, color=MUTED)
pic(s, A / "mixbar.png", L, 2.02, w=CW)
cards = [("mixed_think.png", "전체 정답률 · 생각 모드 켬 → 끔", "시드 1 · 2,669문제 중 2,424 → 2,498 = 93.6% · 빈 답 81 → 0. 같은 방법으로 시드만 바꾼 3개는 93.7 · 85.6 · 90.9% (평균 90.1%)"),
         ("mixed_err2.png", "무관한 말에 항목을 잘못 고름 · 앞단 없음 → 있음", "시드 1 · 4.4% → 3.7%, 구분 안 됨(16 : 8, p=0.15). 시드 3개 단독은 4.3 · 16.0 · 7.3% — 갈리는 곳이 바로 여기")]
for k, (f, lab, sub) in enumerate(cards):
    xx = L + k * 6.07
    box(s, xx, 3.6, 5.76, 2.95, fill=SURFACE, line=BORDER, r=0.22)
    text(s, xx + 0.3, 3.8, 5.2, 0.3, lab, size=14, bold=True)
    text(s, xx + 0.3, 4.12, 5.2, 0.5, sub, size=10.5, color=CAPTION, line=1.1)
    pic(s, A / f, xx + 0.25, 4.8, w=5.25)
foot(s, "일정 질문만 있는 769문제는 시드 3개가 752 · 750 · 745 로 구분 안 됨 — 시드가 가르는 것은 무관한 말을 「없음」으로 거르는 정도. 앞단은 큰 모델 호출 −23%. 서비스에는 시드 1 이 올라가 있음. 합성 시험.")
notes(s, "실제 채팅처럼 잡담, 관광 질문, 구어체를 섞은 2,735문제로 다시 돌렸습니다. 모델의 생각 모드를 끄니 빈 답 81건이 모두 사라지고 정답률이 90.8%에서 93.6%로 올랐습니다. 다만 이것은 시드 하나의 값입니다. 같은 방법으로 시드만 바꿔 학습한 세 모델은 93.7%, 85.6%, 90.9%로 크게 갈렸고, 갈린 곳은 일정과 무관한 말을 「없음」으로 거르는 부분이었습니다. 이 상태에서는 앞단의 규칙과 분류 모델이 정확도를 더 올린다고 말할 수 없었고, 남는 이득은 큰 모델 호출을 23% 줄이는 것입니다. 제품 호출은 이미 생각 모드를 끄고 있다는 것도 실서버에서 확인했습니다.")

# ================================================================ 11 분류
s = new("CLASSIFICATION", "고객 말 꼬리표 중 긴급도가 학습으로 가장 많이 올랐습니다")
bubble(s, L, 2.4, 5.4, "식당 왔는데 우리 네 명 자리 없대요. 어떡하죠?", "고객", mine=True, h=0.72)
tags = [("의도", "사건 신고"), ("대상", "식당"), ("감정", "부정"), ("긴급도", "높음")]
for k, (a_, b_) in enumerate(tags):
    xx = L + k * 1.37
    hi = a_ == "긴급도"
    box(s, xx, 3.42, 1.25, 0.95, fill=SOFT if hi else SURFACE, line=PRIMARY if hi else BORDER, r=0.18, lw=1.5 if hi else 1.0)
    text(s, xx, 3.52, 1.25, 0.3, a_, size=10.5, color=PRIMARY if hi else MUTED, align=PP_ALIGN.CENTER, bold=True)
    text(s, xx, 3.8, 1.25, 0.45, b_, size=16, bold=True, color=PRIMARY if hi else TEXT, align=PP_ALIGN.CENTER)
text(s, L, 4.75, 5.4, 1.4, "꼬리표 네 개로 처리 순서와 담당을 정합니다.\n「얼마나 급한가」는 문장에 잘 드러나지 않아\n가장 어려웠습니다.", size=12.5, color=MUTED, line=1.2)
x = 6.85
box(s, x, 1.8, 5.73, 4.25, fill=SURFACE, line=BORDER, r=0.22)
text(s, x + 0.35, 2.0, 5, 0.3, "긴급도 정확도 · 400문장", size=14, bold=True)
text(s, x + 0.35, 2.32, 5, 0.3, "학습 없이 지시문만 준 E4B → 우리 문장 720개로 학습한 분류 모델", size=10.5, color=CAPTION)
pic(s, A / "urgency.png", x + 0.3, 2.8, w=5.1)
hline(s, x + 0.35, 4.45, 5.03)
text(s, x + 0.35, 4.6, 5, 0.3, "학습한 분류 모델의 나머지 꼬리표", size=11, bold=True, color=MUTED)
for k, (lab, v) in enumerate((("의도", "97.5%"), ("감정", "93.8%"), ("대상", "93.2%"))):
    xx = x + 0.35 + k * 1.7
    text(s, xx, 4.95, 1.6, 0.6, v, size=26, bold=True, color=PRIMARY)
    text(s, xx, 5.55, 1.6, 0.3, lab, size=12, color=MUTED)
foot(s, "CX 400 중 정답 칸이 있는 353문장(합성): 긴급도 312/353 대 215/353 · 갈린 문장 112 : 15, p=1.6e-19 · 차이 +27.5%p (+21.8~+33.1). 단 별도 평가셋 G96(96문장)에서는 네 꼬리표 모두 구분 안 됨 → 다른 자료로는 아직 일반화하지 못했습니다.")
notes(s, "고객 말에는 꼬리표 네 개를 붙입니다. 무엇을 원하는지, 식당인지 활동인지, 감정은 어떤지, 얼마나 급한지입니다. 이 중 긴급도가 가장 어려웠는데, 학습 없이 지시문만 준 모델은 60.9%였고 우리 문장으로 학습한 작은 분류 모델은 88.4%였습니다.")

# ================================================================ 12 RAG (2026-10-07 사용자: 제목이 오른쪽 그림에만 맞음 → 장 전체 제목으로, 지표 뜻을 짧게)
s = new("POLICY SEARCH · RAG", "규정 검색은 지금 62.5%이고, 개선안 두 가지로 목표에 다가갔습니다")
bubble(s, L, 1.7, 5.3, "창덕궁 임시 휴관이면 일정 어쩌죠?", "고객", mine=True, h=0.66)
box(s, L, 2.48, 5.3, 0.72, fill=SURFACE, line=PRIMARY, r=0.18, lw=1.25)
text(s, L + 0.22, 2.5, 4.9, 0.7, [[("찾아야 하는 규정 조각  ", {"size": 9.5, "bold": True, "color": PRIMARY})],
                                 [("「운영 중단과 통제」 문서 · 「임시 휴관과 정기 휴관을 나눈다」 절", {"size": 11, "bold": True})]], space=1, anchor=MSO_ANCHOR.MIDDLE)
text(s, L, 3.35, 5.3, 0.3, "지표 (블라인드 평가셋 B · 답 있는 48문제)", size=10.5, bold=True, color=MUTED)
text(s, L + 3.3, 3.35, 2.0, 0.3, "지금 → 개선 색인", size=10.5, bold=True, color=MUTED, align=PP_ALIGN.RIGHT)
rag = [("Recall@3", "정답 규정이 검색 상위 3개 안에 든 질문 비율", "62.5% → 72.9%"),
       ("Hit@2", "고객 화면에 보이는 2줄 안에 정답이 든 비율", "50.0% → 70.8%"),
       ("정답 줄을 보인 질문", "실제 답에 정답 규정 문장이 실린 질문 수", "21 → 31개"),
       ("선택적 위험", "답한 것 중 틀린 비율 · 낮을수록 좋음", "51.2% → 27.9%")]
for k, (a_, b_, c_) in enumerate(rag):
    yy = 3.7 + k * 0.55
    if k:
        hline(s, L, yy - 0.05, 5.3)
    text(s, L, yy, 3.3, 0.28, a_, size=11, bold=True)
    text(s, L, yy + 0.25, 3.4, 0.28, b_, size=8.5, color=CAPTION)
    text(s, L + 3.35, yy + 0.04, 1.95, 0.35, c_, size=12, bold=True, color=PRIMARY, align=PP_ALIGN.RIGHT)
box(s, L, 5.95, 5.3, 0.82, fill=SOFT, line=None, r=0.18)
text(s, L + 0.22, 5.95, 4.9, 0.82, [[("개선안 2 · 재순위(후보 20개를 다시 줄 세움)", {"bold": True, "color": PRIMARY, "size": 11})],
                                   [("따로 둔 보류 세트 68문제에서 Recall@3 41 → 63개 = 92.6% (목표 90% 달성, 갈린 질문 23 : 1)", {"size": 10})]], space=2, anchor=MSO_ANCHOR.MIDDLE)
x = 6.6
text(s, x, 1.7, 6, 0.3, "개선안 1 · 인덱싱 텍스트를 바꾸면 (직원용 본문 → 고객용 문장)", size=12, bold=True)
text(s, x, 2.0, 6, 0.3, "정답은 늘었지만 오응답도 늘었습니다", size=11, color=MUTED)
pic(s, A / "slope.png", x - 0.1, 2.3, w=5.6, h=3.2)
text(s, x + 0.05, 5.55, 6, 1.2, [[("●  ", {"color": PRIMARY}), ("정답 규정을 보인 질문 (48문제 중)", {"color": MUTED})],
                                 [("●  ", {"color": ERR}), ("예약 요청 같은 여행 말에 규정을 붙인 비율", {"color": MUTED})],
                                 [("그래서 분류 단계 뒤에서 다시 재고 제품 반영을 정합니다.", {"bold": True, "color": TEXT, "size": 12})]], size=11, space=2)
foot(s, "같은 질문 짝 비교: Recall@3 개선은 5 : 0, p=0.0625 로 경계(우연일 확률 약 6%) · 정답 줄은 10 : 0, p=0.002 로 유의. 오응답은 라벨 없는 여행 대화 300건, 의도 분류기를 거치지 않은 값. 규정 문장은 저장된 문장을 그대로 실어 인용 334/334.")
notes(s, "규정 검색입니다. 고객이 창덕궁 임시 휴관이면 어쩌죠라고 물으면 운영 중단 규정의 임시 휴관 절을 찾아야 합니다. 지금은 정답 규정이 상위 3개 안에 드는 비율이 62.5%로 목표 90%에 못 미칩니다. 개선안을 두 가지 시험했습니다. 첫째, 규정을 찾을 때 비교하는 글을 고객용 문장으로 바꾸면 정답은 늘지만 예약 요청 같은 말에도 규정을 붙이는 오응답이 22%에서 37%로 늘었습니다. 둘째, 후보 20개를 다시 줄 세우는 재순위는 따로 둔 보류 세트에서 92.6%로 목표를 넘었고, 지금 제품 반영을 준비하고 있습니다.")

# ================================================================ 13 사람 검수 (2026-10-07 사용자: 문제 항목이 아니라 수작업 검수로 개선한 사항으로)
# 근거: 사람평가_첫_결과 리포트 · 6주차 초안 4.9. 사용자가 내용을 직접 보고 판정했고 기계 의견은 판단 보조로만 썼다.
s = new("HUMAN REVIEW", "사람이 35행을 직접 검수해 기계 검사를 확인하고 결함을 고쳤습니다")
box(s, L, 1.75, 3.7, 4.85, fill=SOFT, line=None, r=0.22)
text(s, L + 0.3, 1.95, 3.2, 0.3, "기계 검사와 사람 판정", size=12, bold=True, color=PRIMARY)
text(s, L + 0.3, 2.3, 3.2, 1.2, "18/19", size=60, bold=True, color=PRIMARY, spacing=-2)
text(s, L + 0.3, 3.45, 3.2, 0.9, "같은 쪽으로 판정 = 94.7%\n(75.4~99.1) · Cohen κ = 0.90", size=12, line=1.15)
hline(s, L + 0.3, 4.45, 3.1, color=rgb("#cfe0d4"))
text(s, L + 0.3, 4.6, 3.2, 1.8, "규정 답 24행 · 알림 번역 11행을\n사람이 원문 · 답 · 근거를 직접 보고\n맞다 / 중간 / 틀리다로 판정했습니다.\n기계 의견은 판단 보조로만 썼습니다.", size=11, color=CAPTION, line=1.2)
x = L + 3.95
text(s, x, 1.8, 7.9, 0.3, "검수로 찾아 고친 것", size=13, bold=True)
text(s, x, 2.12, 7.9, 0.3, [[("고객 질문  ", {"bold": True, "color": MUTED}), ("「한파 특보인데 해돋이 일정 늦추나요?」", {"bold": True})]], size=11.5)
box(s, x, 2.5, 3.8, 2.0, fill=ERR_SOFT, line=ERR_B, r=0.2)
text(s, x + 0.22, 2.6, 3.4, 0.3, "고치기 전 답 · 앞뒤가 모순", size=10.5, bold=True, color=ERR)
text(s, x + 0.22, 2.92, 3.4, 1.55, "한파 규정을 실음: 「…몸을 녹일 실내 장소를\n경로에 넣어 드려요. 해돋이는 옮기지 않고\n준비물을 안내해 드려요」\n끝줄: 「일정은 바꾸지 않았어요」", size=10.5, line=1.2)
text(s, x + 3.8, 2.5, 0.32, 2.0, "→", size=20, bold=True, color=PRIMARY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
box(s, x + 4.12, 2.5, 3.8, 2.0, fill=SURFACE, line=PRIMARY, r=0.2, lw=1.5)
text(s, x + 4.34, 2.6, 3.4, 0.3, "고친 뒤 · 제품 답 문구", size=10.5, bold=True, color=PRIMARY)
text(s, x + 4.34, 2.92, 3.4, 1.55, "머리말: 「해당하는 상황이 되면\n이 기준으로 처리해요」\n끝줄: 「지금 일정은 바꾸지 않았어요」\n→ 규정은 「그런 상황이면」의 기준임이 드러남", size=10.5, line=1.2)
text(s, x, 4.62, 7.9, 0.5, "규정 문장은 「그런 상황이 되면 해 드린다」는 일반 기준인데, 이미 해 준 것처럼 읽혀 끝줄과 부딪혔습니다. 정답 줄 검사(기계)로는 못 잡는 결함입니다.", size=10.5, color=MUTED, line=1.15)
hline(s, x, 5.2, 7.9)
for k, (big, lab, how) in enumerate((("10/24", "규정 질문 답 「맞다」", "틀린 줄만 보인 답 · 답 없는 질문에 답한 경우가 원인 → 규정 검색 개선 근거"),
                                     ("9/10", "알림 번역 「맞다」", "보호 장치를 통과한 번역 8행은 모두 맞음"))):
    xx = x + k * 4.0
    text(s, xx, 5.35, 1.2, 0.5, big, size=22, bold=True, color=PRIMARY)
    text(s, xx + 1.25, 5.37, 2.7, 0.3, lab, size=12, bold=True)
    text(s, xx + 1.25, 5.67, 2.7, 0.7, how, size=9.5, color=CAPTION, line=1.1)
foot(s, "2026-10-06, 35행(틀리기 쉬운 쪽을 많이 뽑은 표본이라 서비스 전체 평균이 아님). 고친 곳: 규정 답 머리말 · 끝줄(itinerary_team.question_answer).")
notes(s, "사람이 직접 35행을 검수했습니다. 원문, 답, 근거를 보고 맞다, 중간, 틀리다로 판정했고, 기계 의견은 판단 보조로만 썼습니다. 기계 검사와 사람 판정은 19개 중 18개가 같아서 기계 검사를 믿을 만하다는 것을 확인했습니다. 어긋난 한 건은 답의 앞뒤 문장이 서로 모순되는 결함이었는데, 정답 줄 검사로는 잡을 수 없는 문제라 검수에서 찾아 제품 문구를 고쳤습니다.")

# ================================================================ 13-2 평가 설계 (평가 설계서: 논문 · 표준 약 70건, 본문까지 읽은 것 약 40건)
s = new("HOW WE MEASURE", "지표와 통계 방법은 공개 벤치마크 · 논문 기준을 따랐습니다")
hdr = ["무엇을", "지표", "근거 문헌", "지금 값 (95% 구간)"]
cols = [1.9, 3.2, 2.6, 4.13]
rows = [("규정 검색", "Hit@2 · Recall@3 · MRR · nDCG@10", "BEIR · MTEB", "Recall@3 62.5% (48.4~74.8)"),
        ("답할지 거절할지", "거절 재현율 · 오거절 · 선택적 위험 · AURC", "SQuAD 2.0 · Geifman·El-Yaniv", "선택적 위험 51.2% → 27.9% (개선 색인)"),
        ("근거 · 환각", "문장 일치 회귀 시험 · 숫자 / 금액 단위 보존", "Wang 2021 · Tang 2025", "인용 334/334 · 숫자 변조 0/115 (상한 3.2%)"),
        ("고객 말 분류", "매크로 F1 · MCC · 네 축 동시 정답 · ECE", "Guo 2017", "네 축 동시 CX 77.1% (71.9~81.6)"),
        ("일정 · 에이전트", "오지목 · pass^k · 시드 변동", "CLINC150 · τ-bench · Bouthillier 2021", "결정 단위 pass^3 91.3% (86.6~95.3)"),
        ("지연 · 오류", "p50 · p95 · p99 · 오류 3분류", "Dean·Barroso 2013 · Google SRE", "규정 답 p95 596ms · 오류 0/680")]
y = 1.72
xx = L
for c, w in zip(hdr, cols):
    text(s, xx, y, w - 0.1, 0.3, c, size=10.5, bold=True, color=MUTED, spacing=0.5)
    xx += w
for k, r in enumerate(rows):
    yy = 2.08 + k * 0.62
    hline(s, L, yy - 0.06, CW)
    xx = L
    for ci, (c, w) in enumerate(zip(r, cols)):
        text(s, xx, yy + 0.06, w - 0.15, 0.5, c, size=12 if ci == 0 else 10.5, bold=ci in (0, 3), color=PRIMARY if ci == 3 else (TEXT if ci < 2 else CAPTION), line=1.05)
        xx += w
hline(s, L, 2.08 + 6 * 0.62 - 0.06, CW)
box(s, L, 6.0, CW, 0.75, fill=SOFT, line=None, r=0.2)
text(s, L + 0.3, 6.0, CW - 0.6, 0.75, [[("통계  ", {"bold": True, "color": PRIMARY}),
                                       ("비율은 Wilson 구간 · 평균과 F1 은 부트스트랩 구간 · 두 방법 비교는 같은 질문 짝 McNemar 정확검정 · 0건은 0% 가 아니라 상한으로 적음", {})]],
     size=11.5, anchor=MSO_ANCHOR.MIDDLE)
foot(s, "평가 설계서(2026-10-06): 논문 · 표준 약 70건 조사(본문까지 읽은 것 약 40건). 합성 질문 점수는 순위 비교에만 믿고 절댓값은 낙관으로 읽습니다(Rahmani 2024). LLM 판정기는 보조로만 씁니다(Zheng 2023).")
notes(s, "평가 지표는 공개 벤치마크와 논문 기준에 맞춰 우리 서비스에 맞는 것을 골랐습니다. 규정 검색은 고객에게 실제로 보이는 두 줄 기준의 Hit@2 와 Recall@3, 답할지 거절할지는 선택적 위험, 근거는 문장 일치와 숫자 보존, 분류는 네 꼬리표 동시 정답과 보정, 에이전트는 같은 일을 세 번 모두 맞히는 pass^3, 지연은 p95 로 봅니다. 모든 비율에는 95% 구간을 붙이고, 두 방법 비교는 같은 질문끼리 짝지은 McNemar 검정으로 했습니다.")

# ================================================================ 13-2b 같은 조건 Luna · Sol (2026-10-07 사용자: 「Luna · Sol 은 같은 조건에서 어떻게 나와?」)
# 근거: final_project_cs/wiki/records/reports/2026-10-07_오응답_실제경로와_Luna_Sol_비교_x600_반영.md §4 (Codex CLI 로 문제마다 호출)
s = new("SAME CONDITIONS", "Sol 은 분류 · 결정에서 앞서고, 규정 재순위는 우리와 같습니다")
hdr = ["지표 (같은 문제 · 같은 채점)", "우리", "Luna", "Sol"]
rows = [("고객 말 분류 · 네 꼬리표 동시 정답", "G96 · 96문장 · Claude 초안 라벨", (43.8, 55.2, 67.7)),
        ("결정 단위 · 3번 모두 맞음(pass^3)", "172사례 × 3번", (91.3, 92.4, 97.1)),
        ("규정 재순위 · Recall@3", "보류 세트 68문제", (92.6, 92.6, 86.8))]
text(s, L, 1.7, 4.3, 0.3, hdr[0], size=11, bold=True, color=MUTED)
for c, name in enumerate(hdr[1:]):
    text(s, L + 4.6 + c * 2.45, 1.7, 2.3, 0.3, name, size=12, bold=True, color=PRIMARY if c == 0 else TEXT)
for r, (lab, sub, vals) in enumerate(rows):
    yy = 2.15 + r * 1.15
    hline(s, L, yy - 0.12, CW)
    text(s, L, yy, 4.4, 0.3, lab, size=12.5, bold=True)
    text(s, L, yy + 0.36, 4.4, 0.3, sub, size=10, color=CAPTION)
    best = max(vals)
    for c, v in enumerate(vals):
        xx = L + 4.6 + c * 2.45
        box(s, xx, yy + 0.42, 2.2, 0.22, fill=SUBTLE, line=None, r=0.11)
        box(s, xx, yy + 0.42, 2.2 * v / 100, 0.22, fill=PRIMARY if v == best else GREY, line=None, r=0.11)
        text(s, xx, yy - 0.04, 2.2, 0.4, f"{v:.1f}%", size=18, bold=True, color=PRIMARY if v == best else MUTED)
hline(s, L, 2.15 + 3 * 1.15 - 0.12, CW)
text(s, L, 5.65, 4.4, 0.3, "1건 비용", size=12.5, bold=True)
for c, v in enumerate(("0원 · 우리 서버", "0.25원", "4.93원")):
    text(s, L + 4.6 + c * 2.45, 5.6, 2.3, 0.4, v, size=15, bold=True, color=TEXT)
foot(s, "Luna · Sol 은 Codex CLI 로 문제마다 불러 쟀습니다(API 직접 호출보다 느림 · 생각 설정 통제 불가라 공정 비교 아님). 규정 재순위는 우리와 2 : 2 로 구분 안 됨. 합성 문제 기준이며, 고객 말 분류는 합성 CX 400 에서만 우리 분류기가 앞섭니다.")
notes(s, "상용 모델 Luna 와 Sol 을 우리와 같은 문제, 같은 채점으로 재 봤습니다. 고객 말 분류와 결정 단위에서는 Sol 이 앞섰습니다. 별도 평가셋에서 네 꼬리표를 동시에 맞힌 비율이 우리 43.8%, Luna 55.2%, Sol 67.7% 이고, 결정 단위를 세 번 모두 맞힌 비율은 우리 91.3%, Sol 97.1% 입니다. 규정 재순위는 우리와 Luna 가 92.6% 로 같고 Sol 은 86.8% 였습니다. 대신 Sol 은 한 건에 약 5원이 들고 우리 모델은 우리 서버에서 돕니다. 그래서 분류와 결정 단위는 우리 모델을 더 키울 여지가 있다는 뜻으로 읽고 있습니다.")

CH = 5
# ================================================================ 13-3 상용화 기준 (2026-10-07 사용자: 「어느 정도 수치가 나와야 상용화 수준인가」)
# 기준 출처: 양식(SLA 15초 · Recall 0.90) · 계획서(결정 단위 95% · 엉뚱한 변경 0) · 팀 목표(환각 0) · 나머지는 Claude 제안(팀 결정 필요).
s = new("COMMERCIAL READINESS", "합성 시험으로 4개를 넘었고, 사람이 쓴 질문으로는 아직 확인 전입니다")
hdr = ["지표", "지금", "상용화 기준", "기준 출처", "상태"]
cw = [3.05, 3.15, 2.75, 1.55, 1.33]
rows = [("응답 시간 p95", "0.6~11.7초", "15초 이내", "양식 SLA", "합성 넘음"),
        ("일정 항목 매칭 (769)", "97.3% (95.9~98.2)", "95% · 구간 하한 기준", "제안", "합성 넘음"),
        ("규정 인용 정확도", "334/334", "100%", "팀 목표", "합성 넘음"),
        ("번역 숫자 · 금액 단위 변조", "0/115 · 단위 대조 추가", "0건", "팀 목표", "합성 넘음"),
        ("규정 검색 Recall@3", "제품 62.5% · 재순위 92.6%", "90% 이상", "양식", "반영 남음"),
        ("결정 단위 pass^3", "91.3% (86.6~95.3)", "95% 이상", "계획서", "미달"),
        ("엉뚱한 대상 변경", "1/172", "0건", "계획서", "미달"),
        ("계획 읽기 글자 오독", "12/350 = 3.4%", "0건", "팀 목표", "미달"),
        ("무관한 말에 항목 오지목", "시드별 4.3~16.0% · 제품 5.3%", "1% 이하", "제안", "미달"),
        ("긴급도 분류", "CX 88.4% · 별도 셋 62.5%", "90% · 「높음」 재현율 95%", "제안", "미달"),
        ("사람 판정 규정 답 「맞다」", "41.7% (어려운 표본 24행)", "90% · 사람이 쓴 질문", "제안", "미달")]
y = 1.62
xx = L
for c, w in zip(hdr, cw):
    text(s, xx, y, w - 0.1, 0.3, c, size=10.5, bold=True, color=MUTED)
    xx += w
col = {"합성 넘음": (SOFT, PRIMARY), "반영 남음": (WARN_SOFT, WARN), "미달": (ERR_SOFT, ERR)}
for k, r in enumerate(rows):
    yy = 1.95 + k * 0.41
    hline(s, L, yy - 0.04, CW, lw=0.5)
    xx = L
    for ci, (v, w) in enumerate(zip(r, cw)):
        if ci == 4:
            f, c = col[v]
            box(s, xx, yy + 0.02, w - 0.08, 0.3, fill=f, line=None, r=0.15)
            text(s, xx, yy + 0.02, w - 0.08, 0.3, v, size=10, bold=True, color=c, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        else:
            text(s, xx, yy + 0.04, w - 0.12, 0.32, v, size=10.5, bold=ci in (0, 2), color=CAPTION if ci == 3 else TEXT)
        xx += w
box(s, L, 6.5, CW, 0.42, fill=SOFT, line=None, r=0.18)
text(s, L + 0.25, 6.5, CW - 0.5, 0.42, [[("공통 조건  ", {"bold": True, "color": PRIMARY}),
                                         ("합성 문제가 아니라 사람이 쓴 실제 질문에서, 95% 구간의 아래 끝이 기준을 넘어야 상용화로 봅니다.", {})]],
     size=11, anchor=MSO_ANCHOR.MIDDLE)
foot(s, "「제안」 기준은 틀렸을 때 고객이 입는 손해로 정한 Claude 제안이며 팀 결정이 필요합니다: 되돌리기 어려운 일(일정 변경 · 금액 · 지어낸 값)은 0건, 답의 정확도는 90~95%, 사람 판정은 90%.")
notes(s, "상용화 기준을 정리했습니다. 양식과 계획서에 정해진 기준은 응답 15초, 규정 검색 90%, 결정 단위 95%와 엉뚱한 변경 0건, 지어낸 값 0건입니다. 나머지는 틀렸을 때 고객이 입는 손해를 기준으로 제안했습니다. 일정을 잘못 바꾸거나 금액을 바꾸는 것처럼 되돌리기 어려운 일은 0건, 답의 정확도는 90~95%입니다. 합성 시험으로는 넷이 기준을 넘었지만, 사람이 쓴 실제 질문으로 잰 것은 아직 없어서 상용화 통과라고 말하지는 않습니다. 규정 검색은 재순위가 92.6%지만 구간 아래 끝이 84%라 90% 기준에는 못 미치고, 여섯은 미달입니다. 그리고 이 모든 값은 사람이 쓴 실제 질문에서, 구간의 아래 끝으로 기준을 넘어야 상용화라고 봅니다.")

# ================================================================ 14 남은 문제
s = new("OPEN ISSUES", "남은 큰 문제는 무관한 말 오지목과 규정 질문 놓침입니다")
text(s, L, 1.65, 4, 0.3, "이번에 해결", size=12, bold=True, color=PRIMARY, spacing=0.5)
done = [("번역 금액 단위 대조", "「35,000원」 → 「35,000円」 같은 단위 바뀜을 거름 · x600 서버 반영"),
        ("규정 답 앞뒤 모순 문구", "사람 검수로 찾아 머리말 · 끝줄 문구를 고침"),
        ("빈 답: 제품은 이미 막혀 있음", "제품 호출은 생각 모드를 끄고 있음 · x600 서버에서 재현 확인 0/20 대 20/20"),
        ("오응답을 실제 경로로 잼", "규정 오응답 8/2,110 = 0.4% · 검증 단계를 넣으면 0.1%")]
for k, (a_, b_) in enumerate(done):
    xx = L + k * 2.98
    box(s, xx, 2.0, 2.85, 1.2, fill=SOFT, line=None, r=0.2)
    text(s, xx + 0.2, 2.08, 2.5, 0.35, "✓  " + a_, size=11.5, bold=True, color=PRIMARY)
    text(s, xx + 0.2, 2.45, 2.5, 0.72, b_, size=9.5, color=CAPTION, line=1.1)
text(s, L, 3.4, 4, 0.3, "남은 것", size=12, bold=True, color=ERR, spacing=0.5)
issues = [("5.3%", "일정과 무관한 말에 일정 항목을 짚음", "실제 경로 · 일상 대화 · 구어체 69/1,300 · 그중 일정까지 바꾸려 한 것 18/1,300", "RAG"),
          ("26%", "규정 질문을 규정으로 못 알아봄", "「바꿔줘요?」 같은 요청 말투 39/148 · 검증 단계를 넣으면 정밀도 80.0 → 87.6%", "RAG · cs"),
          ("2건", "엉뚱한 일정 변경 1/172 · 계획 읽기 글자 오독 12/350", "대상 확인 안전장치 · 두 받아쓰기 맞춰 보기를 다른 세션이 만드는 중", "진행 중"),
          ("켜짐", "파인튜닝 E4B 서비스 연결 · x600 반영(10-07)", "첫 문장은 규칙, 모델은 뒤에서 읽음 · 웹 채팅 끝까지는 아직 확인 안 함 · 재순위 · 검증 단계는 반영 전", "cs"),
          ("일부", "실서버: 실제 사용자 흐름", "서버 응답 · 웹 경로 55개 · 재난 뒤 패널은 확인 · 로그인 · 여행 만들기는 시험 여행 허락 필요", "결정 필요")]
for k, (big, lab, how, owner) in enumerate(issues):
    yy = 3.75 + k * 0.62
    if k:
        hline(s, L, yy - 0.06, CW)
    text(s, L, yy, 1.7, 0.5, big, size=20, bold=True, color=ERR if k < 3 else WARN, spacing=-0.3)
    text(s, L + 1.8, yy + 0.02, 7.8, 0.3, lab, size=12.5, bold=True)
    text(s, L + 1.8, yy + 0.3, 7.9, 0.3, how, size=9.5, color=CAPTION)
    box(s, L + CW - 1.5, yy + 0.08, 1.5, 0.38, fill=SURFACE, line=BORDER, r=0.19)
    text(s, L + CW - 1.5, yy + 0.08, 1.5, 0.38, owner, size=10, bold=True, color=MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
foot(s, "실제 경로 = 고객 문장 → 결정 단위(gemma4:12b) → 규정 질문일 때만 규정 검색 → 문턱 0.55. 문장 2,340개 · 1회 · AI 합성과 공개 대화 자료. 규정만 따로 잰 22~37%는 결정 단위가 거르는 단계를 뺀 값이었습니다.")
notes(s, "이번 주에 고친 것이 넷입니다. 번역 금액 단위 대조, 사람 검수로 찾은 문구 모순, 빈 답이 제품에서는 이미 막혀 있다는 확인, 그리고 오응답을 실제 제품 경로로 잰 것입니다. 실제 경로에서 규정 오응답은 0.4%로 낮았고, 앞서 규정 검색만 따로 잰 높은 값은 앞 단계가 거르는 것을 빼고 잰 값이었습니다. 대신 진짜 문제 둘이 드러났습니다. 일정과 무관한 말에 일정 항목을 짚는 것이 5.3%이고, 「바꿔줘요?」 같은 말투의 규정 질문 26%를 규정 질문으로 못 알아봅니다. 파인튜닝한 모델은 10월 7일에 x600 서버의 서비스에 연결됐고, 웹 채팅 끝까지 확인하는 것과 재순위 · 검증 단계 반영이 남았습니다.")

# ================================================================ 15 다음 주
s = new()
pic(s, SCENE / "tripilot-home-03-journey.png", 0, 0, w=13.333)
pic(s, A / "veil_full.png", 0, 0, w=13.333)
head(s, "NEXT WEEK", "다음 주에는 무관한 말 오지목과 규정 질문 놓침을 줄이고 제품에 반영합니다")
pairs = [("무관한 말에 일정 항목 5.3%", "잡담 · 범위 밖을 「없음」으로 넣어 다시 가르치기 · 일정 변경은 확인 질문  ·  RAG"),
         ("규정 질문 놓침 26%", "요청 말투 규정 질문 예시 추가 · 검증 단계(정밀도 87.6%) 반영  ·  RAG · cs"),
         ("모델로 거르기 아직 효과 없음", "교차 인코더 이어 학습 76.5% — 12B 재순위 92.6% 를 못 넘음 · 다른 방식 시험  ·  RAG"),
         ("재순위 · 검증 단계 반영 전", "재순위 · 검증 단계를 제품에 넣고 웹 채팅 끝까지 확인  ·  cs"),
         ("모델 순위 · 사용자 흐름 미정", "시드 3 · 4 · jevify · Plumb 학습 대기열(약 15시간) · 실제 사용자 흐름 확인  ·  RAG · cs")]
text(s, L, 1.75, 5, 0.3, "지금 막힌 것", size=11, bold=True, color=MUTED, spacing=1)
text(s, L + 5.6, 1.75, 6, 0.3, "다음 주에 할 것", size=11, bold=True, color=PRIMARY, spacing=1)
for k, (a_, b_) in enumerate(pairs):
    yy = 2.15 + k * 0.92
    box(s, L, yy, 5.0, 0.72, fill=SURFACE, line=BORDER, r=0.2)
    text(s, L + 0.25, yy, 4.6, 0.72, a_, size=13, color=TEXT, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 5.05, yy, 0.5, 0.72, "→", size=18, bold=True, color=PRIMARY, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    box(s, L + 5.6, yy, 6.23, 0.72, fill=PRIMARY, line=None, r=0.2)
    text(s, L + 5.85, yy, 5.8, 0.72, b_, size=13, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
notes(s, "다음 주에는 실제 경로에서 드러난 두 문제, 무관한 말에 일정 항목을 짚는 것과 요청 말투의 규정 질문을 놓치는 것을 줄이겠습니다. 검증 단계와 재순위도 제품에 넣고, 웹 채팅으로 끝까지 확인하겠습니다. 재순위 검색을 제품에 넣고, 엉뚱한 일정 변경 안전장치와 받아쓰기 오독을 마무리하고, 실서버에서 실제 사용자 흐름까지 확인합니다. 다른 모델의 D 시험과 시드 반복, 다른 Jev 계열 후보 비교도 이어서 합니다. 감사합니다.")

CH = None
# ================================================================ 16 부록
s = new("APPENDIX", "이 발표의 시험 · 자료 · 구성 이름", "팀이 붙인 이름만 모았습니다. 표준 기술 용어는 풀지 않았습니다.")
gl = [("mock 서버", "서버 응답 모양만 흉내 내는 시험용 대역 서버"), ("cs 프로젝트 서버", "고객 요청을 처리하는 triPilot 앱(api · worker · web · db)"),
      ("x600 서버", "cs 프로젝트 서버가 올라가 있는 팀 기계"), ("GPU 서버 A · B · C", "모델 학습 · 시험용으로 빌린 원격 GPU 기계"),
      ("항로 지킴이", "문제가 생기면 서비스가 먼저 바꿔 두고 알릴지 고르는 스위치"), ("Jev 계열 모델", "선택지 중 하나를 고르는 결정 전용 공개 모델 묶음(Winnow-E4B 등)"),
      ("Jev API(유료)", "같은 계열의 종량 과금 외부 결정 API"), ("시험 세트 mix8~12", "일정 항목 매칭 5묶음 835문제(AI 합성). mix8~11 Codex · mix12 Claude"),
      ("769문제", "835문제에서 복수 항목 질의 66문제를 뺀 주 지표 분모"), ("복수 항목 질의", "한 문장에 일정 항목 두 개를 묻는 질문"),
      ("B · C 채점", "B: 복수 항목 질의는 하나라도 맞으면 정답 · C: 낸 묶음이 정답 묶음과 같아야 정답"),
      ("E2E 파이프라인 테스트", "규칙 → ML 사전 필터 → 라우터 → 파인튜닝 E4B 를 문제마다 실제로 이어 부른 시험"),
      ("ML 사전 필터", "일정과 무관한 잡담을 먼저 거르는 작은 분류 모델"), ("혼합 트래픽 테스트", "일정 835 + 관광지 600 + 일상 대화 1,000 + 구어체 300 = 2,735문제"),
      ("블라인드 평가셋 B", "규정 문장을 보지 않고 따로 쓴 규정 질문 160문제(답 있는 48)"), ("CX 400", "고객 문장 분류 평가셋 400문장(Codex 작성 · Claude 교차 라벨)"),
      ("인덱싱 텍스트", "규정을 찾을 때 질문과 비교하는 글"), ("합성 문제", "사람이 아니라 AI 모델(Codex · Claude)이 쓴 시험 문장")]
half = (len(gl) + 1) // 2
for col in range(2):
    for j, (k, v) in enumerate(gl[col * half:(col + 1) * half]):
        xx = L + col * 6.07
        yy = 2.0 + j * 0.56
        if j:
            hline(s, xx, yy - 0.06, 5.76)
        text(s, xx, yy + 0.04, 2.0, 0.42, k, size=11.5, bold=True, color=PRIMARY)
        text(s, xx + 2.05, yy + 0.04, 3.7, 0.45, v, size=10.5, color=TEXT)
notes(s, "부록은 이 발표에서 팀이 붙인 이름을 모은 것입니다.")

prs.save(OUT)
(V3 / "[발표] triPilot_진행경과_2026-10-06_Claude_v4_대본.md").write_text(
    "# triPilot 5주차 스탠드업 v4 대본 (Claude 판)\n\n" + "\n\n".join(f"## {i + 1}장\n\n{t}" for i, t in enumerate(SCRIPT)) + "\n", encoding="utf-8")
print("saved", OUT)
