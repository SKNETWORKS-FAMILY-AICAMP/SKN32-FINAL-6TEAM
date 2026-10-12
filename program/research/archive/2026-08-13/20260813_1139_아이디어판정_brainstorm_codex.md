# A-COP 고도화 아이디어 — 독립 브레인스토밍 (Codex)

작성일: 2026-08-13

## 전제와 결론

아래는 `A-COP_구현계획서_A2A_Graph반영.md`와 `A-COP_브리핑_A2A_Graph반영_최종.html`을 기준선으로 삼은 독립 검토다. 6명, 8~10주 프로젝트에서 가장 큰 차별점은 “더 많은 Agent”가 아니라 **Case 상태·근거·실행 결과를 다시 재현할 수 있는 운영 런타임**이다.

핵심 결론은 다음과 같다.

1. CoT를 기능으로 추가하지 않는다. 이미 있는 Team/Controller 노드의 입력·출력·근거·재시도 이벤트를 기록하고, 어려운 판단에만 reasoning model을 라우팅한다.
2. Team 내부 self-consistency는 전건 적용하지 않는다. 고위험 환불/권한 변경 판단에 한정한 2회 샘플 + 불일치 시 보류가 비용 대비 낫다.
3. Controller replan은 우선 규칙 기반으로 고정한다. 자기비판 루프보다 `재시도 횟수`, `근거 부족`, `상태 충돌`, `deadline`을 명시한 전이표가 평가·발표에 유리하다.
4. 추가 기능은 “케이스 요약/압축, 프롬프트 버전·회귀, 오프라인 replay, 비용·latency 계측, 감정/반복불만 에스컬레이션”을 우선한다. 아래 제안마다 빼는 항목을 명시했다.

인·일은 한 사람이 하루 동안 설계·구현·테스트까지 하는 대략치다. 기존 계획의 동일 기능과 겹치는 부분은 추가 비용에서 제외했다.

## 1. 추론 기법 판단

| 기법 | 우리 어느 지점에 | 얻는 것 | 비용(인·일) | 평가로 증명 가능한가 | 판정 |
|---|---|---|---:|---|---|
| 고전적 CoT / “step by step” | 프롬프트에 일괄 삽입하지 않음. 대신 내부 판단은 `decision`, `evidence_ids`, `confidence`, `next_action` JSON으로 남김 | 긴 자연어 사고과정 대신 검증 가능한 결정과 근거 | 0~1 (스키마 정리) | 가능. JSON 유효율, 근거 ID 적중률, 정책 위반률 | **불필요(기능으로는)** |
| Self-Consistency | Billing의 환불/보상 여부, Technical의 위험한 계정 조치처럼 오류 비용이 큰 최종 분류에만 2회 샘플. 일반 분류·요약은 1회 | 단일 샘플의 우연한 오류 감소, 불일치 자체를 보류 신호로 사용 | 2~4 (2회 호출·다수결·로그·테스트) + 해당 케이스 LLM 비용 약 2배 | 가능. 동일 seed 고정 A/B, exact decision accuracy, abstention/사람 개입률, latency | **도입(선택적)** |
| ReAct | Team이 실제로 조회→판단→도구 실행을 반복해야 하는 Billing/Technical subgraph 내부에만. 조회 없는 VOC 분류에는 쓰지 않음 | 도구 호출과 관찰 결과가 분리되어 trace에 남음 | 2~3 (tool loop 제한, guardrail, 테스트) | 가능. tool call 성공률, 불필요 호출 수, 정책 근거 포함률 | **도입(제한적)** |
| Reflexion / 자기비판 | Controller 전체의 자동 재귀에는 넣지 않음. `TeamResult`가 `evidence_missing` 또는 schema-invalid일 때 1회 “누락 근거 점검” 노드로 사용 가능 | 실패 원인을 재시도 프롬프트에 구조화, 무한 재계획 방지 | 3~5 (실패 분류·1회 cap·회귀셋) | 가능. 재시도 후 회복률, 추가 토큰/latency, 무한루프 0건 | **보류(Team 실패 복구에 한정)** |
| Tree of Thoughts | Controller 라우팅 후보를 여러 경로로 확장하지 않음. 현재 Team 2개·깊이 1~2에서는 탐색공간보다 복잡도가 큼 | 복수 계획 비교 | 6~10 이상 (branching, pruning, 평가 기준) | 이론상 가능하나 데이터셋이 작아 신뢰도 낮음 | **불필요** |
| Plan-and-Execute | Controller는 이미 Top-Level LangGraph와 Case 상태로 계획을 관리한다. 별도 자유형 plan 객체를 추가하지 말고 `open_tasks`와 상태 전이표를 계획으로 취급 | 장기 업무의 단계 가시성 | 1~2 (open_tasks 계약 보강) | 가능. 계획 일치율, 단계 누락, 재개 성공률 | **도입(현재 구조로)** |
| LLM-as-Judge | 이미 계획된 Baseline A/B/Proposed 평가의 보조 채점기로 사용. 사람 표본 판정과 calibration하고, 정책 위반·결정 정확도는 규칙/정답셋 우선 | 답변 품질·근거성의 대량 비교 | 3~5 (rubric, 샘플 이중채점, agreement) | 가능. human agreement, pairwise win rate, bootstrap CI | **도입(보조)** |
| Constitutional / Critique | 모든 응답에 자기비판을 붙이지 않음. 외부 발송 직전의 안전·정책 위반 검사만 별도 저비용 critique 또는 규칙 필터로 수행 | 금지 문구, 근거 없는 확정, 개인정보 노출 감소 | 2~4 (규칙+소형 모델, 실패 케이스) | 가능. red-team 위반률, false positive, human override | **도입(안전 게이트만)** |

