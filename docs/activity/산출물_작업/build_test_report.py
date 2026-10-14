# -*- coding: utf-8 -*-
"""멀티 에이전트 테스트 계획 및 결과 보고서(.docx)를 양식 위에 채운다 — 활동 에이전트 기준 (2026-10-14).

    cd final_project_cs
    python ../docs/activity/산출물_작업/build_test_report.py <양식.docx> <결과.docx>

원칙: 실측값만 쓴다 — 시험 결과는 `test_run_results_2026-10-14.json`(pytest junit), LLM 판정 평가는
`eval/reports/activity_judge/20261012T022514Z/summary.json`, 검색 시험은 `retrieval_results_*.json`. 안 잰 것은 「해당 없음」.
sLLM 파인튜닝은 하지 않았다 — 3장은 같은 자리에 「LLM 보조 판정 평가」를 쓴다.
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
RUN = json.loads((HERE / "test_run_results_2026-10-14.json").read_text(encoding="utf-8"))
JUDGE = json.loads((HERE.parents[2] / "final_project_cs/eval/reports/activity_judge/20261012T022514Z/summary.json").read_text(encoding="utf-8"))
XP = json.loads((HERE / "query_expansion_results_2026-10-14.json").read_text(encoding="utf-8"))
E1 = json.loads((HERE / "retrieval_results_E_e1.json").read_text(encoding="utf-8"))
FILES = RUN["files"]


def n(prefixes=(), exact=(), contains=()):
    """파일(클래스) 이름 조건에 맞는 시험의 (통과, 실패, 건너뜀, 파일수)."""
    p = f = s = c = 0
    for k, v in FILES.items():
        if k in exact or any(k.startswith(x) for x in prefixes) or any(x in k for x in contains):
            p += v["pass"]; f += v["fail"]; s += v["skip"]; c += 1
    return p, f, s, c


def one(name):
    v = FILES[name]
    return v["pass"], v["fail"], v["skip"]


# ── 문서 조작 도우미 (벡터DB 결과서 스크립트와 같다) ───────────────
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


def clone_after(proto_p, anchor, text: str):
    p = copy.deepcopy(proto_p)
    set_p(p, text)
    anchor.addnext(p)
    return p


def pct(a, b):
    return f"{a / b:.1%}" if b else "—"


doc = Document(TPL)
body = doc.element.body
K = list(body)

# ── 표지 ─────────────────────────────────────────────────────
cells = [[tc for tc in tr.findall(qn("w:tc"))] for tr in K[4].findall(qn("w:tr"))]
set_cell(cells[1][1], "2026. 10. 14.")
set_cell(cells[2][1], "https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM (브랜치 role-activity-b)")

# ── 1. 테스트 개요 및 환경 설정 ───────────────────────────────
tot = RUN["total"]
set_p(K[10], f"본 보고서는 여행 CS의 활동(Activity) 에이전트가 고객의 취소·변경·성립 질문을 근거 있게 판정하는지 검증한 결과이다. "
              f"활동 에이전트는 규칙(요일표·재난표·예약 조건)으로 먼저 판정하고, 규정 문장은 RAG 로 찾아 근거로 붙이며, "
              f"LLM 은 규칙이 읽지 못하는 원문 해석에만 보조로 쓴다. 근거가 없으면 지어내지 않고 「모름」으로 사람에게 넘긴다. "
              f"범위는 판정 규칙의 단위 기능, DB 연동, 규정 검색(RAG) 정확도, LLM 보조 판정의 규칙 대비 정확도, 시나리오 통합 시험이다. "
              f"자동 시험은 {tot['pass'] + tot['fail']}건을 실행했고(2026-10-14), 자체 sLLM 파인튜닝은 하지 않았다.")

fill_table(K[12], None, [
    ["Language & Framework", "Python 3.12.15, pytest 8.4.2 — 코어 컨트롤러 + 팀 레지스트리 구조(LangGraph 는 쓰지 않음, 흐름은 컨트롤러와 Case 상태기계가 정함)"],
    ["LLM / sLLM", "OpenAI gpt-5.4-nano (판정 보조·대체안 순서, reasoning low, 웹 검색 사용 가능) / 임베딩 text-embedding-3-small(1,536차원). sLLM 은 사용하지 않음"],
    ["Database", "PostgreSQL 16.15 + pgvector 0.8.6 (Docker, 정형 데이터와 벡터 검색을 한 DB 에서 처리). 그래프 DB 는 미도입"],
    ["Protocol / Infra", "REST(코어 API) · Docker(DB) · 비용·호출 상한(CallBudget). MCP 는 활동 판정 경로에서 사용하지 않음"],
])

comp = [
    "코어 컨트롤러: 고객 메시지를 Case 로 만들고 분류(일정 제출·사건 신고·확인 요청·조정 거부)한 뒤 팀 레지스트리를 거쳐 활동 팀에 전달한다. 코어는 팀 내부를 알지 못한다.",
    "활동 팀(ActivityTeam): 취소 가능·성립·변경 제안을 판정하고 제안만 반환한다. 결제·예약 변경 같은 부수효과는 실행하지 않고 승인 대기로 넘긴다.",
    "규정 검색(RAG, read.policy): 질문과 가까운 규정 절을 pgvector 로 찾아 고객용 문장을 출처와 함께 싣는다. 못 찾으면 「모름」으로 인계한다.",
    "LLM 판정 보조(activity_judge): 규칙이 읽지 못하는 원문(휴무·운영시간·재난 문구)만 한 번 해석한다. 기본은 규칙, LLM 은 섀도(기록만)이며 켜도 근거(인용)가 있어야 쓴다.",
    "감시·대체: 웹 공지 확인 배치(check_live_status, 저장 값 조회)와 대체 후보 선정·순서(코드가 후보를 고르고 LLM 은 보여줄 3곳의 순서만 정한다).",
]
for i, text in enumerate(comp):
    set_p(K[14 + i], text)

# ── 2. 구성요소 연동 및 단위 기능 테스트 ──────────────────────
db_p, db_f, _, db_c = n(prefixes=("integration.db.test_activity",))
dq = n(exact=("unit.travel.test_activity_data_quality", "unit.travel.test_activity_place_lookup"))
hrs = n(contains=("test_activity_hours_check", "test_activity_read_hours", "test_activity_indoor_outdoor", "test_closure_rules"))
rf = n(contains=("test_activity_rule_first", "test_judge_modes"))
fill_table(K[23], ["테스트 항목", "검증 내용 및 평가 요소", "결과"], [
    ["정형 DB 연동", f"실제 DB 에 대한 장소 실내외 분류·원장 기록·갱신·섀도 기록 {db_p + db_f}건(파일 {db_c}개): 저장·조회·재실행 안전", f"Pass {db_p}/{db_p + db_f}"],
    ["데이터 품질·장소 조회", f"장소 원장 데이터 품질 규칙과 장소 조회 {dq[0] + dq[1]}건", f"Pass {dq[0]}/{dq[0] + dq[1]}"],
    ["운영시간·휴무·실내외", f"요일표 기반 운영시간·정기 휴무·실내외 판정과 휴무 규칙 {hrs[0] + hrs[1]}건", f"Pass {hrs[0]}/{hrs[0] + hrs[1]}"],
    ["역할 분리(규칙 먼저·LLM 뒤)", f"규칙이 판정할 수 있는 것은 LLM 을 부르지 않고, 모드(rule·shadow·llm)에 따라 호출이 갈리는지 {rf[0] + rf[1]}건", f"Pass {rf[0]}/{rf[0] + rf[1]}"],
])

# 2.2 RAG — 규칙 작성 뒤 만든 질문 묶음(E)의 실제 결과
rows = []
for o in E1:
    top = o["top3"][0]
    verdict = f'적중({o["rank"]}위)' if o["rank"] else "미적중"
    rows.append([o["id"], o["query"], "기대 절: " + " / ".join(o["expect"][:2]), f'{top["score"]:.3f} — {top["document"]} · {top["section"]} ({verdict})'])
fill_table(K[25], ["케이스 ID", "입력 쿼리", "기대 결과 및 임계치", "테스트 결과 (Sim. Score)"], rows)
set_p_after = clone_after
sets_txt = " · ".join(f'{x["set"]} {x["off"]}→{x["on"]}/{x["n"]}' for x in XP["sets"])
tot_off = sum(x["off"] for x in XP["sets"]); tot_on = sum(x["on"] for x in XP["sets"]); tot_n = sum(x["n"] for x in XP["sets"])
p1 = clone_after(K[27], K[25], f"질문 변환(사전) 끈 때 → 켠 때 절 단위 Hit@3: {sets_txt}. 합계 {tot_off}/{tot_n}({pct(tot_off, tot_n)}) → {tot_on}/{tot_n}({pct(tot_on, tot_n)}). "
                                 "위 표는 규칙 작성 뒤 만든 E 묶음 10문항의 켠 때 결과이다.")
p2 = clone_after(K[27], p1, "해석 주의: E 를 뺀 나머지 묶음은 규칙을 만들 때 질문 문장을 이미 본 상태라 학습 데이터에 가깝다. E 에서도 개선은 규칙 어휘와 겹친 질문(E01·E06·E08)에서만 나왔고 "
                            "규칙에 없는 표현(E05·E09·E10)은 그대로 미적중이었다. 유사도 임계치는 두지 않았다(제안값 0.4).")

set_p(K[27], f"외부 호출 체계: 외부 호출은 두 가지다 — LLM(웹 검색 포함)과 임베딩. 호출은 CallBudget(DB 집계)으로 일·월 상한을 걸고, 한도에 닿으면 호출하지 않고 「모름」으로 돌아간다. "
              f"웹 공지 확인은 요청 경로가 아니라 배치(72시간 창, 6시간 재확인)로 돌려 저장하고, 요청에서는 저장 값만 읽는다. 관련 시험: 호출 실패 격리 {one('unit.travel.activity.test_activity_judge_faults')[0]}건, "
              f"호출 예산 {one('unit.travel.activity.test_activity_trigger_budget')[0]}건, 저장된 확인값 조회 {one('unit.travel.activity.test_activity_live_status_stored')[0]}건, 감시 배치 {one('unit.travel.activity.test_watch_batch_unit')[0]}건 모두 통과.")
set_p(K[28], "장애 방어(Fallback): 호출 실패·시간 초과·근거(인용) 없음이면 같은 호출을 반복하지 않고(재시도 0회) 해당 판정을 「모름」으로 두며, 실패 코드를 기록해 조용히 지나가지 않는다. "
              "규칙 판정은 LLM 이 실패해도 그대로 유지된다. 외부 도구(MCP) 연동은 활동 판정 경로에 없어 시험 대상이 아니다.")

# ── 3. LLM 보조 판정 평가 (sLLM 파인튜닝은 해당 없음) ───────────
set_cell(K[30].findall(qn("w:tr"))[0].findall(qn("w:tc"))[0], "3. LLM 보조 판정 평가 결과 (자체 sLLM 파인튜닝은 해당 없음)")
cond, kinds = JUDGE["conditions"], JUDGE["kinds"]
set_p(K[31], "3.1 평가 환경 (sLLM 파인튜닝은 수행하지 않음)")
set_p(K[32], f"평가 대상: 외부 LLM {cond['model']}(reasoning {cond['reasoning_effort']}, 웹 검색 사용)의 판정을 규칙과 비교. 사례 {cond['cases']}건 × {cond['repeats']}회 반복, 사람 검토 라벨(휴무·재난·운영시간 {sum(kinds[k]['cases'] for k in ('closure','disaster_effect','operating_hours'))}사례) 기준.")
set_p(K[33], f"실행 조건: 데이터셋 SHA-256 {cond['dataset_sha256'][:12]}…, 프롬프트 {cond['prompt_version']}, 부트스트랩 {cond['bootstrap']['n']:,}회. 소요 {JUDGE['elapsed_s']:.0f}초, 비용 ${JUDGE['cost_usd_total']:.2f}(전체 {JUDGE['observations']}관측).")
set_p(K[34], "파인튜닝: 하지 않음. 규칙 먼저, LLM 은 규칙이 읽지 못하는 원문만 보조로 쓰는 구조이며 sLLM 학습 데이터·하이퍼파라미터는 해당 없음.")
set_p(K[35], "3.2 규칙 대비 정확도 비교")
c, d, o = kinds["closure"], kinds["disaster_effect"], kinds["operating_hours"]
fill_table(K[36], ["평가 지표", "규칙(rule)", f"LLM({cond['model']})", "차이"], [
    ["휴무 판정 정확도", f"{pct(c['rule_accuracy']['num'], c['rule_accuracy']['den'])} ({c['rule_accuracy']['num']}/{c['rule_accuracy']['den']} 사례)",
     f"{pct(c['llm_accuracy']['num'], c['llm_accuracy']['den'])} ({c['llm_accuracy']['num']}/{c['llm_accuracy']['den']} 관측)", f"{(c['llm_accuracy']['value'] - c['rule_accuracy']['value']) * 100:+.1f}%p"],
    ["재난 영향 판정 정확도", f"{pct(d['rule_accuracy']['num'], d['rule_accuracy']['den'])} ({d['rule_accuracy']['num']}/{d['rule_accuracy']['den']} 사례)",
     f"{pct(d['llm_accuracy']['num'], d['llm_accuracy']['den'])} ({d['llm_accuracy']['num']}/{d['llm_accuracy']['den']} 관측)", f"{(d['llm_accuracy']['value'] - d['rule_accuracy']['value']) * 100:+.1f}%p"],
    ["운영시간 판정 정확도", f"{pct(o['rule_accuracy']['num'], o['rule_accuracy']['den'])} ({o['rule_accuracy']['num']}/{o['rule_accuracy']['den']} 사례)",
     f"{pct(o['llm_accuracy']['num'], o['llm_accuracy']['den'])} ({o['llm_accuracy']['num']}/{o['llm_accuracy']['den']} 관측)", f"{(o['llm_accuracy']['value'] - o['rule_accuracy']['value']) * 100:+.1f}%p"],
    ["위험 오답(닫힌 곳을 열렸다고 하는 등)", f"{sum(kinds[k]['rule_dangerous']['num'] for k in ('closure','disaster_effect','operating_hours'))}건",
     f"{sum(kinds[k]['llm_dangerous']['num'] for k in ('closure','disaster_effect','operating_hours'))}건 / {sum(kinds[k]['observations'] for k in ('closure','disaster_effect','operating_hours'))}관측", "—"],
])
ls = kinds["live_status"]
set_p(K[37], f"관찰: 규칙은 위험 오답이 0건이지만 운영시간은 읽지 못하는 사례가 많아 정확도가 낮고, LLM 은 운영시간을 모두 맞혔으나 휴무·재난에서 위험 오답이 나왔다. "
              f"웹 공지 확인(실시간 상태, {ls['cases']}사례 × 3회)은 LLM 이 「모름」으로 답한 비율 {ls['llm_unknown']['num']}/{ls['llm_unknown']['den']}, 지연 중앙값 {ls['latency_ms']['p50'] / 1000:.1f}초(p95 {ls['latency_ms']['p95'] / 1000:.1f}초), 건당 약 ${ls['cost_usd_per_call_mean']:.3f}였다.")
set_p(K[38], "3.3 한계 및 개선 방향")
set_p(K[39], "한계점: 사례가 적고(라벨 42사례) 반복 3회는 같은 사례의 반복이라 독립 표본이 아니다. 위험 오답이 규칙 0건 대비 LLM 5건이므로 LLM 을 판정의 주 경로로 쓰지 않는다. 실운영 정확도·장기 변동은 측정하지 못했다.")
set_p(K[40], "개선 방향: LLM 은 규칙이 「모름」일 때와 섀도 기록(규칙과 어긋난 사례 수집)에만 쓰고, 웹 공지는 배치 저장값으로 읽는다. 라벨을 늘려 다시 측정한 뒤 모드(rule → shadow → llm)를 올릴지 정한다.")

# ── 4. 시나리오 기반 통합 테스트 ──────────────────────────────
sc_p, sc_f, _, sc_c = n(prefixes=("scenario.",))
set_p(K[44], f"4.1 워크플로우 실행 검증 (판정 순서와 시나리오 시험 {sc_p + sc_f}건)")
steps = [
    '사용자 요청: "내일 오후 2시에 예약한 야외 체험, 비가 와도 진행되나요? 취소할 수 있나요?"',
    "의도 파악 및 라우팅: 코어 컨트롤러가 요청을 분류해 활동 팀의 취소 가능 판정 또는 성립 판정으로 보낸다.",
    "판정 순서(활동 팀): ① 이미 시작·정원 확인 → ② 재난·날씨(규칙표, 모르는 문구만 LLM) → ③ 휴무·운영시간(요일표) → ④ 저장된 웹 공지 값 → ⑤ 모르면 고객에게 질문 → ⑥ 성립이면 경고와 함께 성립.",
    "근거 수집: 예약이 있으면 예약 조건(취소 기한·위약금율)을 구조화 표에서 읽고, 규정 문장은 RAG 로 찾아 출처와 함께 붙인다. 근거가 없으면 지어내지 않는다.",
    "결과 취합: 판정·근거·경고를 하나의 결과로 묶고, 일정 변경이 필요하면 제안만 만들어 승인 대기로 넘긴다(결제·변경을 실행하지 않는다).",
    "답변 구성: 모델이 문장을 짓지 않고 규칙 판정 문구와 규정 문서의 고객용 문장을 그대로 싣는다.",
    f"시나리오 시험: 일정 제출·확인 요청·핀 고정 항목·새벽 점검·감시 배치 등 {sc_c}개 파일, {sc_p + sc_f}건 — 로컬 DB 를 실제로 쓰며 {sc_p}건 통과.",
]
for i, text in enumerate(steps):
    set_p(K[45 + i], text)

redir = one("unit.travel.activity.test_activity_submit_redirect")[0]
merge = sum(one(k)[0] for k in FILES if "test_activity_merge" in k or "from_develop" in k)
set_p(K[52], "4.2 협업 및 라우팅 테스트")
set_p(K[53], f"Routing 적절성: 일정 제출은 활동 판정이 아니라 여행 접수로, 일정이 정해진 Case 는 일정 관리로 가는지 {redir}건, develop 병합 시 활동 동작 회귀 {merge}건 모두 통과했다.")
set_p(K[54], f"상태·인계 정합성: 질문 후 재개 시 이전 답과 질문 상태가 이어지는지(고객 답 반영 {one('unit.travel.activity.test_activity_customer_answer')[0]}건)를 시험했다.")

unk = one("unit.travel.activity.test_activity_unknown_inputs")[0]
cp = n(contains=("test_case_path_gate", "test_pinned_items"))
set_p(K[55], "4.3 예외 상황 및 방어 체계 테스트")
set_p(K[56], f"근거 없음 (1차 방어): 입력·근거가 모자라면 판정하지 않고 「모름」으로 두고 고객에게 질문하거나 사람에게 넘긴다. 모르는 입력 처리 {unk}건을 시험했고, 규정 검색 결과가 없으면 취소 가능·변경 판정은 멈추고 「모름」으로 끝난다(활동 팀 코드 규칙).")
set_p(K[57], f"외부 호출 실패 (2차 방어): LLM·웹 호출이 실패하거나 인용이 없으면 해당 판정만 「모름」으로 두고 실패 코드를 기록한다(호출 실패 격리 {one('unit.travel.activity.test_activity_judge_faults')[0]}건, 호출 예산 {one('unit.travel.activity.test_activity_trigger_budget')[0]}건). 재시도는 하지 않는다.")
set_p(K[58], f"승인 없이 실행하지 않음 (3차 방어): 팀은 제안만 반환하고, 핀 고정·확인 우선 항목은 일정을 바꾸지 않고 질문·안전 알림으로만 처리하는지 {cp[0] + cp[1]}건 시험했다({cp[0]}건 통과).")

# ── 5. 종합 ──────────────────────────────────────────────────
groups = [
    ("판정 규칙·단위 기능", n(prefixes=("unit.travel.activity.",), contains=("test_activity_alternatives",))),
        ("평가 도구(데이터셋·검사기)", n(prefixes=("unit.eval.",), exact=("unit.test_eval_activity_a",))),
    ("DB 연동 통합", n(prefixes=("integration.",))),
    ("시나리오 통합", n(prefixes=("scenario.",))),
]
used = {k for k in FILES}
# 겹침 방지: 위 묶음은 이름이 겹칠 수 있으므로 판정 규칙 묶음에서 LLM 경로 파일을 뺀다
rule_p = rule_f = rule_s = 0
judge_keys = {k for k in FILES if any(x in k for x in ("test_judge_", "test_activity_judge", "test_try_activity_judge"))
              and not k.startswith(("unit.eval.", "integration.", "scenario."))}
for k, v in FILES.items():
    if k in judge_keys or k.startswith(("unit.eval.", "integration.", "scenario.")) or k == "unit.test_eval_activity_a":
        continue
    rule_p += v["pass"]; rule_f += v["fail"]; rule_s += v["skip"]
jp = sum(FILES[k]["pass"] for k in judge_keys); jf = sum(FILES[k]["fail"] for k in judge_keys); js = sum(FILES[k]["skip"] for k in judge_keys)
ev = n(prefixes=("unit.eval.",), exact=("unit.test_eval_activity_a",))
dbi = n(prefixes=("integration.",))
scn = n(prefixes=("scenario.",))
rows = []
for name, p, f, s, note in [
    ("판정 규칙·단위 기능(활동 · 대체안 · 데이터 품질)", rule_p, rule_f, rule_s, "휴무·재난·운영시간·성립·취소 가능·질문 변환 등"),
    ("LLM 보조 판정 코드 경로", jp, jf, js, "실호출 없이 가짜 LLM 으로 모드·실패·예산을 시험"),
    ("평가 도구(데이터셋·검사기)", ev[0], ev[1], ev[2], "라벨·집계·리포트 도구의 정합성"),
    ("DB 연동 통합", dbi[0], dbi[1], dbi[2], "실제 DB 사용"),
    ("시나리오 통합", scn[0], scn[1], scn[2], "일정·감시·안전 알림 흐름, 실제 DB 사용"),
]:
    rows.append([name, str(p + f), str(p), str(f), pct(p, p + f), note])
tp = tot["pass"]; tf = tot["fail"]
rows.append(["자동 시험 합계", str(tp + tf), str(tp), str(tf), pct(tp, tp + tf), f"예상 실패(xfail) {tot['skip']}건은 제외, 2026-10-14 실행"])
rows.append(["RAG 검색 시험(수동, 6묶음 {}문항)".format(tot_n), str(tot_n), str(tot_on), str(tot_n - tot_on), pct(tot_on, tot_n),
             f"Hit@3, 질문 변환 켠 때(끈 때 {tot_off}/{tot_n}). 학습 질문 포함 — 일반화 미입증"])
llm_obs = sum(kinds[k]["observations"] for k in ("closure", "disaster_effect", "operating_hours"))
llm_ok = sum(kinds[k]["llm_accuracy"]["num"] for k in ("closure", "disaster_effect", "operating_hours"))
rows.append([f"LLM 판정 평가(휴무·재난·운영시간)", str(llm_obs), str(llm_ok), str(llm_obs - llm_ok), pct(llm_ok, llm_obs),
             "관측 단위(사례×3회). 규칙이 주 경로이고 LLM 은 보조·섀도"])
fill_table(K[63], None, rows)

fill_table(K[65], None, [
    ["보류 제안 표의 유일 제약 누락(로컬 DB) — 시나리오 10건 · 통합 1건 실패",
     "로컬 DB 스키마가 마이그레이션 024 의 UNIQUE(tenant, trip, item, base_version)와 달라 ON CONFLICT 가 동작하지 않음(원인 미상)",
     "제약을 추가한 뒤 해당 시험 109건 전부 통과. 로컬 한정 조치이므로 코어·공유 DB 에 같은 누락이 있는지 확인 필요"],
    ["정리 문서의 해석 문장 오류(원문 대조에서 발견, 6곳)",
     "표준약관·분쟁해결기준을 풀어 쓰며 원문에 없는 해석·누락(단서·사유 목록)이 들어감",
     "원문(HWP 제10~15조, PDF 53·87·88·108·109쪽)과 대조해 문장 수정 후 해당 청크 재적재"],
    ["규정 검색에서 고객 표현과 문서 용어가 달라 미적중",
     "구어체 표현(가족 사망·리프트 고장 등)과 문서 용어 불일치, 두 주제가 섞인 절이 이웃 절에 끌림",
     f"절 분리 2곳 + 규칙 기반 질문 변환(사전, LLM 없음) → Hit@3 {pct(tot_off, tot_n)} → {pct(tot_on, tot_n)}. 규칙 밖 표현은 그대로라 일반화 한계"],
    ["LLM 판정의 위험 오답 5건(휴무·재난)",
     "웹 검색을 쓴 LLM 이 닫힘·영향을 놓치는 경우가 있음(규칙은 0건)",
     "기본 모드를 규칙으로 유지하고 LLM 은 섀도·보조로만 사용. 인용 없으면 쓰지 않음"],
    ["요청 경로의 웹 공지 확인 지연·비용",
     f"건당 지연 중앙값 약 {ls['latency_ms']['p50'] / 1000:.0f}초, 비용 약 ${ls['cost_usd_per_call_mean']:.2f}",
     "배치(72시간 창·6시간 재확인)로 저장하고 요청에서는 저장 값만 읽도록 변경, 일·월 호출 상한 적용"],
    ["대체안 순서가 사유 없이 바뀔 수 있음",
     "LLM 이 후보 전체를 재정렬하면 근거 없는 순위가 나올 수 있음",
     "코드가 후보를 고르고 LLM 은 보여줄 3곳의 순서만 정하게 제한, 순서 변경 시 사유 필수(없으면 거부)"],
])

# ── 5.3 단계별 시험 이력 — 기존 리포트(wiki/records/reports) 12개에 적힌 수치만 옮긴다 ──
hist_head = clone_after(K[64], K[65], "5.3 단계별 시험 이력 (작업 중 남긴 리포트의 실측 기록)")
set_p(hist_head, "5.3 단계별 시험 이력 (작업 중 남긴 리포트의 실측 기록)")
hist_note = clone_after(K[27], hist_head, "아래는 구현 단계마다 돌린 시험·실측이 당시 리포트(wiki/records/reports, 활동 리포트 12건)에 적힌 그대로이다. "
                        "시험 범위(전체 스위트인지 일부인지)와 실행 환경이 시점마다 달라 건수를 서로 더하거나 비교할 수 없다. 5.1 의 종합 표는 2026-10-14 에 한 번 일관되게 다시 실행한 값이다.")
HIST = [
    ["2026-09-28 · 팀 공용 브랜치 작업 전수검수",
     "파일 75개 전수 검수. 자동 시험 1,612 통과 · 64 건너뜀 · 0 실패(96%). 변경 전후를 같은 조건으로 비교한 3개 상황 모두 확인. (09-29 통합 후: 구조·계약·단위 1,779 통과, 여행 통합 150/150)",
     "날씨·재난 값을 못 받으면 건너뛰고 「성립」으로 답함(「값을 모를 때」 결정과 반대), 재난문자 칸 이름 불일치로 판단에 「없음」으로 전달. 판단 부분은 기존 코드를 유지하고 쓸 만한 부분만 골라 반영하기로 함"],
    ["2026-10-01~02 · develop 새 작업 반영",
     "시험 2,454/2,455 통과(99.96%, 실패 1건은 이동 팀 시험으로 전체 실행에서만 실패). 새 단위 시험 55건 + e2e 1건. 코덱스 독립 검토 4/4. 같은 데이터로 두 코드 비교",
     "「매주 일요일 / 월요일」처럼 슬래시 뒤 요일을 놓쳐 월요일 휴무를 「연다」로 읽음(2건) → 수정. 결론이 갈린 행 6건 → 고친 뒤 4건"],
    ["2026-10-06 · LLM 1단계 스파이크(실측)",
     "gpt-5.4-nano + 웹 검색으로 판정 가능 확인. 지연 p50 9.27초(5회 중 2회 20초 초과), 같은 질의 8회 중 열림 6·모름 2, 출처 URL 대조 5/5",
     "스키마를 강제하면 인용(url_citation)이 오지 않음 → 출처 검증을 검색 출처 목록 대조로 변경. seed 사용 불가 → 반복 측정. 지연 때문에 섀도 판정을 고객 응답 경로에서 분리"],
    ["2026-10-06 · LLM 2단계 어댑터",
     "1,917 통과 · 73 건너뜀 · 0 실패(기준선 1,896 + 새 시험 21건). 실호출 시험 1건 통과",
     "고객 답변은 바뀌지 않음(어댑터만 배선)"],
    ["2026-10-06 · LLM 3단계 판정 계층",
     "2,000 통과 · 73 건너뜀 · 0 실패(2단계보다 83건 증가). 실제 모델로 판정 5종 호출 확인",
     "인용이 원문에 없거나 출처가 검색 목록에 없으면 「모름」으로 내림. 호출 실패는 예외 대신 「모름」+실패 코드. 게시일 없는 근거는 버리지 않고 셈"],
    ["2026-10-06 · LLM 4단계 판정 연결",
     "2,016 통과. 기존 여행 시험 1,370건 그대로 통과. 섀도 모드에서 고객 결과가 규칙 모드와 동일. 실호출: 고객 답변 0.01초, 백그라운드 판정 5건 11초 뒤 완료",
     "실호출 첫 회에 판정 5건이 모두 llm_error(시험용 run_id 가 감사 기록 외래 키에 걸림, 운영 경로는 해당 없음) → 예외 종류를 로그에 남기도록 수정. 통합 시험 8건 실패는 RAG 임베딩 미적재로 무관"],
    ["2026-10-06 · 섀도 기록 표",
     "실제 모델로 섀도 실행 1회 → 표에 5행 적재 확인, 종류별 일치율을 SQL 한 줄로 집계. DB 통합 시험 4건",
     "로그로만 남기던 섀도 기록이 운영에서 아무 데도 남지 않던 문제 → DB 표로 이동"],
    ["2026-10-06 · LLM 5단계 골든셋 평가(사람 검토 전)",
     "LLM 0.987(154/156 관측) vs 규칙 0.462(24/52 항목), 차이 +0.526. 위험한 오답 LLM 2/156 · 규칙 13/52. 웹 판정은 호출 성공 16/24(429 8건), 회차 일관성 3/8",
     "라벨을 작성자가 달았고 사람 검토 전이라 낙관일 수 있음(이후 10-12 사람 검토로 재측정). 정기휴무 정규식이 「매주 X」 원문 309건 중 307건을 놓침 → 다음 항목에서 수정"],
    ["2026-10-06 · 정기휴무 규칙 수정",
     "「매주 X」 원문 놓침 307건 → 0건. 새 시험 34건(재발 방지·규칙·성립 판정 연결)",
     "휴무를 한국 날짜 기준으로 판정(전에는 UTC 요일로 하루 어긋남). 공휴일 조회 키가 서비스에 미등록(HTTP 403)이라 공휴일 조건은 당분간 「모름」"],
    ["2026-10-11 · 작업 B: 라벨 검토 도구·결과 상태 계약·재난 분류표",
     "활동·증거 단위 322 통과, 평가 단위 70 통과, 가드레일 계약 6 · 구조 2 통과. 통합(DB)·e2e·live·전체 시험은 돌리지 못했다고 명시",
     "도구 선언에 read.disaster_points 가 빠져 재난으로 막힌 뒤 대체 후보를 찾으면 죽었을 결함 발견·수정. 판정 규칙이 코어 포트를 직접 import 하는 구조 시험 1건은 변경 전부터 실패(이후 우회로 해소)"],
    ["2026-10-11~14 · CSV 컬럼 정리·TourAPI 보강",
     "활동 단위 399 통과. 변경 시점 전체 단위 실행 8 실패 · 3,092 통과(실패는 변경과 무관함을 원인별로 확인). 이후 단계별 시험 13·14·33·42·46 통과, 통합 130 통과",
     "컬럼 29개로 정합, 기존 값은 백업과 대조해 바뀐 값 0. 읽던 코드 4곳 함께 수정. TourAPI 호출 한도·재시도 시험 추가"],
]
hist_tbl = copy.deepcopy(K[65])
fill_table(hist_tbl, ["일자 · 단계", "당시 실행한 시험·실측 결과", "발견한 문제와 조치"], HIST)
hist_note.addnext(hist_tbl)

doc.save(OUT)
print("saved:", OUT)
