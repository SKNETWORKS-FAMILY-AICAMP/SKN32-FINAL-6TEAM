# -*- coding: utf-8 -*-
"""수집 데이터 보고서 — 여행 지속관리 CS 플랫폼.

근거: program/plan/A-COP_구현계획서_v11.md 전문 및 2026-09-10 결정, 특히 §7~§7-C.
      wiki/architecture/notifications.md, program/plan/A-COP_비용과_수익구조.md,
      final_project_cs/app/infrastructure/db/migrations/010~013.
기준: 2026-09-10. API·RAG·합성을 구분하고 구현·확보 상태를 명시한다.

★이 양식은 문단이 아니라 **표**로 되어 있다. after_heading 으로 문단을 끼우면
  표 밖에 글이 붙어 양식이 깨진다. python-docx 로 표를 직접 채운다.

★없는 데이터를 있다고 적지 않는다. 합성·Mock 은 그렇게 표시한다.
"""
import copy
import os
import sys

from docx import Document
from docx.shared import Pt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
SRC = os.path.join(FORMS, "[데이터 수집 및 저장] 수집 데이터 보고서.docx")
OUT = os.path.join(FORMS, "[데이터 수집 및 저장] 수집 데이터 보고서_2차_여행.docx")

d = Document(SRC)
T = d.tables


def setc(cell, text, bold=False):
    """셀 하나를 채운다. 기존 문단 서식을 살리려고 첫 run 만 갈아 끼운다."""
    p = cell.paragraphs[0]
    # ★`[2026-09-10 정정]` 첫 문단만 바꾸면 양식 예시가 **둘째 문단 이후에 남는다.**
    #   실제로 수집 데이터 보고서에 「모델 응답 테스트 · 리파인먼트 · 내부 테스트」가
    #   새 본문 밑에 붙어 나갔다. 첫 문단은 서식을 살리려고 두고 나머지를 지운다.
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
    """데이터 행이 모자라면 마지막 행을 복사해 늘린다."""
    while len(tbl.rows) - 1 < need:
        tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))


def fill(tbl, rows, start=1):
    grow(tbl, start - 1 + len(rows))
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            if j < len(tbl.columns):
                setc(tbl.rows[start + i].cells[j], v)


