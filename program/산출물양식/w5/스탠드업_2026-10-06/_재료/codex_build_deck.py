from pathlib import Path
from io import BytesIO
import os
import tempfile

from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement


ROOT = Path("C:/Users/playdata2/Documents/final_workspace")
BASE = ROOT / "program/산출물양식/w5"
OUTPUT = BASE / "스탠드업_2026-10-06/[발표] triPilot_진행경과_2026-10-06_Codex.pptx"
FACTS = BASE / "스탠드업_2026-10-06/_재료/주간_사실.md"

ASSETS = {
    "compare": BASE / "멀티에이전트_테스트보고서/그림/모델별_769_비교.png",
    "tuning": BASE / "멀티에이전트_테스트보고서/그림/파인튜닝_전후.png",
    "chain": BASE / "멀티에이전트_테스트보고서/그림/한줄연결_시험.png",
    "policy": BASE / "벡터DB_GraphDB_결과서/그림/정책검색_재현율.png",
    "card": BASE / "화면설계서/assets/capture_2026-10-06/card_390.png",
    "home": BASE / "화면설계서/assets/capture_docs/09_trip_home_390.png",
    "new": BASE / "화면설계서/assets/capture_docs/04_trips_new_390.png",
}

FONT = "맑은 고딕"
NAVY = "152C40"
GREEN = "2C614E"
BLUE = "286BA0"
AMBER = "A56A20"
RED = "AB403A"
INK = "203345"
MUTED = "586B79"
LIGHT = "F0F4F6"
WHITE = "FFFFFF"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
prs.core_properties.title = "guguroute 5주차 진행경과"
prs.core_properties.subject = "2026-09-29 ~ 2026-10-06 스탠드업"
prs.core_properties.author = "guguroute"
prs.core_properties.language = "ko-KR"

SCRIPT_NOTES = []


def color(value):
    return RGBColor.from_string(value)


def rect(slide, x, y, w, h, fill, border=None):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color(fill)
    if border:
        shape.line.color.rgb = color(border)
    else:
        shape.line.fill.background()
    return shape


def text(slide, value, x, y, w, h, size=18, bold=False,
         fill=INK, align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP):
    shape = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)
    frame.vertical_anchor = valign
    for index, line in enumerate(value.split("\n")):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.alignment = align
        p.space_before = Pt(0)
        p.space_after = Pt(5)
        p.line_spacing = 1.12
        pPr = p._p.get_or_add_pPr()
        for tag in ("a:buChar", "a:buAutoNum", "a:buBlip", "a:buNone"):
            for element in list(pPr.findall(tag, pPr.nsmap)):
                pPr.remove(element)
        pPr.append(OxmlElement("a:buNone"))
        run = p.add_run()
        run.text = line
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color(fill)
        rPr = run._r.get_or_add_rPr()
        rPr.set("lang", "ko-KR")
        for tag in ("a:latin", "a:ea", "a:cs"):
            element = rPr.find(tag, rPr.nsmap)
            if element is None:
                element = OxmlElement(tag)
                rPr.append(element)
            element.set("typeface", FONT)
    return shape


def slide(title, notes, dark=False):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = color(NAVY if dark else WHITE)
    text(s, title, 0.55, 0.38, 12.15, 0.85, 28, True,
         WHITE if dark else NAVY)
    text(s, "guguroute  ·  5주차  ·  2026-10-06",
         0.58, 7.11, 10.6, 0.22, 9, fill="CBD7DE" if dark else MUTED)
    text(s, str(len(prs.slides)), 12.1, 7.07, 0.65, 0.3, 10,
         fill="CBD7DE" if dark else MUTED, align=PP_ALIGN.RIGHT)
    SCRIPT_NOTES.append((s, notes))
    return s


def metric(s, value, label, source, x, y, w, h,
           accent=GREEN, dark=False, value_size=45):
    rect(s, x, y, w, h, "203E52" if dark else LIGHT)
    text(s, label, x + 0.2, y + 0.18, w - 0.4, 0.6,
         18, True, WHITE if dark else INK)
    text(s, value, x + 0.2, y + 0.85, w - 0.4, 0.95,
         value_size, True, WHITE if dark else accent)
    text(s, source, x + 0.2, y + 1.83, w - 0.4, h - 1.94,
         9, fill="D4E1E8" if dark else MUTED)


