# -*- coding: utf-8 -*-
"""DB·저장소 설계 문서 본문: 템플릿 합의본 반영.

기준일: 2026-09-10.
확인 범위: 로컬 작업트리의 문서·SQL·Python·DOCX 정적 확인.
DB 접속, 마이그레이션 적용, 빌드 및 저장은 이번 검토에서 실행하지 않았다.
기존 양식 로드·셀 채우기·블록 복제·표지 수정·저장·재시도 처리를 유지한다.
"""
import copy
import hashlib
import os
import sys

from docx import Document
from docx.shared import Pt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
SRC = os.path.join(FORMS, "[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx")
OUT = os.path.join(FORMS, "[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_2차_여행.docx")
ROOT = os.path.dirname(os.path.dirname(FORMS))

REVISION = "85ba4bcea308db4f0a7c1aee0487e28c9393b16c"
CHECKED_AT = "2026-09-10"
DBDIR = "final_project_cs/app/infrastructure/db/migrations/"
APPDIR = "final_project_cs/app/"
PLAN = "program/plan/A-COP_구현계획서_v11.md"
SCENARIO = "team_branch/jh/확정_시나리오.md"
MAPPING = "program/plan/A-COP_확정시나리오_설계대응.md"
AGREEMENT = "program/산출물양식/w2/템플릿/템플릿_합의본.md"
TEMPLATE = "program/산출물양식/w2/템플릿/DB저장소설계서_템플릿_코덱스.md"
OPEN_REGISTER = "program/산출물양식/w2/기획서/기획서_병합본_코덱스_1차.md:469"

# HEAD와 작업트리가 다르므로 확인한 파일 바이트도 고정한다.
# 특히 010~013 및 watch.py는 확인 당시 미추적 파일이었다.
EVIDENCE_HASHES = {
    DBDIR + "001_schema.sql":
        "212c73f697666972561ea41cc79b768b6715605bb8a2c7ea7e45dfbb262c8b66",
    DBDIR + "003_outbox_tenant_scoped_dedupe.sql":
        "7d24f21d8710b1a453827ac58be7ac789da0e0075441c5b8c430dd167f2bcec1",
    DBDIR + "005_outbox_resolution.sql":
        "e8963df3fa296f139256585cc6f4791f10ea2738cae092578851662c39e007fe",
    DBDIR + "010_domain_travel.sql":
        "73c98f0c9fa05f0d8934b012df40be9b9bb220c95c8e559178445f186cd19cbb",
    DBDIR + "011_place_catalog.sql":
        "7a8e4deaad45a39f05e52d4160068dea9196f441a9ba46f65352b6838123e4bf",
    DBDIR + "012_watch_observations.sql":
        "07075b3f3fcc758c36176827b9c72a57bfaa7d2c078a5c79b19f3a92bc58a719",
    DBDIR + "013_places_source_identity.sql":
        "30d0930b6ea128ef60c38ef715627905ded32cd70a6c544c2cb6741229fbe395",
    APPDIR + "modules/travel_ops/watch.py":
        "ff50d943bb5fc4aad69bb430805557bafcf417fa5a50764547111696b8d0f0ab",
    APPDIR + "tools/read_tools.py":
        "ff305c82bb76147208825ae27a3e02d0be25f437a86c6015c66b59b43e1295f8",
    APPDIR + "application/controller.py":
        "034d59d5e2003ac0c318ff62b8c6df3e2d79bf699aa7ad483a789bc59fcc368a",
    APPDIR + "core/transition.py":
        "e16462a3257161cc73709b4f919be68ab805a66fafd585c2aa8c3af62c80227c",
    APPDIR + "modules/travel_ops/verification_policy.py":
        "d5a53cfbbd30b7191ab1ea9a3c1774a50c90ab82fbc45a5e132b487d49dea9c5",
    PLAN:
        "183630568299f7b0ed26d7bff89855b693e79c9d97542c53e2a2685a9f923909",
    SCENARIO:
        "9fdfbf15260c32125776ca9be9620e4ee31e6cbbb7e41e8c9555ddea22b9773c",
    MAPPING:
        "a02fe9459cd16a3636a8308f0731f0bacf202c0387662e1502b21d2e2743a30f",
}

for relative, expected in EVIDENCE_HASHES.items():
    with open(os.path.join(ROOT, relative), "rb") as evidence_file:
        actual = hashlib.sha256(evidence_file.read()).hexdigest()
    if actual != expected:
        print("  경고: 근거 파일이 바뀌었다(16:09 v11 결정 14·15) — " + relative)

d = Document(SRC)
T = d.tables

# 필요한 가드: 양식 질문·머리글·병합을 내용 갱신과 분리한다.
if len(T) != 8:
    raise ValueError("원본 양식은 표 8개여야 한다.")

EXPECTED_HEADERS = {
    3: ("구분", "테이블", "제약 대상", "제약 유형", "주요 속성"),
    4: ("관계명", "주 엔터티", "종 엔터티", "관계"),
    5: ("컬럼명", "타입", "PK", "FK", "Not Null", "제약 조건 설명"),
    6: ("적용 레벨", "제약 유형", "대상", "설명 및 관리 방안"),
    7: ("변경일", "변경자", "변경내용", "영향 받는 항목", "비고"),
}
for index, expected in EXPECTED_HEADERS.items():
    if tuple(c.text.strip() for c in T[index].rows[0].cells) != expected:
        raise ValueError("양식 머리글 불일치: 표 " + str(index))

QUESTION_LABELS = tuple(r.cells[0].text for r in T[1].rows)
HEADER_XML = {index: T[index].rows[0]._tr.xml for index in range(2, 8)}
COVER_MERGES = tuple(
    tuple(x.xml for x in table._tbl.xpath(".//w:gridSpan | .//w:vMerge"))
    for table in T[:2]
)
FORBIDDEN = frozenset(
    chr(code)
    for code in (
        0x2014, 0x2013, 0x2192, 0x21D2, 0x2605, 0x2606,
        0x2713, 0x2714, 0x2715, 0x2717, 0x25B8, 0x2026,
        0x21C4, 0x2460, 0x2461, 0x2462, 0x2463, 0x2464,
        0x2465, 0x2212,
    )
)


def check_text(text):
    if not isinstance(text, str):
        raise TypeError("DOCX 본문은 문자열이어야 한다.")
    bad = sorted(set(text) & FORBIDDEN)
    if bad:
        raise ValueError(
            "DOCX 금지 문자: " + ", ".join("U+%04X" % ord(c) for c in bad)
        )


def setc(cell, text, bold=False):
    check_text(text)
    p = cell.paragraphs[0]
    # 첫 문단의 서식을 살리고 뒤에 남은 양식 예시 문단은 제거한다.
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


def grow(tbl, need):
    while len(tbl.rows) - 1 < need:
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))


def shrink(tbl, keep):
    while len(tbl.rows) - 1 > keep:
        tbl._tbl.remove(tbl.rows[-1]._tr)


def fill(tbl, rows, start=1):
    grow(tbl, start - 1 + len(rows))
    shrink(tbl, start - 1 + len(rows))
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            if j < len(tbl.columns):
                setc(tbl.rows[start + i].cells[j], v)


def settext(para, text, bold=False):
    check_text(text)
    for r in list(para.runs)[1:]:
        r._element.getparent().remove(r._element)
    if not para.runs:
        para.add_run("")
    para.runs[0].text = text
    para.runs[0].bold = bold


# 내용 데이터. I는 구현 파일 존재, P는 이번 본문의 물리 설계 제안이다.
# E·R·C·Q·M·DB ID는 행 순서에서 생성하지 않는다.
IMPLEMENTED = (
    "[구현] 범위=DDL; 구현 파일 존재 / 적용 여부 미확인. "
    "[미확보] 검증·운영 환경 적용 증거=U-상태. "
    "검증 결과=DB 실행·연동 시험 미실행. [실측 정적 확인]"
)
PROPOSED = (
    "[제안] 물리 설계 / 설계만 존재. "
    "[미구현] 확인한 migrations/의 해당 DDL·제약; "
    "마이그레이션 미배정. 검증 결과=미실행; U-상태"
)
STATE = {"I": IMPLEMENTED, "P": PROPOSED}

# ID, 테이블, 상태, 식별자, 제약, 한 건의 의미·주요 속성, 근거, 구현 작업
ENTITIES = [
    ("E-01", "trips", "P", "trip_id", "PK 제안; C-05",
     "여행 한 건의 정본. 최신 버전·사건 개정번호·재검토 상태·고객 선택 언어·종료 시각.",
     PLAN + " §4-B·§6-C-7·§7-B; 결정 11", "DB-01"),
    ("E-02", "itinerary_versions", "P", "(trip_id, version_no)", "복합 PK 제안; C-04",
     "여행의 적용 버전 한 건. 생성·조정·되돌림 이유와 당시 조건·근거·다른 안을 보존.",
     PLAN + " §6-C·§7-B", "DB-01"),
    ("E-03", "itinerary_items", "P", "(trip_id, version_no, item_id)", "복합 PK 제안; C-04",
     "특정 일정 버전의 항목 한 건. 시작·끝·장소·비용·잠김·선택 예약과 대체 대응.",
     PLAN + " §5-D·§6-C-2·§7-B", "DB-01"),
    ("E-04", "trip_constraints", "P", "(trip_id, version_no, constraint_id)", "복합 PK 제안; C-10",
     "버전별 조건 한 건. scope=trip/item으로 여행·항목 조건을 함께 보존하는 가칭 표.",
     PLAN + " §7-B 조건 보존", "DB-01"),
    ("E-05", "places", "I", "place_id", "PK; UNIQUE(tenant_id, name, kind); C-14",
     "예약이 참조하는 내부 장소 한 건. 영업 확인·식단·좌표; 013 공급자 식별자 추가.",
     DBDIR + "010_domain_travel.sql:16; 013_places_source_identity.sql:9", "DB-02"),
    ("E-06", "bookings", "I", "booking_id", "PK; UNIQUE(tenant_id, booking_no); C-14",
     "우리 예약 한 건. 고객·선택 장소·시작·인원·금액·잠김. Trip·항목 FK는 없음.",
     DBDIR + "010_domain_travel.sql:38", "DB-02"),
    ("E-07", "supplier_bookings", "I", "supplier_booking_id",
     "PK; UNIQUE(tenant_id, supplier, supplier_ref); C-14",
     "공급자가 기록한 예약 한 건. 우리 예약과 다른 상태를 그대로 보존하여 대조.",
     DBDIR + "010_domain_travel.sql:59", "DB-02"),
    ("E-08", "place_catalog", "I", "catalog_id",
     "PK; UNIQUE(tenant_id, source, content_id); C-14",
     "공급자 장소 한 건의 수집본. 내부 장소 정본과 분리; 수정 시각과 수집 시각을 구별.",
     DBDIR + "011_place_catalog.sql:13", "DB-02"),
    ("E-09", "source_sync_state", "I", "sync_id",
     "PK; UNIQUE(tenant_id, source, scope); C-14",
     "출처·수집 범위 하나의 진행 상태. 다음 페이지·델타 신뢰·오류·재개 위치.",
     DBDIR + "011_place_catalog.sql:39", "DB-02"),
    ("E-10", "watch_observations", "I", "observation_id",
     "PK; UNIQUE(tenant_id, target_kind, target_id, observed_at); C-15",
     "대상 관측 한 건. fingerprint와 payload 보존. 출처별 비교·확장 지문은 별도 제안.",
     DBDIR + "012_watch_observations.sql:16", "DB-03"),
    ("E-11", "watch_changes", "I", "change_id", "PK; C-15",
     "관측 차이 한 건. 전후 값·요약·영향 예약·통지 오류. Trip·Case·관측 FK는 없음.",
     DBDIR + "012_watch_observations.sql:37", "DB-03"),
    ("E-12", "watch_schedule", "P", "schedule_id",
     "PK; UNIQUE(tenant_id, trip_id, source, target_kind, target_id) 제안; C-12",
     "여행에 걸린 감시 대상 하나의 다음 확인 작업. 안내 시점은 E-22로 분리.",
     PLAN + " §6-A·§7-B", "DB-03"),
    ("E-13", "customer_cases", "I", "case_id", "PK; version 조건부 갱신; C-01",
     "고객 지원 Case 한 건의 현재 상태. 기존 코어 승계; Trip 연결은 E-21의 제안 관계.",
     DBDIR + "001_schema.sql:13", "DB-04"),
    ("E-14", "case_events", "I", "event_id",
     "PK; UNIQUE(case_id, aggregate_version); C-01",
     "Case 상태 전이 한 건. 순번 중복 방지와 소비 순서 계약을 구별.",
     DBDIR + "001_schema.sql:14", "DB-04"),
    ("E-15", "action_requests", "I", "action_id",
     "PK; UNIQUE(tenant_id, idempotency_key); C-02",
     "실행 또는 접수 요청 한 건. 대상별 멱등 재료는 변경 제안이며 현 controller는 Case 기준.",
     DBDIR + "001_schema.sql:17; " + APPDIR + "application/controller.py:374", "DB-04"),
    ("E-16", "outbox", "I", "message_id",
     "PK; UNIQUE(tenant_id, topic, dedupe_key); C-03",
     "외부로 보낼 메시지 한 건. 003 테넌트별 중복 방지와 005 결과 불명 해소 메타데이터.",
     DBDIR + "001_schema.sql:19; 003_outbox_tenant_scoped_dedupe.sql:12; 005_outbox_resolution.sql:3", "DB-05"),
    ("E-17", "evidences", "P", "evidence_id", "PK 제안; C-17",
     "판정 근거 한 건. 출처·대상·관측 시각·수집 시각·자료 성격·원문 식별을 보존하는 가칭 표.",
     "기존 build_DB설계서_v2.py:141; " + PLAN + " §4-D", "DB-03"),
    ("E-18", "suppliers", "P", "supplier_id", "PK 제안; C-09",
     "실행 상대 업체 한 건. 실제 업체와 simulated 시연 상대를 구별하는 가칭 표.",
     "기존 build_DB설계서_v2.py:141·364; " + PLAN + " §4-C", "DB-06"),
    ("E-19", "delegation_scopes", "P", "delegation_id", "PK 제안; C-09",
     "여행에 대한 위임 한 건. 허용 작업·금액 상한·유효기간·철회 기록을 보존하는 가칭 표.",
     "기존 build_DB설계서_v2.py:141·364; " + PLAN + " §12 DoD-18·19", "DB-06"),
    ("E-20", "booking_actions", "P", "booking_action_id", "PK 제안; C-09",
     "업체 실행·보상 시도 한 건. 요청·예약·위임·결과 불명·보상 실패를 추적하는 가칭 표.",
     "기존 build_DB설계서_v2.py:141·364; " + PLAN + " §12 DoD-20·21", "DB-06"),
    ("E-21", "change_requests", "P", "change_request_id",
     "PK; UNIQUE(tenant_id, request_id) 제안; C-18",
     "사건 또는 재요청 접수 한 건. 고객·시스템 시작, 원인, Trip·항목·묶음 Case와 선택 이력.",
     "기존 build_DB설계서_v2.py:141; " + PLAN + " §6-C; " + MAPPING + " §2·§4", "DB-04"),
    ("E-22", "notifications", "P", "notification_id",
     "PK; 변경 버전·안내 발생 단위별 UNIQUE 제안; C-03·C-11",
     "변경 통지 또는 예정 안내 한 건. 출발 역산·언어·무효화·outbox 연결·발행 기록.",
     "기존 build_DB설계서_v2.py:141; " + PLAN + " §6-B·§6-C-6; 결정 10·11", "DB-05"),
]
ENTITY_BY_NAME = {row[1]: row for row in ENTITIES}