# ── 1. 수집 데이터 개요 ───────────────────────────────────────────────
# 데이터명 | 수집 대상 | 수집 목적 | 사용 예정 기능 | 출처 / 저작권
fill(T[3], [
    ("API · TourAPI 관광정보",
     "서울 관광지·행사·숙박·음식점의 식별자·좌표·기본 정보",
     "장소 카탈로그를 수집하고 일정에 등장하는 장소의 공급자 신원을 해소한다",
     "장소 식별·카탈로그 동기화. 011 표 생성·013 식별 필드 추가 확인; 수집 완료 건수 [미확보]",
     "[외부] 한국관광공사 TourAPI / 공공데이터포털. 무료; 이용·표시 조건 준수"),
    ("API · 기상 예보·관측",
     "서울의 일정 장소·시간에 대응하는 초단기예보·관측",
     "날씨 조건이 걸린 활동을 검증하고 계획서 관련 변화를 감시한다",
     "Activity 감시 입력. 시연은 Mock 기본 + 실물 조회 확인; 저장 예보 재생은 재생으로 표시",
     "[외부] 기상청 공공데이터. 무료; 예보와 사후 관측을 구분"),
    ("API · 장소 영업시간",
     "서울 계획서에 걸린 장소의 영업시간·휴무 정보; 리뷰는 이용 조건 확인 대상",
     "휴무·운영 변경을 확인하고 조회 시각과 출처를 남긴다",
     "Activity·Dining 입력. 소량 호출 또는 Mock; 현재 대기·혼잡은 원래 알 수 없는 값이라 판정 입력에서 뺀다",
     "[외부] Google Places API. 유료·조건부; 단가 [미확보], 캐싱·표시 조건 확인"),
    ("API · 이동 시간·경로",
     "일정 구간의 이동 시간·운행 정보와 각 항목 출발 안내용 경로",
     "출발 시각 = 시작 − 이동 시간 − 여유. 사전 조회로 재산정하고 출발 안내 시 경로를 다시 조회한다",
     "코어 검증·Mobility·③ 출발 안내. [미구현] read.route·read.transit는 항상 None; 이동 시간 계산 불가",
     "[외부] Google Routes API. 유료; 단가 [미확보]. 경로 상세 수준·사전 조회 시점 [미확보]"),
    ("API · 감시 관측·변화 이력",
     "계획서에 걸린 대상의 관측값·fingerprint·변경 전후·영향받은 예약",
     "판정 관련 필드만 해시하여 직전 관측과 비교하고 변화의 근거를 보존한다",
     "012의 watch_observations·watch_changes 수집. 최소 84초·기본 2분; 카탈로그 전수 폴링 제외",
     "API 응답에서 내부 생성. 현재 대상은 예약에서 추출; 변화→Case 연결 [미구현], 소스별 주기·수집량 [미확보]"),
    ("RAG · 취소·환급 규정",
     "서울 활동의 취소 기한·위약금율·우천 규정 등 잘 변하지 않는 문서",
     "문서 근거를 검색하고 계산 가능한 취소·환급 조건은 코드 판정 규칙으로 전환한다",
     "Activity·Booking Handoff 근거. 여행 코퍼스 전량 교체 대상이며 확보량 [미확보]",
     "[외부] 업체 공개 약관·소비자분쟁해결기준. 공개 여부와 저장·모델 입력 권한은 별도 확인"),
    ("RAG · 동행 조건·변경 안내",
     "식단·연령·인원 조건 문서와 업체 변경 페이지 안내·링크 틀",
     "Trip·항목 조건을 보존하고 업체 건의 대안·차액·변경 링크를 정리한다",
     "지식 문서 표 활용 계획. 변동 영업정보는 API로 조회; 무료·무예약 활동도 Activity 범위",
     "[외부] 시설·예약처 공개 안내. 표본 문서·사별 딥링크 규격 [미확보]; 실제 업체 연동으로 간주하지 않음"),
    ("합성 · 여행·예약·고객",
     "서울 인바운드 7일 여행 20~30건: 일정·잠긴 예약·동행 조건·가상 고객",
     "실제 고객 기록 없이 검증·라우팅·되돌림을 평가한다",
     "§7 생성 목표. case_type은 issue_code 접두; intent는 itinerary_submit·incident_report·confirm_request·adjust_reject·other",
     "[추정] 생성 목표 20~30건, 완료 건수 [미확보]. 자체 생성 계획이며 실제 고객 데이터가 아님"),
    ("합성 · 사건 시나리오",
     "10개 생성 목표: 우천 취소·휴무·운행 중단·무료 활동·동시 다발 등",
     "한 스윕·한 Trip의 사건을 Case 하나로 묶어 재검증·일괄 적용·통지·재요청을 평가한다",
     "①변경(생성 포함) ②여행·하루 시작 ③항목 출발 안내 시험. ②·③은 Case·LLM 없이 문구틀 사용 계획",
     "[추정] 자체 생성 목표 10개, 완료 건수 [미확보]. DoD 26항목(자동 20·아키텍처 4·측정 2)의 여행 평가 입력"),
    ("합성 · 공급자 원장·시뮬레이터",
     "Mock 예약 원장·위임 범위·차액·위약금·보상 거래 실패 입력",
     "우리 예약과 공급자 원장을 대조하고 승인 경계·인계·되돌림 실패를 시험한다",
     "Booking Handoff 시연 계획. [미구현] tier == 'simulated' 게이트: [실측 2026-09-10] app/·tests/ 0건; 자동 실행 분기 없음",
     "자체 합성 계획. 실제 업체 계약·예약 자동화가 아님; 현재 변경·취소는 승인 대기"),
])