def picture(s, path, x, y, w, h, region=None):
    """높이에 먼저 맞춘 뒤 너비가 넘치면 축소한다. 원본 픽셀 비율을 유지한다."""
    absolute_path = Path(path).resolve()
    with Image.open(absolute_path) as im:
        iw, ih = im.size
    if region is None:
        left, top, right, bottom = 0, 0, iw, ih
    else:
        left, top, right, bottom = region
        if not (0 <= left < right <= iw and 0 <= top < bottom <= ih):
            raise ValueError(f"잘못된 그림 표시 영역: {absolute_path}")
    rw, rh = right - left, bottom - top
    scale = min(h / rh, w / rw)
    dw, dh = rw * scale, rh * scale
    px, py = x + (w - dw) / 2, y + (h - dh) / 2
    pic = s.shapes.add_picture(
        str(absolute_path), Inches(px), Inches(py),
        width=Inches(dw), height=Inches(dh)
    )
    if region:
        pic.crop_left = left / iw
        pic.crop_top = top / ih
        pic.crop_right = (iw - right) / iw
        pic.crop_bottom = (ih - bottom) / ih
    return pic


def source(s, value, x=0.6, y=6.65, w=12.1):
    text(s, value, x, y, w, 0.39, 9, fill=MUTED)


def model_band(s, region, y):
    picture(s, ASSETS["compare"], 0.65, y, 11.95, 0.52, region)


