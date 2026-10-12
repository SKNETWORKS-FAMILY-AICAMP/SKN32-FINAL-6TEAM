# -*- coding: utf-8 -*-
"""DB·저장소 설계 문서 3차(여행) — 2차 제출본(결정 16 반영판)에 **구현된 것만** 고쳐 넣는다.

    python build_DB설계서_3차_여행.py --text-only   # 그림 없이 본문판(그림 스크립트의 입력)
    python make_vis_db_3차_여행.py                 # 본문판을 읽어 그림 셋
    python build_DB설계서_3차_여행.py               # 본문 + 새 그림 = 3차

입력: w2/제출본/[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_2차_여행.docx (읽기만 한다)
출력: w3/데이터수집_여행/[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_3차_여행.docx (새 이름)

★2차가 「설계만 존재」로 적은 Trip·일정 버전·일정 항목이 마이그레이션 014·016 으로 구현됐다. 2차의
  제안 칼럼(version_no·current_version_no·incident_revision …)과 실제 칼럼이 다르므로 표 정의를
  **실제 DDL 로 바꾼다.** 구현하지 않은 제안(사건 개정번호·재계산·권한 분리 등)은 「제안으로 남음」으로 적는다.
★근거(2026-09-18 실측): 014_itinerary.sql · 016_trip_request_key.sql, 로컬 개발 DB(acop_cs) information_schema
  (표 29개, trips·itinerary_versions·itinerary_items 존재), itinerary.py:219 조건부 UPDATE.
★로컬 개발 DB 확인은 **검증 환경 적용 판정이 아니다**(C-23 의 증거 조건을 채우지 않았다).
"""
import argparse
import copy
import os
import sys

from docx import Document
from docx.shared import Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
SRC = os.path.join(FORMS, "w2", "제출본", "[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_2차_여행.docx")
OUT_DIR = os.path.join(FORMS, "w3", "데이터수집_여행")
OUT = os.path.join(OUT_DIR, "[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_3차_여행.docx")
#: 그림 스크립트가 읽는 본문판(그림은 2차 그대로). 제출물이 아니다.
TEXT_ONLY = os.path.join(OUT_DIR, "_중간", "DB설계서_3차_본문판.docx")
FIGURES = [os.path.join(OUT_DIR, "그림", name) for name in (
    "DB_적용상태_3차.png", "DB_ERD_전체_3차.png", "DB_ERD_여행핵심_3차.png")]
SUBMIT_DATE = "2026. 9. 18."
MAX_HEIGHT_SHARE = 0.8
LOCAL_DB = "로컬 개발 DB(acop_cs)에 표 존재 확인(2026-09-18, information_schema). 검증 환경·운영 적용은 미확인"


# ── 공통 도구 ─────────────────────────────────────────────────────────
def setc(cell, text):
    p = cell.paragraphs[0]
    for extra in list(cell.paragraphs)[1:]:
        extra._element.getparent().remove(extra._element)
    for r in list(p.runs)[1:]:
        r._element.getparent().remove(r._element)
    if not p.runs:
        p.add_run("")
    run = p.runs[0]
    run.text = text
    run.font.size = Pt(9) if run.font.size is None else run.font.size
    run.font.name = "맑은 고딕"


def set_paragraph_text(p, text):
    for r in list(p.runs)[1:]:
        r._element.getparent().remove(r._element)
    p.runs[0].text = text


def paragraph(doc, startswith):
    hits = [p for p in doc.paragraphs if p.text.strip().startswith(startswith)]
    if len(hits) != 1:
        raise LookupError(f"문단을 하나로 못 찾았다({len(hits)}): {startswith!r}")
    return hits[0]


def replace_in_paragraph(doc, startswith, old, new):
    p = paragraph(doc, startswith)
    if old not in p.text:
        raise LookupError(f"문구가 없다: {old!r}")
    set_paragraph_text(p, p.text.replace(old, new))


def table_with_header(doc, header):
    hits = [t for t in doc.tables if [c.text.strip() for c in t.rows[0].cells][:len(header)] == header]
    if len(hits) != 1:
        raise LookupError(f"표를 하나로 못 찾았다({len(hits)}): {header}")
    return hits[0]


def row_where(tbl, col, startswith):
    hits = [row for row in tbl.rows if row.cells[col].text.strip().startswith(startswith)]
    if len(hits) != 1:
        raise LookupError(f"행을 하나로 못 찾았다({len(hits)}): {startswith!r}")
    return hits[0]


def set_row(tbl, col, startswith, values):
    row = row_where(tbl, col, startswith)
    for j, value in enumerate(values):
        if value is not None:
            setc(row.cells[j], value)


