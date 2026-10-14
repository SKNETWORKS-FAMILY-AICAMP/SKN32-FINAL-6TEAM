# -*- coding: utf-8 -*-
"""벡터DB/GraphDB 구축 결과서(.docx)를 양식 위에 채운다 — 활동 에이전트 기준 (2026-10-13).

    cd final_project_cs
    PYTHONPATH=. python ../docs/activity/산출물_작업/build_vectordb_report.py <양식.docx> <결과.docx>

원칙: 실측값만 쓴다(적재 수 · 검색 시험은 DB 를 직접 조회/`retrieval_results_2026-10-13.json`). 안 잰 것은 「해당 없음/미측정」.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TPL, OUT = sys.argv[1], sys.argv[2]
HERE = Path(__file__).resolve().parent
RESULTS = json.loads((HERE / "retrieval_results_2026-10-13.json").read_text(encoding="utf-8"))
EXT = json.loads((HERE / "retrieval_results_ext_2026-10-14.json").read_text(encoding="utf-8"))

# ── DB 에서 실측 ─────────────────────────────────────────────
from app.infrastructure.db.session import get_connection  # noqa: E402

with get_connection() as conn, conn.cursor() as cur:
    cur.execute("""SELECT d.scope, count(DISTINCT d.document_id), count(k.chunk_id), count(k.embedding)
                   FROM knowledge_documents d LEFT JOIN knowledge_chunks k USING(document_id)
                   WHERE d.scope LIKE 'travel_%' GROUP BY 1 ORDER BY 1""")
    SCOPES = {r[0]: r[1:] for r in cur.fetchall()}
    cur.execute("""SELECT d.title, d.scope, d.source_uri, k.chunk_no, k.metadata_json, k.content
                   FROM knowledge_chunks k JOIN knowledge_documents d USING(document_id)
                   WHERE k.metadata_json->>'section_title' = %s LIMIT 1""", ("휴관일은 규정이 아니라 사실이다",))
    EX = cur.fetchone()
    cur.execute("SELECT vector_dims(embedding) FROM knowledge_chunks WHERE embedding IS NOT NULL LIMIT 1")
    DIM = cur.fetchone()[0]

ACT_SCOPES = ("travel_activity", "travel_weather", "travel_cancellation", "travel_access")
N_DOC = sum(v[0] for v in SCOPES.values())
N_CHUNK = sum(v[1] for v in SCOPES.values())
A_DOC = sum(v[0] for s_, v in SCOPES.items() if s_ in ACT_SCOPES)
A_CHUNK = sum(v[1] for s_, v in SCOPES.items() if s_ in ACT_SCOPES)


# ── 문서 조작 도우미 ─────────────────────────────────────────
def set_p(p, text: str) -> None:
    """문단의 첫 run 서식을 살리고 글만 바꾼다(나머지 run 은 지운다)."""
    runs = p.findall(qn("w:r"))
    if not runs:
        r = OxmlElement("w:r"); r.append(OxmlElement("w:t")); p.append(r); runs = [r]
    first = runs[0]
    for r in runs[1:]:
        p.remove(r)
    ts = first.findall(qn("w:t"))
    for t in ts[1:]:
        first.remove(t)
    t = ts[0] if ts else OxmlElement("w:t")
    if not ts:
        first.append(t)
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def set_cell(tc, text: str) -> None:
    ps = tc.findall(qn("w:p"))
    for p in ps[1:]:
        tc.remove(p)
    set_p(ps[0], text)


def fill_table(tbl, header: list[str] | None, rows: list[list[str]]) -> None:
    trs = tbl.findall(qn("w:tr"))
    head, proto = trs[0], trs[1]
    if header:
        for tc, text in zip(head.findall(qn("w:tc")), header):
            set_cell(tc, text)
    for tr in trs[1:]:
        tbl.remove(tr)
    for row in rows:
        tr = copy.deepcopy(proto)
        for tc, text in zip(tr.findall(qn("w:tc")), row):
            set_cell(tc, text)
        tbl.append(tr)


def mono(proto_p, text: str):
    """고정폭 글(실행 결과용) 문단."""
    p = copy.deepcopy(proto_p)
    set_p(p, text)
    r = p.find(qn("w:r"))
    rpr = r.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr"); r.insert(0, rpr)
    for tag in ("w:b", "w:bCs", "w:rFonts", "w:sz", "w:szCs"):
        for el in rpr.findall(qn(tag)):
            rpr.remove(el)
    f = OxmlElement("w:rFonts"); f.set(qn("w:ascii"), "Consolas"); f.set(qn("w:hAnsi"), "Consolas")
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), "17")
    rpr.append(f); rpr.append(sz)
    return p


def plain(proto_p, text: str):
    p = copy.deepcopy(proto_p)
    set_p(p, text)
    r = p.find(qn("w:r"))
    rpr = r.find(qn("w:rPr"))
    if rpr is not None:
        for tag in ("w:b", "w:bCs"):
            for el in rpr.findall(qn(tag)):
                rpr.remove(el)
    return p


doc = Document(TPL)
body = doc.element.body
K = list(body)          # 원본 인덱스(양식 구조 고정)

# ── 표지 ─────────────────────────────────────────────────────
cover = K[4]
cells = [[tc for tc in tr.findall(qn("w:tc"))] for tr in cover.findall(qn("w:tr"))]
set_cell(cells[1][1], "2026. 10. 14.")
set_cell(cells[2][1], "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM (브랜치 role-activity-b)")

# ── 1. 구축 목적 및 적용 범위 ────────────────────────────────
set_p(K[10], "문제 정의 (Problem Definition): 여행 활동의 취소·변경 문의에서 규정을 기억이나 추정으로 답하면 고객이 손해를 보므로, "
              "서비스가 정한 운영 기준 문서를 근거(출처 포함)로 찾아 인용해야 한다. 질문 표현이 달라지면(위약금·환불·무료 취소 등) "
              "단순 키워드 검색은 맞는 절을 찾지 못해 의미 기반 검색이 필요하며, 근거가 없을 때 답을 지어내지 않도록 검색 실패를 신호로 다룬다.")
set_p(K[12], "벡터 데이터베이스: 서비스 운영 기준 문서(취소·변경 접수, 무료·무예약 판정, 운영 통제, 날씨·재난, 취소 공통 절차, 동행 조건 등) "
              f"및 공정거래위원회 국내여행 표준약관·소비자분쟁해결기준(공식 자료 3문서)을 더한 총 {N_DOC}문서·{N_CHUNK}청크의 임베딩과 유사도 검색 엔진을 PostgreSQL pgvector 로 구축. 활동 에이전트가 쓰는 범위는 4개 scope {A_DOC}문서·{A_CHUNK}청크.")
set_p(K[13], "그래프 데이터베이스: 활동 에이전트에서는 도입하지 않음(2.2 참고). 장소·예약·일정의 관계는 관계형 DB 와 코드 판정으로 처리.")

fill_table(K[15], None, [
    ["정형 데이터", "관계형 DB (PostgreSQL)", "장소 원장·운영시간 요일표·예약·취소 조건·일정 버전 등 판정 입력, PK/FK 기반 정합성 관리",
     "활동 장소 6,338곳(ac_place), 실내외(ac_indoor), 웹 공지 확인 결과(ac_live_status), 취소 조건(cancellation_terms), 예약·일정"],
    ["비정형 데이터", "벡터 DB (pgvector, PostgreSQL 확장)", "규정 문장 근거 검색(RAG) — 규정 질문·취소/변경 근거 인용",
     f"서비스 운영 기준 문서 + 공식 자료(표준약관·분쟁해결기준) {N_DOC}건({N_CHUNK}청크) — 활동 관련 4개 scope {A_DOC}문서"],
    ["관계형 데이터", "그래프 DB — 미도입", "코어에 SQL 재귀 CTE 기반 GraphStore 포트가 있으나 활동 에이전트는 사용하지 않음", "해당 없음"],
    ["상태/대화 데이터", "Case 상태 (PostgreSQL)", "재개를 위한 질문 상태·고객 답 이력(current_state), 판정 근거(Evidence), LLM 섀도 기록",
     "required_input_schema, customer_input(_history), evidence, activity_judge_shadow"],
])

# ── 2. 기술 설계 명세 ────────────────────────────────────────
fill_table(K[20], None, [
    ["임베딩 모델", "OpenAI text-embedding-3-small", "한국어 짧은 규정 문장 검색에 충분하고 비용이 가장 낮음(약 $0.02/100만 토큰). 컬럼 vector(1536)·HNSW 인덱스와 정합"],
    ["차원 수 (Dimension)", f"{DIM:,} (보조 칸 embedding_1024: bge-m3 병행 지원, 이번 구성에서는 미사용)", "text-embedding-3-large(3,072)는 pgvector HNSW 한도(2,000차원)를 넘어 컬럼·인덱스 변경이 필요"],
    ["색인 방식 (Indexing)", "HNSW (vector_cosine_ops)", "근사 최근접 이웃 고속 검색, 코사인 거리 연산자와 일치"],
    ["거리 측정 알고리즘", "Cosine Similarity (점수 = 1 − 코사인 거리)", "고차원 텍스트 벡터의 방향성 유사도 측정에 적합"],
    ["청킹 전략 (Chunking)", "문서의 '## ' 절 단위 — 절 1개 = 청크 1개(고정 길이·오버랩 없음), 본문만 임베딩하고 제목은 메타데이터로 저장",
     "규정 한 가지 판단이 한 절에 담기도록 작성해 문맥 단절 방지. 절 수는 manifest 와 일치해야 적재(불일치 시 중단)"],
    ["검색 범위 제어", "테넌트 + scope(ANY) 필터 후 top-k = 8", "팀별 지식 범위 격리(활동: travel_activity·weather·cancellation·access)"],
])

set_p(K[22], "도입 여부: 도입하지 않음. 활동 에이전트의 판정 입력(장소·운영시간·예약·재난)은 키로 조회되는 사실 데이터이고, 다단계 관계 탐색이 필요한 질의가 없다.")
set_p(K[23], "선택 근거:")
set_p(K[24], "장소–예약–일정 항목–여행 관계는 PK/FK 관계형 모델로 충분하며, 판정은 코드 규칙으로 수행하므로 그래프 탐색을 쓰지 않았다.")
set_p(K[25], "코어에 GraphStorePort 와 SQL 재귀 CTE 어댑터(SqlGraphAdapter)가 마련되어 있으나 활동 에이전트는 호출하지 않는다.")
set_p(K[26], "확장 시 고려:")
set_p(K[27], "고객 취향 메모리(과거 여행–선택한 장소 분류 관계)가 쌓이면 사용자–분류 선호 관계를 그래프로 모델링할 수 있다(향후 과제).")
set_p(K[28], "도입 전까지 노드·엣지·제약 조건 설계와 성능 지표는 수행하지 않았다(아래 검증 표에서 '해당 없음').")
body.remove(K[29])

set_p(K[31], "원문 저장소: 청크 본문(content)과 메타데이터(scope, 문서 ID, 절 제목, 버전, 개인정보 등급, 시행일)는 knowledge_chunks 에, "
              "문서 단위 정보(제목·출처 URI·scope·버전)는 knowledge_documents 에 저장한다. 원문 파일은 저장소 knowledge/travel/ 과 knowledge/travel_ext/(공식 자료 정리본) 이며 S3 연동은 없다.")
set_p(K[33], "Short-term (Case 상태 기반): required_input_schema·customer_input·customer_input_history 를 팀에 전달해 질문 후 재개 시 이어서 판정한다(LangGraph 미사용).")
set_p(K[34], "Long-term (Persisted): 판정 결과·근거(Evidence)·변경 이력은 PostgreSQL 에 영구 저장(일정 버전은 추가만 가능). 고객 취향 프로필(과거 여행 집계)은 미구축 — 향후 과제.")

# ── 검색 성능 및 정확도 검증 ─────────────────────────────────
hits = sum(1 for r in RESULTS if r["id"] != "R-07")
fill_table(K[38], None, [
    ["검색 적중률", "정답 절이 상위 3 안에 있는 질문 비율(Hit@3)", "기본 코퍼스 5/6 (83.3%, 1건 부분 R-05) · 공식 자료 추가 후 신규 질문 2/4 (50%, E-01·E-02는 상위 3 밖)", "기준 미설정(결과 보고)", "질문 6건 + 신규 4건 수동 시험(정답 절 사전 지정, 아래 4장 표)"],
    ["유사도 점수 분리", "범위 안 질문 1위 점수 대 범위 밖 질문 최고 점수", "기본: 범위 안 0.495~0.758 / 범위 밖 0.333. 추가 후 범위 안 1위 0.461~0.696(범위 밖은 재측정하지 않음)", "제안 임계치 0.4 안팎", "7문항 + 5문항, 코사인 유사도"],
    ["응답 속도", "질문 임베딩 + 검색 소요 시간", "0.17~0.35초 (첫 호출 1.1~1.3초)", "2.0초 이내", "호출 시간 직접 측정"],
    ["적재 정합성", "청크 수 대비 벡터 채움률, 차원", f"{sum(v[2] for v in SCOPES.values())}/{sum(v[1] for v in SCOPES.values())} (100%), {DIM:,}차원", "100%", "DB 직접 조회 + 적재 시 차원 검사"],
    ["연결성(Graph)", "노드 간 탐색 성공률", "해당 없음 (GraphDB 미도입)", "—", "—"],
    ["MCP 연동 성공률", "외부 도구 호출·수신", "해당 없음 (RAG 경로에서 미사용)", "—", "—"],
])

set_p(K[40], "검색 0건: 문서는 있는데 선택한 제공자의 벡터 칸이 비어 있으면 0건으로 돌려주지 않고 예외로 알린다. 0건이면 지어내지 않고 '관련 규정을 찾지 못했다'(모름)로 답하며, 규정 질문은 운영 담당자 인계 경로로 간다.")
set_p(K[41], "유사도 임계치: 현재 구현은 top-k(8)만 적용하고 임계치는 두지 않는다. 기본 시험에서 범위 안 1위가 0.495 이상, 범위 밖 최고가 0.333 이었다. 공식 자료를 추가한 뒤 범위 안 1위는 0.461까지 내려갔고 3위 점수는 0.368 까지 있어 0.4 는 경계에 가깝다. 범위 밖 질문은 추가 후 다시 측정하지 않았으므로 임계치는 제안으로만 기록하고 적용은 후속 결정으로 둔다.")
set_p(K[42], "Safe Mode: 규정 근거가 없으면 LLM 의 일반 지식으로 답하지 않는다. 답변에는 규정 문서의 고객용 문장을 출처와 함께 싣고, 근거가 부족하면 모름 또는 인계로 전환한다(Graceful Degradation).")

# ── 3. 데이터 운영 흐름 ──────────────────────────────────────
fill_table(K[47], None, [
    ["Load", "문서 front matter 파싱 → 절 단위 청킹 → 임베딩 → knowledge_documents·knowledge_chunks 적재(재실행 안전: 같은 문서·절은 건너뜀)", "적재 스크립트(knowledge/ingest.py 의 청킹 규칙 재사용)"],
    ["Retrieve", "질문 임베딩 → 테넌트·scope 필터 → 코사인 유사도 top-k → 근거(Evidence)로 부착", "read.policy 도구(search_policy) — 코어 컨트롤러와 활동 팀(취소 확인·변경 제안·규정 질문)"],
    ["Update", "문서 버전을 올려 재적재(본문 변경 시 해당 문서 청크를 교체). 적재 전 코퍼스 게이트(scripts/check_corpus.py)로 길이·중복·scope 겹침 검사", "운영 담당자 · 적재 스크립트"],
    ["Delete", "자동 만료(TTL)는 두지 않음. 개정·폐기 시 해당 문서의 청크를 교체/삭제", "운영 담당자(수동)"],
])
set_p(K[49], '사용자 요청: "무료로 취소할 수 있는 건 언제까지예요? 위약금이 있나요?"')
set_p(K[50], "의도 파악 및 라우팅: 코어 컨트롤러가 요청을 분류하고 활동 팀(activity.itinerary_question 또는 activity.check_cancelable)으로 전달한다.")
set_p(K[51], "근거 수집:")
set_p(K[52], "규정 검색: read.policy 로 활동 관련 scope(travel_activity·weather·cancellation·access)에서 질문과 가까운 절을 top-k 검색한다.")
set_p(K[53], "예약 조건 조회: 예약이 있으면 read.booking_terms 로 취소 기한·위약금율(예약 → 공급자 → 종류 순)을 조회한다. 수치는 RAG 가 아니라 구조화 표에서 온다.")
set_p(K[54], "결과 취합: 규정 절의 고객용 문장과 예약 조건 수치를 Evidence 로 결합한다. 근거가 없으면 모름으로 처리해 운영 담당자에게 넘긴다.")
set_p(K[55], "답변 구성: 모델이 문장을 짓지 않고 규정 문서에 적힌 고객용 문장을 출처와 함께 싣는다(수치는 예약 조건에서).")
set_p(K[56], "응답 및 검수: 팀은 답변·제안만 반환하고 부수효과를 실행하지 않는다. 일정 변경이 필요하면 승인 대기 제안으로 넘긴다.")

# ── 4. 구축 결과 ─────────────────────────────────────────────
body.remove(K[61])       # 「작성 포인트」 안내 상자
LABEL = {"travel_activity": "활동 운영 기준 (travel_activity)", "travel_weather": "날씨·재난 기준 (travel_weather)",
         "travel_cancellation": "취소·환급 공통 (travel_cancellation)", "travel_access": "동행·접근 조건 (travel_access)",
         "travel_dining": "식당 (travel_dining)", "travel_mobility": "이동 (travel_mobility)"}
rows = [[LABEL[s], str(v[0]), str(v[1])] for s, v in SCOPES.items()]
rows.append(["합계", str(sum(v[0] for v in SCOPES.values())), str(sum(v[1] for v in SCOPES.values()))])
fill_table(K[63], None, rows)
set_p(K[64], f"총 {N_DOC}개 문서를 {N_CHUNK}개 청크로 적재했고 모든 청크에 1,536차원 벡터가 채워진 것을 확인했다({sum(v[2] for v in SCOPES.values())}/{N_CHUNK}). 활동 에이전트가 사용하는 범위는 "
              f"4개 scope {A_DOC}문서·{A_CHUNK}청크이다. 이 중 3문서·18청크는 공정거래위원회 국내여행 표준약관(제10020호)과 소비자분쟁해결기준(고시 제2025-14호)을 판단 단위로 풀어 쓴 것이며(knowledge/travel_ext/), 원문과 대조해 문장 6곳을 고친 뒤 재적재했다. 장소별·업체별 약관은 담지 않았다. 그래프 DB 는 구축하지 않았다. 측정: 2026-10-13~14, 로컬 개발 DB(PostgreSQL + pgvector, Docker), OpenAI 임베딩 호출 기본 코퍼스 3회(입력 43,287 토큰) + 공식 자료 적재 2회(재적재 포함, 각 약 5,000 토큰).")

anchor = K[65]            # 「주요 예시 데이터」
title, scope, uri, no, meta, content = EX
ex = [
    plain(K[64], f"문서: {title} · scope {scope} · 출처 {uri}"),
    plain(K[64], f"절 제목(청크 {no}): {meta.get('section_title')} · 버전 {meta.get('version')} · 개인정보 등급 {meta.get('pii_class')}"),
    plain(K[64], "본문: " + content.replace("\n", " ")[:260] + ("…" if len(content) > 260 else "")),
]
for p in ex:
    anchor.addnext(p)
    anchor = p

# 검색 예시 표(7문항) — 5열 양식 표를 복제
anchor = K[66]
tbl_a = copy.deepcopy(K[38])
fill_table(tbl_a, ["ID", "질문", "1위 문서 · 절", "1위 점수", "판정"], [
    [r["id"], r["query"], f'{r["top3"][0]["document"]} · {r["top3"][0]["section"]}', f'{r["top3"][0]["score"]:.3f}',
     {"R-05": "부분 적중", "R-07": "범위 밖(점수 낮음)"}.get(r["id"], "적중")] for r in RESULTS])
anchor.addnext(tbl_a)
r3 = next(r for r in RESULTS if r["id"] == "R-03")
tbl_b = copy.deepcopy(K[15])
fill_table(tbl_b, ["순위", "문서", "절 제목", "점수"],
           [[str(i), t["document"], t["section"], f'{t["score"]:.3f}'] for i, t in enumerate(r3["top3"], 1)])
cap = plain(K[64], f'상위 3 결과 예시 — {r3["id"]} "{r3["query"]}" (scope 필터: 활동 4개 scope, top-k 3, {r3["ms"]}ms)')
tbl_a.addnext(cap)
cap.addnext(tbl_b)

# 공식 자료 추가 후 검색 시험 표
tbl_e = copy.deepcopy(K[38])
EXT_LABEL = {"R-05": "부분 적중(재측정)", "E-01": "미적중(기대 절이 상위 3 밖)", "E-02": "미적중(기대 절이 상위 3 밖)",
             "E-03": "적중", "E-04": "적중"}
fill_table(tbl_e, ["ID", "질문", "1위 문서 · 절", "1위 점수", "판정"], [
    [r["id"], r["query"], f'{r["top3"][0]["document"]} · {r["top3"][0]["section"]}', f'{r["top3"][0]["score"]:.3f}',
     EXT_LABEL[r["id"]]] for r in EXT])
cap_e = plain(K[64], "공식 자료(표준약관·분쟁해결기준) 추가 후 검색 시험 — 활동 4개 scope, top-3, 2026-10-14. E-01~E-04 는 새 질문이고 R-05 는 재측정이다.")
tbl_b.addnext(cap_e)
cap_e.addnext(tbl_e)

anchor = K[67]            # 「화면 캡처 또는 실행 결과」
lines = ["$ python retrieval_test.py   # 활동 scope 4개, top-3", ""]
for r in RESULTS:
    lines.append(f'{r["id"]} {r["query"]}  [{r["ms"]}ms]')
    for t in r["top3"]:
        lines.append(f'   {t["score"]:.3f}  {t["scope"]} | {t["document"]} · {t["section"]}')
lines += ["", "$ python retrieval_test_ext.py   # 공식 자료 추가 후, 활동 scope 4개, top-3", ""]
for r in EXT:
    lines.append(f'{r["id"]} {r["query"]}  [{r["ms"]}ms]')
    for t in r["top3"]:
        lines.append(f'   {t["score"]:.3f}  {t["scope"]} | {t["document"]} · {t["section"]}')
lines += ["", "-- scope 별 적재 현황 (documents, chunks, embedded)"]
for s, v in SCOPES.items():
    lines.append(f"   {s:<20} {v[0]:>3} {v[1]:>4} {v[2]:>4}")
for text in lines:
    p = mono(K[64], text)
    anchor.addnext(p)
    anchor = p

doc.save(OUT)
print("saved:", OUT)
