# -*- coding: utf-8 -*-
"""수집 데이터 보고서 3차(여행) — 2차 제출본(결정 16 반영판)에 **바뀐 칸만** 고쳐 넣는다.

    python build_수집데이터보고서_3차_여행.py

입력: w2/제출본/[데이터 수집 및 저장] 수집 데이터 보고서_2차_여행.docx  (읽기만 한다)
출력: w3/데이터수집_여행/[데이터 수집 및 저장] 수집 데이터 보고서_3차_여행.docx  (새 이름)

★2차는 여러 차례 반박 검토를 거친 판이다. 처음부터 다시 쓰지 않고, 2026-09-18 에
  저장소·DB 를 직접 세어 **달라진 사실만** 바꾼다. 근거는 아래 FACTS 에 모았다.
★없는 것을 있다고 적지 않는다. 연동 안 된 소스(Places·Routes·ODsay)는 그대로 「연동 전」이다.
"""
import copy
import os
import sys

from docx import Document
from docx.shared import Pt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
SRC = os.path.join(FORMS, "w2", "제출본", "[데이터 수집 및 저장] 수집 데이터 보고서_2차_여행.docx")
OUT_DIR = os.path.join(FORMS, "w3", "데이터수집_여행")
OUT = os.path.join(OUT_DIR, "[데이터 수집 및 저장] 수집 데이터 보고서_3차_여행.docx")
SUBMIT_DATE = "2026. 9. 18."

# ── 근거(2026-09-18 실측) ────────────────────────────────────────────
# DB acop_cs: place_catalog 2,063행(tour_api, 2026-09-10 12:08 수집, 좌표 결측 0, content_id 중복 0)
#   분류별 12:391 14:203 15:50 28:54 32:235 38:140 39:990
#   source_sync_state: bootstrap_done, rows_seen 2,063, delta_trusted, 「대조 2063건 · 어긋남 0」
#   watch_observations 7 · watch_changes 1 (tour_api, 2026-09-10)
#   trips·itinerary_versions·itinerary_items 표 존재(014·016 적용), 행 0(시나리오 테넌트 정리 후)
#   knowledge_documents 25 · knowledge_chunks 306 (쇼핑몰 규정 그대로)
# 코드: app/infrastructure/travel/base.py build_travel_sources — 소스 목록·대체 사슬
#   odsay.py 없음(연동 전), Google Places·Routes 호출 코드 없음(app/ 에서 googleapis 검색 0건)
# 학습 데이터: w3/데이터전처리_여행/검수본문/데이터 전처리 결과서_3차_여행.md 의 실행 통계


def setc(cell, text, bold=False):
    """셀 하나를 채운다(2차 빌드와 같은 방식 — 첫 문단 서식을 살리고 나머지 문단은 지운다)."""
    p = cell.paragraphs[0]
    for extra in list(cell.paragraphs)[1:]:
        extra._element.getparent().remove(extra._element)
    for r in list(p.runs)[1:]:
        r._element.getparent().remove(r._element)
    if not p.runs:
        p.add_run("")
    r = p.runs[0]
    r.text = text
    r.bold = bold
    r.font.size = Pt(9)
    r.font.name = "맑은 고딕"


def row_index(tbl, startswith):
    for i, row in enumerate(tbl.rows):
        if row.cells[0].text.strip().startswith(startswith):
            return i
    raise LookupError(f"행을 못 찾았다: {startswith!r}")


def set_row(tbl, startswith, values):
    """첫 칸이 startswith 로 시작하는 행의 칸들을 바꾼다. None 은 그대로 둔다."""
    row = tbl.rows[row_index(tbl, startswith)]
    for j, value in enumerate(values):
        if value is not None:
            setc(row.cells[j], value)


