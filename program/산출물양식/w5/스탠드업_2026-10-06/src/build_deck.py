"""5주차(2026-09-29 ~ 10-06) 스탠드업 발표 — Claude 판 빌더.

재료: ../_재료/주간_사실.md (확인된 숫자만). 그림 · 캡처는 w5 산출물 폴더의 것을 그대로 쓴다.
출력: ../[발표] triPilot_진행경과_2026-10-06_Claude.pptx  (덮어쓰기 전에 _backup/ 에 복사)
"""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
W5 = ROOT.parent
OUT = ROOT / "[발표] triPilot_진행경과_2026-10-06_Claude.pptx"
FIG_M = W5 / "멀티에이전트_테스트보고서" / "그림"
FIG_V = W5 / "벡터DB_GraphDB_결과서" / "그림"
CAP = W5 / "화면설계서" / "assets"

FONT = "맑은 고딕"
GREEN = RGBColor(0x2D, 0x5F, 0x48)
DEEP = RGBColor(0x1E, 0x3F, 0x31)
MINT = RGBColor(0xEE, 0xF4, 0xEF)
GOLD = RGBColor(0xC8, 0x91, 0x3A)
RED = RGBColor(0xB0, 0x3A, 0x2E)
INK = RGBColor(0x22, 0x2A, 0x26)
MUTED = RGBColor(0x5F, 0x6B, 0x64)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, runs, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=0):
    """runs: str 또는 [(글, {size,color,bold})...] 또는 줄 목록(list of list)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    lines = runs if isinstance(runs, list) and runs and isinstance(runs[0], list) else [runs]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if space:
            p.space_after = Pt(space)
        items = line if isinstance(line, list) else [(line, {})]
        if isinstance(line, str):
            items = [(line, {})]
        for t, o in items:
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.color.rgb = o.get("color", color)
    return tb


def box(slide, x, y, w, h, fill=MINT, line=None, round_=True):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    if round_:
        s.adjustments[0] = 0.08
    s.shadow.inherit = False
    return s


def picture(slide, path, x, y, w, h):
    """비율을 지키며 (x,y,w,h) 상자 안 가운데에 넣는다."""
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    return slide.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))


def title(slide, t, sub=None):
    text(slide, 0.6, 0.45, 12.1, 0.9, t, size=28, bold=True, color=DEEP)
    if sub:
        text(slide, 0.6, 1.3, 12.1, 0.45, sub, size=14, color=MUTED)


def stat(slide, x, y, w, h, big, label, how, color=GREEN, big_size=36):
    box(slide, x, y, w, h)
    text(slide, x + 0.25, y + 0.2, w - 0.5, 0.75, big, size=big_size, bold=True, color=color)
    text(slide, x + 0.25, y + 0.2 + big_size / 72 * 1.25, w - 0.5, 0.6, label, size=14, bold=True, color=INK)
    text(slide, x + 0.25, y + h - 0.62, w - 0.5, 0.5, how, size=10, color=MUTED)


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def dark(slide):
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = DEEP


# 1 표지 ---------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
dark(s)
text(s, 0.9, 1.6, 11.5, 0.6, "SKN32 Final 6팀 · A-COPilot", size=18, color=RGBColor(0xBF, 0xD8, 0xCB))
text(s, 0.9, 2.3, 11.5, 1.2, "triPilot 5주차 진행 경과", size=48, bold=True, color=WHITE)
text(s, 0.9, 3.6, 11.5, 0.8, "화면 · 서버 · 모델 · 산출물을 한 주 동안 함께 끌어올렸습니다", size=22, color=WHITE)
text(s, 0.9, 5.4, 11.5, 0.5, "2026.09.29 ~ 10.06   ·   작업 브랜치 커밋 402건 (팀원 브랜치 포함 531건)", size=16, color=RGBColor(0xBF, 0xD8, 0xCB))
text(s, 0.9, 5.9, 11.5, 0.4, "커밋 수: git log, 2026-09-29 ~ 10-06", size=10, color=RGBColor(0x9F, 0xB8, 0xAB))
notes(s, "5주차 진행 경과입니다. 9월 29일부터 10월 6일까지 화면, 서버, 모델, 산출물 네 갈래를 함께 진행했고, 작업 브랜치 기준 커밋은 402건입니다.")

# 2 한 주 요약 ----------------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "네 갈래 모두 숫자로 확인할 수 있는 결과를 냈습니다")
cards = [
    ("12개", "고객 웹 화면 연결", "계획 올리기부터 여행 끝까지. mock 서버 시험으로 화면 반응 확인", GREEN),
    ("99.9%", "자동 시험 통과", "4,245/4,251, 2026-10-06. 실제 모델 시험 238개 제외", GREEN),
    ("750~760", "가르친 4B 모델 정답 /769", "가르치기 전 688. 시드 2개, 합성 시험 문제", GREEN),
    ("5종", "산출물 작성", "5주차 4종 + 6주차 서비스 테스트 보고서 1종", GOLD),
]
for i, (big, lab, how, c) in enumerate(cards):
    stat(s, 0.6 + i * 3.1, 2.0, 2.85, 3.0, big, lab, how, color=c, big_size=40)
text(s, 0.6, 5.5, 12.1, 0.9, [[("다만 시험 문제는 모두 모델이 쓴 합성이고, 사람 평가는 아직 0건입니다. ", {"bold": True}), ("남은 문제는 9장에 숫자로 정리했습니다.", {})]], size=16)
notes(s, "한 주 요약입니다. 화면 12개를 연결했고, 자동 시험은 99.9% 통과, 우리 데이터로 가르친 4B 모델은 769문제 중 750에서 760개를 맞혔고, 산출물은 다섯 종을 만들었습니다. 다만 시험 문제가 모두 합성이고 사람 평가는 아직 없습니다.")

# 3 웹 화면 -------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "고객이 계획을 올리고 여행 끝까지 쓰는 화면이 cs 프로젝트 서버에 붙었습니다")
shots = [(CAP / "capture_docs" / "04_trips_new_390.png", "계획 올리기"),
         (CAP / "capture_2026-10-06" / "card_390.png", "항로 지킴이 카드"),
         (CAP / "capture_docs" / "09_trip_home_390.png", "여행 화면(일정 · 지도 · 채팅)")]
for i, (p, cap) in enumerate(shots):
    picture(s, p, 0.6 + i * 2.75, 1.65, 2.55, 4.85)
    text(s, 0.6 + i * 2.75, 6.55, 2.55, 0.35, cap, size=12, bold=True, align=PP_ALIGN.CENTER)
box(s, 9.05, 1.65, 3.7, 4.85)
text(s, 9.3, 1.85, 3.3, 4.5, [
    [("이번 주에 붙인 것", {"bold": True, "size": 16, "color": DEEP})],
    [("계획 확인 화면 개편", {"bold": True})], [("날짜 칩 · 시간 끌기 · 지도 경로선", {"color": MUTED})],
    [("약관 동의", {"bold": True})], [("필수 2 · 선택 3", {"color": MUTED})],
    [("로그인", {"bold": True})], [("쿠키 로그인 · 구글 소셜 로그인", {"color": MUTED})],
    [("알림 채널", {"bold": True})], [("디스코드 · 텔레그램 연결", {"color": MUTED})],
    [("여행 중", {"bold": True})], [("항로 지킴이 · 로딩 중 질문 · 재난 일정 정지", {"color": MUTED})],
], size=13, space=3)
text(s, 0.6, 6.95, 12.1, 0.35, "캡처는 모두 mock 서버 화면. 실서버 확인은 계획 확인 화면의 읽기 · 수정 · 등록만 했고(2026-10-03), 그 뒤 바뀐 화면은 아직 안 했습니다.", size=10, color=MUTED)
notes(s, "웹 화면입니다. 고객이 계획을 올리고, 확인하고, 여행 내내 쓰는 화면 12개를 서버에 붙였습니다. 이번 주에는 계획 확인 화면 개편, 약관 동의, 소셜 로그인, 디스코드와 텔레그램 연결, 항로 지킴이와 재난 일정 정지를 넣었습니다. 캡처는 mock 서버 화면이고, 바뀐 화면의 실서버 확인은 다음 주 일입니다.")

# 4 서버 기능 -----------------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "개인 AI 입구와 실시간 진행이 생겼고, 시험은 모두 통과했습니다")
cards = [
    ("15/15", "개인 AI 입구(MCP)", "읽기 도구 5 · 쓰기 7(쓰기 기본 꺼짐), 본인 여행만. 2026-10-02"),
    ("21/21", "실시간 진행(SSE)", "채팅 · 일정 짜기 · 접수 읽기를 단계별로 보여 줌. 2026-10-02"),
    ("10/10", "팀 재배분", "받는 팀이 없으면 등록된 팀 중 한 번만 다시 고름. mock 서버 시험, 2026-10-06"),
    ("517/517", "요식 에이전트 시험", "팀원 정세환. 단위 · 통합 · 시나리오 · e2e, 2026-10-06"),
]
for i, (big, lab, how) in enumerate(cards):
    x = 0.6 + (i % 2) * 6.15
    y = 1.75 + (i // 2) * 2.45
    stat(s, x, y, 5.9, 2.2, big, lab, how, big_size=34)
text(s, 0.6, 6.75, 12.1, 0.5, "여행 삭제 · 디스코드 연결 · 텔레그램 연결은 cs 프로젝트 서버 코드에 들어갔지만, x600 서버 반영과 실제 연결은 아직 확인하지 않았습니다.", size=12, color=MUTED)
notes(s, "서버 쪽입니다. 개인 AI가 MCP로 자기 여행을 조회하는 입구를 만들어 15개 시험을 통과했고, 오래 걸리는 일은 실시간으로 진행 상황을 보여 주게 해 21개 시험을 통과했습니다. 팀을 잘못 고르면 한 번 더 고르는 재배분도 넣었습니다. 디스코드와 텔레그램 연결은 코드는 들어갔지만 x600 서버에서의 실제 연결은 아직 확인 전입니다.")

# 5 모델 -----------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "작은 4B 모델을 우리 데이터로 가르치니 26B · 27B 로컬 모델을 넘었습니다")
picture(s, FIG_M / "모델별_769_비교.png", 0.5, 1.55, 7.6, 5.4)
stat(s, 8.4, 1.6, 4.35, 1.75, "688 → 750~760", "가르친 Gemma 4 E4B /769", "같은 평가 틀, 가르치기 전 대비 69 : 7, p=6.4e-14. 시드 2개", big_size=28)
stat(s, 8.4, 3.5, 4.35, 1.75, "732 · 749", "Gemma 26B · Qwen3.8 27B /769", "학습 없는 큰 로컬 모델, 같은 769문제", color=GOLD, big_size=28)
stat(s, 8.4, 5.4, 4.35, 1.55, "4.55초", "CPU 코어 4개로 후속 질문", "GGUF Q8 약 7.5GB, 평균. 새 일정 첫 질문은 67.5초", big_size=26)
text(s, 0.6, 7.0, 12.1, 0.35, "769문제 = mix8~12 에서 「요청 둘」 66문제 제외, 모델이 쓴 합성 문제. 가르친 Winnow-E4B(Jev 계열) 756 은 시드 1개라 E4B 와 순위를 가리지 못합니다.", size=10, color=MUTED)
notes(s, "모델입니다. 고객 말 하나를 일정 항목 하나로 짚는 과제에서, 4B 크기의 Gemma 4 E4B를 우리 데이터로 가르쳤더니 688개에서 750~760개로 올랐습니다. 학습 없는 26B와 27B 모델보다 높습니다. CPU만으로도 후속 질문은 4.5초 정도입니다. 다만 같은 방법으로 가르친 Jev 계열 Winnow-E4B와의 순위는 시드를 더 돌려야 가릴 수 있습니다.")

# 6 한 줄로 이은 시험 --------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "단계를 많이 잇는다고 좋아지지는 않았고, 앞단은 잡담을 거를 때 값을 했습니다")
picture(s, FIG_M / "한줄연결_시험.png", 0.5, 1.55, 7.6, 4.6)
stat(s, 8.4, 1.6, 4.35, 1.7, "745 / 769", "규칙 + ML 거름 → 가르친 E4B", "단독 748 과 구분 안 됨(p=0.51), 모델 호출 19% 감소", big_size=28)
stat(s, 8.4, 3.45, 4.35, 1.7, "697 / 769", "학습 없는 Jev 계열 판정을 넣으면", "Winnow-E4B(학습 없음) 대 가르친 모델이라 공정한 비교 아님", color=RED, big_size=28)
stat(s, 8.4, 5.3, 4.35, 1.65, "90.8% → 91.9%", "잡담이 섞인 2,735문제", "규칙 → ML 앞단을 붙였을 때, 37 : 8, p=1.5e-5", big_size=26)
text(s, 0.6, 6.4, 7.5, 0.9, "규칙 → ML 판별기 → Jev 계열 분류 → 전문가를 문제마다 실제로 불러 끝까지 이었습니다(GPU 서버 C, 2026-10-06). 여러 분야 전문가를 고르는 전체 구성은 아직입니다.", size=12, color=MUTED)
notes(s, "모델 조합입니다. 규칙, ML, Jev 계열 분류, 전문가를 실제로 한 줄로 이어 돌려 봤습니다. 규칙과 ML 거름은 점수는 같고 호출을 19% 줄였습니다. 학습 없는 Jev 계열 모델을 보낼 곳 판정에 넣으면 점수가 떨어졌지만, 가르친 모델과 학습 조건이 달라 공정한 비교는 아닙니다. 잡담이 많이 섞인 흐름에서는 앞단이 확실히 이득이었습니다.")

# 7 분류 · 규정 검색 ----------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "고객 말 분류는 학습으로, 규정 검색은 색인 개선으로 올랐습니다")
stat(s, 0.6, 1.7, 4.2, 2.3, "60.9% → 88.4%", "긴급도 분류 정확도", "학습 없는 E4B → 우리 데이터로 학습한 분류기(e5-base), CX 400 문제", big_size=30)
stat(s, 0.6, 4.2, 4.2, 2.3, "21 → 31 /48", "규정 질문에 정답 규정을 보임", "색인 글을 고객용 문장으로 바꿨을 때, 독립 질문 48개, 2026-10-06", big_size=30)
picture(s, FIG_V / "정책검색_재현율.png", 5.1, 1.7, 7.6, 3.4)
box(s, 5.1, 5.3, 7.6, 1.2, fill=RGBColor(0xFB, 0xEE, 0xE9))
text(s, 5.35, 5.45, 7.2, 1.0, [[("대가도 있습니다. ", {"bold": True, "color": RED}), ("규정이 아닌 여행 대화에 규정을 붙이는 비율이 22.3% → 36.7% 로 늘어, 운영 반영은 분류기 뒤에서 다시 재고 정합니다.", {})]], size=14)
text(s, 0.6, 6.75, 12.1, 0.5, "규정 문장은 모델이 쓰지 않고 저장된 문장을 그대로 실어, 인용 정확도 334/334. 질문은 모두 모델이 쓴 합성입니다.", size=11, color=MUTED)
notes(s, "분류와 규정 검색입니다. 긴급도 분류는 학습 없는 모델 60.9%에서 우리 데이터로 학습한 분류기 88.4%로 올랐습니다. 규정 검색은 색인 글을 고객용 문장으로 바꾸면 정답을 보이는 질문이 21개에서 31개로 늘지만, 규정이 아닌 말에 규정을 붙이는 일도 늘어 운영 반영은 다시 재고 정합니다.")

# 8 산출물 -------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "5주차 산출물 4종과 6주차 보고서 1종을 만들어 교차 검증했습니다")
docs = [("벡터DB · GraphDB\n구축 결과서", "23쪽", "검색 성능 · 저장소별 쓰임"),
        ("멀티 에이전트 테스트\n계획 및 결과 보고서", "50쪽", "파인튜닝 · 한 줄 시험 · C 채점"),
        ("요구사항 정의서\n(업데이트)", "85개 요구", "구현 끝 24 · 일부 58 · 결정 대기 3"),
        ("화면설계서", "25쪽", "화면 12개 · 흐름 · 서버 연결"),
        ("서비스 테스트 계획\n및 결과 보고서\n(6주차)", "10쪽", "Pass/Fail · 이슈 대장")]
for i, (n, big, how) in enumerate(docs):
    x = 0.6 + i * 2.48
    box(s, x, 1.9, 2.3, 3.6, fill=MINT if i < 4 else RGBColor(0xF6, 0xEA, 0xD4))
    text(s, x + 0.2, 2.1, 1.9, 1.0, n, size=14, bold=True, color=DEEP)
    text(s, x + 0.2, 3.3, 1.9, 0.8, big, size=28, bold=True, color=GREEN if i < 4 else GOLD)
    text(s, x + 0.2, 4.3, 1.9, 1.0, how, size=11, color=MUTED)
text(s, 0.6, 5.9, 12.1, 0.8, "모든 문서를 코덱스와 교차 검증해 지적을 반영했고, Jev 계열 모델 표기 · 서버 이름 · 공정성 표시 규칙을 기계 검사로 확인했습니다.", size=14)
notes(s, "산출물입니다. 5주차 네 종과 6주차 서비스 테스트 보고서를 만들었고, 모두 코덱스와 교차 검증해 지적을 반영했습니다.")

# 9 남은 문제 -----------------------------------------------------------
s = prs.slides.add_slide(BLANK)
title(s, "남은 문제도 숫자로 드러나 있습니다")
issues = [("0건", "사람 평가", "평가 시트 35행만 준비, 시험 문제는 모두 합성"),
          ("0.625", "규정 검색 상위 3개 정답 비율", "목표 0.90 미달, 독립 질문 30/48"),
          ("3.1%", "일정 항목 짚기 빈 답", "85/2,735, 같은 85건이 반복, 원인 미확인"),
          ("1/172", "엉뚱한 대상을 바꾼 결정", "목표 0건"),
          ("1건", "번역 금액 단위 변조 통과", "일본어 원 → 엔, 숫자만 대조하는 보호 장치"),
          ("3.4%", "계획 읽기 값 변조", "12/350, 원문에 없는 제목 · 예약번호")]
for i, (big, lab, how) in enumerate(issues):
    x = 0.6 + (i % 3) * 4.1
    y = 1.6 + (i // 3) * 2.6
    stat(s, x, y, 3.85, 2.35, big, lab, how, color=RED, big_size=34)
notes(s, "남은 문제입니다. 사람 평가가 아직 없고, 규정 검색은 목표에 못 미치며, 일정 짚기의 빈 답 3.1%, 엉뚱한 대상 변경 1건, 번역 금액 단위 1건, 계획 읽기 값 변조 3.4%가 남아 있습니다.")

# 10 다음 주 ------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
dark(s)
text(s, 0.9, 0.8, 11.5, 1.0, "다음 주에는 실서버 확인과 사람 평가로 합성 점수의 빈칸을 메웁니다", size=30, bold=True, color=WHITE)
nexts = ["바뀐 화면을 x600 서버의 cs 프로젝트 서버에서 실제로 확인",
         "사람 평가 진행(평가 시트 35행)",
         "가르친 모델 제품 연결 검토, 시드 3개 이상으로 모델 순위 확인",
         "규정 색인 개선을 분류기 뒤에서 다시 재고 운영 반영 결정",
         "다른 Jev 계열 후보 3종을 같은 방법으로 가르쳐 비교(GPU 서버 B)"]
for i, t in enumerate(nexts):
    y = 2.3 + i * 0.85
    c = box(s, 0.9, y, 0.55, 0.55, fill=GREEN)
    text(s, 0.9, y + 0.08, 0.55, 0.4, str(i + 1), size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    text(s, 1.7, y + 0.06, 10.5, 0.5, t, size=18, color=WHITE)
notes(s, "다음 주에는 바뀐 화면의 실서버 확인, 사람 평가, 가르친 모델의 제품 연결 검토와 시드 추가, 규정 색인 개선 재측정, 다른 Jev 계열 후보 비교를 하겠습니다. 감사합니다.")

if OUT.exists():
    bk = ROOT / "_backup" / (datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + "_" + OUT.stem)
    bk.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT, bk / OUT.name)
prs.save(OUT)
print("saved", OUT)