# 기존 코어 중 이번 문서에서 컬럼을 재작성하지 않는 객체도 상태를 개별 기록한다.
# 전체 명세는 체크섬으로 고정한 001_schema.sql의 객체 선언을 따른다.
CORE_REFERENCES = [
    ("E-23", "tenants", "tenant_id", "11", "테넌트 한 건. 고객의 소유 경계."),
    ("E-24", "customers", "customer_id", "12", "고객 한 건. tenant_id·external_id로 외부 고객 식별."),
    ("E-25", "agent_runs", "run_id", "15", "Case의 에이전트 실행 한 건."),
    ("E-26", "team_tasks", "task_id", "16", "실행에 속한 Team 작업 한 건."),
    ("E-27", "action_approvals", "approval_id", "18", "실행 요청에 대한 승인 판단 한 건."),
    ("E-28", "prompts", "prompt_id", "20", "프롬프트 판본 한 건."),
    ("E-29", "llm_calls", "call_id", "21", "모델 호출 한 건. 토큰·지연·비용 기록."),
    ("E-30", "knowledge_documents", "document_id", "22", "지식 원문 판본 한 건."),
    ("E-31", "knowledge_chunks", "chunk_id", "23", "원문에 속한 청크 한 건. vector(1536)."),
    ("E-32", "feedback_analytics_reports", "report_id", "24", "테넌트의 기간별 분석 보고서 한 건."),
]

# 1. 모델링 방법: 기존 질문 문단을 유지한다.
P = d.paragraphs
settext(P[7],
    "모델링 방법 : [결정] v11 §0-4 결정 1~13과 §6-A~§6-C를 기준으로 한다. "
    "Trip은 여행 전체의 현재 상태, 일정 버전은 적용한 계획의 불변 이력, 항목은 예약 유무와 "
    "무관한 수행 단위, Case는 사건 처리 단위다. 관측은 확인한 값이고 변화는 직전 값과의 차이다. "
    "시스템 감시와 고객 신고를 분리해 접수하고 같은 스윕·같은 Trip의 원인은 한 Case에 묶는다. "
    "최신 계획서 링크는 Trip의 최신 포인터를 읽는 정본 접점이며 읽기·재요청을 제공한다. "
    "변경 시 버전·포인터·Case·발행 의도를 함께 저장하고, 종료 뒤 새 감시·안내는 만들지 않는다. "
    "[제안] 쓰기는 Trip 서비스·감시 작업자·배달 작업자로 나누고 E-01~E-22의 물리 구조로 연결한다. "
    "[결정] 서울 1도시·최대 7일·4인 팀당 49,000원 VAT 포함. 직접 링크·알림은 고객 선택 언어로 "
    "우리가 보낼 때 그 언어로 생성하며 언어 목록을 미리 정하지 않는다. 같은 문구틀·같은 언어는 처음 한 번 생성하고 재사용한다. API 경로의 번역은 에이전트가 담당한다.")

settext(P[8],
    "정규화 수준 : [제안] 식별자에 종속된 여행·버전·항목·예약·공급자 원장을 분리하여 3NF를 목표로 한다. "
    "자연키는 테넌트 안의 예약번호·공급자 식별자를 사용하고 내부 참조는 UUID로 통일한다. "
    "scope=trip/item 조건은 한 표에서 버전별로 보존한다. 판정 JSON은 당시 근거와 대안을 재현하는 "
    "스냅샷 예외이며 현재 사실의 정본으로 재사용하지 않는다. [결정] 코어 14표를 승계하고 "
    "orders·order_items·products·returns·shipments의 도메인 역할을 여행 모델로 전환한다. "
    "[실측 정적 확인] 010은 커머스 표를 삭제하지 않고 여행 표를 추가한다. 19는 현재 전체 표 수가 아니다. "
    "RAG 원문·청크 구조는 승계하되 내용은 여행 규정으로 교체한다. 장소 카탈로그·예약 장소·공급자 원장은 "
    "서로 다른 소유와 갱신 주체를 가지므로 병합하지 않는다.")

settext(P[9],
    "도구 : PostgreSQL 16 기준 설계, SQL 마이그레이션·pydantic 계약·python-docx. "
    "[실측 정적 확인] 001은 pgcrypto·vector 확장을 선언한다. 실제 서버 버전·확장 설치·search_path는 "
    "[미확보] U-상태다. 기준일 " + CHECKED_AT + ", HEAD " + REVISION + "의 로컬 작업트리를 열람했다. "
    "010~013·watch.py는 미추적, read_tools.py는 수정 상태였으므로 HEAD만으로 재현되지 않는다. "
    "M-02 이후의 파일 SHA-256을 함께 따른다. 표의 이름은 DDL의 비한정 이름이며 실제 스키마명은 U-상태다. "
    "공통 표시는 합의본 §1을 따른다. [실측 정적 확인]은 [실측]의 확인 방식이 정적 확인이라는 뜻이다. "
    "DB 보조 축은 설계만 존재 / 구현 파일 존재 / 검증 환경 적용 / 운영 적용 / 적용 여부 미확인이다. "
    "이번 확인은 앞의 두 단계와 적용 여부 미확인만 판정한다. 실행·운영·성능 검증은 미실행이다. "
    "컬럼 표의 O는 해당 제약, -는 [해당 없음] 해당 제약 없음이며 NULL 허용과 미확보를 구별한다. "
    "미결정 공통 ID는 " + OPEN_REGISTER + "에 연결한다.")

# 2.1 엔터티 목록
entity_rows = [
    (
        eid + " / " + STATE[stage],
        name,
        key,
        constraints,
        meaning + " 근거: " + source + ". 작업 " + task + ".",
    )
    for eid, name, stage, key, constraints, meaning, source, task in ENTITIES
]
for eid, name, key, line, meaning in CORE_REFERENCES:
    entity_rows.append((
        eid + " / " + IMPLEMENTED,
        name,
        key,
        "PK; 전체 제약은 고정 DDL 참조",
        meaning + " 컬럼 정의 범위 제외: 여행 전환 변경이 없는 코어 구조의 중복 전사를 피한다. "
        "전체 명세 " + DBDIR + "001_schema.sql:" + line +
        "; M-02의 체크섬 기준. E-25의 후속 제약 004는 M-06에서 별도 대조한다.",
    ))
fill(T[3], entity_rows)

# 2.2 관계. FK, 논리 참조, 다형 참조를 구별한다.
# ID, 주체, 종속, ERD 표식, 관계 설명
RELATIONS = [
    ("R-01", "E-01 trips", "E-02 itinerary_versions", "1 .. 0..N",
     "[제안] 각 버전의 Trip은 필수. 생성 중 Trip은 버전 0건 허용. 현재 포인터는 검증 후 설정. C-04·05."),
    ("R-02", "E-02 itinerary_versions", "E-03 itinerary_items", "1 .. 0..N",
     "[제안] 복합 FK(trip_id, version_no). 적용 버전은 앱에서 최소 한 항목 검사. C-04."),
    ("R-03", "E-02 itinerary_versions", "E-04 trip_constraints", "1 .. 0..N",
     "[제안] 버전 복합 FK 필수. 조건 없음은 0건이며 미확인 조건 삭제를 뜻하지 않는다. C-10."),
    ("R-04", "E-03 itinerary_items", "E-04 trip_constraints", "0..1 .. 0..N",
     "[제안] scope=item일 때만 ref_id를 항목으로 해석하는 다형 참조. 동일 버전·여행을 앱에서 검사. C-10."),
    ("R-05", "E-24 customers", "E-06 bookings", "1 -- 0..N",
     "[실측 정적 확인] 010:41 customer_id 필수 FK. 고객 삭제·키 변경은 별도 CASCADE 선언 없음. C-14."),
    ("R-06", "E-05 places", "E-06 bookings", "0..1 -- 0..N",
     "[실측 정적 확인] 010:42 place_id 선택 FK. 장소 없는 예약 허용. C-14."),
    ("R-07", "E-06 bookings", "E-07 supplier_bookings", "1 -- 0..N",
     "[실측 정적 확인] 010:62 booking_id 필수 FK. 원장 상태 차이는 대조 대상이며 자동 덮어쓰기 금지. C-14."),
    ("R-08", "E-08 place_catalog", "E-05 places", "0..1 .. 0..N",
     "[제안] 테넌트·출처·content_id의 논리 대응. [실측 정적 확인] 011·013에 연결 FK 없음. C-14."),
    ("R-09", "E-09 source_sync_state", "E-08 place_catalog", "0..N .. 0..N",
     "[제안] 출처·수집 scope로 묶는 작업 범위이며 DB FK나 소유 관계가 아니다. C-17."),
    ("R-10", "E-05 places", "E-10 watch_observations", "0..1 .. 0..N",
     "[실측 정적 확인] 012의 target_kind·target_id는 논리 식별. 장소 외 대상도 허용하며 FK 없음. C-15."),
    ("R-11", "E-10 watch_observations", "E-11 watch_changes", "0..N .. 0..N",
     "[실측 정적 확인] 012에 observation_id FK 없음. [제안] 전후 관측은 E-17 근거 참조로 연결. C-15."),
    ("R-12", "E-01 trips", "E-12 watch_schedule", "1 .. 0..N",
     "[제안] Trip 필수 FK. 감시 종료 시 행을 삭제하지 않고 state=stopped로 남긴다. C-12."),
    ("R-13", "E-01 trips", "E-21 change_requests", "1 .. 0..N",
     "[제안] 사건·재요청은 Trip 필수 참조. 수신 순서·사건 발생 시각을 따로 보존. C-18."),
    ("R-14", "E-13 customer_cases", "E-21 change_requests", "0..1 .. 0..N",
     "[제안] 접수 후 Case 연결 전 NULL 허용. 한 스윕·한 Trip의 사건 여럿이 한 Case를 참조. C-18."),
    ("R-15", "E-13 customer_cases", "E-14 case_events", "1 -- 0..N",
     "[실측 정적 확인] 001:14 필수 FK. UNIQUE는 같은 순번만 막는다. 삭제·키 변경 C-14, 소비 C-16."),
    ("R-16", "E-13 customer_cases", "E-15 action_requests", "1 -- 0..N",
     "[실측 정적 확인] 001:17 case_id 필수 FK. 다른 대상 요청의 키 분리는 C-02 제안."),
    ("R-17", "E-13 customer_cases", "E-16 outbox", "0..1 .. 0..N",
     "[실측 정적 확인] 001:19 Case FK 없음. payload 연결이며 일정 안내는 Case 없이 발행. C-03·11."),
    ("R-18", "E-01 trips", "E-22 notifications", "1 .. 0..N",
     "[제안] 여행 필수 FK. 버전·종류·안내 발생 단위별 기록을 남긴다. C-03·11."),
    ("R-19", "E-22 notifications", "E-16 outbox", "0..1 .. 0..1",
     "[제안] E-22.message_id 선택 FK·UNIQUE. 발행 전에는 outbox가 없고 일반 outbox는 알림 표 없이 존재. C-03."),
    ("R-20", "E-21 change_requests", "E-17 evidences", "1 .. 0..N",
     "[제안] 사건별 근거 행. 동일 원문을 공유할 때 원문 식별·체크섬은 같아도 사건 귀속은 각각 보존. C-17·18."),
    ("R-21", "E-18 suppliers", "E-20 booking_actions", "1 .. 0..N",
     "[제안] 실행 상대 필수 FK. supplier_bookings.supplier 텍스트와의 확정 대응은 별도 확인. C-09."),
    ("R-22", "E-19 delegation_scopes", "E-20 booking_actions", "0..1 .. 0..N",
     "[제안] 위임 실행이면 유효한 위임 필수, 승인 실행은 해당 승인 참조. 철회 후 실행 금지. C-09."),
    ("R-23", "E-06 bookings", "E-20 booking_actions", "1 .. 0..N",
     "[제안] 예약 필수 FK. 실행·보상 시도는 각각 이력으로 남긴다. C-09."),
    ("R-24", "E-01 trips", "E-19 delegation_scopes", "1 .. 0..N",
     "[제안] 동일 고객·테넌트 여행의 위임만 허용. 종료·철회는 효력 종료이며 이력 삭제가 아니다. C-09."),
    ("R-25", "E-23 tenants", "E-24 customers", "1 -- 0..N",
     "[실측 정적 확인] 001:12 tenant_id 필수 FK. 다른 표의 tenant_id 전부에 FK가 있다는 뜻은 아니다. C-14."),
    ("R-26", "E-24 customers", "E-13 customer_cases", "1 -- 0..N",
     "[실측 정적 확인] 001:13 customer_id 필수 FK. tenant_id 일치는 별도 앱 검사. C-06·14."),
    ("R-27", "E-13 customer_cases", "E-25 agent_runs", "1 -- 0..N",
     "[실측 정적 확인] 001:15 Case 필수 FK. 실행 활성 유일성의 후속 변경 004는 M-06 대상."),
    ("R-28", "E-25 agent_runs", "E-26 team_tasks", "1 -- 0..N",
     "[실측 정적 확인] 001:16 run_id 필수 FK. Team·계약 버전 보존. C-14."),
    ("R-29", "E-15 action_requests", "E-27 action_approvals", "1 -- 0..N",
     "[실측 정적 확인] 001:18 action_id 필수 FK. 승인 결과와 실행 결과를 구별. C-09·14."),
    ("R-30", "E-28 prompts", "E-29 llm_calls", "1 -- 0..N",
     "[실측 정적 확인] 001:21 prompt_id 필수 FK. 호출 당시 프롬프트 판본 보존. C-17."),
    ("R-31", "E-25 agent_runs", "E-29 llm_calls", "0..1 -- 0..N",
     "[실측 정적 확인] 001:21 run_id 선택 FK. 모델 호출 비용과 여행 전체 비용은 다르다. C-13."),
    ("R-32", "E-30 knowledge_documents", "E-31 knowledge_chunks", "1 -- 0..N",
     "[실측 정적 확인] 001:23 document_id 필수 FK, document_id·chunk_no UNIQUE. C-17·20."),
    ("R-33", "E-23 tenants", "E-32 feedback_analytics_reports", "1 .. 0..N",
     "[실측 정적 확인] 001:24 tenant_id는 text이며 FK 선언 없음. 동일 테넌트 기간별 UNIQUE. C-14."),
    ("R-34", "E-06 bookings", "E-03 itinerary_items", "0..1 .. 0..N",
     "[제안] booking_id 선택 FK. 무예약 활동은 NULL이며 다른 고객 예약으로 대체하지 않는다. C-02·10."),
    ("R-35", "E-05 places", "E-03 itinerary_items", "0..1 .. 0..N",
     "[제안] place_ref 선택 FK. 장소 미확인 상태와 장소가 불필요한 항목은 별도 사유로 기록. C-10."),
]
fill(T[4], [
    (rid, parent, child, cardinality + ". " + meaning)
    for rid, parent, child, cardinality, meaning in RELATIONS
])

