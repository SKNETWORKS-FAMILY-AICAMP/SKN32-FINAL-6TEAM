# A-COP 중간발표 현황 정리

기준일은 2026-08-20이다. 중간발표는 2026-09-15이고 최종발표는 2026-10-26이다. 아래 판단은 정적 코드·테스트 파일을 읽은 조사 결과에 따른다. 이번 조사에서 테스트를 실행한 것은 아니다.

## 결론

현재 발표에서 책임 있게 보여줄 수 있는 중심축은 `Case 접수 → 분류 → Context 구성 → 등록된 Team 실행 → 응답 또는 승인 대기`의 런타임 골격과 안전 경계다. A2A와 Response Review는 코드·fixture·테스트가 있으나 기본 설정과 Registry 등록 상태를 구분해서 보여줘야 한다.

현재 상태로는 정량 성능 비교, 통계적 우월성, 일일 배치의 실제 스케줄 실행, outbox 재처리 성공률을 주장할 수 없다. DoD 갭 분석은 29개 중 구현됨 18개, 부분 구현 9개, 미구현 1개, 판정 불가 1개로 판정했다(`program/research/_DoD_구현갭_분석.md:5-7`).

## 1. 지금 시연 가능한 단위

### 1.1 Case 접수와 분류 실패 처리를 포함한 기본 흐름

Case를 REST로 만들고, 인라인 분류 결과에 따라 Team routing 또는 `classification_failed` 경로로 보낼 수 있다. REST Case 진입점과 분류 연결은 `final_project_cs/app/presentation/api/cases.py:65-107`, `final_project_cs/app/modules/customer_ops/feedback.py:86-106`에 있다. 성공·실패 분류 검증은 `final_project_cs/tests/integration/api/test_api_runtime.py:162-200`, `final_project_cs/tests/unit/voc/test_feedback.py:16-35`에 있다.

이 흐름에서 실제로 보여줄 수 있는 것은 분류 성공과 실패를 별도 상태·이벤트로 다루는 방식이다. 계획서가 말하는 60건 정확도나 confusion matrix는 아직 발표 근거가 아니다(`program/plan/A-COP_구현계획서_v8.md:166-169`).

### 1.2 상태 전이, append-only trace, replay의 핵심 골격

상태와 허용 전이, 단일 전이 진입점, version CAS, event append, outbox insert, event replay가 연결되어 있다. 근거는 `final_project_cs/app/domain/events.py:41-70`, `final_project_cs/app/core/transition.py:60-87`, `116-151`, `153-203`, `215-227`이다. 상태표와 reducer·DB 통합 검증 파일은 `final_project_cs/tests/contract/test_case_state_table.py:49-95`, `final_project_cs/tests/integration/db/test_db_integration.py:59-91`, `final_project_cs/tests/unit/core/test_case_reducer.py:112-142`이다.

따라서 Case가 어느 상태에 있고 어떤 event가 누적되는지는 보여줄 수 있다. graph projection replay와 checkpoint 분리까지 완료됐다고 말할 수는 없다. DoD 4는 부분 구현이다.

### 1.3 ContextPack과 tenant·PII 안전 경계

ContextPack의 12,000 token 예산, 초과 거부, tenant 범위, PII redaction을 계약으로 보여줄 수 있다. 근거는 `final_project_cs/app/core/contracts.py:122-156`, `final_project_cs/app/core/transition.py:54-58`, `148-151`, `final_project_cs/app/core/redaction.py:1-25`이다. 계약·보안 테스트는 `final_project_cs/tests/contract/test_contracts.py:82-106`, `final_project_cs/tests/security/test_pii_redaction_runtime.py:43-67`, `final_project_cs/tests/security/test_scope_contract.py:8-18`이다.

정책·FAQ 25건과 300~400 chunk가 실제 ingest됐다는 결과는 아직 제시할 수 없다. RAG 저장·검색 구조만 부분 구현으로 확인됐다(`final_project_cs/app/infrastructure/rag/retriever.py:42-70`).

### 1.4 Team 계약과 현재 등록된 VOC 흐름

`TeamModule`, `TeamManifest`, Registry의 contract version·중복 Team 검사는 구현되어 있다. 근거는 `final_project_cs/app/core/contracts.py:299-330`, `final_project_cs/app/core/registry.py:38-45`, 검증은 `final_project_cs/tests/contract/test_team_contract.py:7-19`이다.