def insert_after(tbl, startswith, rows):
    """startswith 행 뒤에 새 행들을 끼운다 — 그 행을 복사해 서식을 맞춘다."""
    anchor = tbl.rows[row_index(tbl, startswith)]._tr
    for values in rows:
        new = copy.deepcopy(anchor)
        anchor.addnext(new)
        anchor = new
    start = row_index(tbl, startswith) + 1
    for k, values in enumerate(rows):
        for j, value in enumerate(values):
            setc(tbl.rows[start + k].cells[j], value)


def set_paragraph(doc, startswith, text):
    for p in doc.paragraphs:
        if p.text.strip().startswith(startswith):
            for r in list(p.runs)[1:]:
                r._element.getparent().remove(r._element)
            p.runs[0].text = text
            return
    raise LookupError(f"문단을 못 찾았다: {startswith!r}")


#: 문서 순서대로 흐름(2.3) · 확보 상태(3.1) · 수량(3.2). make_vis_data_3차_여행.py 가 만든다.
FIGURES = [os.path.join(OUT_DIR, "그림", name) for name in (
    "수집데이터_흐름_3차.png", "수집데이터_확보상태_3차.png", "수집데이터_소스별수량_3차.png")]
#: 그림 높이는 쪽 본문 높이의 80% 이하(2차와 같은 규칙 — 아래가 잘리지 않게).
MAX_HEIGHT_SHARE = 0.8


def replace_figures(doc) -> None:
    """2차 그림 셋을 3차 그림으로 바꾼다. 비율은 새 그림을 따르고, 너무 길면 폭을 줄인다."""
    from PIL import Image

    shapes = list(doc.inline_shapes)
    if len(shapes) != len(FIGURES):
        raise SystemExit(f"그림 수가 다르다: 문서 {len(shapes)} · 새 그림 {len(FIGURES)}")
    section = doc.sections[0]
    max_height = int((section.page_height - section.top_margin - section.bottom_margin)
                     * MAX_HEIGHT_SHARE)
    for shape, path in zip(shapes, FIGURES):
        if not os.path.exists(path):
            raise SystemExit(f"그림이 없다 — make_vis_data_3차_여행.py 를 먼저 돌린다: {path}")
        rid = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
        part = doc.part.related_parts[rid]
        with open(path, "rb") as f:
            part._blob = f.read()
        w, h = Image.open(path).size
        width = shape.width
        height = int(width * h / w)
        if height > max_height:
            height, width = max_height, int(max_height * w / h)
        shape.width, shape.height = width, height