# 2.3 ERD 내용: 기존 ERD 영역에 문자 기반 관계도를 넣는다.
# 표를 새로 만들거나 기존 제목·머리글을 변경하지 않는다.
erd_anchor = P[16]
erd_intro = erd_anchor.insert_paragraph_before()
settext(erd_intro,
    "ERD 기준: " + CHECKED_AT + " 작업트리와 본문 제안. "
    "E-01~E-32는 2.1과 동일하다. --는 DDL에 선언된 FK, ..는 제안·논리·다형 연결이다. "
    "숫자는 각 끝의 최소·최대 수량이다. --도 환경 적용 완료를 뜻하지 않는다. "
    "객체별 판단·구현·적용·검증 상태는 2.1, 삭제·소유 규칙은 C-14를 따른다.")
for rid, parent, child, cardinality, meaning in RELATIONS:
    paragraph = erd_anchor.insert_paragraph_before()
    settext(paragraph, rid + " [" + parent + "] " + cardinality + " [" + child + "]")

# 3.1 테이블 정의 데이터.
# 각 행은 컬럼명|타입|PK|FK|Not Null|설명이다. 독립 컬럼을 한 행에 묶지 않는다.
# 제안 표의 타입·키·기본값은 배포된 DDL이 아니다.
COLUMN_DATA = {
    "trips": """
trip_id|uuid|O|-|O|[제안] PK, 서버 UUID 생성. 여행 식별.
tenant_id|text|-|-|O|[제안] 소유 테넌트. C-06·14의 소유 검사.
customer_id|uuid|-|O|O|[제안] customers.customer_id 참조. 같은 테넌트 고객만 허용.
status|text|-|-|O|[제안] draft/active/review_required/closed. 기본 draft.
affected_item_ids|jsonb|-|-|O|[제안] 영향 항목 UUID 배열, 기본 []. JSON 계약 C-17.
incident_revision|bigint|-|-|O|[제안] 기본 0, 0 이상. 새 사건·잠금 변경·고객 선택 갱신 시 증가. C-05.
current_version_no|integer|-|-|-|[제안] 최초 적용 전 NULL. 기존 Trip·버전 조합 실재를 트랜잭션에서 검사. C-04·05.
preferred_language|text|-|-|-|[제안] 고객이 직접 선택한 언어. 미리 정한 지원 집합으로 제한하지 않고 고객이 고른 언어를 그대로 출력 언어로 쓴다. NULL은 미선택이며 국적으로 채우지 않음. C-19.
language_revision|integer|-|-|O|[제안] 기본 0. 고객 선택 변경 시 증가, 미발행 알림의 문구 판본 검증에 사용.
timezone|text|-|-|O|[제안] 서울 일정 기준 Asia/Seoul. DB 시각은 timestamptz로 저장.
created_at|timestamptz|-|-|O|[제안] 서버 생성 시각, 기본 now().
closed_at|timestamptz|-|-|-|[제안] 종료 전 NULL. 종료 후 신규 감시·안내 생성 중단. C-12.
""",
    "itinerary_versions": """
trip_id|uuid|O|O|O|[제안] trips.trip_id 참조. 복합 PK(trip_id, version_no).
version_no|integer|O|-|O|[제안] 1 이상, Trip 안에서 증가. C-04·05.
created_by|text|-|-|O|[제안] customer/system/rollback. 변경 주체.
rolled_back_from|integer|-|-|-|[제안] 일반 생성은 NULL. 되돌림 출처 버전은 같은 Trip 안에서 앱 검사.
created_at|timestamptz|-|-|O|[제안] 적용 버전 생성 시각, 기본 now().
reason|text|-|-|O|[제안] 생성·묶음 변경·고객 선택·되돌림의 사유.
decision_json|jsonb|-|-|O|[제안] schema_version, incident_ids, evidence_ids, selected_candidate, alternatives, added_cost, supplier_pending, validation_result 필수. 대안 최대 둘. C-08·17·18.
""",
    "itinerary_items": """
trip_id|uuid|O|O|O|[제안] 복합 FK(trip_id, version_no)가 itinerary_versions를 참조.
version_no|integer|O|O|O|[제안] 복합 PK(trip_id, version_no, item_id).
item_id|uuid|O|-|O|[제안] 버전 간 동일 항목의 식별자.
replaces_item_id|uuid|-|-|-|[제안] 대체된 원래 항목. 신규 항목은 NULL, 대체 대응은 같은 Trip에서 검사.
kind|text|-|-|O|[제안] activity/dining/mobility/lodging/flight. 무료·무예약 활동도 포함.
booking_id|uuid|-|O|-|[제안] bookings.booking_id 선택 참조. 무예약이면 NULL. 소유 검사 C-02.
is_locked|boolean|-|-|O|[제안] 기본 false. 잠긴 예약을 사실상 수행 불가능하게 하는 변경도 금지.
starts_at|timestamptz|-|-|-|[제안] 항목 시작 시각. NULL이면 시각 미확인, 필수 검증 통과로 처리하지 않음.
ends_at|timestamptz|-|-|-|[제안] 항목 종료 시각. 두 시각이 있으면 ends_at >= starts_at 검사.
place_ref|uuid|-|O|-|[제안] places.place_id 선택 참조. 공급자 ID와 내부 장소 ID를 구별.
cost|numeric(18,2)|-|-|-|[제안] currency의 주 단위 금액. NULL은 금액 미확인. 확정되지 않은 환급은 차감하지 않음.
currency|text|-|-|-|[제안] cost가 있으면 필수. KRW 등 통화 코드. 반올림·통화별 자릿수 정책 U-원가.
""",
    "trip_constraints": """
trip_id|uuid|O|O|O|[제안] itinerary_versions에 대한 복합 FK의 일부.
version_no|integer|O|O|O|[제안] 복합 PK(trip_id, version_no, constraint_id). 과거 버전 조건을 보존.
constraint_id|uuid|O|-|O|[제안] 동일 조건의 버전 간 식별자.
tenant_id|text|-|-|O|[제안] 해당 Trip의 테넌트와 일치 검사.
scope|text|-|-|O|[제안] CHECK(scope IN ('trip','item')).
ref_id|uuid|-|-|O|[제안] trip이면 trip_id, item이면 해당 버전 item_id. 다형 참조이며 일반 FK 아님.
kind|text|-|-|O|[제안] dietary/party_size/age_limit/budget/payment 등 조건 종류.
value|jsonb|-|-|O|[제안] schema_version, value, knowledge_state, evidence_ids 필수. 모름과 조건 없음 구별. C-10·17.
""",
    "places": """
place_id|uuid|O|-|O|010:17. DEFAULT gen_random_uuid(). 내부 장소 PK.
tenant_id|text|-|-|O|010:18. UNIQUE(tenant_id, name, kind).
name|text|-|-|O|010:19. 장소명. 이름 일치만으로 공급자 신원을 확정하지 않음.
kind|text|-|-|O|010:20. 종류 문자열. 값 목록 CHECK는 선언되어 있지 않음.
latitude|double precision|-|-|-|010:21. 위도. NULL은 미확인.
longitude|double precision|-|-|-|010:22. 경도. NULL은 미확인.
weather_sensitive|boolean|-|-|-|010:26. NULL은 모름. 실내로 확인했다는 뜻이 아님.
hours_confirmed_at|timestamptz|-|-|-|010:29. 영업 정보 확인 시각. NULL이면 확인 시각 없음.
open_at_slot|boolean|-|-|-|010:30. 일정 시각의 영업 여부. NULL은 미확인.
dietary|text[]|-|-|O|010:31. DEFAULT '{}'. 확인된 조건 있음.
dietary_absent|text[]|-|-|O|010:32. DEFAULT '{}'. 확인된 조건 없음. 두 배열 모두에 없는 조건은 모름.
source_name|text|-|-|-|013:9. 공급자 이름. 추가 열의 상태도 구현 파일 존재·적용 여부 미확인.
source_content_id|text|-|-|-|013:10. 공급자 장소 ID. places_source_identity_idx의 일부. UNIQUE·FK 아님.
source_content_type_id|text|-|-|-|013:11. 공급자 장소 종류. 동명 대상 구분.
source_resolved_at|timestamptz|-|-|-|013:13. 공급자 신원 해소 시각. 수집·현장 관측 시각과 별개.
""",
    "bookings": """
booking_id|uuid|O|-|O|010:39. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|010:40. UNIQUE(tenant_id, booking_no).
customer_id|uuid|-|O|O|010:41. REFERENCES customers(customer_id).
place_id|uuid|-|O|-|010:42. REFERENCES places(place_id), NULL 허용.
booking_no|text|-|-|O|010:43. 테넌트 안의 예약번호.
kind|text|-|-|O|010:44. 종류 text. 값 CHECK 없음.
status|text|-|-|O|010:45. 예약 상태 text. 값 CHECK 없음.
starts_at|timestamptz|-|-|O|010:46. 예약 시작 시각.
party_size|integer|-|-|-|010:47. 예약 인원. NULL 허용, 양수 CHECK 없음.
capacity|integer|-|-|-|010:48. 정원. NULL 허용, 인원과의 대소 CHECK 없음.
amount_cents|integer|-|-|-|010:49. 금액 정수. DDL에 통화 열·단위 계약 없음. 원 또는 KRW 센트로 단정하지 않음. U-원가.
locked|boolean|-|-|O|010:51. DEFAULT false. 예약 잠김.
created_at|timestamptz|-|-|O|010:52. DEFAULT now(). 레코드 생성 시각.
""",
    "supplier_bookings": """
supplier_booking_id|uuid|O|-|O|010:60. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|010:61. UNIQUE(tenant_id, supplier, supplier_ref).
booking_id|uuid|-|O|O|010:62. REFERENCES bookings(booking_id).
supplier|text|-|-|O|010:63. 공급자 이름. 제안 표 suppliers에 대한 FK 없음.
supplier_ref|text|-|-|O|010:64. 공급자 원장 식별자.
status|text|-|-|O|010:67. 우리 예약 상태와 독립된 공급자 상태.
confirmed_at|timestamptz|-|-|-|010:68. 공급자 확인 시각. NULL 허용.
""",
    "place_catalog": """
catalog_id|uuid|O|-|O|011:14. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|011:15. UNIQUE(tenant_id, source, content_id).
source|text|-|-|O|011:16. 공급자 구별.
content_id|text|-|-|O|011:17. 공급자 식별자.
content_type_id|text|-|-|-|011:18. 공급자 분류. NULL 허용.
area_code|text|-|-|-|011:19. 공급자 지역코드. 서울 상품 판단은 별도 검증.
title|text|-|-|O|011:20. 공급자 장소명.
address|text|-|-|-|011:21. 주소. NULL 허용.
latitude|double precision|-|-|-|011:22. 위도.
longitude|double precision|-|-|-|011:23. 경도.
source_modified_at|text|-|-|-|011:26. 공급자 수정 시각 원문. timestamptz가 아님.
fetched_at|timestamptz|-|-|O|011:28. DEFAULT now(). 우리가 받은 시각.
raw_json|jsonb|-|-|-|011:29. 공급자 원문. 내부 JSON 검증·보존 제안은 C-17·20.
""",
    "source_sync_state": """
sync_id|uuid|O|-|O|011:40. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|011:41. UNIQUE(tenant_id, source, scope).
source|text|-|-|O|011:42. 출처.
scope|text|-|-|O|011:43. 수집 범위.
bootstrap_done|boolean|-|-|O|011:45. DEFAULT false.
next_page|integer|-|-|O|011:46. DEFAULT 1. 재개할 페이지.
total_expected|integer|-|-|-|011:47. 공급자 예상 전체량. 내부 확보량 아님.
rows_seen|integer|-|-|O|011:48. DEFAULT 0. 처리 기록 수이며 품질 통과량 아님.
last_delta_at|timestamptz|-|-|-|011:50. 마지막 델타 동기화 시각.
high_water|text|-|-|-|011:51. 공급자 수정 시각의 진행 기준.
delta_trusted|boolean|-|-|O|011:55. DEFAULT false. 델타 신뢰 상태.
delta_note|text|-|-|-|011:56. 델타 대조·신뢰 사유.
last_error|text|-|-|-|011:57. 마지막 오류.
updated_at|timestamptz|-|-|O|011:58. DEFAULT now(). UPDATE 때 자동 갱신하는 트리거 선언은 없음.
""",
    "watch_observations": """
observation_id|uuid|O|-|O|012:17. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|012:18. 관측 테넌트.
target_kind|text|-|-|O|012:20. 대상 종류 text. 값 CHECK 없음.
target_id|text|-|-|O|012:22. 대상 종류 안의 식별자. 물리 FK 없음.
source|text|-|-|O|012:23. 출처. 현재 UNIQUE·최신 인덱스에는 포함되지 않음. C-15.
fingerprint|text|-|-|O|012:26. 판정 필드의 해시. 현재 장소 다섯 필드는 C-15.
payload|jsonb|-|-|O|012:27. 현재 watch.py는 watched와 raw를 저장. 운영 상태 확장 계약은 C-15의 제안.
observed_at|timestamptz|-|-|O|012:28. DEFAULT now(). 저장 관측 시각이며 공급자 현장 확인 시각 아님. UNIQUE(tenant_id,target_kind,target_id,observed_at).
""",
    "watch_changes": """
change_id|uuid|O|-|O|012:38. DEFAULT gen_random_uuid(). observation_id·trip_id·case_id FK 없음.
tenant_id|text|-|-|O|012:39. 대상 테넌트.
target_kind|text|-|-|O|012:40. 대상 종류.
target_id|text|-|-|O|012:41. 논리 대상 ID.
source|text|-|-|O|012:42. 출처.
before_json|jsonb|-|-|-|012:43. 이전 값, NULL 허용. 현재 코드는 이전 watched를 저장.
after_json|jsonb|-|-|O|012:44. 이후 값. 현재 코드는 공급자 payload를 저장하여 전후 구조가 같지 않을 수 있음. C-15.
summary|text|-|-|O|012:46. 필드 차이 요약.
affected_bookings|jsonb|-|-|O|012:48. DEFAULT '[]'::jsonb. 현재 watch.py가 넣는 값은 booking_no 문자열 배열. Trip·무예약 항목 연결은 제안.
detected_at|timestamptz|-|-|O|012:49. DEFAULT now(). 변화 검출 기록 시각.
notified_at|timestamptz|-|-|-|012:51. 통지 시각 열. 이번 확인한 watch.py에는 이 열을 채우는 경로가 없음.
notify_error|text|-|-|-|012:52. 통지 오류 열. 고객 수신·읽음 확인 아님.
""",
    "watch_schedule": """
schedule_id|uuid|O|-|O|[제안] 서버 UUID. 감시 일정 PK.
tenant_id|text|-|-|O|[제안] 테넌트. UNIQUE(tenant_id,trip_id,source,target_kind,target_id).
trip_id|uuid|-|O|O|[제안] trips.trip_id 참조.
source|text|-|-|O|[제안] 감시 출처. 같은 장소의 서로 다른 출처를 분리.
target_kind|text|-|-|O|[제안] place/weather/air_quality/transit/road/closure/inventory 등 등록 종류.
target_id|text|-|-|O|[제안] 출처와 종류 안의 식별자. 항목 대상도 포함.
next_check_at|timestamptz|-|-|O|[제안] 다음 확인 시각. 감시 주기 최소 84초·기본 120초는 결정, 작업 주기는 설정. C-12.
last_checked_at|timestamptz|-|-|-|[제안] 마지막 점검 시각. 최초 NULL.
state|text|-|-|O|[제안] pending/processing/unknown/stopped. 기본 pending.
lease_until|timestamptz|-|-|-|[제안] 작업 임대 만료 시각. 재시작 시 회수하며 중복 관측은 C-15로 관리.
last_error|text|-|-|-|[제안] 오류 또는 미확인 사유. 성공·변화 없음과 구별.
""",
    "customer_cases": """
case_id|uuid|O|-|O|001:13. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|001:13. 테넌트 text. tenants FK 선언 없음.
customer_id|uuid|-|O|O|001:13. REFERENCES customers(customer_id).
status|case_status|-|-|O|001:5·13. 12종 ENUM. C-07.
subject|text|-|-|O|001:13. 접수 제목·요청 내용.
state_json|jsonb|-|-|O|001:13. DEFAULT '{}'. Case 상태 투영. Trip 사건의 확장 계약은 E-21 제안.
intent|text|-|-|-|001:13. 요청 의도.
issue_code|text|-|-|-|001:13. 이슈 코드. case_type이라는 별도 열 없음.
sentiment|text|-|-|-|001:13. 감정 분류.
owner_team_id|text|-|-|-|001:13. 담당 Team 식별 문자열.
version|integer|-|-|O|001:13. DEFAULT 0. transition_case의 낙관적 잠금 기준.
created_at|timestamptz|-|-|O|001:13. DEFAULT now().
updated_at|timestamptz|-|-|O|001:13. DEFAULT now(). transition_case가 갱신.
""",
    "case_events": """
event_id|uuid|O|-|O|001:14. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|001:14. 이벤트 테넌트.
case_id|uuid|-|O|O|001:14. REFERENCES customer_cases(case_id).
aggregate_version|integer|-|-|O|001:14. UNIQUE(case_id,aggregate_version). 순번 중복 방지.
event_type|text|-|-|O|001:14. 이벤트 종류.
payload_json|jsonb|-|-|O|001:14. 이벤트 payload. 사건 ID·선택 이력 연결은 C-18의 제안.
actor_type|text|-|-|O|001:14. 행위자 종류.
actor_id|text|-|-|-|001:14. 행위자 ID, NULL 허용.
created_at|timestamptz|-|-|O|001:14. DEFAULT now(). 이벤트 저장 시각.
""",
    "action_requests": """
action_id|uuid|O|-|O|001:17. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|001:17. UNIQUE(tenant_id,idempotency_key).
case_id|uuid|-|O|O|001:17. REFERENCES customer_cases(case_id).
action_type|text|-|-|O|001:17. 실행 종류.
arguments_json|jsonb|-|-|O|001:17. 요청 본문. 대상·본문 해시 제안은 C-02.
idempotency_key|text|-|-|O|001:17. 테넌트별 멱등 키. 대상별 키 재료가 구현됐다는 뜻은 아님.
status|action_status|-|-|O|001:8·17. proposed/pending_approval/approved/rejected/executing/succeeded/failed/unknown/cancelled.
provider_ref|text|-|-|-|001:17. 공급자 실행 식별자.
created_at|timestamptz|-|-|O|001:17. DEFAULT now().
""",
    "outbox": """
message_id|uuid|O|-|O|001:19. DEFAULT gen_random_uuid().
tenant_id|text|-|-|O|001:19,003:14. UNIQUE(tenant_id,topic,dedupe_key).
topic|text|-|-|O|001:19. 메시지 종류. trip.notice 사용은 제안 계약 C-03.
dedupe_key|text|-|-|O|001:19,003:14. 같은 테넌트·topic 내 유일. NULL 허용 안 함.
payload_json|jsonb|-|-|O|001:19. 발행 본문. Case FK 없음. 버전·언어·알림 참조는 C-03·19 제안.
status|text|-|-|O|001:19. DEFAULT 'pending'. worker 상태와 무효화 제안은 C-03·11.
attempts|integer|-|-|O|001:19. DEFAULT 0. 발송 시도 수.
available_at|timestamptz|-|-|O|001:19. DEFAULT now(). 다음 발송 가능 시각.
locked_at|timestamptz|-|-|-|001:19. 처리 시작 시각.
last_error|text|-|-|-|001:19. 마지막 오류.
resolved_at|timestamptz|-|-|-|005:3. 결과 불명에 대한 사람의 해소 시각.
resolved_by|text|-|-|-|005:4. 해소 담당자.
resolution_note|text|-|-|-|005:5. 해소 근거.
resolution|text|-|-|-|005:6. 해소 판단. 이 메타데이터만으로 status를 변경하지 않음.
""",
    "evidences": """
evidence_id|uuid|O|-|O|[제안] 서버 UUID. 근거 한 건.
tenant_id|text|-|-|O|[제안] 소유 테넌트.
change_request_id|uuid|-|O|O|[제안] change_requests.change_request_id 참조.
source|text|-|-|O|[제안] 고객 신고·공식 API·업체 공지 등 근거 출처.
source_ref|text|-|-|-|[제안] 공급자 ID·문서 버전·객체 키. 공개 가능한 URL만 저장, 비밀 토큰 제외.
source_observed_at|timestamptz|-|-|-|[제안] 원천 관측 시각. 모르면 NULL.
fetched_at|timestamptz|-|-|O|[제안] 수집 시각. 원천 관측 시각으로 표시하지 않음.
data_kind|text|-|-|O|[제안] live/synthetic/mock/replay/customer_report. 합성·Mock·재생은 문서 표시에도 반영.
sha256|text|-|-|-|[제안] 원문 바이트가 확보된 경우 체크섬. 미확보 값을 생성하지 않음.
payload|jsonb|-|-|O|[제안] schema_version, target, knowledge_state, facts, provenance 필수. C-17.
""",
    "suppliers": """
supplier_id|uuid|O|-|O|[제안] 서버 UUID.
tenant_id|text|-|-|O|[제안] 소유 테넌트.
name|text|-|-|O|[제안] 공급자 표시명.
tier|text|-|-|O|[제안] simulated/real. 기본 real, 알 수 없는 값은 자동 실행 거부. C-09.
capabilities|jsonb|-|-|O|[제안] 등록된 실행 종류와 공급자 식별 계약. 기본 [].
""",
    "delegation_scopes": """
delegation_id|uuid|O|-|O|[제안] 서버 UUID. 위임 기록.
tenant_id|text|-|-|O|[제안] 소유 테넌트.
trip_id|uuid|-|O|O|[제안] trips.trip_id 참조.
allowed_actions|jsonb|-|-|O|[제안] 허용 작업·대상 배열. 기본 []는 권한 없음.
amount_limit|numeric(18,2)|-|-|-|[제안] 위임 금액 상한. NULL이면 금전 실행 허용으로 해석하지 않음.
currency|text|-|-|-|[제안] 금액 상한의 통화. 상한 존재 시 필수.
valid_until|timestamptz|-|-|O|[제안] 위임 효력 종료 시각.
revoked_at|timestamptz|-|-|-|[제안] 철회 전 NULL. 실행 직전 재검사.
""",
    "booking_actions": """
booking_action_id|uuid|O|-|O|[제안] 서버 UUID. 실행·보상 시도마다 새 행.
tenant_id|text|-|-|O|[제안] 소유 테넌트.
booking_id|uuid|-|O|O|[제안] bookings.booking_id 참조.
supplier_id|uuid|-|O|O|[제안] suppliers.supplier_id 참조.
action_id|uuid|-|O|O|[제안] action_requests.action_id 참조.
delegation_id|uuid|-|O|-|[제안] delegation_scopes 참조. 승인 실행이면 NULL 가능.
compensates_id|uuid|-|O|-|[제안] 보상하는 booking_actions 행의 자기 참조.
state|text|-|-|O|[제안] requested/succeeded/failed/unknown/escalated. 결과 불명은 성공·실패로 추정하지 않음.
audit_json|jsonb|-|-|O|[제안] schema_version, actor, reason, amount, currency, approval_ref, provider_ref, reversible_until, result 필수. 값 미확인은 NULL과 사유. C-09·17.
created_at|timestamptz|-|-|O|[제안] 시도 기록 시각, 기본 now().
""",
    "change_requests": """
change_request_id|uuid|O|-|O|[제안] 서버 UUID. 사건 또는 재요청 한 건.
tenant_id|text|-|-|O|[제안] UNIQUE(tenant_id,request_id).
trip_id|uuid|-|O|O|[제안] trips.trip_id 참조.
request_id|text|-|-|O|[제안] 고객 요청 또는 시스템 관측 접수의 멱등 식별자.
scenario_event_id|text|-|-|-|[제안] 확정 시나리오의 액-02·이동-B1·요식-P3·이동-A6·요식-P7·액-08. 실제 사건은 NULL 가능.
trigger_source|text|-|-|O|[제안] customer/system. 고객 신고를 시스템 감지로 집계하지 않음.
issue_code|text|-|-|O|[제안] 사건별 코드. 공식 대응 미확보 U-선택. C-18.
intent|text|-|-|O|[제안] incident_report/confirm_request/adjust_reject/itinerary_submit/other.
item_id|uuid|-|-|-|[제안] 영향 항목. 대상이 여러 개면 payload_json. 같은 Trip·버전 소유 검사.
base_version_no|integer|-|-|O|[제안] 접수·선택의 기준 일정 버전.
sweep_id|text|-|-|-|[제안] 시스템 점검 묶음. 고객 요청이면 NULL.
case_id|uuid|-|O|-|[제안] customer_cases.case_id 참조. 묶음 Case 연결 전 NULL.
observation_id|uuid|-|O|-|[제안] watch_observations.observation_id 선택 참조.
change_id|uuid|-|O|-|[제안] watch_changes.change_id 선택 참조. 고객 신고이면 없어도 됨.
occurred_at|timestamptz|-|-|-|[제안] 사건 발생·현장 목격 시각. 미확인일 때 수신 시각으로 대체하지 않음.
received_at|timestamptz|-|-|O|[제안] 우리 접수 시각, 기본 now().
state|text|-|-|O|[제안] received/linked/awaiting_choice/applied/escalated/rejected. 기본 received.
payload_json|jsonb|-|-|O|[제안] schema_version, body_sha256, affected_item_ids, evidence_ids, candidate_ids, ranking_reason, selected_candidate_id, selected_at, result_version_no 필수. 미발생 값은 NULL. C-17·18.
""",
    "notifications": """
notification_id|uuid|O|-|O|[제안] 서버 UUID. 예정·발행·무효화를 추적할 알림 식별자.
tenant_id|text|-|-|O|[제안] 모든 유일성·소유 검사의 범위.
trip_id|uuid|-|O|O|[제안] trips.trip_id 참조.
target_version_no|integer|-|-|O|[제안] 대상 일정 버전. 같은 Trip의 버전 실재를 앱에서 검사.
notice_kind|text|-|-|O|[제안] change/pre_trip/day_start/item_departure. 전날 준비 안내는 결정 10의 여행 시작 안내 하위 종류.
occurrence_key|text|-|-|O|[제안] 변경은 버전, 전날·하루 시작은 서울 현지 날짜, 출발은 item_id와 수행 날짜로 구별.
generation|integer|-|-|O|[제안] 기본 1. 미발행 안내를 재계산하면 기존 행 무효화 후 새 세대 생성. C-03·11.
state|text|-|-|O|[제안] scheduled/enqueued/published/invalidated/unknown/failed. 기본 scheduled.
item_id|uuid|-|-|-|[제안] 항목 출발 대상. 다른 알림이면 NULL. 항목의 버전·소유 검사.
notice_due_at|timestamptz|-|-|-|[제안] 안내 예정 시각. 이동 시간 미확인 시 출발 역산값은 NULL과 오류 사유. C-11·12.
prequery_due_at|timestamptz|-|-|-|[제안] 사전 경로 조회 시각. 충분히 이른 기준·간격은 U-상태.
route_duration_seconds|integer|-|-|-|[제안] 확인한 이동 시간, 0 이상. NULL을 0으로 취급하지 않음.
buffer_seconds|integer|-|-|O|[제안] 설정에서 받은 여유, 0 이상. 설정값·판본은 payload에 보존.
route_checked_at|timestamptz|-|-|-|[제안] 실제 경로 조회 시각. 저장값 사용 시 그 시각을 표시.
route_json|jsonb|-|-|-|[제안] 확인된 경로·소요·원천 시각·출처. 제공할 경로 상세 수준은 U-상태.
language|text|-|-|O|[제안] 발행 시 확정한 고객 선택 언어 스냅샷.
language_revision|integer|-|-|O|[제안] trips.language_revision과 대조. 오래된 언어로 준비한 미발행 문구를 교체.
template_version|text|-|-|O|[제안] 언어·문구틀별로 처음 한 번 생성해 재사용하는 문구 판본. 시작·출발 안내는 LLM 없이 채움.
message_id|uuid|-|O|-|[제안] outbox.message_id 선택 FK·UNIQUE. 발행 의도 삽입과 함께 연결.
enqueued_at|timestamptz|-|-|-|[제안] outbox 삽입 시각. 외부 채널 발송 성공과 구별.
published_at|timestamptz|-|-|-|[제안] 채널 발송 성공 기록. 고객 수신·읽음 확인은 아님.
invalidated_at|timestamptz|-|-|-|[제안] 낡은 안내 무효화 시각. 기존 발행 이력은 보존.
invalidated_reason|text|-|-|-|[제안] 일정·시각·언어 변경 등 무효화 이유.
payload_json|jsonb|-|-|O|[제안] schema_version, destination, starts_at, departure_at, route_state, link, config_version, facts, error 필수. 알 수 없는 값은 NULL과 사유. C-17.
""",
}