현재 활성 등록 Team은 `voc_store_manager` 하나다. 설정 근거는 `final_project_cs/config/project.yaml:1-21`과 `program/research/_cs_구현현황.md:40-67`이다. 따라서 “플러그인 계약이 존재한다”는 시연은 가능하지만 “여러 Team을 교체·확장한다”는 시연은 현재 등록 상태만으로는 부족하다.

### 1.5 ActionProposal, approval, idempotency, degraded 차단

Action 요청 저장, approval 대기, timeout·unknown, idempotency key, proposal 근거 대조와 degraded Context의 자동 실행 차단을 보여줄 수 있다. 근거는 `final_project_cs/app/application/controller.py:180-252`, `final_project_cs/app/application/proposal_guard.py:58-109`, `final_project_cs/app/core/idempotency.py:1-12`, `final_project_cs/app/infrastructure/db/repository.py:42-50`이다. 관련 검증은 `final_project_cs/tests/contract/test_contracts.py:154-210`, `final_project_cs/tests/integration/controller/test_provider_timeout_unknown.py:41-123`, `final_project_cs/tests/integration/controller/test_proposal_guard_blocks.py:148-164`, `final_project_cs/tests/integration/api/test_recheck_before_execution.py:1-100`이다.

시연의 핵심 메시지는 Team이 주문·결제·환불을 직접 실행하지 않고, 근거가 있는 제안을 Core에 넘기며 승인 전후 재검증을 거친다는 것이다. 실제 외부 업무 시스템의 side effect는 보여줄 수 없다.

### 1.6 REST·MCP scope와 운영 진입점

Case REST API, Composer API, 운영 UI route, MCP 3개 tool과 `mcp:read` scope를 보여줄 수 있다. 근거는 `final_project_cs/app/presentation/api/app.py:1-80`, `final_project_cs/app/presentation/api/cases.py:1-110`, `final_project_cs/app/presentation/api/composer.py:1-80`, `final_project_cs/app/presentation/api/mcp.py:5-20`, `final_project_cs/app/presentation/security.py:1-80`이다. API surface·scope 검증은 `final_project_cs/tests/integration/api/test_openapi_surface.py:1-120`, `final_project_cs/tests/security/test_scope_contract.py:8-18`이다.

Composer는 계획서의 v3 토글 계약이 아니라 현재 `/composer/validate`·`/composer/apply` 중심의 구현이다. Composer v3가 완료됐다고 포장하면 안 된다(`program/research/_밤샘작업_요약_2026-08-20.md`, `program/research/_cs_구현현황.md:121-136`).

### 1.7 LOCAL/A2A 결과 정규화와 Remote fixture

Local Executor와 A2A Executor가 모두 canonical `TeamResult`로 결과를 매핑하고, Agent Card·submit·poll·input-required·artifact·실패·timeout·cancel·인증 fixture가 있다. 근거는 `final_project_cs/app/core/remote_team/executor.py:8-19`, `final_project_cs/app/core/remote_team/a2a_executor.py:17-26`, `46-85`, `final_project_cs/app/presentation/a2a/remote_agent.py:45-137`, `final_project_cs/tests/integration/a2a/test_remote_round_trip.py:1-160`이다.

다만 `a2a_executor`는 설정상 비활성이다(`final_project_cs/config/project.yaml`, `program/research/_cs_구현현황.md:59-67`). 따라서 이것은 기본 업무 흐름의 실서비스 Team이 아니라 A2A 계약·실패 매핑을 보여주는 fixture 시연으로 한정해야 한다.

### 1.8 Response Generation & Review의 GEN→REV 흐름

생성·검토·재시도·PII 차단 자체는 구현되어 있고 관련 Team 테스트도 있다. 근거는 `final_project_cs/app/modules/customer_ops/response_review.py:1-160`, `final_project_cs/app/modules/customer_ops/response_review_policy.py:1-39`, `final_project_cs/tests/unit/teams/test_response_review_team.py:53-141`, `final_project_cs/tests/unit/teams/test_response_review.py:40-141`이다.

그러나 `accepted_case_types=[]`이고 `project.yaml`에 등록되지 않았다(`program/research/_cs_구현현황.md:67`, `222-223`). 따라서 현재는 독립 구현·계약 시연이지, Controller가 자동으로 선택하는 두 번째 활성 Team 시연은 아니다.

