# A-COP 심사 방어·발표·실행 방어안

> 적용 범위: 가상 SaaS 도메인 1개, Billing/Subscription Team과 Technical Entitlement Team 2개, Feedback Analytics 배치 1개, 6명·10주 MVP.
>
> 이 문서는 아키텍처/DDL/스키마 설명서가 아니다. 심사에서 말할 문장과 그 문장을 뒷받침할 구현·측정물을 정의한다.

## 1. 심사 방어 논리

모든 답변은 주장보다 `case_id → run trace → tool trace → state transition → metric` 순서로 제시한다. 화면에 숫자를 띄울 수 없으면 답변을 단정하지 않는다.

| 심사위원의 질문 | 모범 답변 | 이 답을 하려면 구현·측정되어 있어야 하는 것 |
|---|---|---|
| “이거 그냥 LLM 파이프라인에 Agent 이름만 붙인 거 아닌가요?” | 아닙니다. 이름이 아니라 실행 책임과 증거가 분리되어 있습니다. Billing은 결제·구독 사실과 환불 정책만 다루고, Technical은 entitlement·계정 상태·장애 이력만 다룹니다. 한 케이스의 trace에서 `routing → team run → evidence → action proposal → approval/resume`을 확인할 수 있고, 잘못된 팀의 tool 호출은 0건이어야 합니다. Proposed를 단순 LLM 파이프라인으로 ablation했을 때 routing, policy grounding, action safety, resume success를 각각 비교합니다. | 두 Team의 허용 capability/tool 목록, 팀별 run trace, 잘못된 tool 호출 카운터, Proposed와 Baseline B의 동일 80건 지표표, approval 후 정확한 재개 노드 로그 |
| “Agent가 2개일 필요가 있나요? 프롬프트 하나로 다 되는 것 아닌가요?” | 단일 프롬프트도 답변은 만들 수 있지만, 이 MVP는 서로 다른 데이터 권한과 실패 책임을 검증하는 과제입니다. Billing과 Technical을 하나로 합친 ablation을 같은 60 golden·20 holdout에 실행합니다. ①정답 routing ②필수 사실 recall ③정책 근거성 ④권한 밖 tool 호출 ⑤handoff precision을 비교해, 2개가 비용만 늘리고 개선이 없으면 그 사실도 결론으로 공개합니다. | `baseline_single_team` 실행기, 팀별 데이터/tool scope, 80건 고정 데이터셋, metric CSV, 2개 Team 유지/폐기 판정 기준(핵심 지표 개선 또는 안전성 개선) |
| “RAG랑 Multi-Agent 둘 다 하는 이유가 뭔가요?” | 둘은 해결하는 오류가 다릅니다. RAG는 정책 문서의 근거를 찾고, Multi-Agent는 업무 책임·권한·다음 행동을 분리합니다. 정책 문서를 잘 찾지만 Technical 계정 정보를 읽지 못하면 실패하고, 팀을 잘 골라도 환불 정책을 인용하지 못하면 실패합니다. 그래서 `RAG 제거`, `Team 제거`, `둘 다 적용`의 3조건을 비교합니다. | 문서 ID가 포함된 evidence trace, 팀별 context scope, RAG on/off·multi-agent on/off 실험 설정, policy groundedness와 action safety 결과 |
| “LangGraph 안 쓰고 그냥 함수 호출로 하면 안 되나요?” | 단순 resolved 건만 보면 함수 호출로 충분합니다. 그러나 승인 대기 후 프로세스가 끊겼다가 재개되는 케이스와 Team handoff를 동일 함수 체인으로 안정적으로 재현하려면 상태·재개 지점·실행 trace가 필요합니다. 본 프로젝트의 주장은 LangGraph 자체가 우월하다는 것이 아니라, `waiting_approval`에서 승인 이벤트 뒤 `execute_approved_action`부터 재개되는 증거를 보이는 것입니다. 같은 시나리오를 함수 체인으로 구현한 baseline과 resume success·중복 side effect를 비교합니다. | 함수 체인 baseline, LangGraph 실행 trace, 강제 프로세스 재시작 테스트, resume success, duplicate side effect 카운터 |
| “정확도가 Baseline보다 얼마나 올랐나요? 비용은 몇 배죠?” | 발표 전 실제 측정값으로 답하겠습니다. 80건에 대해 Baseline A/B/Proposed를 같은 model·temperature·fixture·tool budget으로 실행하고, `correct routing`, `required fact recall`, `policy groundedness`, `action safety`, `case cost`, `p50/p95 latency`를 함께 제시합니다. 정확도만 올리고 비용·지연이 폭증하면 성공으로 포장하지 않습니다. | `python experiments/runner.py --config ...` 실행 결과, config/dataset hash, 모델·토큰·비용 로그, `reports/comparison.csv`, bootstrap 95% CI, 비용 대비 개선 표 |
| “가상 데이터로 한 실험을 어떻게 믿나요?” | 실제 고객 성능을 주장하는 실험이 아니라, 통제된 조건에서 workflow·권한·근거·재개 동작을 검증하는 실험입니다. 25개 정책 문서와 seed DB snapshot으로 재현성을 확보하고, golden 60과 표현·수치·순서를 바꾼 holdout 20을 분리합니다. 한계는 명시하고, 실제 데이터 일반화는 후속 검증 과제로 남깁니다. | seed 생성 명령, corpus/version hash, golden·holdout 분리 파일, 동일 입력 재실행 diff, 데이터 합성 규칙과 한계 문서 |
| “6명이 10주 했는데 결국 챗봇 아닌가요?” | 최종 화면은 채팅처럼 보일 수 있지만 성공 단위는 답변이 아닙니다. 케이스가 생성되고, 두 업무 Team 중 하나가 routing되며, 정책·DB 근거가 기록되고, 고위험 action은 승인 전 실행되지 않고, 승인 이벤트 후 중단 지점에서 재개되며, 불확실하거나 타 업무면 handoff/escalation됩니다. 배치에서는 반복 feedback을 묶어 Technical Team 후보 이슈를 냅니다. 이 상태·trace·배치 결과를 화면과 CSV로 함께 공개합니다. | case timeline, team/run/tool/approval trace 화면, 3종 demo 데이터, feedback report, 80건 평가 결과, action safety 100% 목표와 실패 건수 |
| “Handoff와 실패를 임의로 보여주는 것 아닌가요?” | 임계값을 발표용으로 조정하지 않습니다. capability 불일치, 필요한 데이터 scope 부재, 재시도 예산 초과, 낮은 근거 점수 중 하나가 발생하면 규칙에 따라 handoff/escalation합니다. 같은 fixture를 다시 실행해 동일한 조건에서 동일한 분기를 보여줍니다. | 분기 규칙 버전, 실패 fixture, trace의 `reason_code`, 재실행 결과, handoff precision/recall 또는 최소한 expected-vs-actual 표 |
| “Feedback Analytics 배치는 실시간 Agent와 무슨 관계인가요?” | 배치는 개별 케이스를 대신 처리하지 않습니다. 기간 내 feedback을 분류·중복/유사 cluster·빈도·추세로 묶고, 반복되는 entitlement 이슈를 Technical Team이 검토할 후보로 올립니다. 즉 실시간 workflow의 customer-level resolution과 배치의 운영-level signal을 분리하되, 같은 정책 문서·분류 label·seed 규칙으로 연결합니다. | `batch_run_id`, 기간·입력 hash, cluster 대표 문장과 건수, trend 표, Technical escalation 후보와 원본 feedback 연결 |
| “MCP read-only 3개면 실제 연동이라고 보기 어렵지 않나요?” | MVP의 목표는 외부 시스템을 많이 붙이는 것이 아니라 읽기 권한 경계를 검증하는 것입니다. 세 read-only tool은 subscription, payment, entitlement 조회만 제공하고, 쓰기 action은 별도 승인 흐름의 mock/business action으로 제한합니다. API key와 scope로 권한을 통제하며 OAuth2는 Phase 2입니다. | 3개 tool의 OpenAPI/MCP 호출 trace, scope 부족 거부 테스트, write tool 미노출 확인, API key 만료/위조 테스트, read-only contract test |
| “LLM-as-Judge 점수는 믿을 수 있나요?” | Judge 점수만 정답으로 쓰지 않습니다. DB seed 사실·필수 policy ID·필수 tool·최종 status는 규칙 기반으로 채점하고, 자연어 품질만 judge가 채점합니다. 전체의 20%는 사람이 blind review하여 judge-human 일치율을 보고, 불일치 사례를 공개합니다. | 규칙 점수와 judge 점수 분리, judge JSON rubric, blind 16건 이상(80건의 20%), 사람-judge agreement, unsupported claim 목록 |
| “데모는 잘 되는데 실제로 안정적인가요?” | 성공 영상이 아니라 성공·실패·재개를 같은 trace 구조로 보여줍니다. LLM malformed JSON, timeout, DB conflict, scope 거부, 승인 만료를 fixture로 주입하고, 복구 또는 escalation을 확인합니다. CI에서는 contract test·재개 테스트·평가 smoke를 매 PR 실행합니다. | fault injection fixture, 실패 reason code, 복구/최종 상태 표, CI 로그, seed reset 및 mock mode 명령 |