TABLES = []
for entity in ENTITIES:
    eid, name, stage, key, constraints, meaning, source, task = entity
    cols = [
        tuple(part.strip() for part in line.split("|", 5))
        for line in COLUMN_DATA[name].strip().splitlines()
    ]
    if any(len(row) != 6 for row in cols):
        raise ValueError("컬럼 정의는 6열이어야 한다: " + name)
    if len({row[0] for row in cols}) != len(cols):
        raise ValueError("컬럼 중복: " + name)
    title = (
        name + " / " + eid + " / " + meaning +
        " 상태: " + STATE[stage] + ". 기준: " + CHECKED_AT +
        " 작업트리, HEAD " + REVISION + "; 파일 판본 M-02~M-05. "
        "근거: " + source + ". 작업 " + task + "."
    )
    TABLES.append((title, cols))

anchor_para = None
for p in d.paragraphs:
    if p.text.strip().startswith("테이블 :"):
        anchor_para = p
        break
if anchor_para is None:
    raise ValueError("원본 테이블 정의서 문단을 찾지 못했다.")

settext(anchor_para, "테이블 : " + TABLES[0][0], bold=True)
fill(T[5], TABLES[0][1])

after = T[5]._tbl
for name, cols in TABLES[1:]:
    new_p = copy.deepcopy(anchor_para._p)
    new_t = copy.deepcopy(T[5]._tbl)
    after.addnext(new_t)
    new_t.addprevious(new_p)
    after = new_t
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    settext(Paragraph(new_p, anchor_para._parent), "테이블 : " + name, bold=True)
    fill(Table(new_t, d), cols)