def column_table(doc, name):
    """「테이블: <name> /」 문단 바로 뒤의 칼럼 정의 표와 그 문단."""
    body = list(doc.element.body.iterchildren())
    for i, block in enumerate(body):
        if block.tag.endswith("}p"):
            p = Paragraph(block, doc)
            if p.text.strip().startswith(f"테이블: {name} /"):
                for nxt in body[i + 1:]:
                    if nxt.tag.endswith("}tbl"):
                        return p, Table(nxt, doc)
    raise LookupError(f"칼럼 표를 못 찾았다: {name}")


def set_columns(tbl, rows):
    """칼럼 표의 데이터 행을 rows 로 바꾼다 — 모자라면 마지막 행을 복사하고, 남으면 지운다."""
    while len(tbl.rows) - 1 < len(rows):
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
    while len(tbl.rows) - 1 > len(rows):
        tr = tbl.rows[-1]._tr
        tr.getparent().remove(tr)
    for i, values in enumerate(rows, start=1):
        for j, value in enumerate(values):
            setc(tbl.rows[i].cells[j], value)


# ── 실제 DDL(014·016) ────────────────────────────────────────────────
TRIPS = [
    ("trip_id", "uuid", "O", "-", "O", "DEFAULT gen_random_uuid(). 여행 식별."),
    ("tenant_id", "text", "-", "-", "O", "소유 테넌트. 조회는 tenant_id 조건으로 한다(C-06)."),
    ("customer_id", "uuid", "-", "O", "O", "customers 참조."),
    ("title", "text", "-", "-", "O", "여행 제목."),
    ("locale", "text", "-", "-", "-", "고객 언어. 알림은 보낼 때 이 언어로 생성한다(결정 14). 언어 목록은 미리 정하지 않는다."),
    ("party_size", "int", "-", "-", "-", "인원."),
    ("latest_version", "int", "-", "-", "O", "DEFAULT 0. 최신 일정 버전 포인터. 새 버전은 latest_version = 기준 버전 조건으로만 올린다(C-05)."),
    ("status", "text", "-", "-", "O", "DEFAULT 'active'."),
    ("created_at", "timestamptz", "-", "-", "O", "DEFAULT now()."),
    ("constraints", "jsonb", "-", "-", "O", "DEFAULT '{}'. 여행 수준 조건(결제수단·식단 등). 2차의 trip_constraints 를 흡수(014)."),
    ("request_key", "text", "-", "-", "-", "등록 멱등 키(016). UNIQUE(tenant_id, request_key) WHERE request_key IS NOT NULL."),
    ("request_sha256", "text", "-", "-", "-", "등록 본문 해시(016). 같은 키에 다른 본문이 오면 409로 거부한다."),
]
VERSIONS = [
    ("trip_id", "uuid", "O", "O", "O", "trips 참조, ON DELETE CASCADE. 복합 PK(trip_id, version)."),
    ("version", "int", "O", "-", "O", "Trip 안의 버전 번호. 버전은 추가만 하고 고치지 않는다(C-04)."),
    ("tenant_id", "text", "-", "-", "O", "소유 테넌트."),
    ("reason", "text", "-", "-", "O", "created / auto_adjusted / customer_request / rollback 등 변경 이유."),
    ("cause_json", "jsonb", "-", "-", "O", "DEFAULT '[]'. 원인별 요약. 통지에 그대로 들어간다(§6-C-1)."),
    ("case_id", "uuid", "-", "-", "-", "이 버전을 적용한 Case(Case 버전 경로가 채운다). 선언된 FK는 없다."),
    ("created_at", "timestamptz", "-", "-", "O", "DEFAULT now()."),
]
ITEMS = [
    ("item_id", "uuid", "O", "-", "O", "버전 간 같은 항목의 식별자. 복합 PK(trip_id, version, item_id)."),
    ("trip_id", "uuid", "O", "O", "O", "복합 FK(trip_id, version)가 itinerary_versions를 참조, ON DELETE CASCADE."),
    ("version", "int", "O", "O", "O", "복합 PK·FK의 일부."),
    ("tenant_id", "text", "-", "-", "O", "색인(tenant_id, starts_at). 감시가 곧 시작할 항목을 이 색인으로 고른다."),
    ("seq", "int", "-", "-", "O", "일정 안의 순서."),
    ("kind", "text", "-", "-", "O", "activity / dining / mobility / lodging. 무료·무예약 활동도 포함."),
    ("title", "text", "-", "-", "O", "항목 제목."),
    ("place_id", "uuid", "-", "O", "-", "places 선택 참조. 이동 항목은 NULL."),
    ("starts_at", "timestamptz", "-", "-", "O", "시작 시각."),
    ("ends_at", "timestamptz", "-", "-", "-", "끝 시각."),
    ("locked", "boolean", "-", "-", "O", "DEFAULT false. 잠긴 항목 표시."),
    ("booking_id", "uuid", "-", "O", "-", "bookings 선택 참조. 무예약이면 NULL."),
    ("replaces_item_id", "uuid", "-", "-", "-", "대체 항목이 가리키는 원래 항목(§6-C-2). 지우고 새로 만드는 편법을 막는다."),
    ("detail", "jsonb", "-", "-", "O", "DEFAULT '{}'. 경로 후보·다른 안·고객 고정 표시·항목 수준 조건."),
]
ABSORBED = [
    ("constraints", "jsonb", "-", "-", "O", "trips의 칼럼(014). 여행 수준 조건. trips 한 행이라 버전별로 보존되지는 않는다."),
    ("detail", "jsonb", "-", "-", "O", "itinerary_items의 칼럼(014). 항목 수준 조건. 버전마다 항목과 함께 보존된다."),
]
PLACES_ATTRIBUTES = ("attributes", "jsonb", "-", "-", "O",
                     "014에서 추가. DEFAULT '{}'. 판정용 속성(실내 여부·영업시간·브레이크타임·결제수단·가격 등). "
                     "공급자마다 주는 속성이 달라 한 칸에 둔다.")