## 2. 발표 데모 스크립트 (10분)

데모용 SaaS는 `AcmeCloud`로 고정한다. 모든 화면에 `case_id`, 현재 status, run id를 표시한다. 발표자는 자연어를 즉석에서 바꾸지 않고 아래 입력을 그대로 붙여 넣는다.

| 시간 | 화면 | 입력 | 출력/행동 | Multi-Agent·상태·승인·재개가 드러나는 지점 |
|---|---|---|---|---|
| 0:00–0:30 | 제목 + 시스템 개요 | “이 데모는 3개 케이스와 80건 평가 결과를 보여줍니다.” | 2 Team, 1 batch, 평가 지표 5개를 한 화면에 표시 | 제품 소개가 아닌 검증 대상과 성공 기준 고정 |
| 0:30–1:00 | 운영자 대시보드 | `POST /demo/reset` 실행 | seed 시각, dataset hash, mock mode 표시 | 재현 가능한 출발점 공개 |
| 1:00–1:30 | 새 Case 입력 화면 | “Pro 구독인데 오늘 결제가 또 됐어요. 해지 후 결제인지 확인해 주세요.” | 생성된 `case_id`, `new → classifying → routing` timeline | Case가 단순 chat message가 아니라 상태를 가진 업무 단위임을 표시 |
| 1:30–2:00 | Trace 상세 | 위 케이스 실행 | `subscription_billing` routing, Billing Team run 생성 | Billing만 선택되고 Technical tool은 호출되지 않음 |
| 2:00–2:30 | Evidence/결과 화면 | 추가 입력 없음 | payment history·subscription 상태·정책 ID, refund eligibility, `resolved` | 단순 조회/정책 근거가 한 trace에 연결됨 |
| 2:30–3:00 | 평가 요약 화면 | 버튼 `Run smoke: case=resolved_01` | 예상 status와 실제 status 일치, tool 호출 목록 | (a) resolved 단순건 종료. 가장 빠른 정상 경로 |
| 3:00–3:30 | 새 Case 입력 화면 | “해지 후 3일 이내 결제된 금액을 환불해 주세요.” | `routing → running → waiting_approval`, `refund.request` proposal | 위험 action은 실행되지 않고 승인 대기로 멈춤 |
| 3:30–4:00 | Approval 화면 | 승인 버튼을 누르지 않고 trace를 펼침 | `approval_required=true`, 실제 write 호출 0건, checkpoint/node 표시 | (b) 승인 전 안전 경계와 WAIT 상태 |
| 4:00–4:30 | Approval 화면 | “환불 요청 승인” 클릭 | 승인 event, version 증가, resume 요청 | 승인 event가 state를 바꾸는 명시적 트리거 |
| 4:30–5:00 | Trace/Action 화면 | 자동 재개 대기 | checkpoint의 `execute_approved_action`에서 재개, action 1회 성공, `resolved` | (b) 재개가 처음부터 재실행되지 않고 정확한 지점에서 재개됨 |
| 5:00–5:30 | 새 Case 입력 화면 | “Pro인데 API 권한이 Free처럼 거부됩니다. 결제는 정상입니다.” | `technical_entitlement` routing, entitlement·account 조회 | 같은 도메인 안에서도 다른 책임 Team으로 분리 |
| 5:30–6:00 | Handoff Trace | Technical 실행 결과를 일부러 `entitlement_read` scope 부족 fixture로 설정 | Technical이 추측하지 않고 `escalated`, reason `missing_scope` | (c) 권한 부족 시 handoff/escalation, 근거 없는 답변 금지 |
| 6:00–6:30 | Case timeline | `scope=entitlement:read`로 재시도 | Technical evidence, 해결안, `resolved` 또는 operator handoff | (c) 실패를 성공으로 숨기지 않고 조건 변화와 분기를 표시 |
| 6:30–7:00 | Feedback Analytics 화면 | `batch_run_id=demo_batch_01` 실행 | 기간, 반복 cluster, 건수, 추세, Technical 후보 | 실시간 Case와 별개인 배치 파이프라인 결과 |
| 7:00–7:30 | Baseline 비교 화면 | `Run comparison` | Baseline A/B/Proposed의 routing·grounding·safety·cost·latency 표 | “Agent”라는 이름이 아니라 동일 데이터 비교 |
| 7:30–8:00 | Trace diff 화면 | Proposed와 single-prompt 결과 선택 | 단일 prompt의 누락 fact/권한 밖 action과 Proposed의 대기·근거 차이 | Multi-Agent/RAG의 필요성을 ablation trace로 증명 |
| 8:00–8:30 | 장애 주입 화면 | `Inject: llm_timeout`, `Inject: approval_expired` | retry 후 `escalated` 또는 만료 처리, 중복 action 0 | 실패도 정의된 상태와 audit trail을 가짐 |
| 8:30–9:00 | 평가 결과 화면 | holdout 20건 필터 선택 | golden 60과 분리된 holdout 결과, CI 표기 | 과적합 방지와 불확실성 공개 |
| 9:00–9:30 | 마무리 표 | “이 시스템이 챗봇과 다른 최소 증거는?” | 상태·권한·근거·승인·재개·handoff 6개 체크 | 질문별 증거 화면을 다시 연결 |
| 9:30–10:00 | README/녹화 링크 화면 | `make demo` 또는 PowerShell 명령 표시 | 재현 명령, known limitation, 다음 단계 | 발표자의 설명이 아니라 심사자가 재실행 가능한 인수인계 |