### Team self-consistency의 구체 판정

전건 N=3/5 다수결은 이 프로젝트에서 하지 않는다. Team 2개가 각각 여러 번 실행되면 latency, 토큰, 저장해야 할 trace가 거의 N배가 되고, 같은 프롬프트·같은 검색 결과를 반복해도 독립적인 증거가 늘지 않는다. 대신 **고위험 2종에 N=2**를 적용한다.

| 조건 | 실행 | 불일치 처리 | 보여줄 지표 |
|---|---|---|---|
| 환불/보상 액션 또는 권한 변경 제안 | temperature가 다른 2회 판단, 동일 Context Pack·동일 schema | 일치하면 제안, 불일치하면 `waiting_approval` 또는 `escalated`; 다수결로 위험 액션을 강행하지 않음 | 정확도, 불일치율, 추가 latency, 사람 개입률, action 오류 0건 |
| 단순 의도 분류·VOC 집계·요약 | 1회 | schema 오류만 재시도 1회 | p95 latency, 비용, 정확도 |

### Controller의 라우팅 정책

| 판단 | 모델 | 이유 |
|---|---|---|
| JSON schema 검증, 상태 전이 허용 여부, idempotency, deadline, approval 필요 여부 | LLM 없이 규칙/코드 | 결정적이고 테스트 가능한 영역. 모델을 쓰면 설명은 늘지만 통제성이 떨어짐 |
| 의도·감정·이슈 분류, 짧은 요약, Context Pack 압축 | 저비용 모델 | 반복·대량 처리이며 정답셋으로 측정 가능 |
| 환불 가능성, 권한 불일치 원인, 복수 근거를 비교하는 최종 Team 판단 | reasoning model 또는 고성능 모델 1회, 고위험이면 2-sample | 근거 간 충돌과 예외 조건을 다루는 비용이 높은 판단 |
| replan 후보 생성 | 저비용 모델이 후보를 JSON으로 생성하되, 승인 여부는 규칙 엔진 | 창의적 후보 생성과 실행 결정 분리 |
| 안전/정책 critique | 소형 모델+정규식/정책 룰 | 단순 패턴에 고가 모델을 쓰지 않음 |