def edit_text(d) -> None:
    # 표지
    set_row(d.tables[1], 0, "제출 일자", [None, SUBMIT_DATE])

    # 머리말
    replace_in_paragraph(d, "정규화 수준:", "scope=trip/item 조건은 한 표에서 버전별로 보존한다.",
                         "여행 조건은 trips.constraints, 항목 조건은 itinerary_items.detail에 jsonb로 둔다"
                         "(별도 조건 표는 만들지 않았다).")
    replace_in_paragraph(d, "정규화 수준:", "현재 마이그레이션 001~013의 표는 26개(코어 14, 커머스 5, 여행 7)다.",
                         "현재 마이그레이션 001~016(015는 적용 보류)의 표는 29개(코어 14, 커머스 5, 여행 10)다.")
    replace_in_paragraph(d, "도구:", "기준일 2026-09-10, final_project_cs 저장소의 마이그레이션 001~013을 기준으로 한다.",
                         "기준일 2026-09-18, final_project_cs 저장소의 마이그레이션 001~016(015는 적용 보류)을 "
                         "기준으로 한다.")
    replace_in_paragraph(d, "도구:", "이번 확인은 앞의 두 단계와 적용 여부 미확인만 판정한다.",
                         "이번 확인은 앞의 두 단계와 적용 여부 미확인을 판정하고, 3차에서는 로컬 개발 DB에 표가 "
                         "실제로 있는지(information_schema)를 함께 적는다. 로컬 개발 DB 확인은 검증 환경 적용 판정이 "
                         "아니다.")

    # 2.1 엔터티 목록
    ent = table_with_header(d, ["구분", "테이블", "제약 대상"])
    set_row(ent, 0, "E-01", ["E-01 / 구현 파일 존재 (014·016)", None, "trip_id",
        "PK; 부분 UNIQUE(tenant_id, request_key); C-05",
        "여행 한 건의 정본. 최신 버전 포인터·고객 언어·인원·여행 조건·등록 멱등 키. " + LOCAL_DB +
        ". 근거: 마이그레이션 014·016; 구현계획서 v11 §4-B·§7-B."])
    set_row(ent, 0, "E-02", ["E-02 / 구현 파일 존재 (014)", None, "(trip_id, version)",
        "복합 PK; FK trips ON DELETE CASCADE; C-04",
        "여행의 적용 버전 한 건. 변경 이유와 원인 기록을 보존. " + LOCAL_DB + ". 근거: 마이그레이션 014; "
        "구현계획서 v11 §6-C·§7-B."])
    set_row(ent, 0, "E-03", ["E-03 / 구현 파일 존재 (014)", None, "(trip_id, version, item_id)",
        "복합 PK; 복합 FK → itinerary_versions; 색인(tenant_id, starts_at); C-04",
        "특정 일정 버전의 항목 한 건. 시각·장소·잠김·선택 예약·대체 대응·다른 안. " + LOCAL_DB +
        ". 근거: 마이그레이션 014; 구현계획서 v11 §5-D·§6-C-2·§7-B."])
    set_row(ent, 0, "E-04", ["E-04 / 흡수 (별도 표 없음)", None, "해당 없음", "해당 없음; C-10",
        "조건 표를 따로 만들지 않았다. 여행 조건은 trips.constraints, 항목 조건은 itinerary_items.detail"
        "(jsonb)에 둔다. 근거: 마이그레이션 014."])
    ws = row_where(ent, 0, "E-12")
    setc(ws.cells[4], ws.cells[4].text.strip() +
         " (3차 확인) 지금 일정 감시는 이 표 없이 일정 항목 표에서 앞으로 90분 안에 시작하는 항목을 직접 고른다.")

    # 2.2 관계
    rel = table_with_header(d, ["관계명", "주 엔터티", "종 엔터티"])
    set_row(rel, 0, "R-01", [None, None, None,
        "1 .. 0..N. 구현: itinerary_versions.trip_id FK → trips, ON DELETE CASCADE(014). 최신 버전 포인터는 "
        "trips.latest_version. C-04·05."])
    set_row(rel, 0, "R-02", [None, None, None,
        "1 .. 0..N. 구현: 복합 FK(trip_id, version) → itinerary_versions, ON DELETE CASCADE(014). C-04."])
    set_row(rel, 0, "R-03", [None, None, None,
        "1 .. 0..N. (제안) 조건 표를 따로 만들지 않고 trips.constraints로 흡수했다(014). C-10."])
    set_row(rel, 0, "R-04", [None, None, None,
        "0..1 .. 0..N. (제안) 조건 표를 따로 만들지 않고 itinerary_items.detail로 흡수했다(014). C-10."])
    set_row(rel, 0, "R-34", [None, None, None,
        "0..1 .. 0..N. 구현: itinerary_items.booking_id 선택 FK → bookings(014). 무예약 활동은 NULL. C-02·10."])
    set_row(rel, 0, "R-35", [None, None, None,
        "0..1 .. 0..N. 구현: itinerary_items.place_id 선택 FK → places(014). 이동 항목은 NULL. C-10."])

    # 3.1 테이블 정의서
    head, tbl = column_table(d, "trips")
    set_paragraph_text(head,
        "테이블: trips / E-01 / 여행 한 건의 정본. 최신 버전 포인터·고객 언어·인원·여행 조건·등록 멱등 키. "
        "상태: 구현 파일 존재(마이그레이션 014·016). " + LOCAL_DB + ". 2차 제안 가운데 사건 개정번호·재검토 "
        "상태·종료 시각·언어 판본은 아직 구현하지 않았다(제안으로 남음). 근거: 마이그레이션 014·016; "
        "구현계획서 v11 §4-B·§6-C-7·§7-B; 결정 14.")
    set_columns(tbl, TRIPS)
    head, tbl = column_table(d, "itinerary_versions")
    set_paragraph_text(head,
        "테이블: itinerary_versions / E-02 / 여행의 적용 버전 한 건. 변경 이유와 원인 기록을 보존. "
        "상태: 구현 파일 존재(마이그레이션 014). " + LOCAL_DB + ". 2차 제안의 decision_json·되돌림 출처 "
        "칼럼은 두지 않았고, 다른 안은 항목 detail에 둔다. 근거: 마이그레이션 014; 구현계획서 v11 §6-C·§7-B.")
    set_columns(tbl, VERSIONS)
    head, tbl = column_table(d, "itinerary_items")
    set_paragraph_text(head,
        "테이블: itinerary_items / E-03 / 특정 일정 버전의 항목 한 건. 시각·장소·잠김·선택 예약·대체 대응. "
        "상태: 구현 파일 존재(마이그레이션 014). " + LOCAL_DB + ". 2차 제안의 비용·통화 칼럼은 아직 없다"
        "(제안으로 남음). 근거: 마이그레이션 014; 구현계획서 v11 §5-D·§6-C-2·§7-B.")
    set_columns(tbl, ITEMS)
    head, tbl = column_table(d, "trip_constraints")
    set_paragraph_text(head,
        "테이블: trip_constraints / E-04 / 흡수(별도 표 없음). 2차가 제안한 조건 표는 만들지 않았다. 여행 "
        "조건은 trips.constraints, 항목 조건은 itinerary_items.detail(jsonb)에 둔다(014). 아래는 그 두 칼럼이다. "
        "여행 수준 조건은 버전별로 보존되지 않아 2차의 버전별 보존 요구와 다르다(제안으로 남음). "
        "근거: 마이그레이션 014; 구현계획서 v11 §7-B.")
    set_columns(tbl, ABSORBED)
    head, tbl = column_table(d, "places")
    set_paragraph_text(head, head.text.replace("013 공급자 식별자 추가.", "013 공급자 식별자 추가, 014 판정용 속성 추가."))
    if not any(row.cells[0].text.strip() == "attributes" for row in tbl.rows):
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
        for j, value in enumerate(PLACES_ATTRIBUTES):
            setc(tbl.rows[-1].cells[j], value)

    # 3.2 제약·조회
    rules = table_with_header(d, ["적용 레벨"])
    set_row(rules, 1, "C-04", [None, None, None,
        "적용 버전은 수정하거나 덮어쓰지 않고 새 버전으로만 추가한다. 구현: itinerary_versions PK(trip_id, "
        "version)와 항목 복합 PK로 버전을 쌓는다(014). 되돌림도 옛 버전 내용을 담은 새 버전으로 만든다. "
        "(제안으로 남음) 앱 역할의 UPDATE·DELETE 권한 제거는 아직 하지 않았다. 구현 파일 존재, DoD-1·8·9."])
    set_row(rules, 1, "C-05", [None, None, "trips.latest_version",
        "v11 §6-C-7. 구현(단순판): 새 버전은 trips.latest_version = 기준 버전 조건의 UPDATE로만 올리고, 영향 "
        "행이 0이면 거부한다. Case 버전에서는 적용기가 이를 충돌로 올려 적용 전체를 되돌리고 Case를 사람에게 "
        "넘긴다. 시나리오용 직접 경로는 그 계산을 버린다. (제안으로 남음) "
        "사건 개정번호(incident_revision)와 충돌 시 1회 재계산은 아직 없다. 구현 파일 존재."])
    set_row(rules, 1, "Q-01", [None, None, None,
        "구현: trips.latest_version으로 최신 버전과 그 항목을 읽어 계획서 링크(/plan/{trip_id})와 여행 조회 "
        "API에 준다. 알림을 못 봐도 링크가 최신 상태를 보여 준다(DoD-25). 페이지 크기·p95·동시성 부하 시험은 "
        "미실행."])

    # 변경 이력
    hist = table_with_header(d, ["변경일", "변경자"])
    tbl_rows = hist.rows
    new = copy.deepcopy(tbl_rows[-1]._tr)
    tbl_rows[-1]._tr.addnext(new)
    for j, value in enumerate((
            "2026-09-18", "전체",
            "저장소·DB 실측으로 갱신: Trip·일정 버전·일정 항목을 구현 파일 존재(014·016)로 바꾸고 표 정의를 실제 "
            "칼럼으로 교체, 조건 표는 jsonb 흡수로 정리, places.attributes 추가, 불변 버전·동시성·최신 계획서 "
            "조회의 구현 범위와 남은 제안을 구분",
            "E-01~E-05·E-12, R-01~R-04·R-34·R-35, C-04·C-05·Q-01", "3차")):
        setc(hist.rows[-1].cells[j], value)


