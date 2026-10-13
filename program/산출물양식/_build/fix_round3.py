# -*- coding: utf-8 -*-
"""3차 반박 수정 — DB(줄번호 일괄 제거 + 16건) · 요구사항(17건 + REQ-061/062 순서)."""
import re
import shutil
import sys

import openpyxl
from docx import Document

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SUB = "../w2/제출본/"

DB = "[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_2차_여행.docx"
DB_REP = [
    ("DB 엔터티·관계도(ERD) — 실선 테두리는", "DB 엔터티·관계도(ERD). 실선 테두리는"),
    ("001_schema.sql:17; final_project_cs/app/application/controller.py:374", "001_schema.sql, 현재 Case 처리 코드"),
    ("cases.py:109~135의 접수 본문 해시", "현재 접수 코드의 접수 본문 해시"),
    ("verification_policy.py:69는 starts_at_proposed를", "현재 검증 규칙은 제안 시작 시각을"),
    ("read_tools.py:252~258의 route·transit는", "현재 읽기 도구의 경로·대중교통 조회는"),
    ("cases.py:135~137에 고객 Case·생성", "현재 접수 코드에 고객 Case·생성"),
    ("013:9. 공급자 이름.", "013에서 추가. 공급자 이름."),
]
LEAD = re.compile(r"^\s*\d{3}:\d+(?:~\d+)?\.\s*")                 # 칸 맨 앞 「010:17. 」
FILELINE = re.compile(r"(\b[\w]+\.(?:sql|py)):\d+(?:~\d+)?")        # 「010_domain_travel.sql:16」 → 파일명만
PYPATH = re.compile(r"(?:final_project_cs/)?app/[\w/]+/(\w+\.py)")  # 코드 경로 → 파일명만


def fix_db():
    p = SUB + DB
    d = Document(p)
    paras = list(d.paragraphs) + [pp for t in d.tables for r in t.rows for c in r.cells for pp in c.paragraphs]
    seen, n_rep, n_line = set(), 0, 0
    for pp in paras:
        if id(pp._p) in seen or not pp.runs:
            continue
        seen.add(id(pp._p))
        t0 = pp.text
        t = t0
        for a, b in DB_REP:
            if a in t:
                t = t.replace(a, b); n_rep += 1
        t2 = LEAD.sub("", t)
        t2 = FILELINE.sub(r"\1", t2)
        t2 = PYPATH.sub(r"\1", t2)
        t2 = t2.replace("—", ",").replace("–", "-")
        if t2 != t:
            n_line += 1
        if t2 != t0:
            pp.runs[0].text = t2
            for r in pp.runs[1:]:
                r.text = ""
    d.save(p); shutil.copy(p, "../" + DB)
    left = sum(len(FILELINE.findall(x.text)) + len(LEAD.findall(x.text)) for x in paras)
    print("DB: 교체 %d | 줄번호·경로 정리 문단 %d | 남은 줄번호 %d" % (n_rep, n_line, left))


REQ = "[기획] 요구사항 정의서_2차_여행.xlsx"
REQ_REP = [
    ("예약 확정 자체가 필수 조건이거나 금액·시각을 알 수 없어 필수 판정이 불가능하면 자동 적용하지 않는다.", "예약 확정 자체가 필수 조건이면 자동 적용하지 않는다. 필수 판정에 필요한 금액·시각은 1차 조회 실패 시 대체 소스로 구하고 대체까지 실패하면 치명 결함으로 서버를 중단한다."),
    ("일정 제출·신고·질문·거부·기타 입력에 각각 정의된 intent와 issue_code를 기록한다.", "일정 제출·사건 신고·확인 요청·조정 거부·그 외 입력마다 정의된 요청 종류와 사건 코드를 기록한다."),
    ("요청 종류와 issue_code의 객체 종류는 별도 축이다.", "요청 종류와 사건 코드 접두의 객체 종류는 별도 축이다."),
    ("new 상태의 Case로 접수한다.", "신규 상태의 Case로 접수한다."),
    ("고객·에이전트 요청은 customer, 감시 확인 시점 도래는 schedule, 업체 이벤트는 supplier로 기록한다.", "발생원을 고객·에이전트 요청은 고객, 감시 확인 시점 도래는 일정 도래, 업체 이벤트는 업체로 기록한다."),
    ("접두 없는 other 또는", "접두 없는 그 외 코드 또는"),
    ("등록된 Team·issue_code 접두·라우팅 선언 전체.", "등록된 Team·사건 코드 접두·라우팅 선언 전체."),
    ("자동 실행 시연은 simulated 공급자이며", "자동 실행 시연은 모의 등급 공급자이며"),
    ("supplier.tier == 'simulated' 게이트.", "공급자 등급이 모의일 때만 열리는 게이트."),
    ("simulated·유효 위임·대상 소유 확인을", "모의 등급·유효 위임·대상 소유 확인을"),
    ("실제 공급자·tier 누락·위조·범위 밖 위임 입력에서는", "실제 공급자·공급자 등급 누락·위조·범위 밖 위임 입력에서는"),
    ("키는 tenant·request_id·작업 종류", "키는 테넌트·요청 ID·작업 종류"),
    ("customer·원문·신고 시각·대상 항목을 기록한다.", "발생원 고객·원문·신고 시각·대상 항목을 기록한다."),
    ("outbox 발행, publisher 응답의 시각을", "바깥함 발행, 발행기 응답의 시각을"),
    ("판정값이 확정될 때까지 인수를 보류한다.", "한계값은 운영 설계 단계에서 이 요구의 적용 줄에 기록한다. 기록 전에는 AC-01의 구간별 계측·분모 보고 충족만 판정하고 성능 통과로 표시하지 않는다."),
    ("근거: 구현계획서 §1·§9-C / 결정 9·11", "근거: 구현계획서 §1·§9-C / 결정 9"),
    ("번역 전후 시각·날짜·금액·장소 등 고유명사·예약번호의 원문 필드가 동일하다.", "생성 전후 시각·날짜·금액·장소 등 고유명사·예약번호의 원문 필드가 동일하다."),
]


def fix_req():
    p = SUB + REQ
    wb = openpyxl.load_workbook(p); ws = wb.worksheets[0]
    n = 0
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str):
                v = c.value
                for a, b in REQ_REP:
                    if a in v:
                        v = v.replace(a, b); n += 1
                c.value = v
    # REQ-062 가 REQ-061 보다 앞에 있으면 D~G 값을 맞바꾼다
    r61 = r62 = None
    for r in range(5, ws.max_row + 1):
        d = str(ws.cell(r, 4).value or "").strip()
        if d == "REQ-061": r61 = r
        if d == "REQ-062": r62 = r
    if r61 and r62 and r62 < r61:
        for col in range(4, 8):
            a, b = ws.cell(r62, col), ws.cell(r61, col)
            a.value, b.value = b.value, a.value
        print("REQ-061/062 순서 바로잡음 (%d행·%d행)" % (r62, r61))
    wb.save(p); shutil.copy(p, "../" + REQ)
    print("요구사항: 교체 %d" % n)


if __name__ == "__main__":
    fix_db()
    fix_req()