## 2. 지금은 못 보여주거나 아쉬운 것

### 2.1 정량 평가 결과와 통계적 우월성

A/B/Proposed 60건·holdout 20건을 동일 입력으로 실행하고 checksum·결과를 저장하는 harness가 없다. DoD 15는 미구현이다(`program/research/_DoD_구현갭_분석.md:29`, `program/plan/A-COP_DoD_잔여작업_계획.md:92-102`). bootstrap CI·McNemar 함수와 단위 테스트는 있지만 실제 결과를 report·CI gate로 잇는 경로가 없다. DoD 16은 부분 구현이다(`program/research/_DoD_구현갭_분석.md:30`, `program/plan/A-COP_DoD_잔여작업_계획.md:104-114`).

4주 안에 전체 평가를 신뢰 가능한 형태로 완료하는 것은 어렵다. 두 작업 모두 계획상 큼(3일 이상)이고, fixture·harness·report·CI gate를 함께 고정해야 한다. 중간발표에서는 수치 대신 재현 명령, 입력·출력 schema, 실패 시 차단 규칙, 계약 테스트 목록을 보여준다. 실제 측정값은 제시하지 않는다.

### 2.2 Case trace·approval·VOC의 한 번에 이어지는 운영 화면

각 화면과 일부 E2E는 있으나 Case 생성부터 trace, approval, VOC report까지 한 흐름으로 묶은 검증은 없다. DoD 18은 부분 구현이다(`final_project_cs/app/presentation/ui/routes.py:90-170`, `250-270`, `final_project_cs/tests/e2e/test_operations_ui.py:1-140`, `program/plan/A-COP_DoD_잔여작업_계획.md:131-141`). 이 항목은 1~2일 규모로 4주 안에 가능하다.

### 2.3 일일 VOC report의 실제 scheduler

집계·ratio·surge alert·upsert 함수는 있지만 실제 scheduled-job 등록·실패 처리 경로가 없다. DoD 10은 부분 구현이다(`final_project_cs/app/application/feedback_job.py:30-77`, `program/plan/A-COP_DoD_잔여작업_계획.md:71-81`). 반나절 이내 추정이므로 4주 안에 가능하다. 발표에서는 scheduler를 만들기 전까지 “일일 배치가 운영 중”이라고 말하지 않는다.

### 2.4 RAG corpus 수량과 근거 품질

corpus 로드·ingest 경로와 25문서·306 chunk·1536차원 embedding·tenant scope 검증 테스트가 있다. DoD 6은 구현됨이다(`program/research/_DoD_구현갭_분석.md:20`, `program/plan/A-COP_DoD_잔여작업_계획.md:64-66`). 이번 작업에서는 테스트를 실행하지 않았으므로 발표에서는 정적 근거와 실행 결과를 구분한다.

### 2.5 outbox 재처리와 모든 consumer의 중복 방지

worker 상태 전이와 dedupe 구조는 있으나 failure injection replay와 모든 consumer의 동일 message 2회 처리 검증이 없다. DoD 12·23은 부분 구현이다(`program/research/_DoD_구현갭_분석.md:26`, `37`, `program/plan/A-COP_DoD_잔여작업_계획.md:83-93`, `155-161`). 각각 1~2일 규모로 4주 안에 가능하지만, 중간발표의 첫 화면보다 운영 신뢰성 보강 항목으로 둔다.

### 2.6 Graph projection과 Composer v3

Graph projection replay·revision 경계는 DoD 4 부분 구현이고 3일 이상 규모다(`program/plan/A-COP_DoD_잔여작업_계획.md:47-57`). 중간발표까지 완성 여부를 장담하지 않는다.

Composer v3는 별도 설계와 현재 구현의 endpoint·payload·패키징이 불일치한다. 이번 중간발표의 핵심 시연 범위에 넣지 않고, 현재 구현을 v3 완료처럼 설명하지 않는다(`program/research/_밤샘작업_요약_2026-08-20.md`).

## 3. 4주 안에 우선 채울 것

### 상위 1. 중간발표용 단일 E2E를 고정한다