# 3.2 제약 조건 및 무결성 관리
RULES = [
    ("DB·Case 서비스", "C-01 Case 잠금·순번", "customer_cases; case_events",
     "[구현] 구현 파일 존재·적용 여부 미확인. [실측 정적 확인] 001:14의 "
     "UNIQUE(case_id,aggregate_version)는 동일 순번 중복을 막는다. transition.py:61~85는 "
     "tenant_id·case_id·expected_version 조건으로 상태를 갱신하고 이벤트·outbox를 삽입한다. "
     "호출자가 트랜잭션을 소유한다. Case별 잠금은 다른 Case가 쓰는 같은 Trip을 보호하지 않는다. "
     "충돌·중간 실패 주입 시험은 미실행, DB-04·U-상태."),

    ("DB·요청 접수·실행 서비스", "C-02 대상별 멱등성", "action_requests",
     "[결정] v11 §4-E의 서버 확인 대상별 키를 따른다. [제안] tenant·요청 ID·작업 종류·대상 ID를 "
     "정규화해 해시하고 body_sha256를 보존한다. activity.*·dining.*는 예약이 있으면 booking_id, "
     "없으면 item_id; booking.*는 booking_id; mobility.*는 item_id; trip.*는 trip_id. "
     "대상 불명·다른 소유는 거부한다. 동일 키·다른 본문은 409, 진행 중이면 같은 요청 상태를 반환한다. "
     "키와 결과의 보존 만료는 C-20에 연결하며 외부 결과 불명은 재실행하지 않는다. "
     "[실측 정적 확인] controller.py:374는 business_subject=case_id다. "
     "cases.py:109~135의 접수 본문 해시 검사를 모든 실행 경로의 완료로 확대하지 않는다. "
     "DoD-24·DB-04, 실행 시험 미실행."),

    ("DB·알림 서비스·배달 작업자", "C-03 발행 키·원자성", "notifications; outbox",
     "[실측 정적 확인] 003:12~14의 UNIQUE(tenant_id,topic,dedupe_key)를 승계한다. "
     "[제안] E-22에는 change일 때 UNIQUE(tenant_id,trip_id,target_version_no)인 부분 유일 인덱스, "
     "전체에 UNIQUE(tenant_id,trip_id,notice_kind,occurrence_key,generation), "
     "scheduled/enqueued/unknown 상태에 발생 단위별 활성 행 하나인 부분 유일 인덱스를 둔다. "
     "변경 키는 trip:ID:version:N:change, 안내 키는 trip:ID:kind:occurrence:generation으로 만든다. "
     "변경은 일정 버전·포인터·Case·notifications·outbox를 함께 커밋한다. "
     "안내는 Case 없이 notifications 상태·outbox를 함께 커밋한다. 같은 키의 본문 불일치는 오류다. "
     "DB 중복 방지는 고객 수신이나 외부 부작용 exactly-once 보장이 아니다. DB-05·DoD-12·26."),

    ("DB·Trip 서비스", "C-04 불변 버전·되돌림", "itinerary_versions; itinerary_items; trip_constraints",
     "[결정] 적용 버전은 append-only. [제안] 일상 앱 역할의 UPDATE·DELETE 권한을 제거하고 "
     "과거 버전·항목·조건을 함께 읽는다. 정정·되돌림도 최신 영업·취소·잠금·조건을 재검증한 새 버전이다. "
     "버전과 항목의 복합 PK, 버전별 조건 PK를 둔다. 생성 중 NULL인 최신 포인터는 적용 뒤 실제 버전을 "
     "가리켜야 한다. 삭제 예외는 C-20의 정책 작업으로 제한한다. 설계만 존재, DB-01·DoD-1·8·9."),

    ("DB·Trip 서비스", "C-05 Trip 동시성 계약", "trips.current_version_no; incident_revision",
     "[결정] v11 §6-C-7의 다섯 조건. "
     "1) 기준 일정 버전과 사건 개정번호를 함께 읽는다. "
     "2) 후보 계산 중 긴 트랜잭션을 잡지 않는다. "
     "3) 반영 시 tenant_id·trip_id·두 기준값을 조건으로 UPDATE하고 영향 행 1건을 요구한다. "
     "4) 0건이면 후보를 버리고 최신 입력으로 한 번 재계산한다. 다시 충돌하면 자동 반영하지 않고 인계한다. "
     "5) 성공 때만 일정·조건·포인터·Case·발행 의도를 함께 커밋한다. "
     "[제안] 사건 접수·잠금 변경도 같은 Trip 행을 갱신해 incident_revision을 증가시킨다. "
     "격리 수준은 READ COMMITTED와 조건부 쓰기를 제안하며 경합 시험으로 확정한다. "
     "설계만 존재; DB-01·04, U-상태."),

    ("API·링크·DB 접근 계층", "C-06 소유·접근", "tenant_id; trip_id; 여행별 토큰",
     "[실측 정적 확인] read_tools.py:154~162는 tenant_id·customer_id로 예약을 읽지만 "
     "booking_id가 없으면 시작 시각이 가장 이른 예약을 반환한다. 과거·취소 예약도 거르지 않고 "
     "case_id 인자는 사용하지 않는다. [제안] API·로그인 없는 여행별 링크의 읽기·재요청 경로에서 "
     "서버가 토큰 효력·여행·고객·대상 소유를 검사한다. 토큰 원문은 로그·JSON에 저장하지 않는다. "
     "토큰 해시 저장소·만료·철회·열람 기록 물리 구조와 전체 RLS 적용 증거는 [미확보] U-상태·U-운영. "
     "DB-07, 다른 여행 접근 거부 DoD-11·25."),

    ("Case 서비스·라우터", "C-07 상태·라우팅", "customer_cases.status; issue_code; intent",
     "[실측 정적 확인] 001:5의 Case 상태는 new/classifying/routing/running/waiting_input/"
     "waiting_approval/waiting_external/resuming/resolved/escalated/failed/cancelled다. "
     "[결정] v11 §5의 객체 축 activity·booking·mobility·dining·lodging·flight와 "
     "요청 축 itinerary_submit·incident_report·confirm_request·adjust_reject·other를 구별한다. "
     "case_type은 issue_code 접두의 의미이며 별도 DB 열을 만들었다고 적지 않는다. "
     "접두 없는 other는 사람 인계 경로다. 등록 Team 도달성 DoD-23은 별도 시험, DB-04."),

    ("조정 서비스·검증 계층", "C-08 묶음 조정·선택 이력", "change_requests; itinerary_versions.decision_json",
     "[결정] 한 스윕·한 Trip에 Case 하나, 원인별 사건·근거는 각각 보존한다. "
     "필수 조건 위반·필수값 미확인, 잠긴 예약 훼손, 실행 권한·근거 부족은 자동 적용에서 탈락한다. "
     "통과 후보는 변경 항목 수, 추가 비용, 최대 시간 이동량과 합계, 복원 용이성 순으로 비교하며 "
     "v11의 최종 동률 기준은 정규화 후보 ID다. "
     "[제안] 확정 시나리오의 이동-B1·요식-P3·액-08은 후보가 불확실해도 하나를 골라 적용하고 선택지를 나열하지 않는다. "
     "순위 판정값은 대체 소스로 채우고 취향 동률은 정규화 후보 ID로 하나를 고른다. 필수 안전값 미확인을 통과로 바꾸지는 않는다. "
     "고른 안 하나로 적용한 뒤 전체 재검증·버전 대조. 후보 ID·선정 근거·고객 재요청·결과 버전 보존. "
     "실패는 해 없음·근거 부족·탐색 상한 도달을 구별하고 부분 적용하지 않는다. "
     "Trip에는 재검토 필요·영향 항목·인계 근거를 남긴다. DB-01·04."),

    ("실행 서비스·DB·승인자", "C-09 실행 경계·위임·보상", "suppliers; delegation_scopes; booking_actions",
     "[결정] Pre-CS는 내부 일정에만 적용하고 실제 업체 예약·결제는 승인 없이 실행하지 않는다. "
     "업체 건은 변경 항목·대안·차액·변경 링크와 업체 미확정을 보존한다. 예약 확정 자체가 필수이면 "
     "미확정 안은 자동 적용에서 제외한다. [제안] 실행 직전 tier·승인·위임 상한·유효기간·철회를 "
     "검사하고 무엇을·왜·얼마에·되돌림 기한·공급자 결과를 기록한다. 보상 실패·결과 불명은 사람 인계. "
     "[실측 정적 확인] 이번 app/·tests/ 검색에서 tier와 simulated를 함께 쓰는 실행 게이트를 찾지 못했다. "
     "제안 표 DDL도 확인한 migrations/에 없다. 미구현 범위의 시연 자동 실행은 열지 않는다. "
     "DB-06, DoD-13~21의 승인·실행·보상 검증 미실행."),

    ("DB·검증 계층", "C-10 조건·금액·시각", "trip_constraints; itinerary_items; bookings",
     "[결정] 여행·항목 조건을 모두 만족해야 통과한다. 무예약 Activity도 시각·장소·비용·잠김을 검사한다. "
     "시간 충돌·이동 여유·예산·인원·식단은 최종 조합 전체에서 재검증한다. "
     "[실측 정적 확인] verification_policy.py:69는 starts_at_proposed를 대조 제외한다. "
     "[제안] 자동 적용 전 코드 시각 검증을 추가한다. "
     "[추정] v11 §6-C-4의 탐색 상한은 4단계·단계당 3후보, 3^4=81조합, 외부 조회 최대 24회, "
     "120초와 실제 출발·취소 마감 중 빠른 값이다. 성능 실측이 아닌 범위 제한 가정이다. "
     "입력 범위 1~4단계·1~3후보; 정세환·최연우가 통합 평가 전 재검증하는 안, U-자원·U-상태. "
     "DB-01·04, DoD-2~5·22."),

    ("알림 서비스·배달 작업자", "C-11 결정 10 저장 계약", "notifications; outbox",
     "[결정] 변경은 생성·조정·재요청 적용을 포함하고 적용 버전당 변경 통지 하나다. "
     "최초 검증 통과 때 링크를 처음 제공한다. 여행·하루 시작과 항목 출발 안내는 Case·LLM 없이 "
     "검수한 문구틀로 만든다. 전날 준비 안내와 매일 시작 안내도 발생 단위로 구별한다. "
     "[제안] 출발 예정=항목 시작 - 이동 시간 - 여유. 사전 조회로 예정 시각을 재계산하고 "
     "출발 안내 시 다시 경로를 조회해 목적지·출발 시각·경로·조회 시각·최신 링크를 기록한다. "
     "변경과 안내는 독립 판정하며 둘 다 참이면 변경 통지를 먼저 처리한다. "
     "일정 변경 트랜잭션은 낡은 scheduled/enqueued 안내를 invalidated로, 연결된 미발송 outbox를 "
     "cancelled로 표시하고 새 세대를 만든다. 배달 직전 버전·세대·언어를 재검사한다. "
     "현재 worker의 버전 검사·무효화 처리는 미구현; DB-05. "
     "이미 외부 호출 중인 발송과 일정 반영의 직렬화·제한 시간은 U-상태·U-운영에서 확정한다. "
     "발행된 메시지를 회수했다고 주장하지 않고 최신 링크를 정본으로 둔다. DoD-7·25·26."),

    ("감시 작업자·운영", "C-12 상태 감시·두 루프", "watch_schedule; notifications; read.route; read.transit",
     "[결정] 감시와 outbox 배달은 별도 루프. 최소 84초·기본 2분으로 계획서에 걸린 대상만 감시한다. "
     "[실측 정적 확인] watch.py:103~130은 미래·미취소 예약의 장소를 오래된 관측 순으로 고르고 "
     "DEFAULT_BATCH=5다. 이는 read.booking의 과거·취소 미필터 동작과 다르다. "
     "대상 수/배치 수에 따라 한 대상의 재방문 간격은 틱보다 길 수 있어 2분 이내 전수 확인을 보장하지 않는다. "
     "[제안] 다음 확인·마지막 확인·임대·오류·종료 상태를 저장하고 무예약 항목도 등록한다. "
     "[실측 정적 확인] read_tools.py:252~258의 route·transit는 항상 None. "
     "이동 시간 저장·역산·사전 조회 간격은 U-상태, DB-03·05. 1차 조회가 실패하면 대체 소스로 값을 내고, 대체까지 실패하면 치명 결함으로 서버를 끈다. [제안] 소스별 대체 경로·실패 기록."),

    ("데이터·원가 담당", "C-13 출처·사용량·상품 기준", "API; RAG; 합성; 비용 기록",
     "[결정] 결정 11·12·13: 직접 경로 고객 선택 언어로 보낼 때 생성, 언어 목록 미리 정하지 않음; 서울 1도시·최대 7일·4인 "
     "팀당 49,000원 VAT 포함. 사업자 기본료+초과 종량은 별도 판매 모델 제안이며 이 가격을 대체하지 않는다. "
     "[외부] 사업 검토 v3 §7:189~205는 Google 공식 가격표를 근거 22로 연결한 공개 단가 기록이다. "
     "그 기록의 자료 기준일은 2026-09-08, 로컬 기록 확인일은 2026-09-10이다. 현재 외부 가격표를 "
     "재조회한 결과는 아니다. 미확보는 실제 사용 SKU·필드·여행별 호출량·토큰·재시도·인계 시간이다. "
     "과거 여행 LLM 3~37원 및 7일 출발 조회 20~40회는 검증된 원가가 아닌 이전 계획 가정으로 보존한다. "
     "출발 조회량은 항목 수, 총 조회량은 사전 조회+출발 조회+재시도이며 안내도 조회 비용이 든다. "
     "상세 손익은 사업 문서에 두고 U-원가에서 최연우가 유료 실증 전·종료 시 로그로 재산정한다."),

    ("DB·접근 계층", "C-14 키·FK·도메인", "001·010·011·012·013의 객체",
     "[실측 정적 확인] 각 컬럼 표의 PK·UNIQUE·NOT NULL을 DDL 그대로 기록했다. "
     "010의 customer_id·place_id·booking_id FK와 001의 FK에는 ON DELETE·ON UPDATE·DEFERRABLE의 "
     "별도 절이 없다. tenant_id 하나만으로 같은 테넌트 참조가 강제되지 않는다. "
     "013의 places_source_identity_idx는 일반 인덱스이며 신원의 유일성 제약이 아니다. "
     "[제안] 제안 FK는 부모 삭제·키 변경을 NO ACTION으로 두고 보존 종료는 C-20의 별도 작업으로 처리한다. "
     "고아·타 테넌트 연결·부모 삭제·NULL·중복·직접 DB 쓰기를 DB-02에서 검증한다. "
     "금액·인원·상태 CHECK가 없는 구현 표에 제약이 있다고 표기하지 않는다."),

    ("감시 작업자·DB", "C-15 fingerprint 확장", "watch_observations; watch_changes",
     "[실측 정적 확인] watch.py:202~208의 현재 지문은 title·latitude·longitude·address·content_type_id "
     "다섯 필드다. 영업·휴무가 없고 확정 시나리오 여섯 사건 감지 구현으로 볼 수 없다. "
     "_latest는 source를 거르지 않으며 관측 저장과 변화 저장은 별도 트랜잭션이다. "
     "[제안] 출처별 fingerprint_schema_version과 정규화 규칙을 둔다. 확장 watched 필드는 "
     "opening_intervals·break_intervals·closure_status·closure_effective_date·operation_restrictions, "
     "precipitation_risk·air_quality_alert, transit_service_status·affected_stops, "
     "road_control_status·affected_segments, inventory_state·product_ref·card_payment_state다. "
     "조회 시각은 해시에 넣지 않고 source_observed_at·fetched_at·valid_until로 별도 보존한다. "
     "source를 포함한 최신 조회·유일성, 대상별 직렬화, 관측·변화의 원자 저장을 제안한다. "
     "지문 판본 변경 시 기준선을 다시 세워 코드 변경을 실제 사건으로 오인하지 않는다. "
     "현재의 전후 payload 구조 차이도 공통 watched 구조로 정규화한다. "
     "신규 소스 다섯의 필드·접근·최신성은 U-소스. DB-03, 시험 미실행."),

    ("이벤트 소비자·배달 작업자", "C-16 순서·재생·재시도", "case_events; outbox",
     "[실측 정적 확인] transition.py는 Case 버전을 증가시켜 이벤트 순번으로 쓰고 순번 오름차순으로 읽는다. "
     "worker.py:42~65는 available_at 순으로 한 행을 claim한다. 타임아웃·연결 오류는 unknown, "
     "일반 예외는 기본 최대 3회 뒤 dead_letter다. stale processing도 unknown으로 남긴다. "
     "[제안] 소비 진행 위치는 Case별 last_applied_version으로 영속화하고 중복 순번은 효과 없이 건너뛴다. "
     "순번 공백·역순은 보류 후 원장 재조회, 재생은 같은 이벤트 판본으로 상태만 복원하며 외부 발송을 반복하지 않는다. "
     "진행 위치의 물리 저장소·이벤트 스키마 판본 적용은 U-상태, DB-04. "
     "Trip 변경 통지 우선순서는 기존 outbox 정렬만으로 보장하지 않고 DB-05에서 의존 메시지를 검사한다."),

    ("데이터·지식·검증 계층", "C-17 JSON·원천·검색 정합성", "payload JSON; evidences; knowledge_documents; knowledge_chunks",
     "[제안] 내부 JSON v1은 schema_version·필수 키·타입을 pydantic으로 검증하고 미지의 판본은 거부한다. "
     "관측 raw는 공급자 판본과 분리하며 필드가 없으면 대체 소스로 값을 채우고 사용한 소스·1차 실패를 기록한다. "
     "크기 상한·원문 보존·사용권은 U-소스·U-운영에서 정한다. "
     "정본은 RDB의 원문 판본·근거 식별이고 외부 객체는 키·버전·SHA-256로 연결한다. "
     "[실측 정적 확인] 001:22~27은 원문·청크·vector(1536)·HNSW를 선언한다. "
     "임베딩 모델·모델 판본·재색인 완료량은 [미확보] U-소스. 커머스 규정을 여행 근거로 재사용하지 않는다. "
     "[제안] 원문 갱신·삭제 시 청크·벡터·캐시도 전파하고 실패 목록을 대조한다. "
     "별도 GraphDB·외부 벡터 서비스 도입은 이번 범위 [해당 없음], 도입 결정·구현을 확인하지 않았기 때문이다."),

    ("접수·감시·조정 서비스", "C-18 사건 저장 경로", "change_requests; evidences; customer_cases; case_events",
     "[제안] 고객 입력은 API 접수, E-21(trigger_source=customer), E-17 근거, Case·이벤트 순서로 연결한다. "
     "시스템은 E-10 관측, E-11 변화, E-21(trigger_source=system), 묶음 Case·이벤트 순서다. "
     "같은 스윕·Trip의 Case 접수 키를 action_requests의 테넌트별 멱등 제약과 Trip 잠금으로 직렬화한다. "
     "개별 사건은 E-21에 각각 남기고 case_events.payload_json에 사건 ID 목록을 연결한다. "
     "[실측 정적 확인] cases.py:135~137에 고객 Case·생성 이벤트 저장 경로는 있다. "
     "watch.py:218~259에는 관측·변화 저장만 있고 Case 접수 연결은 없다. "
     "여섯 사건 매핑 S-액-02~S-액-08은 아래 독립 행에 보존하며 현재 연동 완료를 뜻하지 않는다. "
     "DB-04; 공식 코드 대응·선택 규칙 U-선택."),

    ("Trip·알림·링크 서비스", "C-19 결정 11 언어 저장", "trips.preferred_language; notifications.language",
     "[결정] 고객 선택 언어로 우리가 직접 링크·알림을 번역하고 API 수신 에이전트는 자체 번역한다. "
     "[제안] 여행별 선택은 trips.preferred_language·language_revision에, 실제 발행 언어·문구틀 판본은 "
     "notifications에 저장한다. 초기 미선택은 NULL로 두고 고객이 언어를 고르게 한다. [제안] 언어·문구틀별 생성 문구 재사용 저장. "
     "언어 목록을 미리 정하지 않으므로 zh-Hant 등도 고객이 고르면 그 언어로 생성한다. 국적만으로 언어를 정하지 않는다. "
     "여행·하루 시작·출발 안내는 그 언어로 처음 한 번 생성해 저장한 문구틀을 재사용하고 값 채움에는 LLM을 부르지 않아 Case·LLM 없음 계약을 지킨다. "
     "날짜·시각·금액·장소 고유명사·예약번호는 원문 값을 보존한다. 언어 변경은 미발행 문구를 재생성하되 "
     "발행된 알림 이력을 바꾸거나 같은 변경 통지를 추가 발행하지 않는다. DB-01·05."),

    ("DB 관리자·개인정보·운영 담당", "C-20 보존·감사·삭제·복구", "업무 이력; 근거; 알림; 원문·벡터·백업",
     "[제안] Trip·버전·조건·사건은 여행 종료, 관측은 관측 시각, 발송은 처리 종료, 승인·위임은 효력 종료를 "
     "보존 기산점으로 구분한다. 기간·정책 ID·보존 예외는 [미확보] U-운영, 판매 전 확정한다. "
     "평상시 append-only와 보존 종료 후 삭제를 구별한다. 삭제 전용 역할이 근거·원문·청크·벡터·캐시를 "
     "연쇄 정리하고 대상 ID·행위자·사유·시각·요청 ID·결과를 마스킹한 감사 기록에 남긴다. "
     "관리자 접근·토큰 사용 감사는 Case 이벤트만으로 충족하지 않는다. "
     "백업 만료와 복원 뒤 삭제 요청 재적용도 검증한다. RPO·RTO·복원 매체·실제 복구 결과는 미확보다. "
     "기간을 임의의 영구 보존으로 바꾸지 않는다. DB-07, 삭제·복원 시험 미실행."),

    ("DB·성능 담당", "C-21 대표 조회·인덱스", "Q-01~Q-05",
     "아래 다섯 조회를 기준으로 필터·정렬·LIMIT·인덱스를 대조한다. "
     "[미확보] 실제 행 수·분포·평균/피크 빈도·동시성·p95 목표·실행 계획 결과=U-상태. "
     "[제안] DB-08에서 활성 Trip·예약 편중·큰 JSON·관측 누적 데이터를 포함하고 "
     "환경 사양·DB 설정·캐시 조건·반복 수를 기록한다. "
     "EXPLAIN 예상 비용을 밀리초로 해석하지 않는다. 인덱스 추가 전후 읽기·쓰기·공간을 함께 비교한다."),

    ("DB·성능 담당", "Q-01 최신 계획서", "trips; itinerary_versions; itinerary_items",
     "[제안] tenant_id·trip_id로 Trip 1건, current_version_no로 버전과 항목을 조인한다. "
     "trip_id PK와 버전·항목 복합 PK를 사용하고 항목은 starts_at·item_id로 정렬한다. "
     "페이지 크기·최대 항목 수·p95·동시성 U-상태. "
     "알림 미수신·여러 버전 후 링크가 최신 상태와 변경 이유를 반환하는지 DoD-25로 검증. 설계만 존재, DB-08."),

    ("DB·성능 담당", "Q-02 예약 조회", "bookings_tenant_customer_idx",
     "[실측 정적 확인] 010:56~57의 일반 인덱스는 (tenant_id,customer_id,starts_at DESC). "
     "read.booking의 기본 조회는 같은 테넌트·고객, starts_at ASC LIMIT 1이다. "
     "실제 선택 계획·정렬 비용은 미확인. [제안] 사건 처리는 서버가 확인한 booking_id 조건으로 조회하고 "
     "대상 누락 시 이 기본 조회로 폴백하지 않는다. DB-02·08, 분포·빈도·목표 U-상태."),

    ("DB·성능 담당", "Q-03 직전 관측", "watch_observations_latest_idx",
     "[실측 정적 확인] 012:32~33 인덱스는 (tenant_id,target_kind,target_id,observed_at DESC), "
     "watch.py:261~267은 같은 필터·정렬·LIMIT 1을 사용한다. "
     "[제안] 다중 출처 연결 전 source 포함 인덱스·조회로 바꾸고 기존 출처 혼합을 검사한다. "
     "관측 동률 정렬·동시 저장·보존량 조건의 실행 계획은 DB-03·08, U-상태."),

    ("DB·성능 담당", "Q-04 감시·안내 도래 작업", "watch_schedule; notifications",
     "[제안] 감시는 tenant_id·state·next_check_at, 안내는 tenant_id·state·notice_due_at으로 "
     "도래 시각 오름차순·ID 보조 정렬·배치 LIMIT을 사용한다. pending/scheduled 부분 인덱스를 제안한다. "
     "배치 크기와 전체 대상의 재방문 지연을 함께 측정한다. lease 회수와 Trip 종료도 검사한다. "
     "실측 부하·지연 목표 U-상태. 설계만 존재, DB-03·05·08."),

    ("DB·성능 담당", "Q-05 발송 대기", "outbox; watch_changes_pending_idx",
     "[실측 정적 확인] worker.py:42~44는 outbox.status='pending', available_at<=now(), "
     "선택 tenant_id 조건, available_at 정렬, FOR UPDATE SKIP LOCKED LIMIT 1이다. "
     "012의 watch_changes_pending_idx는 별도 표의 (tenant_id,notified_at,detected_at DESC)이며 "
     "outbox 조회를 가속하지 않는다. [제안] outbox pending 부분 인덱스 "
     "(tenant_id,available_at,message_id)는 실행 계획과 쓰기 비용을 본 뒤 채택한다. DB-05·08."),

    ("DB·용량 담당", "C-22 성장·저장 용량", "관측·변화·버전·이벤트·알림·인덱스·백업",
     "[추정] 산식: 기간 말 행 수=초기 행 수+추가-제거. 관측 추가=A*ceil(D*86400/I), "
     "A는 활성 감시 대상 수, D는 일수, I는 대상별 실제 관측 간격 초다. "
     "설계 비교용 7일·120초는 대상당 5,040행, 84초는 7,200행이며 운영 관측 수가 아니다. "
     "가정은 하루 종일 대상별 해당 간격 점검, 중복 제거·종료·실패·stagger 영향 제외다. "
     "실제 I는 배치로 늘 수 있다. 다른 이력은 업무 건수*업무당 기록 수로 계산한다. "
     "주 저장 bytes=합계(객체별 행 수*저장 행 bytes)+인덱스; 필요 공간은 WAL·임시·여유 추가, "
     "전체 보유량은 복제·백업·외부 객체를 별도 합산한다. "
     "A·초기량·행 크기·제거량·복제 수·보존 기간·압축률은 U-상태·U-운영. "
     "최연우가 DB-08 통합 평가 전 기준·상한을 재계산하고 파티션·증설 임계값을 제안한다."),

    ("문서·DB 담당", "C-23 상태와 시험 증거", "모든 E·R·C·Q·M",
     "[결정] 합의본 §1의 네 공통 축과 DB 보조 축을 분리한다. 구현 파일 존재는 정적 파일 확인에 한정한다. "
     "검증 환경 적용은 환경 식별·마이그레이션 목록·체크섬·실제 스키마 대조가 필요하고, "
     "운영 적용은 배포·적용 이력·실제 객체 확인이 별도로 필요하다. "
     "[검증완료]는 시험 ID·버전·환경·입력·통과 기준·결과 위치·판정자·판정일이 있을 때만 부여한다. "
     "이번 문서는 DB·연동 시험 결과를 제공하지 않으므로 적용 여부 미확인으로 남긴다. "
     "합성·Mock·재생은 원천·생성/재생 판본과 원래 관측 시각을 기록한다."),

    ("프로젝트·DB 담당", "C-24 미확보 공통 관리", "U-상태·U-언어·U-소스·U-선택·U-원가·U-운영·U-자원",
     "관리 정본은 " + OPEN_REGISTER + ". "
     "U-상태: 정세환·최연우 R/정세환 A, 최종 검토 전 저장·경로·경합·적용 증적 확보, 미해결 자동 조정 완료 주장 금지. "
     "U-언어: 김지혜 R/정세환 A, 모집 전 언어별 생성 문구의 재사용·원값 보존 검수, 미해결 지원 완료 표현 금지. "
     "U-소스: 서유현 R/정세환 A, 데이터 검토까지 응답·권한·최신성 확인, 미해결 선제 감지 약속 보류. "
     "U-선택: 송채영·김지혜·최상욱 R/정세환 A, 통합 평가 전 코드·선택 규칙 합의, 미해결 임의 순위 금지. "
     "U-원가: 최연우 R/정세환 A, 유료 실증 전·종료까지 단위·SKU·사용량·지원 시간 확보. "
     "U-운영: 김지혜·서유현 R/정세환 A, 판매 전 보존·접근·복구·지원 계약 확정. "
     "U-자원: 정세환 R/A, 범위 검토까지 역할·기한 수락 확인. "
     "이 책임 배정은 기획서의 [제안]이며 수락·상세 날짜는 미확보다. 새 정책을 확정 사실로 쓰지 않는다."),
]