### 실패 대비 운영 명령

```powershell
# 정상 데모: 컨테이너 기동 후 seed와 mock mode로 고정
docker compose up -d
python scripts/reset_demo.py --seed demo --mode mock
python scripts/run_demo.py --scenario resolved_01

# 평가/장애 시나리오
python scripts/run_demo.py --scenario approval_resume_01
python scripts/run_demo.py --scenario handoff_scope_01
python scripts/inject_fault.py --case-id <CASE_ID> --fault llm_timeout
```

실제 명령명이 아직 없으면 발표 7일 전 `scripts/run_demo.py`, `scripts/reset_demo.py`, `scripts/inject_fault.py`를 위 인터페이스로 고정한다. 라이브 API 키와 외부 네트워크에 의존하지 않는 mock mode를 기본값으로 하고, 각 시나리오의 녹화본에는 화면 우측 상단에 `git_sha`, seed, mode를 표시한다. 라이브 데모가 실패하면 녹화본으로 해당 장면을 재생한 뒤, 로컬에서 trace JSON과 reset 결과를 즉시 보여준다.

## 3. 6명 협업 리스크와 해소 방법

### 의존 그래프

```text
A Runtime/State ── contract/state events ──> B API/DB/Tool ──> 외부 API·MCP·mock tool
       │                                      │
       ├── execution interface ──────────────┼──> C Billing Team
       │                                      └──> D Technical Team
       ├── trace/checkpoint ───────────────────────────────> F UI/Eval/QA
       └── state events ───────────────────────────────────> E Data/RAG/Feedback Analytics

E Data/RAG ── ContextPack/evidence fixture ──> C, D, F
C Billing + D Technical ── TeamResult/trace fixture ──> A 통합 테스트, F 시연
B API/DB/Tool ── seed snapshot/read-only tool ──> C, D, E
F UI/Eval/QA ── contract test/metric report ──> 전원 merge gate
```