# ── 2.1 / 2.2 수집 방식 체크 ─────────────────────────────────────────
# (수집 방식 | 선택 | 수집 방식 | 선택) 4열
# ★`[2026-09-10]` 양식의 질문 칸(0열 라벨)은 바꾸지 않는다. 답은 값 칸, 우리 항목은 덧붙인 행 (템플릿_합의본 0-2)
fill(T[4], [
    ("웹 크롤링",
     "☐ 쓰지 않는다. 공개 사이트 공지는 감시 2단계 후보(표본·방식 [미확보])",
     "API 호출",
     "☑ 공공 무료(TourAPI·기상청) + 상용 유료(Places·Routes: 단가 공개 [외부] · 사용량 [미확보] · Mock 허용)"),
    ("사용자 입력",
     "☑ 개인 에이전트가 제출하는 일정·사건 신고 (평가용은 합성)",
     "문서 파일 업로드 (PDF, CSV 등)",
     "☑ 공개 규정 문서 선별·RAG 적재 (여행분 교체 대상)"),
    ("기타: 자체 합성 생성(여행·사건·Mock). 제휴 업체 직접 수신은 MVP 밖",
     "☑"),
])

# 2.2 한 줄 표 셋 — 「라벨 | 값」. 값은 1열
setc(T[5].rows[0].cells[1],
     "Python 3.12 + httpx, pydantic. API 조회·RAG 문서 적재·합성 시드를 구분한다. 저장은 PostgreSQL")
setc(T[5].rows[1].cells[1],
     "감시 루프(계획서에 걸린 대상만, 최소 84초·기본 2분, 소스별 주기 [미확보])와 배달 루프(outbox 일꾼)가 따로 돈다. 지금은 로컬 주기 실행")
setc(T[5].rows[2].cells[1],
     "조회 실패는 대체 소스로 바꿔 값을 내고, 대체까지 실패하면 치명 결함으로 서버를 끈다(v11 §4-D, 결정 15). 값을 지어내지 않는다. 알림 중복은 outbox UNIQUE(tenant_id, topic, dedupe_key)로 막는다. 묶음 조정은 부분 반영 없이 실패 근거를 사람에게 인계한다(§6-C). 재시도 횟수·대기 간격 [미확보]")

