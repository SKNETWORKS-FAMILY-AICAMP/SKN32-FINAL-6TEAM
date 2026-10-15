# -*- coding: utf-8 -*-
"""멀티 에이전트 테스트 계획 및 결과 보고서 — 팀원 문서(md)와 작성자 문서(docx)를 합친 판 (2026-10-14).

    cd final_project_cs
    python ../docs/activity/산출물_작업/build_test_report_merged.py <양식.docx> <팀원문서.md(참고용 경로, 읽지 않음)> <결과.docx>

합치기 원칙
 1. 수치는 원자료와 일치하는 것만 쓴다 — LLM 평가는 `eval/reports/activity_judge/20261012T022514Z/summary.json` 에서 읽는다.
 2. 시험 항목 상세는 팀원 문서를 뼈대로, 작성자 문서에서 RAG 정확도 실험 · 질문 변환 효과 · 단계별 이력 · 재현 조건을 가져온다.
 3. 코드 기준 시점(팀원 측정 966d2fbd / 작성자 측정 이후 변경)을 문서에 밝힌다.
 4. RAG 기준 두 가지(상위 8 안의 정답 문서 / 상위 3 안의 정답 절)는 이름을 붙여 따로 적는다.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TPL, _MD, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = Path(__file__).resolve().parent
JUDGE = json.loads((HERE.parents[2] / "final_project_cs/eval/reports/activity_judge/20261012T022514Z/summary.json").read_text(encoding="utf-8"))
XP = json.loads((HERE / "query_expansion_results_2026-10-14.json").read_text(encoding="utf-8"))
E1 = json.loads((HERE / "retrieval_results_E_e1.json").read_text(encoding="utf-8"))
RUN = json.loads((HERE / "test_run_results_2026-10-14.json").read_text(encoding="utf-8"))
_src = (HERE / "build_test_report.py").read_text(encoding="utf-8")
_ns: dict = {}
exec(_src[_src.index("HIST = ["):_src.index("hist_tbl = copy")], _ns)   # 단계별 시험 이력(기존 리포트 12건의 수치) 재사용
HIST = _ns["HIST"]


# ── 문서 조작 도우미 ───────────────────────────────────────────
def set_p(p, text: str) -> None:
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


def fill_table(tbl, header, rows) -> None:
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


def pct(a, b):
    return f"{a / b:.1%}" if b else "—"


doc = Document(TPL)
body = doc.element.body
K = list(body)
P_NORMAL, P_HEAD = K[27], K[64]


class Cursor:
    """앞에서부터 차례로 문단·표를 끼워 넣는 커서."""

    def __init__(self, anchor):
        self.a = anchor

    def p(self, text, proto=None):
        el = copy.deepcopy(proto if proto is not None else P_NORMAL)
        set_p(el, text)
        self.a.addnext(el); self.a = el
        return el

    def h(self, text):
        return self.p(text, P_HEAD)

    def t(self, proto_tbl, header, rows):
        el = copy.deepcopy(proto_tbl)
        fill_table(el, header, rows)
        self.a.addnext(el); self.a = el
        return el


REPRO = ("재현 조건: 팀원 측정은 코드 기준 966d2fbd(2026-10-13), 작성자 측정은 이후 변경(절 분리·질문 변환·공식 자료 적재)을 포함한 2026-10-14 로컬 환경이다. "
         "다른 환경에서는 DB 적재 상태(문서 적재 여부·임베딩 제공자), 마이그레이션 적용 여부, 설치 패키지, API 키와 모드 설정에 따라 시험 건수와 검색·판정 결과가 달라질 수 있다.")

# ── 표지 ─────────────────────────────────────────────────────
cells = [[tc for tc in tr.findall(qn("w:tc"))] for tr in K[4].findall(qn("w:tr"))]
set_cell(cells[1][1], "2026. 10. 14.")
set_cell(cells[2][1], "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM (final_project_cs/, 브랜치 role-activity-b)")

# ── 1. 테스트 개요 ───────────────────────────────────────────
set_p(K[10], "이 보고서는 triPilot 멀티 에이전트 시스템 가운데 Activity(활동) 에이전트를 검증한 결과이다. 검증 항목은 다음과 같다. "
              "① 판정 정확성 — 성립·취소·휴무·운영시간·재난·실내외 판정이 규칙대로 나오고 「모름」을 「성립」이나 「휴무 아님」으로 바꾸지 않는다. "
              "② 판정 LLM의 안전성 — shadow로 동작할 때 고객 결과를 바꾸지 않고, llm 모드에서는 조심하는 쪽 값만 받으며 인용·출처 검증을 통과하지 못하면 unknown이 된다. "
              "③ 에이전트 간 협업 — Core(분류·라우팅·Controller)를 거쳐 Activity에 도달하고, 감시 루프의 묶음 재계획에서 식당·이동 항목과 하나의 초안·버전·알림을 만든다. "
              "④ 저장소·RAG 연동 — 활동 원장, 실내외·웹 공지 저장소, shadow 기록 표, 여행 규정 검색이 의도대로 읽고 쓴다. "
              "⑤ 장애 방어 — 외부 소스 실패, LLM 시간 초과·429·스키마 오류, 예산 초과에서 정해진 상태로 끝난다. "
              "범위 밖은 Dining·Mobility의 내부 판정 정확도, 웹 화면, 실제 운영 서버 배포이며, 실제 OpenAI를 부르는 live 시험은 비용 때문에 제외하고 판정 LLM 정확도는 2026-10-12 평가 기록을 인용한다.")

fill_table(K[12], None, [
    ["Language & Framework", "Python 3.12(팀원 3.12.10 · 작성자 3.12.15), FastAPI, Pydantic 2(extra='forbid'), pytest 8.4.2"],
    ["오케스트레이션", "자체 Controller + 12상태 Case 상태기계(LangGraph 미사용)"],
    ["LLM (판정)", "OpenAI gpt-5.4-nano — Responses API, Structured Outputs(strict), 웹 검색(실시간 운영 판정만), reasoning low"],
    ["LLM (Core 공통) / sLLM", "Ollama gemma4:12b(분류·결정 단위). Activity 판정용 sLLM 전환은 조건부 계획이며 파인튜닝은 하지 않음"],
    ["Database", "PostgreSQL 16(팀원 127.0.0.1:5433 acop_cs · 작성자 16.15), pgvector 0.8.6(HNSW cosine), pgcrypto. 그래프 DB 미도입"],
    ["임베딩 (두 경로)", "ollama: bge-m3(1024차원, embedding_1024 칸) — 팀원 측정 환경, RAG 통합 시험 17건. / openai: text-embedding-3-small(1536차원, embedding 칸) — 작성자 환경, 검색 정확도 실험·공식 자료 적재. 제공자는 설정(ACOP_EMBEDDING_PROVIDER)이 고르며 두 벡터는 공존한다"],
    ["Protocol / Infra", "REST, MCP(FastMCP, 활동 판정 경로에서는 미사용), 로컬 실행(Windows 11), Docker(DB)"],
])
c = Cursor(K[12])
c.p("실행 환경 메모: 팀원 환경에서는 .env의 임베딩 서버(127.0.0.1:11435, 원격 GPU 터널)가 꺼져 RAG 시험 8건이 연결 거부로 실패해, 같은 모델(bge-m3)이 있는 로컬 Ollama(11434)로 "
    "실행할 때만 주소를 바꿔 다시 돌렸다(.env는 수정하지 않음). 작성자 환경에는 Ollama가 없어 공식 자료 20청크를 OpenAI 임베딩으로 적재했고, "
    "이 환경에서 tests/integration/rag를 실행하면 임베딩 제공자 차이로 17건 중 14건이 오류·2건이 실패한다(코드 결함이 아니라 환경 차이).")
c.p("코드 기준 시점: 팀원 측정은 커밋 966d2fbd(2026-10-13), 작성자 측정은 그 이후의 변경 — 규정 문서 절 분리 2곳, 규칙 기반 질문 변환(policy_query), 공식 자료 3문서·20청크 추가 — 를 포함한다. "
    "따라서 팀원 측정의 RAG 결과에는 공식 자료와 질문 변환이 반영되어 있지 않다.")

comps = [
    "Core 인라인 분류기: intent·issue_code를 분류하고 activity_* 접두면 Activity로 보낸다. 분류 어휘와 Team 수신 종류의 정합(라우팅 도달성)을 본다.",
    "Controller: Case 상태 전이, Team 호출, 대기·재개, 승인을 맡는다. 상태 전이, Case당 활성 실행 1개, 재개를 본다.",
    "Activity 에이전트: 성립·취소 판정, 변경 제안, 대체 장소, 일정 관리를 맡는다. 판정 순서, 모름 처리, 고객 질문, 대체 후보를 본다. 부수효과는 실행하지 않고 제안만 반환한다.",
    "Activity 판정 LLM: 지금 화면에 나가는 판정은 규칙이다. LLM은 설정에 따라 휴무·날씨 민감도·재난 영향·실시간 운영 상태·대체안 순서를 백그라운드에서 판정해 규칙과의 차이만 기록한다(shadow, 운영시간은 규칙만). 기록이 쌓여 정확도가 확인되면 LLM 판정으로 교체할 계획이며 인용이 없으면 어느 모드에서도 쓰지 않는다.",
    "Dining · Mobility: 식당·이동 항목을 판정한다. 묶음 재계획에서 Activity와의 협업을 본다.",
    "감시 루프: 외부 사건을 감지해 여행당 Case 1건을 연다. 묶음 재계획 시나리오를 본다.",
    "정책 RAG: 여행 규정 문서를 pgvector로 검색해 고객용 문장을 출처와 함께 싣는다. 검색 정확도, scope·tenant 격리를 본다.",
]
for i in range(5):
    set_p(K[14 + i], comps[i])
c2 = Cursor(K[18])
c2.p(comps[5]); c2.p(comps[6])

# ── 2. 구성요소 연동 및 단위 기능 테스트 ──────────────────────
T3 = copy.deepcopy(K[23])    # 3열 표 원형
T4 = copy.deepcopy(K[25])    # 4열 표 원형
T6 = copy.deepcopy(K[63])    # 6열 표 원형
T2 = copy.deepcopy(K[12])    # 2열 표 원형

fill_table(K[23], ["테스트 항목", "검증 내용 및 평가 요소", "결과"], [
    ["실내외 저장소 activity.ac_indoor", "우선순위(operator > customer > llm > class)대로 높은 값을 낮은 값으로 덮지 않음, 「모름」은 저장하지 않음 (6건)", "Pass 6/6"],
    ["shadow 기록 표 activity_judge_shadow", "규칙 vs LLM 판정 기록, 장소명·고객 문장 미포함 (4건)", "Pass 4/4"],
    ["활동 원장 activity.ac_place", "방문 시각마다 운영 여부 판정, 원장에 없는 장소는 None(「열었다」로 바꾸지 않음) (3건)", "Pass 3/3"],
    ["원문 변경 갱신(refresh_places)", "관광공사 원문이 바뀐 장소만 다시 받고 요일표를 비워 다시 읽게 함 (6건)", "Pass 6/6"],
    ["대체 후보 풀 place_catalog", "반경 바운딩 박스로 후보 조회, 응답 모양 계약 (6건)", "Pass 6/6 (작성자 환경은 보류 제안 표 제약 보정 후)"],
    ["장소 원장 품질·장소 조회", "원장 데이터 품질 규칙과 장소 조회 (작성자 환경 34건)", "Pass 34/34"],
    ["프롬프트 배포 정합", "허용된 프롬프트 키마다 활성 버전이 DB에 정확히 1개 (10건)", "환경 의존 — 팀원 DB Fail 9/10(alternative_order 미등록), 작성자 DB Pass 10/10"],
])
c = Cursor(K[23])
c.p("소계(팀원 환경): 35건 중 34 Pass · 1 Fail. Fail은 코드가 아니라 프롬프트 등록(register_prompts) 누락이며 5.2 D-1에 적었다.")

# 2.2 RAG
c = Cursor(K[24])
c.p("Activity는 travel_activity · travel_weather · travel_cancellation · travel_access 네 scope의 규정 문서를 read.policy로 검색한다(pgvector, top_k 8, 유사도 하한 없음). "
    "RAG는 두 가지 기준으로 시험했다. [통합 시험 — 정답 문서가 상위 8개 안에 있는가]는 아래 첫 표, [정확도 실험 — 정답 절이 상위 3개 안에 있는가]는 그 뒤 표이다. 두 기준은 엄격함이 달라 수치를 직접 비교하지 않는다.")
fill_table(K[25], ["케이스 ID", "입력 쿼리", "기대 결과", "결과 (통합 시험, 상위 8 기준)"], [
    ["RAG-ACT-01", "「비가 와서 야외 활동을 못 하게 됐다」", "t_doc_04 기상 취소 기준 검색", "Pass"],
    ["RAG-ACT-02", "「예약을 이틀 전에 취소하면 위약금이 있나요」", "t_doc_01 활동 취소 접수 검색", "Pass"],
    ["RAG-ACT-03", "「지하철 운행이 중단돼서 다음 일정에 못 갈 것 같아요」", "t_doc_08 이동 장애 검색(mobility · weather scope)", "Pass"],
    ["RAG-ACT-04", "「휠체어를 쓰는 일행이 있는데 들어갈 수 있나요」", "t_doc_12 동행 조건 검색(dining · access scope)", "Pass"],
    ["RAG-ACT-05", "문서가 없는 scope로 검색", "빈 결과 — 일반 지식으로 메우지 않음", "Pass"],
    ["RAG-ACT-06", "여행과 무관한 질문", "여행 문서만 반환(커머스 문서 미반환)", "Pass"],
    ["RAG-ACT-07", "다른 tenant로 검색", "tenant 격리", "Pass"],
    ["RAG-ACT-08", "정책이 필요한 모든 Team", "각 scope에 문서가 있음(0건 degraded 방지)", "Pass"],
    ["RAG-ACT-09", "일정 생성기 근거 3건", "여행 규정만 근거로 사용", "Pass"],
])
c = Cursor(K[25])
c.p("통합 시험 합계(팀원 환경, Ollama bge-m3): tests/integration/rag 17/17 Pass.")
c.p("정확도 실험(작성자, OpenAI 1536): 공식 자료(국내여행 표준약관 제10020호, 소비자분쟁해결기준 고시 제2025-14호의 국내여행·체육시설·레저·공연)를 판단 단위로 풀어 쓴 3문서·20청크를 추가하고, "
    "혼재된 절 2곳을 나누고, 고객 표현을 문서 용어로 덧붙이는 규칙 기반 질문 변환(사전, LLM 호출 없음)을 넣은 뒤 질문 묶음 6개로 Hit@3(상위 3개 안에 정답 절)을 쟀다.")
c.t(T4, ["질문 묶음", "문항", "질문 변환 끈 때", "켠 때"],
    [[x["set"], str(x["n"]), f'{x["off"]}/{x["n"]}', f'{x["on"]}/{x["n"]}'] for x in XP["sets"]])
tot_off = sum(x["off"] for x in XP["sets"]); tot_on = sum(x["on"] for x in XP["sets"]); tot_n = sum(x["n"] for x in XP["sets"])
c.p(f"합계 {tot_off}/{tot_n}({pct(tot_off, tot_n)}) → {tot_on}/{tot_n}({pct(tot_on, tot_n)}). 해석 주의: E 묶음을 뺀 나머지는 규칙을 만들 때 질문 문장을 이미 본 상태라 학습 데이터에 가깝다. "
    "규칙 작성 뒤 만든 E 묶음에서도 개선은 규칙 어휘와 겹친 질문(E01·E06·E08)에서만 나왔고 규칙에 없는 표현(E05·E09·E10)은 그대로 미적중이었다. 즉 사전에 있는 표현에는 효과가 있으나 일반화는 입증하지 못했다.")
rows = []
for o in E1:
    top = o["top3"][0]
    rows.append([o["id"], o["query"], "기대 절: " + " / ".join(o["expect"][:2]),
                 f'{top["score"]:.3f} — {top["document"]} · {top["section"]} (' + (f'적중 {o["rank"]}위' if o["rank"] else "미적중") + ")"])
c.t(T4, ["케이스 ID", "입력 쿼리(규칙 작성 후 만든 E 묶음)", "기대 결과", "결과 (질문 변환 켠 때, Sim. Score)"], rows)
c.p("임베딩 제공자 차이: 위 정확도 실험은 OpenAI text-embedding-3-small(1536차원)로 쟀다. 팀 환경(ollama bge-m3, 1024차원)에서 공식 자료 20청크가 검색되려면 같은 문서를 embedding_1024 칸에도 적재해야 하며, 적재 전에는 이 청크들이 검색되지 않을 수 있다. "
    "유사도 임계치는 두지 않았다(제안값 0.4). 임베딩 모델 비교는 하지 않았다.")

# 2.3
set_p(K[27], "외부 호출 체계: 외부 호출은 판정 LLM(웹 검색 포함)과 임베딩 두 가지이다. 호출은 일·월 상한(텍스트 2,000/30,000, 웹 50/1,000)으로 막고 넘으면 호출하지 않고 skipped로 남긴다. "
              "웹 공지 확인은 요청 경로가 아니라 배치(시작 72시간 이내 활동, 6시간 재확인)로 돌려 저장하고 요청에서는 저장 값만 읽는다. 호출은 외부 변경 사항을 실행하지 않는다.")
c = Cursor(K[27])
c.t(T3, ["테스트 항목", "검증 내용", "결과"], [
    ["Responses API 어댑터", "요청 스키마(strict JSON Schema), 응답 파싱, 검색 출처 수집, 감사 기록 (16건)", "Pass"],
    ["LLMJudge 검증 로직", "인용이 원문에 없으면 버림, 웹 출처가 검색 목록에 없으면 버림, 180일 넘은 근거 버림, 검증 실패 시 unknown (26건)", "Pass"],
    ["장애 처리", "429는 한 번 쉬었다 재시도, 두 번째 429는 unknown, 다른 오류·시간 초과는 재시도하지 않음, 스키마 밖 답은 unknown, 동시 호출 슬롯이 차면 호출 생략, 고객 대기 상한 (7건)", "Pass"],
    ["판정 모드", "종류별 rule/shadow/llm, 잘못된 설정값은 추측하지 않고 멈춤, 일·월 예산 (20건)", "Pass"],
    ["판정 요청 생성", "요일·몇째 주·마지막 주·공휴일을 코드가 계산해 넣음 (8건)", "Pass"],
    ["프롬프트 파일", "판정 종류마다 프롬프트 파일 존재, 키 등록과 일치 (2건)", "Pass"],
    ["조립(wiring)", "전역 모드가 rule이면 판정 LLM 미주입, shadow면 주입 (8건)", "Pass"],
    ["저장된 웹 공지값(live_status)·감시 배치·호출 예산", "저장된 값 조회·재확인 주기, 배치 한 틱, 호출 예산 (작성자 환경 14·15·3건)", "Pass"],
])
set_p(K[28], "장애 방어 정책(시험으로 확인한 동작): 판정 LLM은 예외를 밖으로 던지지 않고 모두 unknown + 실패 코드(llm_timeout, llm_schema_invalid, llm_error, llm_busy, llm_uncited)로 바꾼다. "
              "고객 결과는 규칙 판정이 정하므로 LLM 장애는 고객 응답에 영향을 주지 않는다. 같은 호출은 반복하지 않으며(429만 1회), 실패 코드를 기록해 조용히 지나가지 않는다. "
              "외부 도구(MCP) 연동은 활동 판정 경로에 없어 시험 대상이 아니다.")

# ── 3. LLM 보조 판정 평가 ──────────────────────────────────────
set_cell(K[30].findall(qn("w:tr"))[0].findall(qn("w:tc"))[0], "3. LLM 보조 판정 평가 결과 (자체 sLLM 파인튜닝은 해당 없음)")
cond, kinds = JUDGE["conditions"], JUDGE["kinds"]
LAB = ("closure", "operating_hours", "weather_sensitive", "disaster_effect")
NAME = {"closure": "① 휴무", "operating_hours": "② 운영시간", "weather_sensitive": "③ 실내외", "disaster_effect": "④ 재난"}
set_p(K[31], "3.1 평가 환경 (sLLM 파인튜닝은 수행하지 않음)")
set_p(K[32], f"골든셋: eval/activity_judge/cases.jsonl {cond['cases']}건(휴무 16, 운영시간 14, 실내외 10, 재난 12, 실시간 운영 8). 정답 라벨 52건은 Claude 1차 라벨을 사람 검토(2026-10-12)로 확정했고 실시간 운영 8건은 라벨이 없다. "
              "Activity는 파인튜닝을 하지 않았다 — 판정이 원문 해석이고 표본이 작아 「규칙 + 소형 API LLM + 코드 검증」이 맞다고 판단했다.")
set_p(K[33], f"모델 {cond['model']}, reasoning effort {cond['reasoning_effort']}, 프롬프트 {cond['prompt_version']}, 사례당 {cond['repeats']}회 반복, 항목 단위 군집 부트스트랩 {cond['bootstrap']['n']:,}회(seed {cond['bootstrap']['seed']}), 95% CI. 비교 기준은 현재 팀 규칙 그대로(judge/rule.py).")
set_p(K[34], f"실행: python -m eval.activity_judge.run --repeats 3 --concurrency 2 --no-db (2026-10-12, {JUDGE['elapsed_s']:.0f}초, ${JUDGE['cost_usd_total']:.2f}, 데이터셋 SHA-256 {cond['dataset_sha256'][:12]}…).")
set_p(K[35], "3.2 성능 비교 — 규칙 vs 판정 LLM")
rows = []
for k in LAB:
    v = kinds[k]; la, ra, dm = v["llm_accuracy"], v["rule_accuracy"], v["llm_minus_rule"]
    rows.append([NAME[k], f"{ra['num']}/{ra['den']}", f"{la['num']}/{la['den']} = {pct(la['num'], la['den'])} ({la['ci95'][0]:.2f}~{la['ci95'][1]:.2f})",
                 f"{dm['value']:+.2f} ({dm['ci95'][0]:+.2f}~{dm['ci95'][1]:+.2f}) · 확정했는데 틀림 규칙 {v['rule_dangerous']['num']} / LLM {v['llm_dangerous']['num']}"])
a = kinds["_labeled_all"]
rows.append(["라벨 전체", f"{a['rule_accuracy']['num']}/{a['rule_accuracy']['den']}", f"{a['llm_accuracy']['num']}/{a['llm_accuracy']['den']} = {pct(a['llm_accuracy']['num'], a['llm_accuracy']['den'])} ({a['llm_accuracy']['ci95'][0]:.2f}~{a['llm_accuracy']['ci95'][1]:.2f})",
             f"{a['llm_minus_rule']['value']:+.2f} ({a['llm_minus_rule']['ci95'][0]:+.2f}~{a['llm_minus_rule']['ci95'][1]:+.2f}) · 확정했는데 틀림 규칙 {a['rule_dangerous']['num']} / LLM {a['llm_dangerous']['num']}"])
fill_table(K[36], ["판정", "규칙 정답", "LLM 정답 (95% CI)", "LLM − 규칙 (95% CI) · 위험 오답"], rows)
lat = "; ".join(f"{NAME[k]} {kinds[k]['latency_ms']['p50'] / 1000:.1f}s/{kinds[k]['latency_ms']['p95'] / 1000:.1f}s·${kinds[k]['cost_usd_per_call_mean']:.5f}" for k in LAB)
ls = kinds["live_status"]
set_p(K[37], f"지연 p50/p95·호출당 비용: {lat}. 반복 일관(같은 사례 3회 같은 답): "
              + ", ".join(f"{NAME[k]} {kinds[k]['consistent_cases']['num']}/{kinds[k]['consistent_cases']['den']}" for k in LAB)
              + f". ⑤ 실시간 운영(웹, 라벨 없음, {ls['cases']}사례 × 3회): 모름 {ls['llm_unknown']['num']}/{ls['llm_unknown']['den']}, 지연 p50 {ls['latency_ms']['p50'] / 1000:.1f}초(p95 {ls['latency_ms']['p95'] / 1000:.1f}초), 건당 약 ${ls['cost_usd_per_call_mean']:.3f}. "
              "채점 주의: 휴무·재난에서는 규칙의 「모름」(휴무 5건)이 허용되는 답으로 채점되어 규칙 16/16·12/12에 포함되며, 운영시간·실내외에서는 「모름」이 오답으로 계산된다(8/14, 5/10).")
c = Cursor(K[37])
c.p("LLM이 확정했는데 틀린 5건(QA 관찰): closure-06(3회 중 2회 not_closed, 정답 휴무, 규칙은 모름) — 제각각인 휴무 원문을 「휴무 아님」으로 풀어 줌. "
    "disaster-04(3회 모두 no_effect, 정답 막아야 함, 규칙은 막음) — 남산공원·폭염(야외 위험형)에서 LLM 입력에 장소의 실내외를 넣지 않아 근거가 없었음. "
    "5건 모두 「풀어 주는 쪽」 오답이어서 안전 비대칭(CAUTIOUS_VALUES: 휴무는 closed만, 재난은 blocks만 LLM이 확정)을 넣었고, 이 규칙이 있었다면 두 사례는 「모름」 또는 「막음」으로 남는다.")
c.p("비교 시점 주의: 10-06 평가의 규칙 휴무 정확도(7/16)와 10-12 평가(16/16)는 같은 대상을 잰 값이 아니다. 그 사이 휴무 규칙을 새로 썼고(closure_rules), 새 규칙은 이 평가에서 드러난 결함을 고치며 만들어져 같은 사례에 맞춰진 면이 있다. 개선 폭으로 읽지 않는다.")
set_p(K[38], "3.3 모델 한계 및 개선 방향")
set_p(K[39], "한계점: 표본이 작다(라벨 52건 × 3회, 반복은 독립 표본이 아니다). 사람 검토자가 1명이고 1차 라벨을 보고 판단했다(수정 1건). 실시간 운영(웹)은 라벨이 없어 정확도를 모르고 지연이 길다(10-06 측정: p50 15.7초, p95 40.7초, 24회 중 8회 429). "
              "sLLM(gemma4:12b)의 판정 정확도는 미측정이다(현재 평가기에 로컬 모델 옵션이 없다). 실운영 정확도·장기 변동은 측정하지 못했다.")
set_p(K[40], "개선 방향(결정 D-CS-015 개정 2): 휴무·재난은 규칙을 유지하고 LLM은 shadow(백그라운드로 돌려 규칙과의 차이만 기록)로 쓴다. 운영시간·실내외는 규칙이 먼저 판정하고 모르는 곳만 LLM이 1회 읽어 저장한다. "
              "실시간 운영은 shadow를 유지하고 장소·날짜당 1회 배치로 돌린다. 기록이 쌓여 사람 라벨로 정확도를 확인하면 모드(rule → shadow → llm)를 올려 LLM 판정으로 교체한다. "
              "sLLM 전환은 ① 팀 GPU 서버 안정 ② gemma4:12b가 같은 골든셋에서 위험 0건 ③ 호출량 증가를 모두 충족할 때 설정으로 전환한다.")

# ── 4. 시나리오 기반 통합 테스트 ──────────────────────────────
set_p(K[44], "4.1 워크플로우 실행 검증 (Controller · Case 상태기계)")
set_p(K[45], "triPilot은 LangGraph를 쓰지 않는다. 워크플로우는 Controller와 12상태 Case 상태기계(new → classifying → routing → running → resolved / waiting_* / resuming / escalated …)가 제어한다.")
set_p(K[46], "시나리오 A — 감시 루프의 묶음 재계획(tests/scenario/test_watch_batch.py): ① 감시 루프가 한 여행의 항목 두 개가 깨진 것을 감지한다. ② 여행당 Case 1건을 연다. "
              "③ Activity가 조정자가 되어 활동 → 식당 → 이동 순으로 앞 초안을 다음 항목에 넘긴다. ④ 합친 초안을 전체 재판정하고 새 버전 1개 + 알림 1건으로 적용한다.")
set_p(K[47], "시나리오 B — 실내외를 모르는 활동에 날씨 사건(tests/e2e/test_indoor_unknown_consent.py): 실내외를 모르는 장소에 날씨 사건이 걸리면 Activity는 대체안을 계산하지 않고 「바꿀까요?」만 묻는다. "
              "「바꿔」라고 답하면 그때 후보를 계산하고 고객이 고르면 적용하며, 「그대로」면 아무것도 바꾸지 않고 계산도 하지 않는다.")
set_p(K[48], "시나리오 C — 고객 문의 성립 점검(tests/unit/travel/activity/): 방문 시각·장소·인원 모름 처리, 재난문자 §8 분류, 휴무 원문 절 단위 판정, 고객 답 재개를 단위 시험으로 확인한다.")
set_p(K[49], "시나리오 시험 전체(작성자 환경): tests/scenario 14개 파일 103건 통과(보류 제안 표 제약 보정 후, 5.2 M-1 참고). 팀원 환경은 묶음 재계획 9건, e2e 21건, Controller 113건, 라우팅 21건이 통과했다.")
body.remove(K[50]); body.remove(K[51])
c = Cursor(K[49])
c.p("시나리오 A 결과:")
c.t(T3, ["테스트", "확인한 것", "결과"], [
    ["한 여행의 깨진 항목 두 개", "Case 1건 · 버전 1개 · 알림 1건", "Pass"],
    ["묶음 기능을 끔", "항목마다 각자의 Case·버전·알림", "Pass"],
    ["한 항목을 풀지 못함", "나머지는 진행하고 같은 알림에 한 줄로 알림", "Pass"],
    ["고정(변경 안 함) 항목", "그 항목은 묻고 나머지는 적용, 질문은 새 버전 기준", "Pass"],
    ["모든 항목이 보호됨", "버전을 쓰지 않고 각 질문은 현재 버전 기준", "Pass"],
    ["아무것도 바꿀 수 없음", "고객에게 한 번만 알리고 같은 묶음으로는 다시 알리지 않음", "Pass"],
    ["안전 사건", "안전 줄이 맨 위, 알림 종류는 안전 알림", "Pass"],
    ["이미 단일 Case가 다룬 항목", "이후 묶음에 끌어오지 않음", "Pass"],
    ["완료된 묶음 안의 소스 실패", "다음 회차에 그 항목만 다시 엶", "Pass"],
])
c.p("시나리오 B 결과(21/21 Pass, 대표):")
c.t(T3, ["주요 테스트", "확인한 것", "결과"], [
    ["실내외를 모르면", "대체안 계산 없이 먼저 질문", "Pass"],
    ["「바꿔」 → 후보 계산", "선택하면 적용", "Pass"],
    ["「그대로」", "변경 없음, 계산 없음", "Pass"],
    ["동의 전에 후보 키를 보내면", "거부", "Pass"],
    ["야외로 알려진 장소", "자동 설정이 아니면 먼저 질문", "Pass"],
    ["「자동」을 명시하면", "바로 바꾸고 되돌리기 제공", "Pass"],
    ["자동인데 대안이 없으면", "조용히 끝내지 않고 질문", "Pass"],
    ["카탈로그 장소", "동의 후 제안하고 선택될 때만 등록", "Pass"],
    ["브랜드 매장", "관광공사 번호 없이도 제안·등록", "Pass"],
])
c.p("시나리오 C 결과(Activity 단위 시험 451건 중 대표):")
c.t(T3, ["단계", "대표 테스트", "결과"], [
    ["방문 시각 모름", "상향 전달하지 않고 고객에게 질문, 장소는 읽지 않음, 정원 초과는 숨기지 않음", "Pass"],
    ["장소 모름", "운영 담당자에게 상향하고 이후 점검은 건너뜀", "Pass"],
    ["인원·정원 모름", "막지 않고 경고만 남김", "Pass"],
    ["재난문자", "§8 분류표(37개 시험), 미분류 위급 문자는 재난 정지와 같은 기준으로 막음, 훈련 문자는 막지 않음", "Pass"],
    ["휴무 원문", "절 단위 판정, 못 읽은 조각은 모름(29개 시험)", "Pass"],
    ["고객 답 재개", "선택지로 질문, 숫자·글자 답 매칭, 자유 문장이면 다시 질문, 장소 기록이 고객 답보다 우선", "Pass"],
])

set_p(K[52], "4.2 에이전트 협업 및 라우팅 테스트")
set_p(K[53], "일정 제출은 활동 판정이 아니라 여행 접수로, 일정이 정해진 Case는 일정 관리로, 조정 거부는 변경 제안으로 가는지, develop 병합 시 활동 동작이 유지되는지를 시험했다(작성자 환경: 라우팅 8건, develop 병합 회귀 72건 통과).")
set_p(K[54], "아래 표는 팀원 환경의 협업·라우팅 시험이다.")
c = Cursor(K[54])
c.t(T3, ["테스트 항목", "검증 내용", "결과"], [
    ["라우팅 도달성", "분류 어휘의 issue_code 접두가 등록된 모든 Team의 수신 종류와 일치, 잘못된 선언은 실패 (21건)", "Pass"],
    ["Controller 통합", "Case 상태 전이, Case당 활성 실행 1개, 대기·재개, 승인, 동시성 충돌 재계산 (113건)", "Pass"],
    ["Activity capability 선택", "일정 제출 → 접수 안내, 조정 거부 → 변경 제안, 여행이 정해진 Case → 일정 관리 (8건)", "Pass"],
    ["취향 전달(설문 → Activity)", "Core TEAM_STATE_KEYS가 취향을 Team에 넘기는지 (1건)", "XFail — Core가 아직 넘기지 않음(5.2 D-3)"],
    ["묶음 재계획 협업", "Activity → Dining → Mobility 초안 전달 (9건)", "Pass"],
])

set_p(K[55], "4.3 예외 상황 및 방어 체계 테스트")
set_p(K[56], "1차 방어(근거·데이터 누락): 예약·장소·정책을 모르면 확정하지 않고 「모름」·질문·상향으로 끝내며 일반 지식으로 메우지 않는다. 외부 소스가 대체까지 실패하면 fatal_source_failure로 상향한다.")
set_p(K[57], "2차 방어(판단 오류·과호출): shadow LLM이 반대 판정을 내도 고객 결과는 불변이고, llm 모드에서도 LLM의 「휴무 아님·괜찮다」는 받지 않는다. 예산 초과·같은 도구 반복·허용 목록 밖 도구는 차단한다.")
set_p(K[58], "3차 방어(출력 검수): 인용이 원문에 없거나 웹 출처가 검색 목록에 없으면 버리고 unknown으로 둔다. 대체 순서 LLM이 목록 밖 장소를 내면 코드 순서를 유지하고, Team이 외부 변경을 직접 실행하는 것은 아키텍처 시험으로 금지한다.")
c = Cursor(K[58])
c.t(T3, ["방어 계층 · 상황", "기대 동작", "결과"], [
    ["1차 · 예약·장소·정책을 모름", "확정하지 않고 「모름」·질문·상향. 일반 지식으로 메우지 않음", "Pass"],
    ["1차 · 외부 소스가 대체까지 실패", "fatal_source_failure로 상향, 조회 실패를 일정 변경 사유로 쓰지 않음", "Pass"],
    ["1차 · 정책 RAG 빈 scope", "빈 결과(RAG-ACT-05)", "Pass"],
    ["2차 · shadow LLM이 반대 판정", "고객 결과 불변", "Pass"],
    ["2차 · llm 모드에서 「휴무 아님」·「괜찮다」", "받지 않고 규칙의 「모름」 유지", "Pass"],
    ["2차 · 예산 초과·예산을 읽지 못함", "호출하지 않고 skipped로 기록, 고객 결과 불변", "Pass"],
    ["2차 · 같은 도구 반복·허용 목록 밖 도구", "차단", "Pass"],
    ["2차 · 이미 시작한 활동", "지난 시각의 날씨로 변경 제안하지 않음", "Pass"],
    ["3차 · LLM 인용이 원문에 없음 / 웹 출처가 검색 목록에 없음", "버리고 unknown(llm_uncited)", "Pass"],
    ["3차 · 대체 순서 LLM이 목록 밖 장소를 냄", "버리고 코드 순서 유지, 검증된 후보는 잃지 않음", "Pass"],
    ["3차 · shadow 기록에 장소명·고객 문장", "싣지 않음", "Pass"],
    ["3차 · Team이 외부 변경을 직접 실행", "아키텍처 시험으로 금지 확인", "Pass"],
])

# ── 5. 종합 ──────────────────────────────────────────────────
mine = RUN["total"]
ROWS51 = [
    ["단위 기능 — Activity Team (팀원)", "tests/unit/travel/activity/ 34개 파일", "451", "450", "0", "100%", "XFail 1(D-3, 의도된 실패 고정)"],
    ["단위 기능 — 대체 장소·데이터·평가기·어댑터 (팀원)", "test_activity_*, tests/unit/eval, 어댑터·조립", "219", "219", "0", "100%", ""],
    ["DB·저장소 연동 (팀원)", "tests/integration/db, 후보 풀, 프롬프트 배포 계약", "35", "34", "1", "97.1%", "D-1 프롬프트 미등록(환경)"],
    ["RAG 통합 시험 (팀원, 상위 8 기준)", "tests/integration/rag", "17", "17", "0", "100%", "로컬 Ollama bge-m3로 실행(D-2)"],
    ["통합·시나리오 (팀원)", "묶음 재계획 9 · e2e 21 · Controller 113 · 라우팅 21", "164", "164", "0", "100%", ""],
    ["아키텍처 (팀원)", "tests/architecture", "152", "151", "1", "99.3%", "Env: acop_composer 미설치(D-4)"],
    ["합계 (팀원, 커밋 966d2fbd)", "", "1,038", "1,035", "2", "99.8%", "XFail 1은 분모에서 제외"],
    ["작성자 환경 재실행 (질문 변환·공식 자료 반영)", "활동 단위·DB 통합·시나리오", str(mine["pass"] + mine["fail"]), str(mine["pass"]), str(mine["fail"]), pct(mine["pass"], mine["pass"] + mine["fail"]), "2026-10-14, 팀원 측정과 범위·환경이 달라 합산하지 않음"],
    ["RAG 정확도 실험 (작성자, 상위 3 기준 정답 절)", "질문 묶음 6개", str(tot_n), str(tot_on), str(tot_n - tot_on), pct(tot_on, tot_n), f"질문 변환 켠 때(끈 때 {tot_off}/{tot_n}). 학습 질문 포함 — 일반화 미입증"],
    ["판정 LLM 정확도 (참고)", "골든셋 52건 × 3회, 10-12", "156 관측", "151", "5", "96.8%", "5건 모두 「풀어 주는 쪽」 → 안전 비대칭으로 차단"],
]
fill_table(K[63], None, [[(f"{r[0]} — {r[1]}" if r[1] else r[0])] + r[2:] for r in ROWS51])
c = Cursor(K[63])
c.p("두 실패는 Activity 판정 코드의 결함이 아니다. D-1은 DB에 프롬프트가 등록되지 않은 배포 단계 누락이고 D-4는 관리용 패키지가 venv에 없는 환경 문제이다. " + REPRO)

ROWS52 = [
    ["D-1", "activity_judge.alternative_order 활성 프롬프트 0개(계약 시험 Fail, 팀원 DB)", "프롬프트(alternative_order.v2.md)가 허용 목록에는 들어갔지만 이 DB에 register_prompts로 등록되지 않음. 켜면 호출 전에 멈춤(fail-closed)",
     "미조치 — 등록 스크립트 재실행 후 재확인 필요. 현재 alternative_order는 shadow라 고객 결과 무영향. 작성자 DB는 등록되어 10/10 Pass"],
    ["D-2", "RAG 시험 8건 연결 거부(팀원)", ".env의 임베딩 서버(127.0.0.1:11435, 원격 GPU 터널)가 꺼져 있음", "이번 실행만 로컬 Ollama(11434, 같은 bge-m3)로 바꿔 17/17 통과. 기동 절차를 실행 매뉴얼에 남길 필요"],
    ["D-3", "설문 취향이 Activity로 전달되지 않음(XFail)", "Core Controller.TEAM_STATE_KEYS가 survey·activity_preference를 Team 상태에 넣지 않음", "Core 협의 대기 — Core가 고치면 strict XFail이 알려 줌. 그 전까지 대체 순서 LLM은 고객 문장만 단서로 씀"],
    ["D-4", "아키텍처 시험 1건(test_the_registry_and_the_catalog_agree)", "관리용 Composer 패키지 acop_composer가 venv에 설치되지 않음", "환경 문제 — 관리 빌드 의존성을 설치한 환경에서 재실행"],
    ["D-5", "판정 LLM의 「풀어 주는 쪽」 오답 5건(10-12 평가)", "제각각인 휴무 원문을 「휴무 아님」으로, 야외 위험형 재난을 「괜찮다」로 판정", "조치 완료 — 안전 비대칭(CAUTIOUS_VALUES): 휴무는 closed만, 재난은 blocks만 LLM이 확정"],
    ["D-6", "웹 판정 지연·429(p50 15.7초, p95 40.7초, 24회 중 8회 429)", "웹 검색 호출이 고객 응답 경로에 있었음", "조치 완료 — 장소·날짜당 1회 배치(check_live_status.py)로 옮겨 저장값만 읽음, 429는 쉬었다 1회 재시도, 동시 호출 슬롯"],
    ["D-7", "정기휴무 규칙이 「매주 X」 원문 309건 중 307건을 「휴무 아님」으로 확정(10-06 발견)", "정규식이 「매주 X (휴무|휴관)」 꼴만 읽음", "조치 완료 — closure_rules로 통합: 절 단위 판정, 못 읽은 조각은 「모름」(29개 시험). 공휴일 조건은 조회 키 미등록(403)으로 당분간 「모름」"],
    ["M-1", "보류 제안 표의 유일 제약 누락 — 시나리오 10건·통합 1건 실패(작성자 로컬 DB)", "로컬 DB 스키마가 마이그레이션 024의 UNIQUE(tenant, trip, item, base_version)와 달라 ON CONFLICT가 동작하지 않음(원인 미상, 팀원 환경은 해당 시험 통과)", "환경 문제로 분류 — 제약 추가 후 109건 전부 통과(로컬 한정). 공유 DB에 같은 누락이 있는지 확인 필요"],
    ["M-2", "규정 정리 문서의 해석 문장 오류 6곳(원문 대조에서 발견)", "표준약관·분쟁해결기준을 풀어 쓰며 원문에 없는 해석·누락(단서·사유 목록)이 들어감", "조치 완료 — 원문(HWP 제10~15조, PDF 53·87·88·108·109쪽)과 대조해 수정 후 해당 청크 재적재"],
    ["M-3", "규정 검색에서 고객 표현과 문서 용어가 달라 미적중", "구어체(가족 사망·리프트 고장 등)와 문서 용어 불일치, 두 주제가 섞인 절이 이웃 절에 끌림", f"부분 조치 — 절 분리 2곳 + 규칙 기반 질문 변환 → Hit@3 {pct(tot_off, tot_n)} → {pct(tot_on, tot_n)}. 규칙 밖 표현은 그대로라 일반화 한계"],
    ["M-4", "공식 자료 20청크가 팀 환경(ollama bge-m3)에서 검색되지 않을 수 있음", "작성자 환경에 Ollama가 없어 OpenAI 1536 칸에만 적재했고 embedding_1024 칸이 비어 있음", "미조치 — 팀 DB에 knowledge/travel_ext를 코어 적재 방식(bge-m3)으로 적재 후 같은 질문으로 재측정 필요"],
]
fill_table(K[65], None, [[f"{r[0]} · {r[1]}", r[2], r[3]] for r in ROWS52])

c = Cursor(K[65])
c.h("5.3 단계별 시험 이력 (작업 중 남긴 리포트의 실측 기록)")
c.p("아래는 구현 단계마다 돌린 시험·실측이 당시 리포트(wiki/records/reports, 활동 리포트 12건)에 적힌 그대로이다. 시험 범위와 실행 환경이 시점마다 달라 건수를 서로 더하거나 비교할 수 없다. "
    "10-06 평가의 규칙 정확도(휴무 7/16)와 10-12 평가(16/16)는 같은 대상을 잰 값이 아니다 — 그 사이 휴무 규칙을 새로 썼고 새 규칙은 같은 사례에 맞춰진 면이 있어 개선 폭으로 읽지 않는다.")
c.t(K[65], ["일자 · 단계", "당시 실행한 시험·실측 결과", "발견한 문제와 조치"], HIST)
c.h("5.4 남은 검증 과제")
c.t(T2, ["과제", "이유"], [
    ["D-1 프롬프트 등록 후 계약 시험 재실행", "대체 순서 LLM을 llm 모드로 올리기 전 필수"],
    ["공식 자료 20청크를 팀 DB(bge-m3)에 적재하고 같은 질문으로 재측정", "임베딩 제공자가 다르면 검색 결과가 달라질 수 있음(M-4)"],
    ["질문 변환의 일반화 시험 — 실제 고객 말투로 만든 새 질문", "지금 수치는 규칙을 만들 때 본 질문이 섞여 있음"],
    ["실시간 운영(웹) 판정 라벨 확보", "정확도를 모르면 llm 모드로 올리지 않음"],
    ["gemma4:12b 골든셋 측정(평가기에 로컬 모델 옵션 추가)", "sLLM 전환 조건 ②"],
    ["live 마크 시험(실제 OpenAI 호출) 재실행", "이번 실행에서 비용 때문에 제외"],
    ["골든셋 확대와 검토자 2인 이상 일치도", "표본 52건, 검토자 1명의 한계"],
])

doc.save(OUT)
print("saved:", OUT)