핵심 블로킹은 `A→C/D`, `B→C/D/E`, `A+B→F`, `E→C/D`이다. 따라서 C·D가 Core 완성을 기다리게 두지 않는다.

### 1~3주차 Core 부재를 막는 실제 해법

| 시점 | 할 일 | 실제 파일/명령 | 완료 조건 |
|---|---|---|---|
| 1주차 월요일 | A가 최종 상태·TeamTask·TeamResult 예시 JSON과 error code를 작성 | `contracts/team_task.v1.json`, `contracts/team_result.v1.json`, `contracts/errors.v1.json` | C·D가 문서만 보고 fixture 입력/출력 작성 가능 |
| 1주차 화요일 | A가 Python protocol과 fake runtime 제공 | `app/core/ports/team_runtime.py`, `app/core/fakes/fake_runtime.py` | `python -m pytest tests/contracts -q` 통과 |
| 1주차 수요일 | B가 seed snapshot과 read-only tool fake 제공 | `tests/fixtures/customers/cust_001.json`, `app/integrations/fake_tools.py` | `python scripts/seed_demo.py --mode fixture`로 동일 결과 생성 |
| 1주차 목요일 | C·D가 실제 LLM 없이 팀 내부 규칙/프롬프트/결과를 구현 | `app/teams/billing/`, `app/teams/technical/` | fake runtime에 TeamResult를 반환하고 policy ID·required facts 포함 |
| 1주차 금요일 | F가 fixture 기반 trace viewer와 golden schema를 시작 | `tests/fixtures/cases/*.json`, `experiments/datasets/golden_cases.jsonl` | 실제 Core 없이 fixture trace를 렌더링 |
| 2주차 | A/B가 fake와 real adapter를 같은 protocol에 연결 | `app/core/fakes/`, `app/infrastructure/` | `--runtime fake`와 `--runtime real`의 contract test 동일 통과 |
| 3주차 | 실제 runtime을 1개 resolved fixture에 연결 | `python scripts/run_case.py --fixture resolved_01` | `new→resolved` 1건이 fake/real 양쪽에서 재현 |