### 구조화 출력과 추론의 양립

사고 과정을 JSON에 길게 노출하지 않는다. 각 Team은 `decision`, `confidence`, `evidence_ids[]`, `uncertainties[]`, `proposed_action`, `need_more_context`만 반환하고, prompt에는 “근거 ID는 Context Pack에 실제 존재하는 값만 선택”을 강제한다. Pydantic/JSON Schema 검증 실패는 같은 모델 1회 재시도, 두 번 실패하면 `escalated`다. 즉, reasoning은 모델 내부 또는 짧은 내부 메모리로 끝내고, 시스템에 저장·평가하는 것은 **결정·근거·불확실성·다음 전이**다.

## 2. 기능적으로 더 넣을 요소 (순증 금지)

아래는 10개가 아니라 우선순위가 높은 8개만 제안한다. `빼는 것`은 기존 계획의 해당 작업을 삭제·축소해 얻는 시간이며, 전부 추가하는 경우의 순증을 허용하지 않는다.

| 기능 | 왜 지금 필요한가 | 무엇을 빼고 넣는가 | 추가 비용(인·일) | 발표에서 어떻게 보여주는가 |
|---|---|---|---:|---|
| Case 요약·Context Pack 압축 | 장기 Case가 길어질수록 thread 재개와 Team 전달 비용이 증가. 현재 Shared State의 핵심 증거를 잃지 않고 오래 유지해야 함 | 별도 Episodic Memory 고도화와 자유형 대화 메모리의 3~4일을 빼고, `case_summary`, `open_questions`, `evidence_ids` 압축 노드로 대체 | 3~4 | 같은 Case를 1턴/10턴 뒤 재개하고 “요약 전후 토큰 수·근거 보존·결과 동일성”을 화면에 표시 |
| 프롬프트 버전·실행 manifest | Baseline/Proposed의 비교가 prompt 변경으로 오염되지 않게 해야 함 | 새 Prompt UI는 만들지 않고 기존 prompts 파일 규칙·Evaluation harness 문서화 2일을 줄여 `prompt_hash`, model, seed, schema version 기록 | 2~3 | 동일 입력을 v1/v2로 replay해 결과와 diff를 나란히 표시 |
| 회귀 테스트 자동화 | 기능이 늘면 정책 근거·상태 전이·JSON contract가 조용히 깨짐 | 별도 광범위 E2E 시나리오 4~5개를 줄이고, 25건 corpus를 golden JSON fixture로 승격 | 3~4 | PR/실행 화면에 contract pass, policy pass, decision accuracy, regression diff를 표시 |
| 오프라인 replay | 장애·재시도·A2A timeout을 실제 외부 서비스 없이 반복 재현해야 함 | 실제 Remote Agent를 여러 개 붙이는 PoC와 라이브 연동 문서 3일을 빼고, 저장된 `Task/Event/TeamResult` replay runner를 구현 | 3~4 | 같은 `case_id`를 정상/timeout/schema-fail 입력으로 재생해 상태 전이가 동일하게 복구되는 장면 |
| 비용·latency 계측 대시보드 | “Agentic이라 좋아졌다”를 비용과 시간 없이 주장할 수 없음 | 시각적으로 화려한 별도 운영 대시보드 3일을 빼고 기존 운영 UI에 case별 4개 KPI 카드만 추가 | 2~3 | Baseline A/B/Proposed의 token 추정치, LLM 호출 수, p95, human intervention을 한 화면 비교 |
| 감정·반복불만 에스컬레이션 | 현재 VOC 급증 분석과 고객지원 흐름을 실제 정책으로 연결하는 작은 기능 | 독립 감정분석 모델 튜닝은 빼고 기존 intent/sentiment 출력에 `negative_streak`, `repeat_issue_count` 규칙을 추가 | 2~3 | 같은 고객의 3회 반복 불만에서 자동 `escalated`와 담당 Team 변경을 trace로 표시 |
| 안전 필터/PII 마스킹 게이트 | 외부 AI/MCP/A2A 경계가 있으므로 프롬프트·로그에 개인정보가 남는 것이 발표 리스크 | OAuth 전체 고도화·다중 IdP 지원 3~4일을 축소하고 입력/출력 마스킹, 금지 action rule을 넣음 | 3~4 | 주민번호/이메일 샘플을 넣어 “LLM 입력에는 마스킹, audit에는 원문 hash, 위험 action은 승인”을 시연 |
| A2A/LOCAL 동일 결과 contract test | A2A의 존재보다 실행 경로 교체에도 `TeamResult`가 보존되는지가 핵심 증거 | Remote Agent 2개째 구현은 삭제하고 더미 Remote 1개에 contract test와 timeout mapping 추가 | 2~3 | 같은 입력을 LOCAL/A2A로 보내 schema·decision·evidence_ids·Case status diff를 0/동일로 표시 |