Case 생성 → 분류 → ContextPack → `voc_store_manager` 응답 또는 승인 대기 → trace → 운영 UI → VOC report를 하나의 fixture와 재현 명령으로 묶는다. DoD 10·18에 해당하고, 계획상 scheduler는 반나절 이내, UI 통합 E2E는 1~2일이다(`program/plan/A-COP_DoD_잔여작업_계획.md:71-81`, `131-141`). 이 작업이 끝나면 관객에게 보여줄 순서와 화면이 고정된다.

### 상위 2. 활성 Team을 최소 2개로 만든다

플러그인 구조의 최소 신뢰 기준은 서로 다른 두 Team이 같은 `TeamModule`·Registry 계약을 통과하고, case type 또는 intent에 따라 선택되는 것이다. 한 Team만 등록하면 계약 존재는 증명되지만 교체·확장성은 증명되지 않는다.

가장 현실적인 두 번째 Team은 이미 구현된 `ResponseGenerationReviewTeam`이다. `accepted_case_types`, prompt 등록, `project.yaml` 등록, contract fixture를 보완한다(`program/plan/A-COP_예제Team모듈_확충설계.md:3-17`, `program/research/_cs_구현현황.md:67`, `222-223`). 6개 Team 전체 등록은 목표 상태일 뿐 4주 내 필수 발표 조건으로 두지 않는다. Return & Refund Mock을 세 번째로 추가하는 것은 두 Team 경로가 안정된 뒤 남는 시간에만 판단한다.

### 상위 3. 평가 수치 대신 검증 가능한 evidence 패키지를 만든다

중간발표까지 60/20 harness와 통계 report를 완성한다고 전제하지 않는다. 계획상 DoD 15·16은 각각 3일 이상 규모이고 선행 fixture·schema·CI 연결이 필요하다(`program/plan/A-COP_DoD_잔여작업_계획.md:95-117`).

대신 동일 fixture로 재현할 수 있는 Case ID, event trace, TeamResult, evidence ID, proposal guard 차단 로그, approval 상태, API scope 결과를 한 묶음으로 남긴다. 정량 결과가 없다는 사실을 명시하고, 테스트 실행을 완료한 뒤에만 pass 수나 성공률을 넣는다. 이전 브리핑의 “315 pytest passed”, “60/20 평가 완료” 표기는 이번 DoD 갭 분석의 정적 조사·미실행 전제와 충돌하므로 재실행 전에는 발표 근거로 사용하지 않는다(`program/briefing/A-COP_파트별_진행_브리핑.html`, `program/research/_밤샘작업_요약_2026-08-20.md`).

## 4. 발표 자료로 쓸 수 있는 산출물

다이어그램은 계획·구조 설명용으로 사용한다. 실제 구현 범위를 입증하는 자료로 단독 사용하지 않는다. 다이어그램 근거 문서도 대부분 계획서 계약과 런타임을 기준으로 한다(`program/plan/diagram/_다이어그램_근거.md`).

| 제안 슬라이드 | 자료 | 사용할 내용 | 주의점 |
|---|---|---|---|
| 1. 문제와 범위 | `program/plan/diagram/acop_usecase_v2.svg` | 고객·운영자·Core·Team·MCP·A2A의 역할 범위 | 계획된 주체와 실제 활성 Team을 구분 |
| 2. 전체 구성 | `program/plan/diagram/acop_component_v2.svg` | Core Runtime, CS Pack, API, Broker, Team 경계 | 다수 Team이 등록된 것처럼 보이지 않게 설명 |
| 3. 실제 Case 흐름 | `program/plan/diagram/acop_sequence_v2.svg` | Case 생성, 분류, Context, Team, WAIT/RESUME, 응답 | 단일 시연 fixture의 실제 trace와 함께 사용 |
| 4. 상태와 안전 | `program/plan/diagram/acop_state_v2.svg` | 상태 전이, terminal, 대기·재개 개념 | graph projection 완료를 의미하지 않음 |
| 5. 승인·A2A | `program/plan/diagram/acop_a2a_sequence_v2.svg` | Agent Card, task, input-required, 결과 정규화 | 설정상 A2A executor 비활성이고 fixture 시연임을 표시 |
| 6. 데이터와 근거 | `program/plan/diagram/acop_erd_v2.svg` | Case·event·action·approval·knowledge 관계 | 25문서·chunk 수량은 별도 검증 결과가 있어야 주장 |
| 7. 코드 경계 | `program/plan/diagram/acop_class_v2.svg` | ContextPack, TeamTask, TeamResult, Registry, Controller | 계약 구현 근거 파일을 옆에 배치 |
| 8. 배포·사용 시나리오 | `program/plan/diagram/acop_deploy_v2.svg`, `acop_sequence_v2.svg` | 실행 구성과 사용자 요청 왕복 | 배포 다이어그램은 선 교차가 많아 확대·부분 캡처 필요 |