C·D의 PR에는 LLM 호출이 없어도 된다. 먼저 고정된 `TeamResult` fixture로 routing·handoff·approval UI와 통합하고, real retrieval/LLM은 그 뒤 adapter만 교체한다. Core가 늦어질수록 fixture를 더 많이 쓰며, 실제 통합을 기다리느라 작업을 멈추지 않는다.

### 인터페이스 동결 및 Git 운영

| 규칙 | 실행 기준 |
|---|---|
| 인터페이스 동결 | 2주차 금요일 18:00에 A가 contract v1, B가 tool response v1, E가 ContextPack v1, C/D가 TeamResult v1을 PR로 머지한다. 이후 breaking change는 2명(A와 영향 팀) 승인 및 v2 병행 기간 없이는 금지한다. |
| 브랜치 | `main`은 항상 배포 가능한 상태, `feat/<owner>/<topic>`는 1~2일 수명, release는 `release/week-N` 태그로만 만든다. |
| PR | 300줄 이하를 권장하고 contract/example/test를 함께 제출한다. 담당자 1명 + 영향받는 팀 1명 review 후 merge한다. |
| 통합 주기 | 매일 17:30 `main` 통합, 수요일은 end-to-end smoke, 금요일은 milestone demo와 release tag. |
| CI 게이트 | formatting/type check, unit test, contract test, migration/seed smoke, approval-resume test, duplicate-action test, evaluation smoke(최소 10건)를 모두 통과해야 merge한다. |
| 충돌 처리 | 30분 이상 막히면 개인 브랜치에서 해결하지 말고 `#integration`에 재현 명령·기대 결과·막힌 contract를 남긴다. A가 상태/계약, B가 외부 adapter, F가 테스트 기준의 최종 조정자다. |