# ── 3.1 파일 및 필드 설명 ────────────────────────────────────────────
# 파일명/테이블명 | 필드명 | 데이터 타입 | 설명 | 예시
fill(T[6], [
    ("places (010·013)",
     "place_id / source_name / source_content_id / source_content_type_id / source_resolved_at",
     "uuid / text / text / text / timestamptz",
     "[실측] 정의 존재. 내부 장소와 공급자 식별자를 연결하며 이름만으로 동일 장소라고 판정하지 않는다",
     "[추정] source_name=tour_api, source_content_type_id=12"),
    ("place_catalog (011)",
     "tenant_id / source / content_id / source_modified_at / fetched_at / raw_json",
     "text / text / text / text / timestamptz / jsonb",
     "[실측] 정의 존재. (tenant_id, source, content_id) 유일; 공급자 수정 시각과 수집 시각을 구분한다",
     "[추정] source=tour_api, fetched_at=2026-09-10T09:00+09:00"),
    ("source_sync_state (011)",
     "scope / next_page / rows_seen / delta_trusted / high_water",
     "text / int / int / boolean / text",
     "[실측] 정의 존재. 카탈로그 수집 재개·변경분 동기화 상태; rows_seen을 수집 완료 건수로 단정하지 않는다",
     "[추정] next_page=2, delta_trusted=false"),
    ("bookings (010)",
     "booking_id / place_id / starts_at / locked / party_size / capacity / amount_cents",
     "uuid / uuid / timestamptz / boolean / int / int / int",
     "[실측] 정의 존재. read.booking은 booking_id가 없으면 시작 시각이 가장 이른 예약(과거·취소도 안 거른다)을 반환하며 case_id를 사용하지 않는다",
     "[추정] kind=activity, locked=false"),
    ("supplier_bookings (010)",
     "booking_id / supplier / supplier_ref / status / confirmed_at",
     "uuid / text / text / text / timestamptz",
     "[실측] 정의 존재. 우리 예약과 대조할 별도 원장; 표 존재는 실제 공급자 연동의 증거가 아니다",
     "[추정] supplier=mock_supplier, status=confirmed"),
    ("watch_observations (012)",
     "target_kind / target_id / source / fingerprint / payload / observed_at",
     "text / text / text / text / jsonb / timestamptz",
     "[실측] 정의 존재. 매 폴링 관측과 판정 관련 필드 해시. (tenant_id, target_kind, target_id, observed_at) 유일",
     "[추정] target_kind=place, payload={\"open_at_slot\": false}"),
    ("watch_changes (012)",
     "before_json / after_json / summary / affected_bookings / detected_at / notified_at / notify_error",
     "jsonb / jsonb / text / jsonb / timestamptz / timestamptz / text",
     "[실측] 정의 존재. fingerprint 변화의 전후·영향 예약·통지 기록; 수신·열람 확인을 뜻하지 않는다",
     "[추정] summary=영업 상태 변경, notified_at=NULL"),
    ("knowledge_documents / knowledge_chunks",
     "source_uri / version / content / metadata_json",
     "text / text / text / jsonb",
     "[실측 2026-09-09] 25문서/306청크 전부 쇼핑몰. 문서·청크 표는 유지하고 여행 내용은 전량 교체 대상",
     "여행 규정 적재 건수 [미확보]"),
    ("trips",
     "trip_id / status",
     "uuid / text (설계)",
     "[미구현] 마이그레이션 없음. 여행 전체 상태·최신 계획서의 기준 집합체 설계",
     "[추정] status=active"),
    ("itinerary_versions",
     "version_no / created_by",
     "int / text (설계)",
     "[미구현] 마이그레이션 없음. 불변 버전 추가·최신 포인터·되돌림 설계",
     "[추정] version_no=7, created_by=system"),
    ("itinerary_items",
     "item_id / starts_at / ends_at / place_ref / is_locked",
     "uuid / timestamptz / timestamptz / uuid / boolean (설계)",
     "[미구현] 마이그레이션 없음. 무료·무예약 항목도 시작·끝·장소·비용·잠김을 보존하며 예약은 선택 정보",
     "[추정] 경복궁 방문 항목, booking_id 없음"),
    ("trip_constraints (가칭)",
     "scope / ref_id / kind / value",
     "text / uuid / text / 형식 [미확보] (설계)",
     "[미구현] 마이그레이션 없음. scope=trip|item 한 표로 보존; 전체 조건과 항목 조건을 모두 만족해야 한다",
     "[추정] scope=item, kind=party_size"),
    ("watch_schedule",
     "next_check_at",
     "timestamptz (설계)",
     "[미구현] 마이그레이션 없음. 다음 감시 시점 저장 설계; 012 관측 이력과 별개",
     "[추정] 2026-09-10T09:02+09:00"),
])

# ── 3.2 데이터 양 ────────────────────────────────────────────────────
setc(T[7].rows[0].cells[1],
     "API: 서울 카탈로그·관측·변화의 저장 완료 건수 [미확보]. RAG: [실측 2026-09-09] 25문서/306청크 전부 쇼핑몰, 당시 datasets/에 여행 없음; 여행분 전량 교체 대상. 합성: 여행 20~30건 + 사건 10개 생성 목표 [추정], 완료 건수 [미확보]. 출발 안내 조회는 7일 여행당 20~40회 [추정]이며 사전 조회·재계산은 별도; 유료 API 단가는 공개 [외부], 사용량·인계 비율·처리 시간 [미확보].")
setc(T[7].rows[1].cells[1],
     "[미확보] 품질 통과 기준을 아직 정하지 않았다. 확보량·검사량·품질 통과량·사용 가능량을 따로 세며 예정량을 합산하지 않는다")

# ── 3.3 저장 위치 및 포맷 ────────────────────────────────────────────
setc(T[8].rows[0].cells[1],
     "계획: datasets/travel/<이름>/raw·processed·scripts·REPORT.md (확보 완료 경로가 아니다). PostgreSQL: 010 여행 표, 011 카탈로그·동기화 상태, 012 관측·변화 이력, 013 places 공급자 신원 필드. RAG는 knowledge_documents·knowledge_chunks; Trip·일정 버전·항목·조건·감시 일정은 설계 [미구현]")
setc(T[8].rows[1].cells[1],
     "☐ CSV    ☑ JSON    ☐ SQLite    ☑ 기타: PostgreSQL 표 · 합성은 JSONL")
setc(T[8].rows[2].cells[1],
     "☑ UTF-8    ☐ 기타: __________")

