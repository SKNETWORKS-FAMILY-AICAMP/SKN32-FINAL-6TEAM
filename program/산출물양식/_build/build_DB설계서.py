# -*- coding: utf-8 -*-
"""데이터베이스와 저장소 설계 문서(DB, Vector DB 설계서)를 만든다.

테이블 소유 경계는 A-COP_구현계획서_v8.md 16절, 관계는 11절을 따른다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from docxfill import Doc, esc, check

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FORMS))
c = lambda n: os.path.join(REPO, "program", "plan", "diagram", "charts", n)

d = Doc(os.path.join(FORMS, "[데이터 수집 및 저장] 데이터베이스_저장소 설계 문서.docx"),
        os.path.join(HERE, "_tmp_db"))

d.replace_text("SK 네트웍스 Family AI 00기 : _____팀",
               "SK 네트웍스 Family AI 32기 : 6팀 A-COPilot")
d.replace_text("2026. 4. 18. ", "2026. 9. 10.")
d.replace_text("000", "김지혜, 서유현, 송채영, 정세환, 최상욱, 최연우")
d.fill_empty_para("00000014", "https://github.com/roroblack/A-COP.git")
d.fill_empty_para("00000015", "https://github.com/roroblack/A-COP.git")


def fill_row(row_xml, values):
    cells = list(re.finditer(r'<w:tc>.*?</w:tc>', row_xml, re.S))
    assert len(cells) == len(values), "셀 수가 다르다 %d vs %d" % (len(cells), len(values))
    out, last = [], 0
    for m, val in zip(cells, values):
        check(val)
        cell, seen = m.group(0), [False]

        def sub(mm):
            if not seen[0]:
                seen[0] = True
                return '<w:t xml:space="preserve">%s</w:t>' % esc(val)
            return '<w:t xml:space="preserve"></w:t>'
        cell = re.sub(r'<w:t[^>]*>[^<]*</w:t>', sub, cell)
        out.append(row_xml[last:m.start()] + cell)
        last = m.end()
    return "".join(out) + row_xml[last:]


def replace_rows(first_anchor, last_anchor, rows):
    i = d.xml.index(first_anchor)
    rs = d.xml.rindex("<w:tr>", 0, i)
    re_ = d.xml.index("</w:tr>", d.xml.index(last_anchor)) + len("</w:tr>")
    tpl = re.sub(r' w14:paraId="[0-9A-F]{8}"', "",
                 d.xml[rs:d.xml.index("</w:tr>", rs) + len("</w:tr>")])
    d.xml = d.xml[:rs] + "".join(fill_row(tpl, r) for r in rows) + d.xml[re_:]


# ---------------------------------------------------------------- 1. 모델링 방법
d.replace_para("00000028", [
    "모델링 방법. 업무 상태를 단일 원천 하나에 모으는 방식으로 설계했다. "
    "Case 생명주기와 Action 트랜잭션은 PostgreSQL 한 곳에서만 관리한다. "
    "지식 검색은 같은 PostgreSQL 안의 pgvector 확장을 쓰므로 트랜잭션을 함께 묶을 수 있다.",
])
d.replace_para("00000029", [
    "정규화 수준. 3정규형을 기본으로 한다. 다만 Case 이벤트와 감사 로그는 "
    "추가만 하고 고치지 않는 append only 방식이라 정규화보다 재생 가능성을 우선한다.",
])
d.replace_para("0000002A", [
    "도구. SQLAlchemy 로 모델을 정의하고 Alembic 으로 스키마를 옮긴다. "
    "Alembic 은 단일 브랜치로 유지하고 revision 을 만들기 전에 main 을 rebase 한다.",
])
d.insert_after_para("0000002A", d.build([
    ("b", "저장소를 셋으로 나눈 이유"),
    "업무 상태, 지식 검색, 관계 조회는 성격이 다르다. 하나에 다 넣으면 한쪽 부하가 다른 쪽을 끌어내린다. "
    "다만 업무 상태와 Action 트랜잭션은 반드시 한 곳에 모은다. "
    "두 곳에 나누면 어느 쪽이 진짜인지 판정할 수 없기 때문이다.",
    ("img", c("07_storage.png"), "그림 1. 저장소 구조. Graph Store 는 Port 로 분리해 두고 "
                                 "채택 기준을 넘을 때만 켠다.", 6.2),
]))

# ---------------------------------------------------------------- 2.1 엔터티 목록
ENTITIES = [
    ("Primary Key", "customer_cases", "case_id", "UUID PK", "tenant_id, customer_id, status, intent"),
    ("Primary Key", "case_events", "event_id", "BIGSERIAL PK", "case_id(FK), event_type, payload, created_at"),
    ("Primary Key", "shared_state", "case_id", "UUID PK", "version, state(JSONB), updated_at"),
    ("Primary Key", "agent_runs", "run_id", "UUID PK", "case_id(FK), team_id, started_at, status"),
    ("Primary Key", "team_tasks", "task_id", "UUID PK", "run_id(FK), team_id, input, result"),
    ("Primary Key", "outbox", "outbox_id", "BIGSERIAL PK", "topic, payload, published_at"),
    ("Primary Key", "action_requests", "action_id", "UUID PK",
     "case_id(FK), action_type, payload, idempotency_key"),
    ("Primary Key", "action_approvals", "approval_id", "UUID PK",
     "action_id(FK), approver, decision, decided_at"),
    ("Primary Key", "audit_logs", "audit_id", "BIGSERIAL PK", "actor, action, target, created_at"),
    ("Primary Key", "knowledge_documents", "document_id", "UUID PK", "tenant_id, title, source, version"),
    ("Primary Key", "knowledge_chunks", "chunk_id", "UUID PK",
     "document_id(FK), content, embedding vector(1536)"),
    ("Primary Key", "tenants", "tenant_id", "UUID PK", "name, created_at"),
    ("Primary Key", "customers", "customer_id", "UUID PK", "tenant_id(FK), external_ref"),
    ("Unique", "action_requests", "idempotency_key", "UNIQUE",
     "같은 요청이 여러 번 들어와도 부수효과가 한 번만 일어나게 막는다"),
    ("Unique", "shared_state", "case_id, version", "UNIQUE",
     "비교 후 교체를 위한 버전 관리. 버전이 다르면 쓰기를 거부한다"),
]
replace_rows("users", "사용자 이메일 중복 방지", ENTITIES)

# ---------------------------------------------------------------- 2.2 관계
RELATIONS = [
    ("테넌트와 고객", "tenants", "customers", "1:N"),
    ("고객과 Case", "customers", "customer_cases", "1:N"),
    ("Case와 이벤트", "customer_cases", "case_events", "1:N"),
    ("Case와 공유 상태", "customer_cases", "shared_state", "1:1"),
    ("Case와 실행 기록", "customer_cases", "agent_runs", "1:N"),
    ("실행과 Team 작업", "agent_runs", "team_tasks", "1:N"),
    ("Case와 액션 요청", "customer_cases", "action_requests", "1:N"),
    ("액션과 승인", "action_requests", "action_approvals", "1:N"),
    ("문서와 조각", "knowledge_documents", "knowledge_chunks", "1:N"),
]
replace_rows("사용자 - 소셜", "chat_messages", RELATIONS)

# ---------------------------------------------------------------- 2.3 ERD
d.insert_after_para("0000006B", d.image_xml(c("uml_erd_v2.png"), 5.6)
                    + d.caption("그림 2. 개체 관계도. 업무 상태와 Action 트랜잭션이 한 저장소 안에 있다."))

# ---------------------------------------------------------------- 3.1 테이블 정의서
d.replace_para("0000006E", ["테이블 : customer_cases"])
COLUMNS = [
    ("case_id", "UUID", "O", "", "O", "Case 고유 식별자"),
    ("tenant_id", "UUID", "", "O", "O", "tenants.tenant_id 를 가리킨다"),
    ("customer_id", "UUID", "", "O", "O", "customers.customer_id 를 가리킨다"),
    ("status", "VARCHAR", "", "", "O", "12개 상태 중 하나. 전이표에 없는 값은 거부한다"),
    ("intent", "VARCHAR", "", "", "", "billing, technical, other 중 하나"),
    ("issue_code", "VARCHAR", "", "", "", "이슈 분류 코드"),
    ("severity", "SMALLINT", "", "", "", "심각도"),
    ("sentiment", "VARCHAR", "", "", "", "감성 분류 결과"),
    ("created_at", "TIMESTAMPTZ", "", "", "O", "기본값은 현재 시각이다"),
    ("updated_at", "TIMESTAMPTZ", "", "", "", "마지막 전이 시각"),
]
replace_rows("user_id", "DEFAULT:CURRENT_TIMESTAMP,  가입일시", COLUMNS)

# ---------------------------------------------------------------- 3.2 제약
CONSTRAINTS = [
    ("DB 레벨", "PK", "모든 테이블", "각 테이블의 고유 식별자를 보장한다"),
    ("DB 레벨", "FK", "case_events.case_id", "customer_cases.case_id 를 가리킨다. 삭제 시 함께 지운다"),
    ("DB 레벨", "FK", "action_requests.case_id", "customer_cases.case_id 를 가리킨다"),
    ("DB 레벨", "FK", "action_approvals.action_id", "action_requests.action_id 를 가리킨다"),
    ("DB 레벨", "FK", "knowledge_chunks.document_id", "knowledge_documents.document_id 를 가리킨다"),
    ("DB 레벨", "UNIQUE", "action_requests.idempotency_key",
     "같은 요청 10회에 실제 부수효과가 1회만 일어나게 만드는 핵심 제약이다"),
    ("DB 레벨", "CHECK", "customer_cases.status", "허용된 12개 상태 값만 저장한다"),
    ("DB 레벨", "INDEX", "FK 컬럼 전체", "조인과 조회 성능을 위해 건다"),
    ("DB 레벨", "INDEX", "knowledge_chunks.embedding", "pgvector 의 근사 최근접 검색 인덱스"),
    ("DB 레벨", "NOT NULL", "필수 컬럼 전체", "빈 값 저장을 원천 차단한다"),
    ("앱 레벨", "비교 후 교체", "shared_state.version",
     "읽은 버전과 다르면 쓰기를 거부하고 다시 읽게 한다. 나중 쓰기가 앞선 쓰기를 덮지 않는다"),
    ("앱 레벨", "상태 전이 검사", "customer_cases.status", "허용된 다음 상태 표를 벗어나면 거부한다"),
    ("앱 레벨", "append only", "case_events, audit_logs", "추가만 하고 고치지 않는다. 그래야 재생과 감사가 된다"),
    ("앱 레벨", "트랜잭션", "Outbox 발행", "DB 기록과 메시지 발행을 한 트랜잭션으로 묶는다"),
]
replace_rows("모든 테이블", "여러 테이블 동시 변경 시 원자성 보장", CONSTRAINTS)

# ---------------------------------------------------------------- Vector DB 와 Graph DB 절 추가
d.insert_before_para("000000C6", d.build([
    ("b", "4. Vector DB 설계"),
    "지식 문서를 조각으로 나눠 pgvector 에 넣는다. pgvector 는 PostgreSQL 확장이라 "
    "별도 서버를 세우지 않고 같은 트랜잭션 안에서 다룰 수 있다.",
    ("l", "저장 대상. 정책 문서, FAQ, 응대 지침, 상품과 배송 안내"),
    ("l", "조각 나누기. 문단 경계를 우선하고 너무 짧은 조각은 앞뒤와 합친다. "
          "조각마다 원본 문서와 위치를 남겨 인용을 되짚을 수 있게 한다."),
    ("l", "임베딩. 조각 본문을 벡터로 바꿔 embedding 컬럼에 넣는다. 차원 수는 모델에 맞춘다."),
    ("l", "검색. 질문 벡터와 가까운 조각을 찾아 ContextPack 에 넣는다. "
          "테넌트와 Team 권한 범위 밖의 문서는 애초에 후보에 넣지 않는다."),
    ("l", "판정. 검색 결과가 없거나 유사도가 기준 아래면 근거 부족으로 본다. "
          "지어낸 답을 내보내지 않고 사람에게 넘긴다. 임계값은 실제 분포를 측정한 뒤 확정한다."),
    ("l", "버전. 문서가 바뀌면 새 버전으로 넣고 이전 버전을 지우지 않는다. "
          "과거 Case 가 인용한 근거를 나중에도 그대로 볼 수 있어야 하기 때문이다."),
    ("b", "5. Graph DB 설계"),
    "Case, 이슈, 정책, Team, Action 사이의 관계를 다룬다. "
    "관계를 따라가며 묻는 질문에 강하지만, 지금 단계에서는 필수가 아니다.",
    ("l", "다루는 관계. Case 와 이슈, 이슈와 정책, 정책과 Team, Team 과 Action"),
    ("l", "구현 선택지. Apache AGE 또는 Neo4j 를 후보로 둔다. "
          "지금 실제로 동작하는 선택은 PostgreSQL 기반 구현이다."),
    ("l", "Port 와 Adapter 로 분리한다. Core 는 GraphStorePort 만 알고 어떤 제품인지 모른다. "
          "갈아 끼워도 Controller 는 바뀌지 않는다."),
    ("l", "채택 기준. 8주차와 9주차 비교 실험에서 관계 질문의 정답률과 응답 시간을 "
          "pgvector 단독 구성과 견준다. 기준을 넘지 못하면 도입하지 않고 그 사실을 기록한다."),
    ("b", "6. 백업과 보존"),
    ("l", "업무 상태는 PostgreSQL 정기 백업으로 보존한다."),
    ("l", "case_events 와 audit_logs 는 추가만 되므로 시점 복원의 기준이 된다."),
    ("l", "개인정보가 포함된 원본 수집 파일은 저장소에 올리지 않는다. "
          "스크립트와 스키마와 보고서만 올린다."),
]))

# ---------------------------------------------------------------- 변경 이력
CHANGES = [
    ("2026-08-28", "A-COPilot", "초안 작성. 업무 상태 9개, 지식 2개, 공통 2개 테이블",
     "전체", "구현계획서 11절과 16절을 따름"),
    ("2026-08-28", "A-COPilot", "pgvector 와 Graph Store 절 추가", "지식 저장소",
     "Graph Store 는 채택 기준 통과 시에만 도입"),
]
replace_rows("2026.04.11", "user_results", CHANGES)

out = d.save(os.path.join(FORMS, "[데이터 수집 및 저장] DB_VectorDB 설계서_A-COPilot.docx"))
print("저장:", out)