def build():
    s = slide(
        "화면과 검증을 늘렸고, 제품 연결은 다음 주에 확인한다",
        "5주차에는 자유여행자의 계획 접수부터 여행 중 이용까지 화면과 기능을 확장했습니다. "
        "작은 모델 학습과 규정 검색도 검증했지만, 바뀐 화면의 실제 응답과 가르친 모델의 제품 연결은 남아 있습니다.",
        dark=True
    )
    text(s, "guguroute", 0.6, 1.55, 11.8, 0.9, 54, True, WHITE)
    text(s, "5주차 진행경과\n2026-09-29 ~ 2026-10-06",
         0.65, 2.62, 11.8, 0.9, 23, fill="D8E5ED")
    metric(s, "402건", "작업 브랜치 커밋",
           "role-manager · git log\n2026-09-29 ~ 10-06",
           0.65, 3.78, 5.87, 2.7, dark=True)
    metric(s, "531건", "모든 브랜치 커밋",
           "팀원 커밋 포함 · git log\n2026-09-29 ~ 10-06",
           6.77, 3.78, 5.87, 2.7, dark=True)

    s = slide(
        "화면 구현과 자동 시험은 늘었고, 사람 평가는 아직 없다",
        "웹 화면을 cs 프로젝트 서버에 붙였고 cs 프로젝트 전체 자동 시험은 4,245개가 통과했습니다. "
        "모델 시험 문제는 모두 합성이며 사람 평가는 아직 없으므로, 높은 시험 성적을 실제 사용 성능으로 단정하지 않겠습니다."
    )
    metric(s, "12개", "웹 화면 구현",
           "화면설계서 5주차 · 2026-10-06 기준\ncs 프로젝트 서버 연결 · 캡처는 mock 서버",
           0.65, 1.55, 3.85, 4.8)
    metric(s, "99.9%", "cs 프로젝트 자동 시험",
           "4,245 / 4,251 · 2026-10-06 18:09\n실제 모델 시험 238개 제외",
           4.74, 1.55, 3.85, 4.8, accent=BLUE)
    metric(s, "0건", "사람 평가",
           "2026-10-06 기준 · 평가 시트 35행 준비\n모델 시험 문제는 전부 합성",
           8.83, 1.55, 3.85, 4.8, accent=AMBER)
    source(s, "구현, 자동 시험, 사람 평가는 서로 다른 확인 범위다.")

    s = slide(
        "자유여행자의 계획 접수부터 여행 중 이용까지 화면을 붙였다",
        "계획 올리기, 항로 지킴이 카드, 여행 화면을 포함해 화면 12개를 cs 프로젝트 서버에 붙였습니다. "
        "여기 보이는 캡처는 모두 mock 서버 화면이며, 실제 응답은 10월 3일 계획 확인 화면의 읽기·결과·수정·등록만 확인했습니다. "
        "그 뒤 바뀐 화면은 실제 응답을 다시 확인해야 합니다."
    )
    for key, x, label in (
        ("new", 0.7, "계획 올리기"),
        ("card", 4.92, "항로 지킴이 카드"),
        ("home", 9.14, "여행 중 이용"),
    ):
        rect(s, x, 1.45, 3.48, 4.98, LIGHT)
        picture(s, ASSETS[key], x + 0.12, 1.5, 3.24, 4.65)
        text(s, label + " · mock 서버 화면",
             x, 6.2, 3.48, 0.35, 11, align=PP_ALIGN.CENTER)
    source(s, "실제 응답 확인: 계획 확인의 읽기·결과·수정·등록만 · 2026-10-03. 이후 변경 화면은 미확인.")

    s = slide(
        "개인 AI 입구와 실시간 진행을 구현했고, 실제 연결 확인은 남았다",
        "개인 AI용 MCP 여행 도구와 웹 실시간 진행 시험은 각각 모두 통과했습니다. "
        "팀 재배분은 mock 서버에서 확인했고, 여행 삭제와 디스코드·텔레그램 연결은 cs 프로젝트 서버 코드에 구현했습니다. "
        "이 기능들의 x600 서버 반영과 실제 연결은 아직 확인하지 않았습니다."
    )
    metric(s, "15 / 15", "MCP 여행 도구",
           "통과 / 시험 · 2026-10-02\n읽기 5 · 쓰기 7 · 쓰기는 기본 꺼짐",
           0.65, 1.52, 3.85, 4.85, value_size=38)
    metric(s, "21 / 21", "웹 실시간 진행",
           "통과 / 시험 · 2026-10-02\nSSE · 채팅·일정 짜기·접수 읽기",
           4.74, 1.52, 3.85, 4.85, accent=BLUE, value_size=38)
    metric(s, "10 / 10", "팀 재배분",
           "통과 / mock 서버 시험 · 2026-10-06\n받는 팀이 없으면 등록 팀에서 한 번 재선택",
           8.83, 1.52, 3.85, 4.85, accent=AMBER, value_size=38)
    source(s, "여행 삭제·디스코드·텔레그램: cs 프로젝트 서버 코드 구현. x600 서버 반영·실제 연결 미확인.")

    s = slide(
        "Gemma 4 E4B를 가르치니 같은 시험의 정답이 늘었다",
        "Gemma 4 E4B를 QLoRA로 가르치자 같은 769문제에서 정답이 688개에서 750개로 늘었습니다. "
        "시드만 바꾼 재시험에서는 760개를 맞혔지만, 문제는 모두 모델이 만든 합성입니다. "
        "아래 그림은 주간 사실에 있는 전체 시험 묶음만 발췌했습니다."
    )
    picture(s, ASSETS["tuning"], 0.65, 1.45, 7.5, 4.9,
            region=(0, 0, 500, 600))
    metric(s, "750 / 769", "QLoRA 학습 후",
           "정답 / 합성 시험 · 97.5%\nmix8~12 · 요청 둘 66문제 제외\n학습 전 688 / 769",
           8.35, 1.52, 4.3, 2.62, value_size=34)
    metric(s, "760 / 769", "시드를 바꾼 재시험",
           "정답 / 같은 합성 시험 · 98.8%\n학습 전 대비 이쪽만 정답 69 : 7\np=6.4e-14 · 제품 연결 전",
           8.35, 4.32, 4.3, 2.22, value_size=34)
    source(s, "원본 파인튜닝_전후.png의 주 지표 부분 발췌. 비교는 같은 769문제이며 사람 평가가 아니다.")

    s = slide(
        "가르친 작은 모델이 큰 로컬 모델을 넘었지만, 모델 순위는 미정이다",
        "가르친 E4B는 같은 769문제에서 학습 없는 큰 로컬 모델들보다 높은 정답 수를 보였습니다. "
        "같은 방법으로 가르친 Winnow-E4B는 Jev 계열 모델이며 756개를 맞혔지만, E4B와 순위를 구분하려면 시드 3개 이상이 필요합니다. "
        "상용 CLI 결과는 출제자 편향 때문에 이 비교에서 제외했습니다."
    )
    text(s, "같은 합성 시험에서의 정답 수", 0.65, 1.43, 12, 0.45, 20, True)
    bands = [
        (0, 278, 1440, 328),
        (0, 321, 1440, 371),
        (0, 364, 1440, 414),
        (0, 493, 1440, 543),
        (0, 622, 1440, 672),
    ]
    for index, region in enumerate(bands):
        model_band(s, region, 2.0 + index * 0.65)
    metric(s, "756 / 769", "가르친 Winnow-E4B · Jev 계열 모델",
           "정답 / 같은 시험 · 시드 1개\nE4B와 구분 안 됨 · 순위 확인은 시드 3개 이상",
           0.65, 5.37, 12.0, 1.23, value_size=27)
    # 짧은 가로 카드에서는 숫자와 근거를 각각 독립 배치한다.
    for shape in list(s.shapes)[-4:]:
        element = shape._element
        element.getparent().remove(element)
    rect(s, 0.65, 5.4, 12.0, 1.05, LIGHT)
    text(s, "756 / 769", 0.85, 5.56, 3.15, 0.5, 29, True, GREEN)
    text(s, "정답 / 같은 합성 시험 · 가르친 Winnow-E4B(Jev 계열 모델) · 시드 1개",
         4.1, 5.55, 8.15, 0.35, 13)
    text(s, "E4B와 구분 안 됨 · 모델 사이 순위는 시드 3개 이상 필요",
         4.1, 5.98, 8.15, 0.25, 9, fill=MUTED)
    source(s, "모델별_769_비교.png에서 확인된 로컬 비교 행만 발췌. 큰 로컬 모델은 학습 없음.")

    s = slide(
        "규칙과 ML은 호출을 줄였지만, 단계를 늘려도 정답은 늘지 않았다",
        "GPU 서버 C에서 문제마다 실제 호출한 시험에서는 가르친 E4B 하나가 748개를 맞혔습니다. "
        "규칙과 ML로 거르면 745개로 구분되지 않았고 E4B 호출은 19% 줄었습니다. "
        "학습 없는 Winnow-E4B를 판정에 넣은 구성은 학습 조건이 달라 공정한 모델 비교가 아닙니다."
    )
    picture(s, ASSETS["chain"], 0.65, 1.55, 12.0, 2.5,
            region=(0, 0, 1180, 258))
    metric(s, "19% 감소", "가르친 E4B 호출",
           "규칙 + ML 거름 대 E4B 단독 · 정답 745 대 748 /769\nGPU 서버 C · 2026-10-06 · 구분 안 됨",
           0.65, 4.15, 5.86, 2.15, value_size=34)
    metric(s, "697 / 769", "학습 없는 Winnow-E4B 포함",
           "Jev 계열 모델 · 학습 조건 달라 공정 비교 아님\n사후 개선 판 · 사전 등록 판은 472 / 769",
           6.78, 4.15, 5.86, 2.15, accent=AMBER, value_size=34)
    source(s, "한줄연결_시험.png의 확인된 기준 구성만 발췌. 일정과 무관한 말이 섞인 흐름에서는 앞단이 이득.")

    s = slide(
        "분류는 개선됐지만, 규정 검색은 목표에 못 미쳤다",
        "학습한 e5-base 분류 인코더의 긴급도는 CX 400에서 88.4%였습니다. "
        "제품 코드 그대로의 규정 검색은 10월 6일 독립 질문 48문제에서 정답 규정을 상위 3개 안에 30번 넣어 목표에 미달했습니다. "
        "고객용 색인은 정답 노출을 늘렸지만 불필요한 규정 노출도 늘려 운영 반영을 결정하지 않았습니다."
    )
    metric(s, "88.4%", "학습한 분류 인코더의 긴급도",
           "CX 400 · Codex 작성 · Claude 교차 라벨\n학습 없는 E4B 60.9% 대 학습 후 88.4%",
           0.65, 1.5, 5.86, 2.64)
    metric(s, "30 / 48", "정답 규정이 상위 3개 안",
           "62.5% · 제품 코드 그대로 · 독립 질문 B\n2026-10-06 · 양식 목표 0.90 미달",
           6.78, 1.5, 5.86, 2.64, accent=AMBER)
    rect(s, 0.65, 4.35, 12.0, 2.15, LIGHT)
    text(s, "고객용 색인은 정답 노출과 불필요한 노출을 함께 늘렸다",
         0.87, 4.55, 11.55, 0.5, 21, True)
    text(s, "정답 노출 21/48 → 31/48", 0.9, 5.23, 5.5, 0.5, 25, True, GREEN)
    text(s, "불필요한 노출 22.3% → 36.7%",
         6.45, 5.23, 5.9, 0.5, 24, True, RED)
    text(s, "독립 질문 B · 2026-10-06 · 운영 반영 결정 전",
         0.9, 5.86, 5.25, 0.28, 9, fill=MUTED)
    text(s, "규정이 아닌 여행 대화에 규정을 붙인 비율",
         6.45, 5.86, 5.85, 0.28, 9, fill=MUTED)
    source(s, "발표 수치는 2026-10-06 제품 코드 그대로 잰 규정 검색 결과(독립 질문 B 48문제, 합성).")

    s = slide(
        "5주차 산출물과 6주차 시험 문서를 만들고 지적을 반영했다",
        "5주차 산출물 4종과 6주차 서비스 테스트 문서 1종을 만들었습니다. "
        "요구사항 85개 중 구현 끝은 24개이고 일부 구현은 58개, 결정 대기는 3개입니다. "
        "산출물은 모두 코덱스와 교차 검증하고 지적을 반영했습니다."
    )
    rows = [
        ("벡터DB·GraphDB 구축 결과서", "23쪽"),
        ("멀티 에이전트 테스트 계획 및 결과 보고서", "50쪽"),
        ("요구사항 정의서 업데이트", "85개 요구"),
        ("화면설계서", "25쪽"),
        ("6주차 서비스 테스트 계획 및 결과 보고서", "10쪽"),
    ]
    for index, (label, value) in enumerate(rows):
        y = 1.48 + index * 0.88
        rect(s, 0.65, y, 8.1, 0.73, LIGHT)
        text(s, label, 0.9, y + 0.16, 6.15, 0.44, 19, True)
        text(s, value, 7.07, y + 0.12, 1.42, 0.47, 22, True,
             GREEN, align=PP_ALIGN.RIGHT)
    metric(s, "24 / 85", "요구사항 구현 끝",
           "2026-10-06 업데이트 기준\n일부 구현 58 · 결정 대기 3\n구현 상태이며 시험 통과율이 아님",
           9.0, 1.48, 3.65, 4.99, value_size=35)
    source(s, "산출물 분량·요구사항 상태: 주간_사실.md의 산출물 기록. 모두 교차 검증 후 지적 반영.")

    s = slide(
        "합성 시험의 성과와 별개로, 데이터 변조와 실제 응답 확인이 남았다",
        "사람 평가가 없고 가르친 모델도 제품에 아직 연결하지 않았습니다. "
        "계획 읽기 값 변조와 일정 항목의 빈 답은 원인을 더 확인해야 하며, 엉뚱한 대상 변경과 일본어 알림의 금액 단위 변조도 발견했습니다. "
        "바뀐 화면 대부분은 실제 응답을 확인하지 않았습니다."
    )
    metric(s, "0건", "사람 평가",
           "2026-10-06 기준 · 시트 35행만 준비\n합성 시험 결과의 실제 사용 검증 전",
           0.65, 1.48, 3.85, 3.37, accent=AMBER)
    metric(s, "12 / 350", "계획 읽기 값 변조",
           "변조 / 시험 · 3.4%\n2026-10-06 주간 사실 기준",
           4.74, 1.48, 3.85, 3.37, accent=RED, value_size=36)
    metric(s, "85 / 2,735", "일정 항목 짚기 빈 답",
           "빈 답 / 흐름 시험 · 3.1%\n2026-10-06 기준 · 원인 미확인",
           8.83, 1.48, 3.85, 3.37, accent=RED, value_size=32)
    rect(s, 0.65, 5.06, 12.0, 1.43, LIGHT)
    text(s, "엉뚱한 대상 변경 1/172",
         0.9, 5.29, 5.3, 0.48, 24, True, RED)
    text(s, "금액 단위 변조 1건 통과",
         6.45, 5.29, 5.9, 0.48, 24, True, RED)
    text(s, "발생 / 결정 단위 · 주간 사실 기준",
         0.9, 5.94, 5.3, 0.26, 9, fill=MUTED)
    text(s, "일본어 알림 번역 · 원을 엔으로 변경 · 주간 사실 기준",
         6.45, 5.94, 5.9, 0.26, 9, fill=MUTED)
    source(s, "규정 검색 목표 미달도 미해결. 변경 화면 대부분 실제 응답 미확인 · 가르친 모델 제품 연결 전.")

    s = slide(
        "다음 주에는 실제 응답과 사람 평가를 확인하고 제품 반영을 결정한다",
        "다음 주에는 바뀐 화면의 실제 응답을 확인하고 준비한 시트로 사람 평가를 진행합니다. "
        "가르친 모델의 제품 연결을 검토하고 시드 3개 이상으로 순위를 확인하며, 규정 색인 개선도 분류기 뒤에서 다시 측정합니다. "
        "GPU 서버 B 대기열에 있는 다른 Jev 계열 후보도 같은 방법으로 가르쳐 비교합니다.",
        dark=True
    )
    metric(s, "35행", "사람 평가 진행",
           "이미 준비한 평가 시트 행 수\n6주차 예정 · 완료한 평가 수가 아님",
           0.65, 1.55, 5.86, 3.02, dark=True)
    metric(s, "시드 3개 이상", "모델 순위 재확인",
           "가르친 모델 제품 연결 검토와 함께 진행\n6주차 예정 · 현재 순위 확정 전",
           6.78, 1.55, 5.86, 3.02, dark=True, value_size=31)
    text(s, "바뀐 화면의 실제 응답 확인\n규정 색인 개선을 분류기 뒤에서 다시 측정",
         0.85, 4.87, 11.65, 0.96, 24, True, WHITE)
    text(s, "Jev 계열 후보: Plumb-4B · spark-s1-4b-v6 · jevify-gemma4-e4b\n"
            "같은 방법으로 가르쳐 비교 예정 · GPU 서버 B 대기열",
         0.85, 6.03, 11.65, 0.66, 15, fill="D4E1E8")