# ── 4. 법적·윤리적 검토 ──────────────────────────────────────────────
# ★`[2026-09-10]` 양식의 질문 칸(0열 라벨)은 바꾸지 않는다. 답은 값 칸, 우리 항목은 덧붙인 행 (템플릿_합의본 0-2)
fill(T[9], [
    ("개인정보 포함 여부",
     "☐ 포함    ☑ 미포함 — 평가용 여행·예약·고객은 합성 생성 계획. 실제 고객 기록과 공개 리뷰를 합성 자료로 간주하지 않는다."),
    ("포함된 경우 필드",
     "[해당 없음] 지금 수집 자료에는 없다. 운영 입력의 여행 토큰·알림 채널(디스코드 웹훅) 주소는 사람과 연결될 수 있어 공개 데이터셋에 넣지 않는다. 운영 개인정보 범위는 [미확보]."),
    ("비식별화 조치 여부",
     "☐ 이름 마스킹    ☐ 고유키 대체    ☑ 기타: 실제 고객 기록을 쓰지 않고 합성으로 대체. 실제 수행 기록의 동의 범위는 MVP 이후 파일럿에서 정한다."),
    ("출처 및 사용권 — 공개 여부",
     "☐ 공개    ☑ 내부사용 한정 — 출처·확인 시각을 보존하고 계획서 링크·API 응답에서 표시 조건을 지킨다. 외부 응답을 재판매하거나 범용 중계 권한이 있다고 가정하지 않는다. Mock·합성·저장 예보 재생은 현장 확인과 구별한다."),
    ("라이선스 / 약관 검토 여부",
     "[외부] TourAPI·기상청은 무료 공개 API이나 이용 조건을 따른다. Places·Routes는 유료이며 단가는 공개(사업 검토서 v3 §7), 사용량은 [미확보]. 리뷰 원문 장기 저장·재배포 권한을 가정하지 않는다. 모델 입력 허용 범위는 자료별로 확인한다. 검토 완료 여부 [미확보]."),
    ("검토자",
     "[미배정] 데이터 담당 서유현·김지혜 [제안]"),
    ("검토 일자",
     "[미확보] 수집 착수 전 [제안]"),
    ("언어 (우리 항목)",
     "API 경로 출력은 한국어이고 번역은 개인 에이전트가 한다(v11 결정 11). 고객에게 직접 가는 알림·링크는 보낼 때 고객이 고른 언어로 생성하며 언어 목록을 미리 정하지 않는다(v11 결정 14). 같은 문구틀·같은 언어는 처음 한 번 생성하고 재사용하며, 시각·날짜·금액·고유명사·예약번호는 원값을 싣는다. 확정 페르소나(대만)의 번체 중국어도 같은 방식으로 생성한다. datasets/mt/*는 제품 경로에서 제외."),
    ("동의·접근 (우리 항목)",
     "여행 토큰·웹훅 주소를 공개 데이터셋에 넣지 않는다. 링크 열람 시각은 운영 정보로 다루고 알림 수신 확인을 제품 조건으로 두지 않는다."),
], start=0)