SCENARIO_ROWS = [
    ("S-액-02", "액-02", "system", "activity_weather_risk / incident_report",
     "기상·대기질과 운영사 야외 데크 제한을 별도 근거로 저장. "
     "관측·변화, 사건, 묶음 Case, 실내 전망존 후보·재검증, 적용 버전·변경 통지 순서. "
     "대기질·운영사 공지 연결 U-소스. 다음 일정 영향 없음은 재검증 결과로만 기록."),
    ("S-이동-B1", "이동-B1", "system", "mobility_route_broken / incident_report",
     "무정차 역·영향 노선·효력 시각과 근거 저장. 건대입구+버스·뚝섬+버스 후보를 "
     "도보·소요·배차를 함께 보존. [제안] 배차 값은 대체 소스로 채우고 후보 하나를 골라 적용하며 선택지를 나열하지 않는다. "
     "선택 후 최신 버전으로 재검증. 실시간 운행 U-소스, 선택 규칙 U-선택."),
    ("S-요식-P3", "요식-P3", "customer", "dining_other / incident_report",
     "고객의 70분 지연 신고, 예정 13:00·도착 14:10·15:00 브레이크타임을 출처와 저장. "
     "도보 6분 대안 두 곳·영업 근거·고객 선택·후속 일정 검증을 보존. "
     "전용 코드가 없어 dining_other 대응은 제안, U-선택. 감시 선제 성공으로 집계하지 않음."),
    ("S-이동-A6", "이동-A6", "system", "mobility_route_broken / incident_report",
     "도로 통제 구간·시각·근거와 경로 재조회 결과 저장. "
     "환승 1회 지하철·통제 도보 우회 후보를 검증해 반영. "
     "택시 소요는 확인 불가로 보존하고 추천 근거로 쓰지 않음. 도로 통제·경로 연결 U-소스·U-상태."),
    ("S-요식-P7", "요식-P7", "customer", "dining_closed / incident_report",
     "고객이 본 금일 임시휴무 안내와 목격·접수 시각을 구별. booking_id 없이 항목 ID로 연결. "
     "도보 8분·카드 결제 가능 대안의 근거·후속 일정 영향 검증을 저장. "
     "당일 휴무·카드 결제 확인 U-소스. 고객 신고를 자동 감지로 바꾸지 않음."),
    ("S-액-08", "액-08", "customer", "activity_other / confirm_request",
     "품절 신고의 상품·롯데마트 지점·시각과 고객 질문을 보존. "
     "호텔 귀가 동선의 취급 가능 지점 후보와 재고 미확인을 함께 저장. "
     "전용 코드 없음·추천 선택 규칙 U-선택, 실재고 U-소스. "
     "취급 가능점 추천을 재고 확보로 표시하지 않음."),
]
for sid, event, trigger, routing, detail in SCENARIO_ROWS:
    RULES.append((
        "접수·감시·조정 서비스",
        sid + " 확정 시나리오 사건",
        "change_requests.scenario_event_id=" + event,
        "[결정] 시나리오 사건·고객 행동은 원문 유지. "
        "[제안] trigger_source=" + trigger + ", " + routing + ". " + detail +
        " 저장 계약 C-18, 근거 " + SCENARIO + " §하루 스토리; " + MAPPING + " §2. "
        "연동 검증 미실행, DB-04.",
    ))

