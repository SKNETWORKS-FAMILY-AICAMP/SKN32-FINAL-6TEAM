# -*- coding: utf-8 -*-
"""진행 공유 PPT(2026-09-28) — CI/CD · 유스케이스 · 변경 흐름 · 공통 플로우 · 화면 목업.

    python build_진행공유_2026-09-28.py

★양식은 09-11 진행경과 PPT(배경·제목 서식)를 따른다. 그 판의 「Team Architecture」 딱지 그림은
  쓰지 않는다 — 장마다 자기 딱지를 그린다.
★출력은 새 이름(`-v2`). 같은 이름이 있으면 멈춘다(덮어쓰지 않는다).
★내용 근거: `.github/workflows/ci-*.yml`·커밋 53184c94·ce1f288c, `program/briefing/A-COP_유스케이스_2026-09-24.html`,
  `wiki/decisions/D-020-trip-survey-and-ask-first.md`, 코드 대조(2026-09-28), 팀 FigJam 보드 캡처, 09-23 목업 HTML 캡처.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
FORMS = HERE.parent
OUT = FORMS / "w4" / "[발표] triPilot_진행공유_2026-09-28-v2.pptx"
SRC = FORMS / "[발표] A-COP_진행경과_2026-09-11.pptx"
ASSETS = Path(sys.argv[1]) if len(sys.argv) > 1 else None   # 그림 폴더(FigJam 캡처 1.png · shots/)

if OUT.exists():
    raise SystemExit(f"[멈춤] 이미 있다 — 덮어쓰지 않는다: {OUT}")

INK = RGBColor(0x0F, 0x17, 0x2A)
MUTE = RGBColor(0x47, 0x55, 0x69)
SOFT = RGBColor(0x64, 0x74, 0x8B)
LINE = RGBColor(0xE2, 0xE8, 0xF0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C = {"blue": (RGBColor(0x25, 0x63, 0xEB), RGBColor(0xDB, 0xEA, 0xFE)),
     "green": (RGBColor(0x05, 0x96, 0x69), RGBColor(0xDC, 0xFC, 0xE7)),
     "amber": (RGBColor(0xB4, 0x53, 0x09), RGBColor(0xFE, 0xF3, 0xC7)),
     "violet": (RGBColor(0x6D, 0x28, 0xD9), RGBColor(0xED, 0xE9, 0xFE)),
     "slate": (RGBColor(0x47, 0x55, 0x69), RGBColor(0xF1, 0xF5, 0xF9)),
     "red": (RGBColor(0xB9, 0x1C, 0x1C), RGBColor(0xFE, 0xE2, 0xE2))}
FONT = "Pretendard"

src = Presentation(str(SRC))
BG_COVER = [s for s in src.slides[0].shapes if s.shape_type == 13][0].image.blob
BG = [s for s in src.slides[4].shapes if s.shape_type == 13][0].image.blob
p = Presentation()
p.slide_width, p.slide_height = src.slide_width, src.slide_height
BLANK = p.slide_layouts[6]


# ── 부품 ─────────────────────────────────────────────────────────
def text(s, x, y, w, h, lines, size=12, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    b = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = b.text_frame
    tf.word_wrap, tf.vertical_anchor = True, anchor
    tf.margin_left = tf.margin_right = Inches(0.02)
    for i, line in enumerate([lines] if isinstance(lines, str) else lines):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        spec = line if isinstance(line, tuple) else (line, size, bold, color)
        r = para.add_run()
        r.text = spec[0]
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(spec[1]), spec[2], spec[3], FONT
        para.space_after = Pt(3)
    return b


def card(s, x, y, w, h, title, body=None, tone="slate", title_size=13, body_size=10.5, align=PP_ALIGN.LEFT,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE, bar=True):
    fg, bg = C[tone]
    b = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid()
    b.fill.fore_color.rgb = bg
    b.line.color.rgb = LINE
    b.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        b.adjustments[0] = 0.08
    if bar:
        a = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 0.12), Inches(y + 0.14), Inches(0.06), Inches(0.3))
        a.fill.solid()
        a.fill.fore_color.rgb = fg
        a.line.fill.background()
    pad = 0.28 if bar and align == PP_ALIGN.LEFT else 0.12
    lines = [(title, title_size, True, fg if bar else INK)]
    for line in body or []:
        lines.append((line, body_size, False, MUTE))
    text(s, x + pad, y + 0.1, w - pad - 0.1, h - 0.15, lines, align=align,
         anchor=MSO_ANCHOR.TOP if body else MSO_ANCHOR.MIDDLE)
    return b


def pill(s, x, y, label, tone="blue", w=None):
    fg, bg = C[tone]
    w = w or 0.2 + 0.11 * len(label)
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.3))
    b.adjustments[0] = 0.5
    b.fill.solid()
    b.fill.fore_color.rgb = bg
    b.line.fill.background()
    b.shadow.inherit = False
    tf = b.text_frame
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    r = tf.paragraphs[0].add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(10), True, fg, FONT
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    return b


def arrow(s, x1, y1, x2, y2, color=RGBColor(0x94, 0xA3, 0xB8)):
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    ln.line.color.rgb = color
    ln.line.width = Pt(2)
    ln.line._get_or_add_ln().append(_arrow_head())
    return ln


def _arrow_head():
    from pptx.oxml.ns import qn
    from lxml import etree
    tail = etree.SubElement(etree.Element(qn("a:ln")), qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    return tail


def page(title, badge, tone="blue", num=None):
    s = p.slides.add_slide(BLANK)
    s.shapes.add_picture(io.BytesIO(BG), 0, 0, p.slide_width, p.slide_height)
    text(s, 0.46, 0.3, 11.2, 0.5, title, 21, True)
    ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.46), Inches(0.88), Inches(12.42), Inches(0.012))
    ln.fill.solid()
    ln.fill.fore_color.rgb = LINE
    ln.line.fill.background()
    pill(s, 12.88 - (0.2 + 0.11 * len(badge)), 0.4, badge, tone)
    if num:
        text(s, 12.2, 7.05, 0.7, 0.3, f"{num}", 9, False, SOFT, PP_ALIGN.RIGHT)
    return s


def kpi(s, x, y, w, value, label, tone):
    fg, bg = C[tone]
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(1.05))
    b.adjustments[0] = 0.1
    b.fill.solid()
    b.fill.fore_color.rgb = WHITE
    b.line.color.rgb = LINE
    b.shadow.inherit = False
    text(s, x + 0.15, y + 0.08, w - 0.3, 0.55, value, 24, True, fg)
    text(s, x + 0.15, y + 0.6, w - 0.3, 0.4, label, 9.5, False, MUTE)


# ── 1 표지 ────────────────────────────────────────────────────────
s = p.slides.add_slide(BLANK)
s.shapes.add_picture(io.BytesIO(BG_COVER), 0, 0, p.slide_width, p.slide_height)
pill(s, 0.46, 1.75, "PROGRESS · 2026. 9. 28.", "blue", 2.6)
text(s, 0.46, 2.2, 12, 0.9, "triPilot 진행 공유", 40, True)
text(s, 0.46, 3.05, 12, 0.5, "팀 A-COPilot · 여행 전체를 끝까지 관리하는 Headless Agentic CS 플랫폼", 15, False,
     RGBColor(0x33, 0x41, 0x55))
agenda = [("01", "CI/CD", "합칠 때마다 자동 검사", "blue"), ("02", "유스케이스", "행위자·묶음·점검", "violet"),
          ("03", "변경 흐름", "감지와 요청은 가운데가 같다", "green"), ("04", "공통 플로우", "액티비티 & 요식업", "amber"),
          ("05", "화면 목업", "09-23 기준선 → 실제 연결", "slate")]
for i, (n, t, d, tone) in enumerate(agenda):
    x = 0.46 + i * 2.5
    card(s, x, 4.25, 2.3, 1.0, f"{n}  {t}", [d], tone, 14, 10.5)

# ── 2 CI/CD ──────────────────────────────────────────────────────
s = page("CI/CD: 합칠 때마다 자동 검사 — develop·main 두 관문", "CI/CD · GitHub Actions", "blue", 2)
text(s, 0.5, 1.05, 4, 0.3, "develop 관문 — 빠르게 도는 것만", 12.5, True)
steps = [("push / PR", "develop 브랜치", "slate"), ("ruff 린트", "버그 규칙 F·E9", "blue"),
         ("시험", "architecture · contract · unit", "blue"), ("PostgreSQL", "pgvector 컨테이너", "blue")]
for i, (t, d, tone) in enumerate(steps):
    card(s, 0.5 + i * 3.1, 1.4, 2.7, 0.85, t, [d], tone, 12, 10, PP_ALIGN.CENTER, bar=False)
    if i:
        arrow(s, 0.5 + i * 3.1 - 0.38, 1.82, 0.5 + i * 3.1 - 0.05, 1.82)
text(s, 0.5, 2.45, 4, 0.3, "main 관문 — 내보내기 전에 전부", 12.5, True)
steps = [("push / PR", "main 브랜치", "slate"), ("아키텍처 시험 먼저", "가장 싸고, 어기면 되돌리기 비싸다", "green"),
         ("전체 시험", "live 제외 · 데모 데이터 시드 후", "green"), ("Docker 빌드", "이미지 push 는 안 한다", "amber")]
for i, (t, d, tone) in enumerate(steps):
    card(s, 0.5 + i * 3.1, 2.8, 2.7, 0.85, t, [d], tone, 12, 10, PP_ALIGN.CENTER, bar=False)
    if i:
        arrow(s, 0.5 + i * 3.1 - 0.38, 3.22, 0.5 + i * 3.1 - 0.05, 3.22)
kpi(s, 0.5, 4.05, 2.9, "91건", "도입 때 걸린 린트 오류 정리(자동 74 · 수동 11)", "blue")
kpi(s, 3.55, 4.05, 2.9, "1,015 / 1,400", "깨끗한 환경 재현 통과 — develop / main(09-24)", "green")
kpi(s, 6.6, 4.05, 2.9, "0", "CI 에 넣은 실제 키·서버 주소(전부 시험용 가짜, LLM 은 mock)", "violet")
kpi(s, 9.65, 4.05, 3.2, "빌드까지", "CD 범위 — MVP 는 로컬 실행이라 자동 배포 대상 서버가 없다", "amber")
card(s, 0.5, 5.4, 6.1, 1.1, "정한 원칙", ["누가 올려도 공용 브랜치가 깨지지 않게 — 검사 실패 시 병합하지 않는다",
                                         "검사 범위는 이미 가진 시험(아키텍처·계약·단위·통합)을 그대로 건다"], "blue")
card(s, 6.75, 5.4, 6.1, 1.1, "CI 에서 빼고 로컬에서 도는 것", ["실제 LLM 시험(live) — 실제 키가 필요하다",
                                                           "RAG 통합 시험 — 정책 코퍼스 적재에 실제 임베딩이 필요하다"], "slate")

# ── 3 유스케이스 한눈에 ─────────────────────────────────────────
s = page("유스케이스: 여행자·개인 에이전트 27개 · 개발·운영팀 18개", "USE CASE · 2026-09-24 v2", "violet", 3)
card(s, 0.5, 1.1, 3.1, 3.55, "행위자", ["여행자 — 서울 자유여행 외국인, 최대 4인", "개인 에이전트 — REST · A2A",
                                        "시계 — 스케줄러 · 3분 감시", "외부 데이터 — 기상·대기·관광·교통·재난",
                                        "알림 채널 — 디스코드", "업체 — 지금은 Mock", "개발·운영팀 — 버그 대응"],
     "violet", 13, 10.5)
groups = [("A 여행 전", "설문 · 초안 · 등록 · 사용자 키", "blue"), ("B 매일 안내", "① 하루 시작 ② 다음 일정 ③ 이동", "blue"),
          ("C 시스템이 먼저", "변화 감지 · 적용 · 선택 요청 · 안전 알림", "blue"),
          ("D 여행자가 먼저", "조회 · 선택 · 신고 · 대안 · 되돌리기", "blue"), ("E 업체 예약", "MVP 다음 단계", "slate"),
          ("F 치명 결함 대응", "대체 소스로 · 그래도 안 되면 서버를 끈다", "green"),
          ("G 상시 실행 관리", "되잡기 · 3분 감시 · 바깥함 일꾼", "green"), ("H 검증", "시험 · 시나리오 측정", "green"),
          ("I 데이터·배포", "마이그레이션 · 시드 · CI", "green")]
for i, (t, d, tone) in enumerate(groups):
    card(s, 3.8 + (i % 3) * 3.05, 1.1 + (i // 3) * 1.2, 2.9, 1.05, t, [d], tone, 12.5, 9.5)
text(s, 0.5, 4.85, 6, 0.3, "하루 안내 — 알림 ①②③ (Case 를 만들지 않고 LLM 을 부르지 않는다)", 12, True)
flow = [("03:00", "조용히 정리", "새벽 식당 영업 확인", "slate"), ("08:00", "① 하루 시작", "오늘 일정 · 바뀐 일정 수", "blue"),
        ("일정 시작", "② 다음 일정", "지금 / 다음", "blue"), ("이동 시작", "③ 이동", "어디로 · 언제 · 어떻게", "green"),
        ("수시", "3분 감시", "변경 · 선택 요청 · 안전", "amber")]
for i, (tm, t, d, tone) in enumerate(flow):
    x = 0.5 + i * 2.5
    card(s, x, 5.25, 2.25, 1.15, f"{tm}  {t}", [d], tone, 11.5, 9.5)
    if i:
        arrow(s, x - 0.23, 5.82, x - 0.02, 5.82)
text(s, 0.5, 6.55, 12.3, 0.35, "판단은 여행자가 한다 — 사람(운영자)이 끼는 곳은 버그 대응뿐.  ③ 출발 시각 = 다음 일정 시작 − 이동 − 여유 10분.",
     10, False, SOFT)

# ── 4 유스케이스 점검 ───────────────────────────────────────────
s = page("유스케이스 점검: 설문 · 요식 호출 · 대안 선택 — 준비 5 / 10", "D-020 · 코드 대조 09-28", "violet", 4)
rows = [("설문 묶음 — 테마·구성·이동수단·내국인·우선순위1·2", "완료", "계약에 칸이 있다. 판정에는 안 쓰고 받기만 한다", "green"),
        ("13 실내·실외 · 14 세부 테마", "완료", "세부 선택지는 담당 팀이 정한다", "green"),
        ("15 꼬이면 — 바꿔줘 / 먼저 물어봐줘", "완료", "같은 판정 문 · 보류 제안 · 시험 18건", "green"),
        ("16 여유 → 밀도 0.40 / 0.55 / 0.70", "완료", "일정 생성기가 하루 곳 수를 재서 고른다", "green"),
        ("하루 08:00 ~ 22:00", "완료", "「절반 숙소 나감 10시」는 뜻이 아직 안 정해졌다", "green"),
        ("요식 — 새벽 3시 영업 확인 · 사용자 요청", "완료", "구글 무료 한도 예산을 건 채로 돈다", "green"),
        ("0 언어 · 3 기피 음식 · 12 종교", "부분", "언어는 여행 locale 로 받는다. 3·12 는 설문 계약에 칸이 없다", "amber"),
        ("밀도 초과 → 대안 1·2·3 보여 주고 선택", "부분", "선택 흐름은 있다. 밀도 초과를 계기로 거는 곳은 없다", "amber"),
        ("요식 — 방문 직전(가장 가까운 DB 판정값)", "없음", "새벽 판정값을 방문 직전에 다시 쓰는 곳이 없다", "red"),
        ("요식 — 웨이팅 20분 주기", "팀 몫", "요식업 팀이 방법을 고안 중(D-020)", "slate")]
tbl = s.shapes.add_table(len(rows) + 1, 3, Inches(0.5), Inches(1.1), Inches(12.35), Inches(5.6)).table
for j, (w, head) in enumerate(((5.1, "항목"), (1.1, "상태"), (6.15, "근거 · 비고"))):
    tbl.columns[j].width = Inches(w)
    cell = tbl.cell(0, j)
    cell.text = head
    cell.fill.solid()
    cell.fill.fore_color.rgb = INK
    r = cell.text_frame.paragraphs[0].runs[0]
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(11), True, WHITE, FONT
for i, (item, state, note, tone) in enumerate(rows, start=1):
    fg, bg = C[tone]
    for j, value in enumerate((item, state, note)):
        cell = tbl.cell(i, j)
        cell.text = value
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg if j == 1 else (WHITE if i % 2 else C["slate"][1])
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        para = cell.text_frame.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER if j == 1 else PP_ALIGN.LEFT
        r = para.runs[0]
        r.font.size, r.font.name = Pt(10.5), FONT
        r.font.bold = j == 1
        r.font.color.rgb = fg if j == 1 else (INK if j == 0 else MUTE)

# ── 5 변경 흐름 ─────────────────────────────────────────────────
s = page("변경 흐름: 「변경 감지」와 「사용자 요청」은 가운데가 같다", "USE CASE C · D", "green", 5)
card(s, 0.5, 1.5, 2.9, 1.0, "앞 ① 변경 감지", ["3분 감시가 기상·교통·재난·영업을 조회"], "blue", 12.5, 10)
card(s, 0.5, 3.3, 2.9, 1.0, "앞 ② 사용자 요청", ["문장 → Case → 분류 → 신고 뽑기"], "violet", 12.5, 10)
mid = [("대안 만들기", "같은 시각 근처 · 같은 종류"), ("같은 판정 문", "apply_or_ask / pending.decide"),
       ("새 판 쓰기", "itinerary_versions 에 쌓는다")]
for i, (t, d) in enumerate(mid):
    card(s, 4.0 + i * 2.35, 2.4, 2.1, 1.0, t, [d], "green", 12.5, 9.5)
    if i:
        arrow(s, 4.0 + i * 2.35 - 0.23, 2.9, 4.0 + i * 2.35 - 0.02, 2.9)
arrow(s, 3.42, 2.0, 3.98, 2.7)
arrow(s, 3.42, 3.8, 3.98, 3.1)
card(s, 11.0, 1.5, 1.85, 1.0, "끝 ① 알림", ["변경 통지 · 계획서 링크"], "blue", 12, 9.5)
card(s, 11.0, 3.3, 1.85, 1.0, "끝 ② 답", ["Case 종료 + 답 문장"], "violet", 12, 9.5)
arrow(s, 10.55, 2.7, 11.0, 2.0)
arrow(s, 10.55, 3.1, 11.0, 3.8)
card(s, 0.5, 4.85, 6.1, 1.15, "판정 문이 가르는 것 — 둘 다 같다",
     ["고정한 일정 → 묻는다 ·  먼저 물어봐줘 → 안 1·2·3 을 보여 주고 기다린다",
      "그 외 → 가장 좋은 안으로 바로 바꾸고 알린다"], "green")
card(s, 6.75, 4.85, 6.1, 1.15, "다른 점 둘",
     ["안전 알림만 보내는 갈래(먼저 물어봐줘 + 지진·재난·경보)는 감지 쪽에만 있다",
      "사용자가 직접 고른 교체·선택·되돌리기는 판정 문 없이 바로 적용한다"], "amber")

# ── 6 공통 플로우 ───────────────────────────────────────────────
s = page("공통 플로우: 액티비티 & 요식업 — CORE → Agent", "FLOW · 팀 FigJam", "amber", 6)
if ASSETS and (ASSETS / "1.png").exists():
    im = Image.open(ASSETS / "1.png").crop((128, 126, 1912, 842))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    s.shapes.add_picture(buf, Inches(0.46), Inches(1.05), Inches(12.42))
steps = [("CORE", "하루 시작·종료 → 변경 필요 판단", "blue"), ("CORE", "조건 이동 · 외부 API 조회", "blue"),
         ("Agent", "대체 장소 조회 → 1~3순위 후보", "violet"), ("Agent", "확인 필요 표시 → CORE 로 반영", "violet")]
for i, (t, d, tone) in enumerate(steps):
    card(s, 0.46 + i * 3.15, 6.2, 2.95, 0.8, t, [d], tone, 11, 9.5)

# ── 7 화면 목업 ─────────────────────────────────────────────────
s = page("화면 목업: 09-23 목업을 기준선으로 — 이제 실제 서버에 붙었다", "MOCKUP → LIVE", "slate", 7)
shots = [("m_tripilot-intro-animated-nav-switch.png", "인트로"), ("m_tripilot-mobile-onboarding.png", "온보딩 · 취향 설정"),
         ("m_tripilot-intake-wireframe.png", "계획 등록")]
for i, (f, cap) in enumerate(shots):
    x = 0.55 + i * 2.6
    path = ASSETS / "shots" / f if ASSETS else None
    if path and path.exists():
        pic = s.shapes.add_picture(str(path), Inches(x), Inches(1.1), height=Inches(5.05))
        pic.line.color.rgb = LINE
    pill(s, x, 6.3, cap, "slate", 2.3)
flow = [("온보딩", "언어 · 약관 · 취향 9문항", "slate"), ("계획 등록", "글 · 사진 · PDF · 워드 · 엑셀", "blue"),
        ("확인 화면", "원문 그대로 · 규칙 배치 · 조회 확인 · 확인 필요", "blue"),
        ("여행 화면", "일정 · 지도 · 채팅(실제 여행 상담)", "green"), ("일정 짜 줘", "조건 확인 → 생성기 → 판정 → 등록", "green")]
for i, (t, d, tone) in enumerate(flow):
    y = 1.1 + i * 1.02
    card(s, 8.55, y, 4.3, 0.85, t, [d], tone, 12, 9.5)
    if i:
        arrow(s, 10.7, y - 0.17, 10.7, y - 0.01)
text(s, 8.55, 6.25, 4.3, 0.5, "09-27~28 실제 연결 · 실제 모델로 브라우저에서 끝까지 확인(각 1회)", 9.5, False, SOFT)

# ── 8 다음 단계 ─────────────────────────────────────────────────
s = page("다음 단계", "NEXT", "blue", 8)
nxt = [("CI/CD", ["cs Dockerfile 을 만들면 main 관문이 그 이미지를 빌드", "배포 대상은 MVP 뒤에 정한다"], "blue"),
       ("유스케이스", ["방문 직전 판정값 재사용 · 밀도 초과 → 대안 1·2·3", "「절반 숙소 10시」 · 지연 때 70% 구간 처리 결정"], "violet"),
       ("공통 플로우", ["액티비티·요식업 대체 장소 우선순위를 코드와 대조", "웨이팅 수집 방법은 요식업 팀과 맞춘다"], "amber"),
       ("화면 · 평가", ["확인 화면 · 여행 화면 실제 연결 검수", "계획 읽기 평가셋 60건"], "green")]
for i, (t, body, tone) in enumerate(nxt):
    card(s, 0.5 + (i % 2) * 6.25, 1.3 + (i // 2) * 1.75, 6.05, 1.45, t, body, tone, 16, 12)

p.save(str(OUT))
print("저장:", OUT, len(p.slides), "장")