바로 쓸 수 있는 브리핑은 `program/briefing/A-COP_브리핑_v8.html`, `program/briefing/A-COP_브리핑_v8_쉬운설명.html`, `program/briefing/A-COP_에이전트팀구성_브리핑.html`, `program/briefing/A-COP_파트별_진행_브리핑.html`이다. 다만 진행 브리핑은 최신 DoD 갭 분석과 수치가 충돌하므로 현황 슬라이드의 기준 자료로 그대로 사용하지 않는다. Composer 패키징 브리핑은 Composer v3의 불일치 결정을 먼저 확정한 뒤 별도 부록으로 사용한다.

부족한 자료는 다음 네 가지다.

- 실제 실행된 중간발표 E2E의 화면 캡처와 Case ID·trace evidence
- 25문서·chunk 수량·metadata·embedding dimension을 출력하는 ingest 결과
- 활성 Team 2개가 같은 Registry 계약으로 resolve되는 결과
- 평가를 주장하려면 60/20 harness 실행 로그와 checksum. 없으면 정량 그래프를 만들지 않는다.

## 5. §26 답변과 현재 상태의 불일치

### “Team이 Tool을 직접 호출하는가? 아니다.”

현재 `VocStoreManagerTeam`이 `self.tools.call()`을 직접 호출한다(`final_project_cs/app/modules/customer_ops/voc_store_manager.py:46-51`). DoD 22는 부분 구현이다(`program/research/_DoD_구현갭_분석.md:36`). 따라서 현재 답변은 사실과 맞지 않는다. 중간발표 전에는 Context Broker 경유로 바꾸고 AST·runtime spy 검증을 추가하거나, 수정 전에는 “현재 구현은 직접 호출 경로가 남아 있다”고 답해야 한다.

### “통계적으로 믿을 수 있는가? 60+20, 3회 반복, paired bootstrap CI, McNemar와 한계를 함께 보고한다.”

현재 60/20 harness와 실제 paired 결과 report가 확인되지 않았다. DoD 15는 미구현이고 DoD 16은 통계 함수·단위 테스트까지만 있는 부분 구현이다(`program/research/_DoD_구현갭_분석.md:29-30`). 따라서 §26의 답변은 현재 상태와 맞지 않는다. 중간발표에서는 통계적 결론을 말하지 않고, 평가 설계와 미완료 상태를 보고한다.

### “왜 Team인가?”

답변의 설계 취지는 유효하지만, 현재 활성 Team은 `voc_store_manager` 하나다(`program/research/_cs_구현현황.md:40-67`). “독립된 Team의 교체와 확장이 이미 동작한다”고 확장해서 말하면 현재 상태와 어긋난다. 최소 2개 Team이 Registry에서 선택되는 증거를 만들기 전에는 “계약과 확장 구조가 구현되어 있고, 현재 등록은 1개”라고 제한한다.

### “왜 A2A인가?”

답변의 개념 설명은 현재 A2A fixture와 일치한다. 다만 기본 설정의 `a2a_executor`가 비활성이고 실제 활성 Remote Team이 없으므로, A2A가 현재 업무 흐름에서 운영 중이라고 말하면 안 된다(`program/research/_cs_구현현황.md:59-67`).

### “Graph DB를 반드시 쓰는가? 아니다.”

이 답변은 현재 상태와 대체로 맞다. `SqlGraphAdapter`와 관계 질의 3종이 구현·검증되어 있고, graph projection replay는 아직 부분 구현이라는 범위만 함께 밝힌다(`program/research/_DoD_구현갭_분석.md:35`, `program/plan/A-COP_DoD_잔여작업_계획.md:47-57`).

## 발표용 한 줄 정리

중간발표의 정직한 범위는 “Case·계약·안전·승인·A2A 경계를 가진 실행 골격과 한 개의 실제 등록 Team을 보여주고, 두 번째 Team·단일 E2E·운영 report를 4주 안에 보강하는 단계”다. 정량 우월성이나 운영 자동화가 완료됐다고 말할 근거는 아직 없다.