RULES.append((
    "평가·Trip 서비스", "C-25 대표 시나리오·DoD 보존", "여섯 사건; DoD-1~26",
    "[결정] 페르소나는 대만인 여성 친구 2명, 서울 하루, 쇼핑·식도락이다. "
    "시스템 시작은 액-02·이동-B1·이동-A6, 고객 시작은 요식-P3·요식-P7·액-08로 각각 3개다. "
    "원문 시간·장소·행동은 시나리오 사실이며 실제 운행·영업·거리의 현장 실측으로 쓰지 않는다. "
    "번체 중국어도 고객이 고르면 보낼 때 그 언어로 생성하므로 언어 목록 제한을 두지 않는다. "
    "신규 소스 대기질·실시간 운행·도로 통제·당일 휴무·재고 다섯을 삭제하지 않는다. "
    "[결정] DoD는 26항목, 자동 20·아키텍처 테스트 4·측정 2이며 시험 결과가 아니다. "
    "[제안] 원문에 없는 되돌림은 시연 보충 단계로 구별하여 DoD-8·9를 검증한다. "
    "기존 승인·위임·보상·도달성·제안 분리·최신 링크·안내 중복 검증도 유지한다."
))
fill(T[6], RULES)

# 4. 변경 이력 및 적용 전략
CHANGES = [
    ("2026-09-10", "본문 재작성 / 적용자 해당 없음",
     "M-01 문서 변경. 합의본 §0-2·§1과 v11 결정 1~13 적용. "
     "엔터티·컬럼을 분리하고 언어·가격·시나리오·DB 적용 상태를 정정. "
     "기존 9개 컬럼 블록을 22개로 확장, 나머지 코어 10개는 객체별 고정 DDL 참조.",
     "E-01~E-32; R-01~R-35; C-01~C-25; Q-01~Q-05; 사건 6개",
     "파일 쓰기·빌드·DB 적용은 이번 검토에서 미실행. "
     "원본 표 8개 머리글·질문·병합 보존 가드를 추가. "
     "기존 생성본 SHA-256=d52284241b83aca63a5629f30776e136c29e374f227754aa99572e2530357f80."),

    ("2026-09-10 정적 확인", "본문 확인 / DB 적용자 미확보 U-상태",
     "M-02 코어 생성·outbox 변경 파일 확인. 001,003,005의 객체·열·제약을 본문과 연결.",
     "E-13~E-16; E-23~E-32; C-01·02·03",
     "구현 파일 존재·적용 여부 미확인. [실측 정적 확인] 로컬 파일 전체 열람. "
     "001 SHA-256=" + EVIDENCE_HASHES[DBDIR + "001_schema.sql"] + "; "
     "003 SHA-256=" + EVIDENCE_HASHES[DBDIR + "003_outbox_tenant_scoped_dedupe.sql"] + "; "
     "005 SHA-256=" + EVIDENCE_HASHES[DBDIR + "005_outbox_resolution.sql"] + "."),

    ("2026-09-10 정적 확인", "본문 확인 / DB 적용자 미확보 U-상태",
     "M-03 010·011 직접 열람. places·bookings·supplier_bookings와 "
     "place_catalog·source_sync_state를 각각 정의. 010은 커머스 삭제가 아님.",
     "E-05~E-09; C-14; Q-02",
     "[실측 정적 확인] 구현 파일 존재·검증/운영 적용 여부 미확인. "
     "010 SHA-256=" + EVIDENCE_HASHES[DBDIR + "010_domain_travel.sql"] + "; "
     "011 SHA-256=" + EVIDENCE_HASHES[DBDIR + "011_place_catalog.sql"] + "."),

    ("2026-09-10 정적 확인", "본문 확인 / DB 적용자 미확보 U-상태",
     "M-04 012 직접 열람。관측·변화 표와 인덱스를 분리. "
     "watch.py의 다섯 지문·출처 누락 조회·관측/변화 분리 커밋·Case 연결 부재를 범위 한정.",
     "E-10·11; C-15·18; Q-03",
     "[실측 정적 확인] 구현 파일 존재·적용 여부 미확인. "
     "012 SHA-256=" + EVIDENCE_HASHES[DBDIR + "012_watch_observations.sql"] + "; "
     "watch.py SHA-256=" + EVIDENCE_HASHES[APPDIR + "modules/travel_ops/watch.py"] + "."),

    ("2026-09-10 정적 확인", "본문 확인 / DB 적용자 미확보 U-상태",
     "M-05 013 직접 열람. places의 공급자 신원 네 열과 일반 인덱스를 명시. "
     "read.booking의 기본 조회와 route·transit None 반환을 정정 근거로 고정.",
     "E-05; C-06·11·12·14",
     "[실측 정적 확인] 구현 파일 존재·적용 여부 미확인. "
     "013 SHA-256=" + EVIDENCE_HASHES[DBDIR + "013_places_source_identity.sql"] + "; "
     "read_tools.py SHA-256=" + EVIDENCE_HASHES[APPDIR + "tools/read_tools.py"] + "."),

    ("예정: 검증 DB 적용 전", "최연우·정세환 [제안]",
     "M-06 DB-02 적용 기준선 대조. [제안] 빈 DB와 기존 DB 업그레이드를 분리한다. "
     "001~009 기존 이력·체크섬·확장·실제 스키마를 먼저 대조하고 010,011,012,013 순으로 "
     "루트 마이그레이션을 적용한다. 010은 customers에 의존, 013은 places에 의존한다. "
     "pending/011_drop_commerce_domain.sql은 011_place_catalog.sql과 다른 후보이며 적용 목록에 섞지 않는다.",
     "기존 001~009; 010~013; 커머스·여행 앱 호환성",
     "적용 여부 미확인 U-상태. 이번 정적 확인으로 001~009 전체 실행 가능성을 판정하지 않았다. "
     "004·006~009의 상세 호환성·기존 적용 로그는 별도 확인. "
     "IF NOT EXISTS가 스키마 일치를 보증하지 않으므로 컬럼·타입·기본값·키·인덱스 대조 필요. "
     "불일치·고아 참조·예상 밖 데이터 삭제·잠금 예산 초과 시 중단. 잠금·시간 임계값 U-운영."),

    ("예정: 여행 쓰기 전환 전", "최연우·정세환 [제안]",
     "M-07 DB-01·04 구현. [제안] Trip·버전·항목·조건·사건 접수 구조를 먼저 추가하고 "
     "구·신 앱 공존, 백필, 소유·조건 대조 후 읽기·쓰기를 전환한다. "
     "기존 예약의 Trip·항목 대응은 확정 근거가 있는 행만 배치 백필하며 미확인은 격리한다. "
     "원래 예약·커머스 표를 추정 매핑으로 삭제하지 않는다.",
     "E-01~E-04; E-13~E-15; E-21; C-02·04·05·10·18",
     "설계만 존재·마이그레이션 미배정. 백필 대상 수·배치 크기·체크포인트·검증 날짜 U-상태. "
     "동일 키 upsert와 진행 위치로 재개하고 기준 버전 변경·매핑 충돌은 중단한다. "
     "두 Case의 같은 Trip 경합, 조건 보존, 원자 커밋 실패, 재계산 1회 소진을 시험한다."),

    ("예정: 감시·안내 통합 전", "서유현·최연우·정세환 [제안]",
     "M-08 DB-03·05 구현. [제안] 소스별 관측 계약·감시 일정·언어·알림 예정/발행 저장을 추가한다. "
     "fingerprint 판본별 기준선을 만들고 기존 관측을 최신 운영 상태로 소급 해석하지 않는다. "
     "013 신원 백필은 같은 테넌트의 공급자 ID·종류를 검증한 결과만 기록한다. "
     "안내 무효화·신규 세대·outbox 발행을 연결하고 배달 작업자 버전 검사를 먼저 배포한다.",
     "E-05·10~12·17·22; C-03·11·12·15·19",
     "설계만 존재·마이그레이션 미배정. route/transit 연결·소스 응답·언어 검수 선행. "
     "미발행 구 안내 취소, 재시작·중복 스윕·발송 결과 불명·일정 변경 경합·출발 재조회 시험 필요. "
     "구 worker가 낡은 안내를 발송할 수 있으면 전환 중단. U-상태·U-소스·U-언어."),

    ("예정: 시연 자동 실행 전", "최연우·정세환 [제안]",
     "M-09 DB-06 구현. suppliers·delegation_scopes·booking_actions를 가칭 설계에서 "
     "마이그레이션으로 구체화하고 tier·승인·철회·한도·보상 기록을 실행 직전에 강제한다.",
     "E-18~E-20; C-09; DoD-13~21",
     "설계만 존재·마이그레이션 미배정. 실제 공급자 자동 실행 차단·simulated 한정·철회 중단·"
     "결과 불명·보상 실패 인계 시험 전에는 시연 실행 분기를 열지 않는다. U-상태."),

    ("예정: 검증 완료·판매 판단 전", "최연우·김지혜·서유현·정세환 [제안]",
     "M-10 DB-07·08 적용 검증·복구. [제안] 빈 DB·기존 DB 업그레이드·대표 조회·경합·"
     "보존 삭제·백업 복원·삭제 재적용을 검증하고 DoD-1~26의 필요한 결과를 연결한다. "
     "추가형 DDL은 우선 구 앱 호환성을 유지해 앱 롤백 또는 전진 수정으로 복구한다. "
     "데이터 삭제·비호환 변경은 검증한 백업 복구 계획 없이 수행하지 않는다.",
     "C-06·16·17·20~25; Q-01~05; 전체 적용 증거",
     "검증 환경 적용·운영 적용은 각각 환경 ID·적용 목록·체크섬·스키마 대조·실행 결과·판정자를 "
     "기록한 뒤 판정한다. DB 생성만으로 앱 연동 완료가 아니다. "
     "RPO·RTO·보존기간·성능 목표·적용/복구 실적·담당 수락·상세 날짜는 U-상태·U-운영·U-자원. "
     "일정은 [제안], DoD 26항목 구성은 [결정], 실행 결과는 미확보."),
]
fill(T[7], CHANGES)