def build() -> str:
    d = Document(SRC)
    T = d.tables

    # ── 표지 ──────────────────────────────────────────────────────
    set_row(T[1], "제출 일자", [None, SUBMIT_DATE])

    # ── 1. 수집 데이터 개요 ────────────────────────────────────────
    ov = T[3]
    set_row(ov, "API · TourAPI 관광정보", [
        None,
        "서울 관광정보 전 분류 2,063건(관광지 391, 문화시설 203, 행사 50, 레포츠 54, 숙박 235, 쇼핑 140, "
        "음식점 990)의 식별자·좌표·주소·분류·공급자 수정 시각. 지역기반 목록(areaBasedList2)으로 전수 수집했다"
        "(2026-09-10)",
        None,
        "장소 카탈로그 표(place_catalog)에 저장해 일정 등록 때 장소를 검증하고 액티비티 후보를 고른다. "
        "호출 한도(하루 1,000건) 안에서 페이지마다 진행 상태를 저장해 끊겨도 이어받는다. 변경분 동기화"
        "(areaBasedSyncList2)는 응답이 0건이라 그대로 믿지 않고 전체 목록과 다시 대조한다(대조 2,063건, "
        "어긋남 0건). 운영시간·휴무일·이용요금은 소개정보(detailIntro2)로 추가 조회한다.",
        None])
    set_row(ov, "API · 기상 예보·관측", [
        "API · 기상 예보·특보",
        "서울의 일정 장소·시간에 대응하는 시간별 예보(강수·풍속)와 발효 중인 기상특보",
        None,
        "액티비티 감시 입력으로 사용한다. 1차 소스와 대체 소스를 사슬로 묶어 1차가 값을 못 주면 대체가 값을 "
        "낸다(Open-Meteo와 기상청 단기예보, 어느 쪽을 먼저 쓸지는 설정으로 정한다). 저장된 예보를 재생하는 "
        "경우에는 재생 자료임을 표시한다.",
        "Open-Meteo(무료, 인증키 없음), 기상청 단기예보·기상특보(공공데이터포털, 무료). 예보와 사후 관측을 구분"])
    set_row(ov, "API · 장소 영업시간", [
        None, None, None,
        "액티비티·식사 검증의 입력으로 쓸 계획이다. 연동 코드는 아직 없다(2026-09-18 저장소 확인). 지금 판정은 "
        "일정 등록 때 함께 받은 장소 속성(영업시간·브레이크타임·결제수단)을 쓴다. 현재 대기·혼잡은 파악할 수 "
        "없는 값이므로 판정 입력에서 제외한다. 연동 후에는 TourAPI로 선별한 후보만 1단계 매칭과 2단계 "
        "영업상태 재확인 순으로 조회한다(월 4,000건 이하, 팀원 조사 기준 추정).",
        None])
    set_row(ov, "API · 이동 시간·경로", [
        None, None, None,
        "공통 일정 검증·이동 검증·(3) 출발 안내에 쓸 계획이다. 대중교통 경로(ODsay)와 Google Routes 모두 아직 "
        "연동되지 않았다(2026-09-18 저장소 확인). 지금 이동 항목은 일정 등록 때 함께 받은 경로 후보와 도로 "
        "통제 사건으로 판정한다. 연동 뒤 1차 소스가 실패하면 대체 소스에서 값을 확보하고, 대체 소스까지 "
        "실패하면 서버를 중단한다.",
        None])
    set_row(ov, "API · 감시 관측·변화 이력", [
        None, None, None, None,
        "API 응답을 바탕으로 내부에서 생성한다. 장소 정보 감시는 예약에서, 일정 감시는 일정 항목에서 대상을 "
        "뽑는다."])
    set_row(ov, "API · 감시 관측·변화 이력", [
        None, None, None,
        "감시 관측·변화 이력 표에 저장한다. 2026-09-10 TourAPI 장소 정보 기준 관측 7건, 변화 1건을 저장했다. "
        "운영 상태(대기질 경보·기상특보·도로 통제·휴무)는 일정 감시가 항목마다 조회해 판정하고, 판정 결과는 "
        "일정 버전의 원인 기록에 남긴다. 무료 소스의 조회 주기는 최소 84초·기본 2분이고, 유료 Places는 주 1회 "
        "이하로 조회한다.",
        None])
    insert_after(ov, "API · 감시 관측·변화 이력", [
        ("API · 대기질",
         "서울 구 측정소의 1시간 미세먼지(PM10·PM2.5) 측정값",
         "야외 활동의 미세먼지 경보 기준(PM10 150·300, PM2.5 75·150) 초과 여부를 판정한다",
         "액티비티 감시 입력. 1차는 에어코리아 실측값, 대체는 Open-Meteo 대기질 모델 추정값이다(에어코리아가 "
         "시간 초과로 연달아 실패한 사례가 있어 대체를 둔다). 공식 경보는 2시간 평균 기준임을 함께 표시한다.",
         "한국환경공단 에어코리아(공공데이터포털, 무료), Open-Meteo(무료, 인증키 없음)"),
        ("API · 재난문자·지진",
         "서울 대상 긴급재난문자와 최근 지진(규모·진앙)",
         "재난·안전 사건을 일정 판정의 원인으로 반영한다",
         "액티비티·이동 감시 입력. 재난문자는 인증키가 있으면 API로, 없으면 샘플 CSV(2023-09 일부 기간)로 "
         "조회하며 샘플 기간 밖은 「연결 안 됨」으로 답한다.",
         "행정안전부 긴급재난문자(공공데이터포털), 기상청 지진정보(공공데이터포털). 무료"),
        ("API · 교통 돌발·도로 통제",
         "시내 도로의 사고·공사·행사·집회 통제 사건",
         "이동 항목의 경로가 통제 구간에 걸리는지 판정한다",
         "이동 감시 입력. 두 소스를 합쳐 쓴다(시내 행사·집회는 UTIC가 본체). UTIC 키는 등록된 IP에서만 "
         "호출된다. 지하철 무정차는 아직 소스가 없어 「확인 못 함」으로 따로 센다.",
         "경찰청 도시교통정보센터 UTIC, 국토교통부 국가교통정보센터 ITS. 무료, 각 기관 발급 키"),
        ("API · 국가유산 좌표",
         "고궁·유적 등 국가유산의 위치",
         "좌표를 모르는 장소의 좌표를 채운다",
         "장소 검증 보조. 운영시간은 주지 않는다. 인증키가 필요 없어 항상 붙는다.",
         "국가유산청 공개 API. 무료"),
    ])
    set_row(ov, "RAG · 취소·환급 규정", [
        None, None, None,
        "Activity·Dining·Mobility 근거(Booking Handoff는 MVP 다음). 여행 코퍼스로 전량 교체할 대상이다. "
        "2026-09-18 기준 적재분은 여전히 쇼핑몰 25문서·306청크이고 여행 문서는 0건이다.",
        None])
    set_row(ov, "합성 · 여행·예약·고객", [
        None, None, None, None,
        "확정 시나리오 여행 1건(대만인 2인, 서울 하루)을 구현했다. 목표 20~30건 중 1건. 자체 생성이며 실제 "
        "고객 데이터가 아님"])
    set_row(ov, "합성 · 사건 시나리오", [
        None, None, None, None,
        "확정 시나리오 사건 6개(액-02 기상 악화, 이동-B1 무정차, 요식-P3 지연, 이동-A6 도로 통제, 요식-P7 "
        "임시휴무, 액-08 품절)를 재생 입력으로 구현했다. 목표 10개 중 6개. 재생 결과에는 재생 표시를 붙인다."])
    set_row(ov, "수집 예정 · 특일 정보", [
        "API · 특일 정보(공휴일)",
        "조회 연도의 공휴일·대체공휴일. 저장하지 않고 필요할 때 조회한다",
        None, None, None])
    last = ov.rows[-1].cells[0].text.strip()[:10]
    insert_after(ov, last, [
        ("학습 · 소비자상담 여행 품목",
         "공정거래위원회 소비자상담 공개 데이터 2종 1,236,805행 중 항공·해외여행·숙박·공연·외식·철도·버스 등 "
         "여행 서비스 품목 139,539행의 사건제목",
         "고객 문장의 요청 종류(5종)·문제 코드(17종) 분류 모델을 학습한다",
         "Case 인라인 분류를 외부 LLM 없이 로컬 모델로 수행한다. 라벨은 교사 모델(Gemma 4 12B)이 붙였다"
         "(6,287건 중 6,067건 확정). 자세한 처리는 데이터 전처리 결과서 3차에 있다.",
         "공정거래위원회·한국소비자원(공공데이터포털). 이용허락범위 제한 없음"),
        ("학습 · 쇼핑 리뷰 감정 말뭉치",
         "네이버쇼핑 리뷰 199,908건(긍정·부정 이분류)",
         "고객 문장의 감정 분류 모델을 학습한다",
         "Case 인라인 분류의 감정 라벨. 여행 문장과의 차이는 평가 전용 여행 문장 41건으로 따로 잰다",
         "공개 말뭉치(bab2min/corpus). Public Domain"),
        ("입력 · 고객 자유 문장",
         "여행 중 고객(또는 개인 에이전트)이 보내는 자유 문장",
         "신고 종류(지연·휴무·품절·재요청)와 값(지연 분·상품명)을 뽑아 일정 조정에 쓴다",
         "여행 메시지 API로 받는다. 개인정보를 가린 뒤 로컬 Gemma 4가 분류·추출한다. 원문은 Case 기록으로 남는다",
         "고객 입력(운영). 평가용은 시나리오 문장"),
    ])

    # ── 2.1 수집 방식 ─────────────────────────────────────────────
    way = T[4]
    setc(way.rows[1].cells[3],
         "☑ 무료 공공 API(TourAPI, 기상청 예보·특보·지진, 에어코리아, 재난문자, 특일, 국가유산청), 인증키 없는 "
         "공개 API(Open-Meteo), 교통 돌발(UTIC·ITS)을 호출한다. 유료 상용 API(Google Places·Routes)는 아직 "
         "연동 전이다. 시연에는 저장된 자료의 재생도 허용하며 재생임을 표시한다.")
    setc(way.rows[2].cells[1],
         "☑ 개인 에이전트·고객이 보내는 일정 등록과 자유 문장(로컬 Gemma 4가 분류·추출). 평가용은 합성")
    setc(way.rows[2].cells[3],
         "☑ 인허가 CSV, 공정위 소비자상담 CSV, 재난문자 샘플 CSV를 내려받아 쓴다. 공개 규정 문서는 선별해 "
         "검색용으로 적재할 계획이며 기존 쇼핑몰 문서는 여행 자료로 교체한다.")

    # ── 2.2 사용 언어·자동화·예외 ──────────────────────────────────
    tools = T[5]
    setc(tools.rows[0].cells[1],
         "서비스 코드는 Python 3.12 + httpx, pydantic. 학습 데이터 처리는 Python 3.12 csv·json·unicodedata, "
         "scikit-learn, 교사 라벨은 로컬 Ollama(Gemma 4 12B). 요식업장 수집 스크립트는 Python 3.11 + requests, "
         "python-dotenv, pyproj(좌표계 변환), csv·json·difflib. 저장은 PostgreSQL")
    setc(tools.rows[1].cells[1],
         "일정 감시와 알림 발송을 별도 작업으로 실행한다. 일정 감시는 한 번 돌 때 앞으로 90분 안에 시작하는 "
         "항목을 점검하고, 깨진 항목이 있으면 Case를 연다. Team이 대안을 고르면 코어가 새 일정 버전·Case 완료·"
         "통지를 한 트랜잭션으로 적용한다(2026-09-17 구현). 시나리오 모드의 기본 엔진은 Team을 거치지 않고 같은 "
         "계산을 바로 적용한다. 알림 발송은 발송 "
         "대기열을 꺼내 고객 언어로 옮겨 보낸다. 장소 카탈로그는 처음 한 번 전체를 받고 이후에는 전체 대조로 "
         "확인한다. 지금은 로컬에서 주기 실행하며, 주기는 코드가 아니라 운영이 정한다. 2분 주기는 무료 소스에만 "
         "쓰고 유료 Places 영업상태 재확인은 주 1회 이하로 둔다. 요식업장 수집 스크립트는 수동 실행이다.")
    setc(tools.rows[2].cells[1],
         "모든 외부 소스에 같은 규칙을 적용한다. 못 가져오면 값을 비우고 이유를 센다. HTTP 200이어도 본문이 "
         "오류면 실패로 본다. 자동 재시도는 하지 않는다. 호출 한도는 소스 전체가 공유하는 속도 제한기로, 재사용은 "
         "응답 캐시로 관리하며 캐시 값에는 처음 받아 온 시각을 붙인다. 필요한 값마다 대체 소스를 둔다(기상은 "
         "Open-Meteo와 기상청, 대기질은 에어코리아와 Open-Meteo, 교통 돌발은 ITS와 UTIC 합산). 대체 소스까지 "
         "실패하면 치명적 결함으로 처리한다(v11 결정 15). 값을 지어내지 않는다. 알림 중복은 발송 대기열의 유일 "
         "제약(테넌트, 주제, 중복 방지 키)으로 막는다. 묶음 조정은 부분 반영 없이 실패 근거를 사람에게 인계한다. "
         "요식업장 수집에는 요청 간격 0.5초와 실패 시 3회 재시도(대기 3초, 6초)를 적용했고, 원본 JSON을 먼저 "
         "저장한 뒤 CSV를 만든다.")

    # ── 2.3 흐름 설명 문단 ─────────────────────────────────────────
    set_paragraph(d, "요식업장 데이터 수집은",
        "요식업장 데이터 수집은 지역명을 지역코드로 변환하는 단계부터 진행한다. 캐치테이블은 지역별 상위 100곳, "
        "트립어드바이저는 반경 내 1,000곳 중 리뷰 수 상위 100곳의 목록을 수집하고, 매장별 상세 정보를 0.5초 "
        "간격으로 조회한다. 원본 JSON을 저장한 뒤 CSV를 만든다. 인허가 CSV는 좌표를 EPSG:5174에서 WGS84로 "
        "변환한 뒤 지정 반경 안의 행만 추출했다. 세 소스의 교차 매칭은 장소 간 거리 80m와 이름 유사도 0.75를 "
        "기준으로 했다. TourAPI는 지역기반 목록(areaBasedList2)으로 서울 2,063건을 22쪽에 걸쳐 전수 수집했고, "
        "페이지마다 진행 상태를 저장한다. 운영시간·휴무일·이용요금은 소개정보(detailIntro2)로 추가 조회한다. "
        "공정위 소비자상담 CSV는 여행 서비스 품목만 골라 정규화·마스킹·중복 제거 뒤 학습 표본을 뽑는다. Google "
        "Places·Routes는 연동 뒤 TourAPI 후보에 한해 매칭하고 영업상태를 주 1회 이하 재확인한다.")

    # ── 3.1 파일 및 필드 ───────────────────────────────────────────
    fields = T[6]
    set_row(fields, "place_catalog", [None, None, None,
        "(tenant_id, source, content_id) 유일. 공급자 수정 시각과 수집 시각을 구분한다. 2,063행 저장(좌표 결측 "
        "0, 식별자 중복 0)",
        "source=tour_api, content_type_id=12, fetched_at=2026-09-10T12:08+09:00"])
    set_row(fields, "source_sync_state", [None, None, None,
        "카탈로그 수집 재개와 변경분 동기화 상태를 저장한다. 처리 중 확인한 행 수와 수집 완료 건수를 구분한다. "
        "1행(서울 TourAPI)",
        "next_page=22, rows_seen=2,063, delta_trusted=true"])
    set_row(fields, "watch_observations", [None, None, None, None,
        "target_kind=place, source=tour_api (7행 저장)"])
    set_row(fields, "watch_changes", [None, None, None, None,
        "source=tour_api (1행 저장)"])
    set_row(fields, "knowledge_documents", [None, None, None,
        "기존 25문서/306청크는 모두 쇼핑몰 자료다. 문서·청크 표는 유지하고 내용은 여행 자료로 교체한다"
        "(2026-09-18 기준 여행 문서 0건).", None])
    set_row(fields, "trips", [
        "trips (014·016)",
        "trip_id / customer_id / title / locale / party_size / latest_version / constraints / request_key",
        "uuid / uuid / text / text / int / int / jsonb / text",
        "여행 전체와 최신 일정 버전 포인터. 고객 언어(locale)로 알림을 생성한다. 같은 등록 요청은 request_key "
        "부분 유일 색인으로 한 번만 만든다. Trip 수준 조건(결제수단·식단)은 constraints에 둔다. 구현 완료",
        "locale=zh-TW, party_size=2, constraints={\"payment\": \"card\"}"])
    set_row(fields, "itinerary_versions", [
        "itinerary_versions (014)",
        "trip_id / version / reason / cause_json / case_id / created_at",
        "uuid / int / text / jsonb / uuid / timestamptz",
        "기존 버전을 고치지 않고 새 버전을 추가한다(append-only). 새 버전은 기준 버전 조건으로만 올려 낡은 "
        "쓰기를 거부한다. 원인 기록은 통지에 그대로 들어간다. 구현 완료",
        "version=4, reason=customer_request"])
    set_row(fields, "itinerary_items", [
        "itinerary_items (014)",
        "item_id / version / seq / kind / place_id / starts_at / ends_at / locked / booking_id / replaces_item_id "
        "/ detail",
        "uuid / int / int / text / uuid / timestamptz / timestamptz / boolean / uuid / uuid / jsonb",
        "무료·무예약 항목도 보존한다(예약은 선택). 대체 항목은 원래 항목을 가리킨다. 항목 수준 조건과 다른 안은 "
        "detail에 둔다. 구현 완료",
        "kind=dining, booking_id=NULL, detail={\"alternates\": [...]}"])
    set_row(fields, "trip_constraints", [
        "trip_constraints (가칭, 흡수)", "trips.constraints / itinerary_items.detail", "jsonb / jsonb",
        "별도 표를 만들지 않았다. 여행 수준 조건은 trips.constraints, 항목 수준 조건은 itinerary_items.detail에 "
        "두는 방식으로 구현했다(014)",
        "constraints={\"payment\": \"card\"}"])
    set_row(fields, "watch_schedule", [None, None, "timestamptz (미구현)",
        "별도 표는 아직 없다. 지금 일정 감시는 매번 앞으로 90분 안에 시작하는 항목을 일정 항목 표에서 직접 "
        "골라 점검한다",
        "lookahead=90분"])
    set_row(fields, "tourapi_activity_candidates", [
        "place_catalog 로 대체 (TourAPI 목록)",
        None, None,
        "예정 테이블 대신 장소 카탈로그 표에 저장했다. 운영시간·휴무는 소개정보(detailIntro2)로 추가 조회",
        None])
    insert_after(fields, "place_catalog 로 대체", [
        ("학습 조각 JSONL (datasets/ml/)",
         "text / label, text / intent / issue_code",
         "string / category",
         "감정과 요청 종류·문제 코드 학습·검증·시험 조각. 저장소 밖에 두며 같은 명령과 seed(7)로 다시 만든다",
         "요청 종류 학습 4,859 / 검증 604 / 시험 604건"),
    ])

    # ── 3.2 데이터 양 ─────────────────────────────────────────────
    qty = T[7]
    setc(qty.rows[0].cells[1],
         "API: TourAPI 서울 카탈로그 2,063건 저장, 감시 관측 7건·변화 1건 저장(2026-09-10). 대기질·기상·특보·"
         "재난문자·지진·교통 돌발은 저장하지 않고 필요할 때 조회한다. 학습: 공정위 소비자상담 1,236,805행에서 "
         "여행 서비스 139,539행 선별, 네이버쇼핑 리뷰 199,908건. RAG: 기존 25문서/306청크는 쇼핑몰 규정이라 여행 "
         "규정으로 전량 교체할 대상이다(여행 문서 0건). 합성: 확정 시나리오 여행 1건과 사건 6개를 구현했다(목표 "
         "여행 20~30건, 사건 10개). 요식업장(팀원 수집, 2026-09-10): 캐치테이블 496곳, 트립어드바이저 5,000곳"
         "(지역별 1,000곳 × 5) 중 상위 500곳, 인허가 685,389행(일반음식점 538,310 + 휴게음식점 147,079). "
         "TourAPI 영문 약 1,200건은 수집 예정이며 건수는 추정이다.")
    setc(qty.rows[1].cells[1],
         "장소 카탈로그 2,063건(좌표 결측 0건, 식별자 중복 0건, 전체 대조 어긋남 0건). 학습: 여행 사건제목은 "
         "정규화·마스킹·중복·길이 필터 후 고유 101,112건, 그중 표본 6,287건에 교사 라벨 6,067건 확정(96.5%). "
         "감정은 전처리 후 199,889건. 요식업장 약 20,020건은 수집 완료 3종의 합계이며 품질 통과량이나 소스 간 "
         "중복을 뺀 고유 매장 수가 아니다: 캐치테이블 496곳(영업시간 496곳, 브레이크타임 267곳), 트립어드바이저 "
         "500곳(상위 150곳 상세 조회에서 영업상태 150곳, 가격대 129곳), 인허가 19,024곳(좌표 유효·지역 원 내부 "
         "68,380곳 중 영업/정상).")

    # ── 3.3 저장 위치 ─────────────────────────────────────────────
    store = T[8]
    setc(store.rows[0].cells[1],
         "PostgreSQL에는 장소 카탈로그·동기화 상태, 감시 관측·변화 이력, 여행·일정 버전·일정 항목(014·016 적용), "
         "예약 표가 있다. 검색용 문서는 knowledge_documents·knowledge_chunks에 저장한다. 학습 조각과 모델 "
         "가중치는 저장소 밖 datasets/ml/에 둔다(용량이 크고 같은 명령으로 다시 만든다). 재난문자 샘플 CSV는 "
         "datasets/travel/에 있다. 요식업장 수집분은 수집 팀원이 보관하며, 정리한 뒤 datasets/travel/<이름>/ "
         "아래 raw·processed·scripts·REPORT.md로 옮긴다.")

    # ── 4. 법적·윤리적 검토 ────────────────────────────────────────
    law = T[9]
    set_row(law, "개인정보 포함 여부", [None,
        "☐ 포함 ☑ 미포함  -  평가용 여행·예약·고객은 합성 생성. 학습용 공개 데이터에서 개인정보 형식(전화·"
        "주민번호·계좌·이메일·카드번호)은 마스킹했다(사건제목 2건, 리뷰 20건 치환)."])
    law_row = law.rows[row_index(law, "라이선스")]
    setc(law_row.cells[1], law_row.cells[1].text.strip() +
         " 3차에 더한 소스: 에어코리아·재난문자·기상청 특보·지진·특일은 공공데이터포털 이용 조건을 따르고, "
         "UTIC·ITS는 각 기관 발급 키의 이용 조건을 따른다. Open-Meteo는 무료 공개 API이며 상용 전환 전에 "
         "이용 조건을 다시 확인한다. 공정위 소비자상담 데이터는 이용허락범위 제한이 없고, 네이버쇼핑 리뷰 "
         "말뭉치는 Public Domain이다.")

    # ── 6. 변경 이력 ──────────────────────────────────────────────
    hist = T[11]
    insert_after(hist, hist.rows[-1].cells[0].text.strip(), [
        ("2026-09-18", "전체",
         "저장소·DB 실측으로 갱신: TourAPI 서울 2,063건 수집 완료, 대기질·재난문자·지진·교통 돌발·국가유산 "
         "소스와 대체 사슬 반영, 여행·일정 버전·항목 표 구현(014·016) 반영, 학습 데이터(공정위 여행 품목·감정 "
         "말뭉치)와 고객 자유 문장 입력 추가. Places·Routes·대중교통은 연동 전으로 유지",
         "3차"),
    ])

    replace_figures(d)

    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(OUT):
        raise SystemExit(f"이미 있다 — 덮어쓰지 않는다. 먼저 _backup/ 으로 옮긴다: {OUT}")
    d.save(OUT)
    return OUT


if __name__ == "__main__":
    print("저장:", build())