### 주간 회의 아젠다 템플릿

매주 월요일 30분은 계획, 금요일 45분은 증거 확인으로 고정한다.

| 순서 | 질문 | 산출물 |
|---|---|---|
| 1 | 지난주 DoD 중 실제로 명령으로 재현되는 것은 무엇인가? | 실행 명령 1개와 로그 링크 |
| 2 | 현재 블로커는 어느 의존성인가? | owner, unblock 날짜, 임시 fixture |
| 3 | 이번 주에 삭제할 범위는 무엇인가? | scope cut 1개 이상 또는 “없음” 근거 |
| 4 | contract 변경이 필요한가? | v1 유지 또는 변경 PR 번호 |
| 5 | 지표가 좋아졌는가, 비용/지연은 늘었는가? | 최신 metric table |
| 6 | 금요일에 실패해도 보여줄 장면은 무엇인가? | 녹화/fixture/mock 시나리오 |

## 4. 기술 난이도 현실성

학습비용은 해당 기술을 처음 접한 팀원이 MVP의 최소 사용법을 익히고 테스트 1개를 통과시키는 기준이다. 팀 전체가 전문가가 될 필요는 없다.

| 기술 | 학습비용(일) | 대체 가능 여부 | 못 하면 무너지는 것 | 판정 | 못 하는 팀원이 있을 때의 우회로 |
|---|---:|---|---|---|---|
| LangGraph | 3 | 가능: 명시적 상태 머신/함수 runner | WAIT/RESUME trace와 재개 데모 | 필수(최소 사용) | A가 graph를 소유하고 C/D는 `Team.execute()` protocol만 구현한다. 복잡한 병렬 graph는 금지한다. |
| pgvector | 2 | 가능: PostgreSQL full-text 또는 고정 top-k fixture | 정책 근거 검색 재현성 | 필수 | E가 pgvector adapter를 담당하고, 실패 시 25개 문서의 precomputed retrieval fixture로 demo·평가를 계속한다. |
| PostgreSQL 트랜잭션/락 | 3 | 제한적: 단일 worker + optimistic version | stale write, 중복 action 방지 | 필수 | B가 transaction boundary와 conflict test를 소유한다. 팀원은 repository API만 사용하고 raw SQL을 쓰지 않는다. |
| FastAPI | 1 | Flask도 가능 | API key/scope와 demo endpoint | 필수 | B가 endpoint template을 만들고 F/C/D는 OpenAPI example을 먼저 작성한다. |
| Pydantic v2 | 1 | dataclass도 가능하나 비추천 | contract validation, malformed output 차단 | 필수 | A가 공용 모델을 관리하고 나머지는 생성된 example JSON과 helper 함수만 사용한다. |
| outbox 패턴 | 2 | MVP에서는 단일 worker polling 가능 | 상태 변경과 event 발행 불일치 | 선택 | 외부 broker 대신 같은 DB transaction에 event를 기록하고 `scripts/publish_pending.py`를 cron처럼 실행한다. |
| Docker Compose | 1 | 로컬 프로세스 실행 가능 | 심사자 재현 환경 | 필수 | B가 compose를 소유하고, 서비스 수를 API·DB·worker 3개 이하로 고정한다. |
| MCP(FastMCP) | 2 | REST read-only endpoint 가능 | 외부 AI 연동의 MCP 장면 | 선택 | MVP는 REST와 동일 tool contract를 우선 완성하고, 3개 read-only MCP wrapper는 마지막에 붙인다. |
| API key + scope | 1 | 없음(대체 불가) | 외부 요청 권한 경계 | 필수 | OAuth2는 제외하고 B가 고정 scope 3~4개와 거부 테스트만 구현한다. |
| LLM-as-Judge | 2 | 규칙 기반 + 사람 평가 가능 | 자연어 품질 비교 | 선택 | F가 규칙 점수와 blind human 20%를 먼저 운영하고 judge는 보조 지표로만 추가한다. |
| 부트스트랩 신뢰구간 | 1 | 단순 평균만 가능하나 비추천 | 작은 60/20 표본의 불확실성 설명 | 선택 | F가 1개 공용 스크립트로 metric별 10,000회 resample을 실행하며 팀원은 결과 CSV만 사용한다. |
| React 상태관리 | 2 | React local state/context 가능 | trace·approval·resume 화면 | 필수(간단히) | 전역 store를 도입하지 않고 URL의 `case_id`와 서버 조회를 단일 source로 둔다. |