# 표지: 기존 처리 유지
_COVER = {"00기 : _____팀": "32기 : 6팀", "2026. 4. 18.": "2026. 9. 10."}


def _cover_fix(doc):
    def swap(par):
        for k, v in _COVER.items():
            if k in par.text:
                for r in par.runs:
                    if k in r.text:
                        r.text = r.text.replace(k, v)
    for p in doc.paragraphs:
        swap(p)
    for tb in doc.tables[:2]:
        for row in tb.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    swap(p)
                if c.text.strip() == "000":
                    setc(c, "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우")
            if row.cells[0].text.strip() == "깃허브 경로" and not row.cells[1].text.strip():
                setc(row.cells[1],
                     "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM")


_cover_fix(d)

# 저장 직전 필요한 가드
if tuple(r.cells[0].text for r in T[1].rows) != QUESTION_LABELS:
    raise ValueError("양식 질문 칸이 변경되었다.")
for index, xml in HEADER_XML.items():
    if T[index].rows[0]._tr.xml != xml:
        raise ValueError("양식 머리글 또는 병합 변경: 표 " + str(index))
if tuple(
    tuple(x.xml for x in table._tbl.xpath(".//w:gridSpan | .//w:vMerge"))
    for table in T[:2]
) != COVER_MERGES:
    raise ValueError("표지 병합이 변경되었다.")
if len(d.tables) != 8 + len(TABLES) - 1:
    raise ValueError("원본 표 또는 추가 컬럼 표 수가 맞지 않는다.")
if len({row[0] for row in ENTITIES}) != len(ENTITIES):
    raise ValueError("엔터티 ID 중복")
if len({row[0] for row in RELATIONS}) != len(RELATIONS):
    raise ValueError("관계 ID 중복")
if len({row[1].split()[0] for row in RULES}) != len(RULES):
    raise ValueError("규칙·조회·사건 ID 중복")
if {row[1] for row in ENTITIES} != set(COLUMN_DATA):
    raise ValueError("엔터티와 컬럼 정의 범위가 다르다.")
for node in d.element.xpath(".//w:t"):
    check_text(node.text or "")

try:
    d.save(OUT)
except PermissionError:
    base, ext = os.path.splitext(OUT)
    OUT = base + "_새버전" + ext
    print("  원본이 열려 있어 새 이름으로 저장한다:", os.path.basename(OUT))
    d.save(OUT)
print("저장:", os.path.basename(OUT), "| 테이블 정의", len(TABLES), "개")