## 3. 레퍼런스 플랫폼 조사

“구조가 유사하다”는 것은 AI 기능이 있다는 뜻이 아니라, **업무 객체를 상태로 보존하고, 담당자/에이전트로 라우팅하며, 인계·재개·감사를 지원한다**는 뜻으로 판정했다.

| 플랫폼 | 어떤 구조인가 | A-COP와 닮은 점 | 다른 점 | 우리가 훔칠 아이디어 |
|---|---|---|---|---|
| Salesforce Agentforce Service / Cases | Case가 고객 이슈를 추적·해결하는 기록이고, Case Team과 자동 라우팅을 제공. Agentforce Service 문서는 Case를 서비스 운영의 중심 객체로 설명 | Case, Team, 라우팅, Knowledge, 사람/AI 인계가 A-COP와 가장 직접적으로 유사 | 상용 CRM·권한·데이터 모델이 훨씬 크고, 내부 오케스트레이션/모델 세부는 공개 범위가 제한적 | Case를 “대화”가 아니라 업무 기록으로 유지하고, 담당 변경 때 summary·history·next action을 함께 넘김 |
| Intercom Fin + Workflows | Workflow 안에서 Fin이 응답하고, 조건에 따라 더 많은 정보를 수집하거나 teammate/workflow로 handover. 반복 무응답·부정 피드백 등 인계 조건이 있음 | `waiting_input`, escalation, human handoff, 고객 감정/반복 질문을 흐름 조건으로 삼는 점이 유사 | Intercom 대화 중심 제품이며 A-COP의 별도 Team Registry·A2A Task·공유 상태는 확인되지 않음 | “사람 연결” 전에 부족한 Context를 한 번 수집하고, 인계 시 팀이 바로 쓸 수 있는 요약을 전달 |
| Zendesk AI agent tickets + Omnichannel routing | AI 대화도 ticket으로 보존하고, 진행 중/해결/인계 상태를 구분. 인계 시 일반 ticket 처리 흐름으로 돌아가며 priority/SLA/queue로 라우팅 | Ticket 상태 머신, AI→사람 인계, queue/routing, SLA deadline이 A-COP Case lifecycle과 유사 | Zendesk의 상용 ticket·채널·SLA 생태계가 중심이고, Case 간 관계 그래프나 A2A 위임은 확인되지 않음 | AI가 잡고 있는 상태와 사람이 처리할 상태를 분리하되, 인계 순간 history/context를 누락하지 않기 |
| LangGraph | 상태 그래프 기반 agent/workflow runtime. durable execution, persistence/checkpoint, human-in-the-loop, subgraph를 제공 | Top-Level LangGraph, `thread_id=case_id`, WAIT/RESUME, Team subgraph와 직접 대응 | 프레임워크이지 고객지원 Case 제품이 아님. Case 권한·업무 상태·audit은 애플리케이션 책임 | checkpoint 경계를 업무 이벤트와 맞추고, interrupt/resume를 사람 승인에 사용. 구조화된 node 결과를 저장 |
| Temporal | 코드로 정의한 장기 workflow를 crash 후 재개하고 retry·timer·signal 등으로 외부 입력을 기다리는 내구 실행 플랫폼 | 장기 Case, 재시도, deadline, 재개, 외부 이벤트를 1급 상태로 보는 관점이 유사 | LLM/Agent Team·RAG·MCP는 기본 제공 개념이 아니며, 별도 workflow service 운영 부담이 있음 | 지금은 도입하지 않고, Temporal식 “재시도 가능한 activity와 상태 밖 side effect 금지” 원칙만 차용 |
| Camunda 8 | BPMN 프로세스 인스턴스가 human task·microservice·API를 연결하고 process variable로 상태를 이동 | 명시적 상태 전이, 사람 승인, 업무 프로세스와 API/worker의 분리 | BPMN 모델링·workflow engine 중심이며 LLM 자율 판단은 기본이 아님 | 발표용 Case state diagram을 BPMN식으로 명확히 그리고, 자동 전이와 human task를 구분 |
| CrewAI Crews/Flows | Crews는 역할 기반 협업, Flows는 event-driven·조건·상태 관리형 오케스트레이션. 공식 문서도 예측 가능·감사 가능한 결정에는 Flows를 권장 | Team 내부 협업과 상위 Controller를 분리하는 A-COP 경계와 유사 | A-COP의 외부 A2A·Case source of truth·Port 계약은 기본 구조가 아님 | 자율 Team은 작은 경계 안에 두고, 상위 Case lifecycle은 결정적인 Flow로 유지 |
| Dapr Workflows / Agents | Dapr Workflow가 내구 실행을 제공하고, Dapr Agents가 workflow-backed durable agent·retry·state·HTTP runner를 제공 | Message/Service 경계, 내구 상태, 장기 Agent, 외부 실행 경로가 A-COP Port 구상과 유사 | 2026년 Agent 기능과 버전별 성숙도·운영 요구는 확인 필요. 6명 부트캠프에 Dapr runtime까지 추가하면 범위가 큼 | 실행기·메시지·상태를 교체 가능한 경계로 두되, MVP는 이미 확정된 LangGraph/PostgreSQL로 고정 |