# ── 5. 데이터 품질 및 정합성 관리 ────────────────────────────────────
# ★`[2026-09-10]` 양식의 질문 칸(0열 라벨)은 바꾸지 않는다. 답은 값 칸, 우리 항목은 덧붙인 행 (템플릿_합의본 0-2)
fill(T[10], [
    ("중복 제거 기준",
     "장소 카탈로그는 tenant_id+source+content_id, 장소는 013 공급자 신원으로 식별한다. 관측은 대상·시각별 보존하고 fingerprint 변화만 분리한다. 멱등 대상 설계는 서버가 실재·소유를 확인한 객체 id; activity.*·dining.*는 예약 있으면 booking_id, 없으면 item_id. 현재 case_id 고정 경로 교체 [미구현]."),
    ("정합성 검증 방법",
     "§6-C 자동 적용 탈락: ①필수 조건 위반 ②잠긴 예약 변경 ③실행 권한·근거 부족. 통과안은 변경 항목 수→추가 비용→시간 차이(최대→합계)→되돌림 용이성 순으로 비교하며 동률은 정규화 후보 id로 결정한다. 부분 반영 없이 실패 근거를 인계하고, 업체 변경 필요·미확정은 기존 확정 예약과 함께 표시하는 설계이다."),
    ("Null 처리 및 결측치 전략",
     "값을 모르는 상황을 만들지 않는다(v11 결정 15). 필요한 값마다 대체 소스를 두고, 1차 조회가 실패하면 대체 소스로 바꿔 값을 내며, 대체까지 실패하면 치명 결함으로 서버를 끈다. 0이나 빈칸으로 채우거나 모델이 지어내지 않는다. 원래 알 수 없는 값(현재 대기·실제 혼잡)은 판정 입력에서 뺀다. 후보 값이 불확실해도 하나를 고르고 선택지를 나열하지 않는다."),
    ("표준화 전략",
     "공급자 수정 시각·수집 시각·예보 대상 시각·변화 감지 시각을 구분한다(timestamptz). 재조회 시각을 현장 관찰 시각으로 표시하지 않는다. 장소는 013 공급자 신원으로 정규화한다. Mock·합성 입력과 예상 결과를 구별하고, 과거 기상 재생은 저장 예보와 시뮬레이션 시각을 사용한다."),
    ("신선도·알림 검증 (우리 항목)",
     "계획서 관련 대상만 최소 84초·기본 2분 감시하며 소스별 주기는 [미확보]. Places의 오늘 포함 7일 정보는 현장 개점 확인이 아니다. 변경과 안내 시점을 각각 판정하고, 변경 통지는 적용 버전당 하나로 설계한다. 일정 변경 시 미발행 출발 안내를 무효화·재산정하고 outbox 중복 방지를 검증한다. Routes 미구현 상태에서 경로·출발 시각을 지어내지 않는다."),
], start=0)

# ── 6. 변경 이력 ─────────────────────────────────────────────────────
fill(T[11], [
    ("2026-09-08",
     "전체",
     "커머스 CS에서 여행 지속관리 CS로 수집 대상을 교체한 최초 작성 기록",
     "v10 §7 (보존 이력)"),
    ("2026-09-10",
     "전체",
     "서울·한국어 기준으로 API·RAG·합성을 재구분; 번역 자료를 제품 수집 대상에서 제외",
     "v11 §0-4·§1·§7-A"),
    ("2026-09-10",
     "전체",
     "010~013 정의와 설계 표를 구별하고 감시 관측·변화·공급자 신원을 반영; 데이터 적재 건수는 미확보로 표시",
     "v11 §7-B·§7-C / migrations 010~013"),
    ("2026-09-10",
     "전체",
     "알림 세 시점·묶음 조정·최신 링크·미확정 예약을 평가 입력에 반영. 화면 범위는 운영자 넷(일정·사건·승인·추적)+고객 링크 하나",
     "v11 §6-A~§6-C·§9-C·§12"),
    ("2026-09-10",
     "전체",
     "무료·유료 소스와 미확보 단가를 구분하고 RAG 실측·합성 목표를 정정; 이동 조회·자동 실행 게이트 미구현 명시",
     "비용과 수익구조 / [실측 2026-09-09~10]"),
    ("[예정]",
     "서유현·김지혜",
     "서울 표본 커버리지·규정 코퍼스·딥링크·API 단가·합성 완료 건수 확인. 착수 2026-09-08, 최종발표 2026-10-26; 09-10 기준 잔여 6주 4일",
     "확보 일정 [미확보]; §9-B 주차 배분은 [추정]"),
])

# ── 표지 ────────────────────────────────────────────────────────────
# ★`[2026-09-10]` 양식 자리표시자가 그대로 나가고 있었다 — "00기 : _____팀",
#   작성 팀원 "000", 제출 일자 "2026. 4. 18.". 심사 제출본에 남으면 안 된다.
#   기획서와 같은 값으로 맞춘다.
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

try:
    d.save(OUT)
except PermissionError:
    base, ext = os.path.splitext(OUT)
    OUT = base + "_새버전" + ext
    print("  원본이 열려 있어 새 이름으로 저장한다:", os.path.basename(OUT))
    d.save(OUT)
print("저장:", os.path.basename(OUT))