판정 원칙은 기술 이름이 아니라 발표 증거다. 6주차까지 필수 항목 중 하나라도 실제 시나리오에 연결되지 않으면 선택 기술(MCP, judge, outbox, 고급 React 상태관리)을 즉시 동결한다.

## 5. 플랜 B — 실패 대응

### 6주차 진도 40%일 때 버리는 순서

아래 순서대로 제거한다. 앞 번호를 제거하고도 최소 데모의 재현성을 지키는 것이 원칙이다.

| 우선순위 | 버릴 것 | 남기는 대체물 | 즉시 조치 |
|---:|---|---|---|
| 1 | OAuth2 | API key + scope | OAuth endpoint·token refresh PR을 닫고 README에 Phase 2로 이동 |
| 2 | MCP 3개 wrapper | REST read-only 3 tool | MCP 서버는 녹화본/문서만 남기고 REST contract test를 우선 통과 |
| 3 | Feedback Analytics 고급 cluster/rerank | 기간별 분류·빈도·대표 문장 batch | E가 `batch_v1`만 유지하고 trend 시각화는 표로 대체 |
| 4 | outbox/Redis 등 비동기 인프라 확장 | DB pending event + 단일 worker | B가 로컬 polling 명령으로 실행 |
| 5 | LLM-as-Judge 자동화 | 규칙 점수 + blind human 20% | F가 judge 호출을 끄고 동일 rubric CSV를 수동 검증 |
| 6 | pgvector hybrid/rerank 최적화 | pgvector top-k 또는 precomputed retrieval | E가 검색 파이프라인을 단일 방식으로 고정 |
| 7 | 다중 Team 내부 agent 수 증가 | Billing 1 graph + Technical 1 graph | C/D가 각 팀의 대표 workflow 1개만 유지 |
| 8 | UI polish/외부 AI 연동 데모 | Case list/detail, trace, approval 3화면 | F/B가 API와 trace JSON으로 발표를 보장 |

### “이것만 되면 발표 가능” 최소 데모 정의

다음 목록을 모두 충족하면 나머지 기능이 없어도 MVP 발표가 가능하다.

| 필수 기능 | 구체적 합격 조건 |
|---|---|
| 가상 SaaS 데이터 | 고객 10명 이상, 구독·결제·entitlement snapshot, 정책문서 25건과 chunk 300~400개가 seed 명령으로 재생성됨 |
| 공통 Case | 입력 1건이 `case_id`를 받고 상태 timeline과 trace를 남김 |
| Billing Team | 구독/결제 사실과 정책 근거를 조회해 단순건 1개를 `resolved`로 종료 |
| Technical Team | entitlement/계정 사실을 조회해 권한 오류 1개를 해결하거나 escalation |
| 승인 | 환불 request proposal은 승인 전 실행되지 않음 |
| 재개 | 승인 후 중단된 노드에서 재개하고 action이 정확히 1회 실행됨 |
| handoff/escalation | scope 부족 또는 책임 불일치 fixture에서 근거 없는 답 대신 `escalated`와 사유를 기록 |
| Feedback batch | 최소 20개 feedback을 넣어 반복 이슈 cluster/건수/Technical 후보 1개를 출력 |
| 평가 | golden 60·holdout 20에 Baseline A/B/Proposed를 실행하고 핵심 지표·비용·지연을 CSV로 출력 |
| 재현 | `docker compose up -d`와 reset/demo 명령만으로 녹화본과 같은 3종 시나리오 재실행 |

### 주차별 조기경보 신호