### 레퍼런스에서의 독립 판단

가장 닮은 제품은 Salesforce의 Case 중심 서비스 운영과 Zendesk의 AI ticket 인계이고, 가장 닮은 실행 런타임은 LangGraph다. Intercom은 감정·반복·추가 정보 수집을 실제 handoff 정책으로 연결한 점이 유용하다. Temporal/Camunda/Dapr는 “내구 실행”의 비교 레퍼런스이지, 이 프로젝트에 추가 도입할 후보는 아니다.

확인 필요로 남긴 항목: 각 상용 제품의 내부 모델 라우팅 방식, Agentforce의 실제 A2A 호환 범위, Zendesk의 Case 간 관계 그래프, Intercom Fin의 내부 추론/모델 구성, Dapr Agents의 2026년 버전별 API 안정성. 공개 공식 문서로 확인되지 않은 내부 구현을 A-COP와 동일하다고 주장하지 않는다.

## 4. 발표 임팩트가 큰 요소 3개

| 요소 | 구현 비용 | 왜 인상적인가 | 발표 장면 |
|---|---:|---|---|
| 1. 동일 Case의 LOCAL ↔ A2A 실행 교체 | 2~3 인·일 (기능 제안 8에 포함) | “Agent를 더 만들었다”가 아니라 실행 위치가 바뀌어도 Core 계약과 Case 결과가 보존됨을 증명 | 같은 case_id·입력·seed를 두 경로로 실행하고 `TeamResult`/status/evidence diff가 동일함을 실시간 표시 |
| 2. 실패 후 재개 + Replay | 3~4 인·일 | 정상 데모보다 timeout·schema 오류·approval 대기가 업무 시스템의 실체임을 보여줌 | Team 실행 중 A2A timeout을 주입 → `waiting_input/escalated` → 재개 → audit/event 순서와 최종 결과 재생 |
| 3. 근거·비용·사람 개입을 한 화면에서 비교 | 2~3 인·일 | 품질만 말하지 않고 Baseline A/B/Proposed의 accuracy, evidence, p95, cost, intervention을 함께 설명 | Case를 클릭하면 답변 문장보다 먼저 상태 전이, evidence IDs, tool trace, LLM 호출 수, 정책 승인 여부가 보임 |