def finalize():
    if len(prs.slides) != 11:
        raise RuntimeError("슬라이드는 11장이어야 합니다.")
    for s, notes in SCRIPT_NOTES:
        s.notes_slide.notes_text_frame.text = notes
        for element in list(s._element):
            if element.tag.rsplit("}", 1)[-1] in ("timing", "transition"):
                s._element.remove(element)

    for s in prs.slides:
        for shape in s.shapes:
            if shape.left < 0 or shape.top < 0:
                raise RuntimeError("슬라이드 밖에 배치한 요소가 있습니다.")
            if shape.left + shape.width > prs.slide_width + Inches(0.01):
                raise RuntimeError("슬라이드 너비를 넘은 요소가 있습니다.")
            if shape.top + shape.height > prs.slide_height + Inches(0.01):
                raise RuntimeError("슬라이드 높이를 넘은 요소가 있습니다.")
            if shape.has_text_frame:
                if "—" in shape.text or "…" in shape.text or "..." in shape.text:
                    raise RuntimeError("금지된 줄표 또는 말줄임표가 있습니다.")

    buffer = BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    check = Presentation(buffer)
    if len(check.slides) != 11:
        raise RuntimeError("저장 후 슬라이드 수 검증 실패")
    if any(not s.notes_slide.notes_text_frame.text.strip() for s in check.slides):
        raise RuntimeError("발표 대본이 없는 슬라이드가 있습니다.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=str(OUTPUT.parent), prefix=".triPilot_", suffix=".pptx", delete=False
        ) as temporary:
            temporary.write(buffer.getvalue())
            temporary_path = Path(temporary.name)
        os.replace(str(temporary_path), str(OUTPUT))
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    print(str(OUTPUT))


def main():
    required = [FACTS, *ASSETS.values()]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError("필수 자료를 찾을 수 없습니다:\n" + "\n".join(missing))
    FACTS.read_text(encoding="utf-8-sig")
    build()
    finalize()


if __name__ == "__main__":
    main()