def replace_figures(doc) -> None:
    from PIL import Image

    shapes = list(doc.inline_shapes)
    if len(shapes) != len(FIGURES):
        raise SystemExit(f"그림 수가 다르다: 문서 {len(shapes)} · 새 그림 {len(FIGURES)}")
    section = doc.sections[0]
    max_height = int((section.page_height - section.top_margin - section.bottom_margin) * MAX_HEIGHT_SHARE)
    for shape, path in zip(shapes, FIGURES):
        if not os.path.exists(path):
            raise SystemExit(f"그림이 없다 — make_vis_db_3차_여행.py 를 먼저 돌린다: {path}")
        rid = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
        with open(path, "rb") as f:
            doc.part.related_parts[rid]._blob = f.read()
        w, h = Image.open(path).size
        width = shape.width
        height = int(width * h / w)
        if height > max_height:
            height, width = max_height, int(max_height * w / h)
        shape.width, shape.height = width, height


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-only", action="store_true", help="그림 없이 본문판만 만든다")
    args = parser.parse_args()
    d = Document(SRC)
    edit_text(d)
    if args.text_only:
        os.makedirs(os.path.dirname(TEXT_ONLY), exist_ok=True)
        d.save(TEXT_ONLY)       # ★중간 산출물 — 매번 다시 만든다(제출물 아님)
        print("본문판:", TEXT_ONLY)
        return
    replace_figures(d)
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(OUT):
        raise SystemExit(f"이미 있다 — 덮어쓰지 않는다. 먼저 _backup/ 으로 옮긴다: {OUT}")
    d.save(OUT)
    print("저장:", OUT)


if __name__ == "__main__":
    main()