## 5. 하지 말아야 할 것

| 함정 | 이유 | 대체 판단 |
|---|---|---|
| Team마다 N=3/5 self-consistency | 6명/8~10주에서 비용·latency·trace가 폭증하고, 검색·정책이 같으면 정보가 늘지 않음 | 환불/권한 변경만 N=2, 불일치는 보류/승인 |
| Controller에 Reflexion/ToT 무제한 루프 | replan의 원인이 불명확해지고 상태 머신보다 LLM 호출이 흐름을 지배함 | 규칙 기반 replan + 실패 유형별 1회 critique |
| 전용 Graph DB를 MVP에 병행 | 계획서의 25~40 인·일 projection/동기화/검증 비용이 6명 프로젝트와 맞지 않음 | PostgreSQL `SqlGraphAdapter`; multi-hop·깊이 3이 반복될 때만 비교 실험 |
| 실제 고객지원 채널·외부 Agent를 여러 개 연동 | OAuth, webhook, rate limit, 계약 변동이 핵심 데모를 가림. A2A 2개째는 순증 | 더미 Remote Agent 1개 + LOCAL/A2A contract test + replay |
| 화려한 Agent 대시보드와 자유형 trace부터 개발 | 화면은 많아지지만 평가 근거·재현성이 없으면 “로그 뷰어”에 머묾 | 기존 UI에 상태·근거·오류·cost·latency 5개 축만 먼저 노출 |

## 참고한 공식 자료

- [Salesforce: Set Up and Manage Cases](https://help.salesforce.com/s/articleView?id=sf.cases_intro.htm&language=en_US&type=5) — Case 중심 서비스 운영, Case Team, AI/담당자 라우팅.
- [Intercom: Use Fin AI Agent in Workflows](https://www.intercom.com/help/en/articles/10032299-use-fin-ai-agent-in-workflows) — 추가 정보 수집, handover, 반복/부정 피드백 기반 인계.
- [Zendesk: Routing incoming support requests](https://support.zendesk.com/hc/en-us/articles/4944922385050-Getting-started-with-Zendesk-Suite-Part-6-Routing-incoming-support-requests), [AI agent tickets](https://support.zendesk.com/hc/en-us/articles/9204149016346-Understanding-AI-agent-tickets-for-AI-agent-only-conversations) — queue/SLA 라우팅과 AI ticket→사람 ticket 상태 전환.
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [Persistence](https://docs.langchain.com/oss/javascript/langgraph/persistence), [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — durable execution, checkpoint, HITL resume.
- [Temporal documentation](https://docs.temporal.io/) — crash 후 재개하는 durable workflow.
- [Camunda Processes](https://docs.camunda.io/docs/components/concepts/processes/) — BPMN process instance와 human task/API orchestration.
- [CrewAI Agents and Flows](https://docs.crewai.com/core-concepts/Agents) — Crews와 결정적 Flows의 분리.
- [Dapr overview](https://docs.dapr.io/overview/), [Dapr Agents introduction](https://docs.dapr.io/developing-ai/dapr-agents/dapr-agents-introduction/) — workflow-backed durable agents와 메시지/상태 경계.