| 주차 | 경고 신호 | 이 신호가 보이면 이미 늦은 이유 | 즉시 조치 |
|---:|---|---|---|
| 1 | contract example 없이 각자 코드를 시작함 | 2주차에 결과 형식 통합이 재작업으로 변함 | 금요일까지 v1 JSON·fake runtime·fixture를 merge하지 않으면 새 기능 금지 |
| 2 | C/D가 real Core를 기다리며 commit이 없음 | 팀 구현이 3주차 이후 한꺼번에 합쳐져 통합 불가 | fake runtime과 fixture 결과를 의무화하고 48시간 내 PR 제출 |
| 3 | `new→resolved` 한 건도 명령으로 재현되지 않음 | UI·평가를 만들어도 실제 시스템이 없음 | 모든 선택 기술 중단, 단순 resolved vertical slice만 완성 |
| 4 | 승인 전 action 실행 로그가 한 번이라도 있음 | 안전성 핵심 주장과 데모가 동시에 무너짐 | action adapter를 mock으로 고정하고 승인 전 호출을 CI에서 fail |
| 5 | Case trace에 run/tool/state 연결이 없음 | 심사 질문에 말로만 답하게 됨 | F가 trace JSON을 기준으로 UI를 만들고 모든 호출에 correlation id 강제 |
| 6 | golden 데이터가 아직 변하거나 holdout이 노출됨 | 7~8주차 수치가 재현되지 않고 과적합 의심을 받음 | 데이터·정책 corpus freeze, hash 기록, holdout 접근 제한 |
| 7 | 3종 demo 중 approval/resume가 수동 DB 수정으로만 됨 | 실제 상태·승인 검증이 아니라 연출로 보임 | 승인 API와 resume 명령을 먼저 완성하고 DB 직접 수정 금지 |
| 8 | p95 latency·cost·safety 중 하나를 측정하지 않음 | “얼마나 좋아졌나/얼마나 비싼가” 질문에 답할 수 없음 | 모든 run에 token·cost·latency·status 계측, 미측정 기능은 발표에서 제외 |
| 9 | holdout 성능이 golden보다 급락하고 원인을 모름 | 최종 발표 직전 데이터 누수·표현 과적합을 발견함 | holdout 오류 5건을 수동 분류하고 prompt·retrieval·routing 중 하나만 수정 |
| 10 | 발표용 명령이 팀원 한 명 PC에서만 실행됨 | 재현 실패 시 복구할 운영자가 없음 | 새 clone/깨끗한 환경에서 30분 리허설, 실패 시 mock mode와 녹화본으로 전환 |

### 마일스톤 게이트 실패 조치

| 마일스톤 | 통과 게이트 | 실패 시 당일 조치 | 다음 게이트까지의 복구 기준 |
|---|---|---|---|
| M1 (3주) | fake/real contract 통과, `new→resolved` 1건, seed reset, 두 Team fixture | OAuth/MCP/UI polish 중단. A·B·F가 vertical slice를 공동 소유하고 C/D/E는 fixture로 연결 | `python scripts/reset_demo.py` 후 3회 연속 resolved 재현, stale write·schema error 0 |
| M2 (6주) | approval→resume, handoff/escalation, golden 60 초회 실행, cost/latency 계측 | 8순위 컷을 순서대로 적용. Team 내부 agent 수와 hybrid retrieval 제거 | 세 시나리오 각각 3회 재현, 승인 전 side effect 0, 승인 후 중복 0, 평가 CSV 생성 |
| M3 (9주) | holdout 20, Baseline A/B/Proposed 비교, batch report, 발표 녹화 | 새 기능 금지. 숫자·trace·README·녹화본만 고정하고 known limitation을 명시 | 새 환경에서 30분 내 설치·reset·3종 demo·평가 smoke 완료 |

최종 방어선은 “모든 기능 완성”이 아니다. `resolved 1건 + approval/resume 1건 + handoff 1건 + 재현 가능한 비교표`를 실제 trace와 명령으로 보여주는 것이다. 이 네 가지가 없으면 기능을 더 추가하지 말고, 해당 네 장면의 신뢰성을 먼저 회복한다.
