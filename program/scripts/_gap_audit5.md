===== DOC: A-COP_구현계획서_v8.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 문서 상태 | 일부 | `wiki/log.md`, `governance/drift-case-voc.md`; v8 기준선·이전 문서 우선순위·병합 출처 표가 온전히 없다 |
| v6 → v7 변경 요약 | 일부 | `architecture/`, `decisions/`, `evaluation/finetuning.md`; 7개 변경의 이전값·새값·이유를 묶은 표가 없다 |
| v7 → v7.1 변경 요약 [v7.1] | 일부 | `architecture/pack-model.md`, `evaluation/finetuning.md`, `delivery/roles.md`; 7개 변경 대조표와 보안 변경 일부가 빠졌다 |
| v7 → v8 변경 요약 [v8] | 반영 | `architecture/pack-model.md`, `delivery/timeline.md` |
| v8 재판정 [2026-09-01] — VOC 소관 정리 | 일부 | `governance/drift-case-voc.md`, `final_project_cs/wiki/teams/voc-store-manager.md`; `run_case()`의 트랜잭션 내 LLM 잔존과 `case.created` outbox 후속 조치가 빠졌다 |
| 0-1. 한 줄 요약 [A2A] | 반영 | `quickstart.md`, `architecture/pack-model.md`, `architecture/system-context.md`, `final_project_cs/wiki/data/schema/` |
| 0-2. 절 색인 | 일부 | 영역별 `index.md`는 있으나 원문의 절 42개와 내용을 대응시킨 색인 표는 없다 |
| 1. 프로젝트명 정리 [A2A] | 일부 | `quickstart.md`, `product/positioning.md`; `A-COPilot` 팀명과 풀네임·부트캠프 주제의 3행 정의가 없다 |
| 1-1. 포지셔닝 [v7 신설] | 반영 | `product/positioning.md` |
| 1-2. 제품 구조 — 하나의 Runtime, 두 도메인 팩 [v7 신설] | 반영 | `architecture/pack-model.md`, `product/positioning.md`, `product/scope.md` |
| 2. 문제 정의 [A2A] | 반영 | `product/problem.md`, `architecture/core-design.md` |
| 3. 프로젝트 목표 [A2A] | 반영 | `quickstart.md`, `architecture/`, `final_project_cs/wiki/`의 계약·Runtime 문서 |
| 3-A. 부트캠프 주제 요구사항 ↔ 구현 대응표 [v5 흡수] | 일부 | `delivery/dod.md`, `delivery/timeline.md`, `evaluation/`; 요구사항 11행과 산출물·검증의 완전한 대응표가 없다 |
| 4. 핵심 아이디어 [A2A] | 반영 | `architecture/core-design.md`, `architecture/core-vs-team.md` |
| 5. 시스템 범위 [A2A] | 반영 | `product/scope.md` |
| In Scope | 반영 | `product/scope.md` |
| Out of Scope | 반영 | `product/scope.md`, `architecture/system-context.md` |
| 6. 타깃 도메인 [A2A] | 반영 | `product/scope.md`; 원문의 SaaS 도메인과 2026-08-18 변경 사실까지 기록돼 있다 |
| 7. Agent Team Module 구성 원칙 [A2A] | 반영 | `architecture/core-vs-team.md`, `final_project_cs/wiki/teams/team-boundary.md` |
| v6 대비 개정 기록 | 일부 | `final_project_cs/wiki/teams/voc-store-manager.md`, `governance/drift-case-voc.md`; v6·v7·v8의 4행 비교표가 그대로 있지는 않다 |
| 7-A. Feedback Analytics 배치 파이프라인 [v5 흡수] | 일부 | `final_project_cs/wiki/quality/guardrails.md`, `teams/voc-store-manager.md`; 00:10 UTC와 급증 공식은 있으나 `voc:false`가 판단층·화면만 끈다는 전체 동작과 시계열 공백 이유가 분산·축약됐다 |
| 7-B. 전체 구성 | 일부 | `architecture/core-design.md`, `pack-model.md`, `system-context.md`; Core 1·Core 2·LOCAL/A2A·VOC 입출력을 한데 묶은 구성도와 일부 설명이 없다 |
| 8. Basement(Core) 설계 [A2A] | 반영 | `architecture/core-design.md` |
| 8-1. Agent Gateway | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/external/auth-boundary.md` |
| 8-2. Customer Case Layer | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/runtime/case-lifecycle.md` |
| 8-3. Agent Team Registry / Team Contract | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/teams/team-registry.md`, `teams/team-contract/` |
| 8-4. Context Broker | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/context/context-broker.md` |
| 8-5. Message Broker | 반영 | `architecture/core-design.md`, `decisions/D-003-message-broker.md`, `final_project_cs/wiki/runtime/message-broker.md` |
| 8-6. Shared State | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/runtime/shared-state.md` |
| 8-7. Tool / Action Layer | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/actions/` |
| 8-8. Agentic Controller / Orchestration | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/runtime/agentic-controller.md` |
| 8-A. Message Broker와 Context Broker 분리 [A2A] | 반영 | `architecture/core-design.md`, `decisions/D-003-message-broker.md` |
| Message Broker | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/runtime/message-broker.md` |
| Context Broker | 반영 | `architecture/core-design.md`, `final_project_cs/wiki/context/context-broker.md` |
| 8-A-1. 계층 경계 | 반영 | `architecture/core-design.md`, `decisions/D-003-message-broker.md` |
| 8-A-2. 전달 보장과 중복 처리 규칙 | 반영 | `decisions/D-003-message-broker.md`, `final_project_cs/wiki/runtime/message-broker.md`, `actions/idempotency.md` |
| 8-B. Agent Team 플러그인/모듈화 계획 [A2A] | 반영 | `architecture/pack-model.md`, `architecture/core-vs-team.md`, `final_project_cs/wiki/teams/index.md` |
| Response Generation & Review 모듈 [v7.1] | 반영 | `final_project_cs/wiki/teams/response-review.md`, `response-review-design.md` |
| Agent Team Registry | 반영 | `final_project_cs/wiki/teams/team-registry.md` |
| Team 내부 자유도 | 반영 | `architecture/core-vs-team.md`, `final_project_cs/wiki/teams/team-boundary.md` |
| Platform과 Team의 경계 | 반영 | `architecture/core-vs-team.md`, `final_project_cs/wiki/teams/team-boundary.md` |
| 권장 구조 | 누락 | `app/core/`와 `app/modules/customer_ops/team_modules/team_a·team_b`를 제시한 원문의 디렉터리 트리가 없다 |
| 8-C. Agent/Team 경합과 동시성 처리 책임 [A2A] | 반영 | `architecture/concurrency.md`, `final_project_cs/wiki/runtime/conflict-retry.md` |
| 9. 외부 소비자 AI 연동 구조 [A2A] | 반영 | `architecture/system-context.md`, `final_project_cs/wiki/external/` |
| 핵심 개념 | 반영 | `architecture/system-context.md`, `final_project_cs/wiki/external/mcp-tools.md` |
| 예시 | 누락 | `get_my_subscription`→`get_payment_history`→`open_support_case`→`request_refund`의 구독 환불 예시가 없다 |
| 보안 원칙 | 반영 | `architecture/system-context.md`, `final_project_cs/wiki/external/auth-boundary.md` |
| MCP 쓰기 3단계와 v6 개정 | 반영 | `final_project_cs/wiki/external/mcp-tools.md` |
| 9-C. MCP / A2A / Message Broker 역할 분리 [A2A] | 반영 | `architecture/system-context.md`, `final_project_cs/wiki/external/a2a-protocol.md`, `runtime/message-broker.md` |
| A2A가 쓰이는 세 경로 | 반영 | `final_project_cs/wiki/external/a2a-protocol.md` |
| A2A인지 판별하는 기준 | 반영 | `final_project_cs/wiki/external/a2a-protocol.md` |
| Personal AI 경로와 기업용 Agent 경로 | 반영 | `architecture/system-context.md`, `research/a2a-adoption.md` |
| A2A Task와 Case 상태 매핑 | 반영 | `final_project_cs/wiki/external/a2a-protocol.md` |
| MVP 범위 | 일부 | `final_project_cs/wiki/external/a2a-protocol.md`, `teams/remote-team-a2a.md`; Port·Agent Card·더미 1개는 있으나 Signed Agent Card와 다자 위임 후속 범위가 없다 |
| 9-C-1. A2A Remote Team 후보 판정 | 일부 | `final_project_cs/wiki/teams/catalog-verification.md`, `remote-team-a2a.md`; Catalog 선정 결론은 있으나 VOC·Return/Refund·Fraud 후보 비교표와 기각 사유가 빠졌다 |
| Agent Team Registry 확장 | 일부 | `architecture/pack-model.md`; `execution_type`은 있으나 `agent_card_url`·`a2a_endpoint`·`auth_scheme`을 포함한 전체 필드 표가 없다 |
| 9-D. Graph DB / GraphRAG 활용 계획 [A2A] | 반영 | `research/graphrag.md`, `decisions/D-002-graph-store-gate.md` |
| Port / Adapter 설계 | 일부 | `architecture/pack-model.md`, `decisions/D-002-graph-store-gate.md`; `neighbors`·`path`·`subgraph` Protocol 전문과 Adapter별 세부가 없다 |
| 8~9주차 비교 실험 | 일부 | `decisions/D-002-graph-store-gate.md`, `delivery/timeline.md`; 비교 계획은 있으나 근거 포함률·p95·인일·Projection lag의 4행 측정표가 없다 |
| Graph DB 판단 기준표 | 일부 | `decisions/D-002-graph-store-gate.md`; 정확도·비용·지연 게이트만 있고 관계 깊이·스키마·관계 위치·질의 빈도·시각화·팀 규모·운영 인력 7행 표가 없다 |
| 역할과 적용 단계 | 일부 | `research/graphrag.md`, `architecture/pack-model.md`; Vector Search·관계 조회·Context Broker의 3자 역할과 적용 순서가 축약됐다 |
| 9-E. 쓰기 권한을 여는 전제 조건: ActionProposal 할루시네이션 방어 | 반영 | `decisions/D-005-write-gate.md`, `final_project_cs/wiki/actions/evidence-check.md` |
| ActionProposal 근거 대조 규칙 | 반영 | `decisions/D-005-write-gate.md`, `final_project_cs/wiki/actions/evidence-check.md` |
| 거부 시 동작과 평가 연결 | 반영 | `decisions/D-005-write-gate.md`, `evaluation/metrics.md` |
| 10. 핵심 사용자 시나리오 [A2A] | 반영 | `product/scope.md`, `architecture/pack-model.md`, `final_project_cs/wiki/teams/index.md` |
| 11. 데이터 구조 초안 [A2A] | 반영 | `final_project_cs/wiki/data/schema/index.md`, `fields.md` |
| 12. 기술 스택 [A2A] | 반영 | `architecture/tech-stack.md` |
| 13. 리포지터리 스캐폴딩 [A2A+v5] | 누락 | `app/core`·`application`·`domain`·`infrastructure`·`modules`·`eval`·`scripts` 전체 트리가 없다 |
| 14. 구현 단계 계획 [A2A+v5] | 반영 | `delivery/timeline.md` |
| 15. 평가 계획 [v5 흡수] | 반영 | `evaluation/`, `final_project_cs/wiki/quality/eval-harness.md` |
| 비교군과 통제 | 반영 | `evaluation/protocol.md` |
| 골든셋 | 반영 | `evaluation/protocol.md`, `evaluation/golden-set.md` |
| 지표와 산식 | 반영 | `evaluation/metrics.md` |
| LLM-as-Judge | 반영 | `evaluation/judge.md` |
| 통계와 harness | 반영 | `evaluation/protocol.md`, `final_project_cs/wiki/quality/eval-harness.md` |
| 15-7. (v5 흡수) harness 디렉터리 구조와 실행 명령 | 반영 | `final_project_cs/wiki/quality/eval-harness.md`, `operations/run.md` |
| 15-8. 파인튜닝 경로와 증명 범위 | 반영 | `evaluation/finetuning.md`, `final_project_cs/wiki/decisions/D-CS-002-finetuned-model-not-adopted.md` |
| 15-8-A. 데이터 2트랙과 모듈별 배분 [v7.1] | 일부 | `evaluation/finetuning.md`; 6개 모듈의 소스 표는 있으나 golden 16·12·10·12·10 및 holdout 4건씩 배분 수치가 없다 |
| 15-9. REST surface와 Team 수의 확장 규칙 | 일부 | `delivery/dod.md`, `product/scope.md`; REST 5가 상한이 아니라는 결론은 있으나 endpoint 추가의 resource·scope·idempotency·audit·fixture 5조건이 없다 |
| 16. 팀 역할과 소유 경계 [A2A] | 반영 | `delivery/roles.md` |
| 17. 사용자 본인 역할 어필 문장 [A2A] | 누락 | 개인 발표용 역할 문장이 wiki에 없다 |
| 18. 예상 리스크 [A2A] | 반영 | `product/scope.md`, `delivery/timeline.md` |
| 18-A. 결정사항의 주의점 [A2A] | 반영 | `decisions/D-003-message-broker.md`, `D-002-graph-store-gate.md`, `delivery/timeline.md`, `final_project_cs/wiki/external/a2a-protocol.md` |
| 19. 케이스 생명주기 구현 명세 [v5 흡수] | 반영 | `final_project_cs/wiki/runtime/case-lifecycle.md` |
| 20. 동시성·정합성·Action 구현 명세 [v5 흡수] | 반영 | `final_project_cs/wiki/runtime/conflict-retry.md`, `actions/idempotency.md`, `actions/outbox.md` |
| 21. 통합 계약 전문 [v5+A2A] | 반영 | `final_project_cs/wiki/teams/team-contract/index.md`, `fields.md` |
| 22. PostgreSQL DDL 전문 [v5 흡수] | 반영 | `final_project_cs/wiki/data/schema/fields.md` |
| 23. Context Broker 구현 명세 [v5 흡수] | 반영 | `final_project_cs/wiki/context/context-broker.md`, `context-budget.md` |
| 24. 보안과 감사 [v5 흡수] | 반영 | `final_project_cs/wiki/external/auth-boundary.md`, `data/tenancy.md`, `actions/` |
| 25. 공식 부트캠프 일정에 따른 구현 계획 [v8] | 일부 | `delivery/timeline.md`; 주차·산출물·역할 표는 있으나 4W의 `run_case()` 트랜잭션 분리와 `case.created` outbox 작업이 빠졌다 |
| 26. 심사 대응 질문과 답변 [v5+A2A] | 반영 | `delivery/milestones/midterm-2026-09-15.md` |
| 27. 완료 기준 체크리스트(DoD) [v5 번호 보존 + 신규] | 반영 | `delivery/dod.md` |
| 28. 엑셀 입력용 요약 [v6 병합 시 유실 → v7 복원·갱신] | 일부 | `product/positioning.md`, `architecture/tech-stack.md`; 팀원 6명·주제·설명·기술·선정 이유를 한 행에 담은 제출표가 없다 |
| 셀이 길 때 쓰는 압축본 | 일부 | `quickstart.md`, `product/positioning.md`, `architecture/tech-stack.md`; 제출 셀용 압축 문구 그대로는 없다 |
| 범위 표기 원칙 | 반영 | `product/scope.md`, `product/positioning.md`, `delivery/milestones/` |
| v6 이전 표기에서 바로잡은 것 | 반영 | `architecture/tech-stack.md`, `product/positioning.md`, `architecture/pack-model.md` |
| 부록 A. v5 대비 계약 변경점과 코드 영향 | 일부 | `final_project_cs/wiki/teams/team-contract/`, `team-boundary.md`, `runtime/`; 2026-08-14 실측 경로와 8행 코드 영향·검증 표가 완전하지 않다 |
| 실측에서 드러난 선행 정리 항목 | 일부 | `final_project_cs/wiki/`에 평면 구조는 있으나 MessageBrokerPort 중복 정의, 빈 패키지 4곳, 정리 순서가 없다 |
| 참고 출처 | 일부 | `research/a2a-adoption.md`, `research/graphrag.md`; A2A 플랫폼별 공식 URL은 오히려 미확보로 명시돼 있다 |

**빠진 것 요약:** 권장 디렉터리 구조·리포지터리 스캐폴딩·개인 역할 문장·외부 AI 예시가 누락됐고, 버전 변경표·VOC 후속 결함·A2A 후보 기각표·Graph 판단표·평가 데이터 배분·제출표가 일부만 반영됐다.

===== DOC: 07_모듈화_구조.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 왜 HTML 을 쓰나 | 누락 | HTML이 더 상세한 유일 출처이며 md와 충돌 시 md가 우선한다는 출처 판정이 없다 |
| 1. 모듈형 Basement — 4개 축 (§6) | 일부 | `wiki/architecture/core-design.md`, `system-context.md`, `core-vs-team.md`; Core Runtime·Agent Interoperability·Context & Knowledge·Agent Team Modules의 4축 표가 없다 |
| 2. 목표 디렉터리 구조 (§5 그대로) | 누락 | `presentation`·`core/case_runtime`·`core/access_action`·`infrastructure`·`modules` 전체 목표 트리가 없다 |
| 3. 현재 구조 → 목표 구조 대응 | 누락 | 현재 파일 13개를 목표 디렉터리에 대응시킨 표가 없다 |
| 4. ★신설해야 할 것 (현재 코드에 없음 — `git grep` 실측) | 일부 | `wiki/architecture/pack-model.md`, `decisions/D-002-graph-store-gate.md`, `final_project_cs/wiki/external/a2a-protocol.md`; 7개 컴포넌트의 당시 미구현 판정과 위치 표는 없다 |
| 5. 이동 규칙 — ★기존 동작을 깨지 않는다 | 일부 | `final_project_cs/wiki/runtime/`, `quality/invariants.md`; 113 passed 기준선, 기존 import re-export, 계층별 이동 순서가 빠졌다 |
| 6. 검증 | 일부 | `final_project_cs/wiki/operations/run.md`, `quality/evidence.md`; 원문의 두 명령과 “구조 이동으로 DoD가 바뀌면 동작 변경”이라는 판정이 한곳에 없다 |

**빠진 것 요약:** HTML을 기준으로 삼은 이유, 목표 디렉터리 전체 트리, 현재→목표 13행 대응표가 누락됐고 이동 절차와 당시 미구현 표는 일부만 남았다.

===== DOC: 02_DB_스키마.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 실행 환경 (실측 2026-08-12) | 반영 | `final_project_cs/wiki/data/schema/fields.md`, `operations/local-setup.md` |
| 1. DDL 전문 (v5 §8) | 반영 | `final_project_cs/wiki/data/schema/fields.md` |
| 2. ★빠뜨리면 시스템이 무너지는 제약 3개 | 반영 | `final_project_cs/wiki/data/schema/index.md`, `runtime/shared-state.md`, `actions/idempotency.md`, `actions/outbox.md` |
| 3. 쓰기 규칙 (전 스트림 필수) | 반영 | `final_project_cs/wiki/data/schema/index.md`, `runtime/case-lifecycle.md`, `data/tenancy.md` |
| optimistic concurrency (v5 §6-1) — 이 문 그대로 | 반영 | `final_project_cs/wiki/data/schema/fields.md` |
| outbox worker claim (v5 §6-4) | 반영 | `final_project_cs/wiki/data/schema/fields.md` |
| RAG 검색 (v5 §9-2) | 반영 | `final_project_cs/wiki/data/schema/fields.md`, `context/rag-retrieval.md` |
| 4. seed 데이터 (`scripts/seed.py`, S-DB 소유) | 반영 | `final_project_cs/wiki/data/schema/fields.md` |
| ★테스트는 seed 데이터를 오염시키지 않는다 | 일부 | `final_project_cs/wiki/data/schema/fields.md`; 전용 tenant·teardown 규칙은 있으나 오염으로 `tenants`가 19행이 된 실측이 없다 |
| 5. 검증 (DoD 근거로 `docs/evidence/` 에 남긴다) | 일부 | `final_project_cs/wiki/quality/evidence.md`, `operations/run.md`; `\dt` 14개+mock, `\di` 인덱스 3종+UNIQUE, `\dx` 2 extension의 검증 명령·합격선이 없다 |

**빠진 것 요약:** 스키마·제약·SQL·seed 계약은 반영됐고, seed 오염 19행 사례와 DB 객체 수를 세는 검증 명령만 일부 빠졌다.

===== DOC: _컴포저_UI배포구조_점검_2026-08-29.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 결론 먼저 | 일부 | `wiki/decisions/D-006-composer-ownership.md`, `final_project_cs/wiki/decisions/D-CS-003-composer-scope.md`; 당시 UI 패키지·CRUD·독립 배포 3건이 모두 미완이었다는 대조표가 없다 |
| 1. 먼저 — UI 작업을 이 세션에서 하는 게 맞나 | 일부 | `wiki/decisions/D-006-composer-ownership.md`, `architecture/repository-map.md`; 별도 저장소 규칙과 “sample은 패키지를 만들고 UI 화면은 UI 세션이 만든다”는 세션 경계가 완전하지 않다 |
| 2. 무엇이 빠져 있나 — UI 가 import 할 패키지 | 일부 | `wiki/decisions/D-006-composer-ownership.md`; 패키지 소유 결정은 있으나 당시 실제 패키지가 없었다는 판정이 없다 |
| 2.1 결정된 설계 | 일부 | `wiki/decisions/D-006-composer-ownership.md`; 3개 패키지 구조의 취지는 있으나 `acop_composer_ui`를 별도 세 번째 배포 단위로 둔 원문 구조와 다르다 |
| 2.2 실제 상태 | 누락 | `acop_composer`의 서버 파일 4개와 HTTP 클라이언트 0개라는 실측이 없다 |
| 3. 그 결과 — UI 는 클라이언트를 손으로 따로 만들어 쓰고 있다 | 누락 | `console/composer.py` 167줄과 네 함수, 중복 구현이지만 즉시 고장은 아니라는 판정이 없다 |
| 4. ★인스턴스 CRUD 는 종단으로 성립하지 않는다 | 일부 | `final_project_cs/wiki/decisions/D-CS-003-composer-scope.md`; `/catalog` 필요성과 토글 한계는 있으나 UI grep 0건·화면 미연결 실측이 없다 |
| 5. pip 제공이 지금 구조로는 안 된다 | 누락 | 단일 `final-project-sample` 배포판이 `app`·`acop_basement`까지 포함한다는 `pyproject.toml` 판정이 없다 |
| 6. 지금 상태가 "틀린" 것인가 | 일부 | `wiki/decisions/D-006-composer-ownership.md`, `final_project_cs/wiki/decisions/D-CS-003-composer-scope.md`; 정상·미완·미연결·위험의 4행 판정표가 없다 |
| 7. 권고 — 다음 순서 | 일부 | `wiki/decisions/D-006-composer-ownership.md`, `delivery/open-items.md`; 권고 순서와 1~6번 작업 전체가 없다 |
| 7-1. sample 에서 할 일 (여기서 한다) | 일부 | `wiki/decisions/D-006-composer-ownership.md`; UI 클라이언트 경계는 있으나 독립 배포 메타데이터와 wheel 금지파일 검사가 없다 |
| 7-2. ui 세션에서 할 일 (거기서 한다) | 일부 | `final_project_cs/wiki/decisions/D-CS-003-composer-scope.md`; JSON Schema 폼·desired/effective 구분은 있으나 자체 클라이언트 교체와 화면 작업 순서가 없다 |
| 7-3. 하지 말 것 | 일부 | `wiki/decisions/D-006-composer-ownership.md`, `D-CS-003-composer-scope.md`; 서버 패키지 import·UI 판정 금지는 있으나 배포 분리 없이 pip 제공이라 쓰지 말라는 항목이 없다 |
| 8. 확인하지 못한 것 | 일부 | `wiki/delivery/open-items.md`, `decisions/D-011-composer-v3-gap.md`; 패키지 이름·cs 계약 문제는 있으나 HTTP 종단 미시험과 introspection 버전 불일치 재확인 항목이 없다 |
| 9. 조치 결과 (2026-08-29, 같은 날 후속) | 일부 | `wiki/decisions/D-007-central-config-store.md`; 구현 완료라는 상위 상태만 있고 §9-1~§9-6의 증거가 없다 |
| 9-1. 만든 것 (`final_project_sample`) | 누락 | 독립 패키지 경로, 의존성 0개, 경계 테스트 7건, E2E 7건, wheel 금지파일 0개가 없다 |
| 9-2. 바꾼 것 (`final_project_ui`) | 누락 | 자체 전송 제거, 얇은 어댑터 전환, `read_catalog`·`submit_change`, 의존성 추가 결과가 없다 |
| 9-3. ★검증 중 실제로 잡은 결함 2건 | 누락 | 금지된 `aud`로 인한 422와 `/composer/auth/token` 경로 중복 결함, 안내 문구 회귀가 없다 |
| 9-4. 검증 | 누락 | sample 401 passed·UI 119 passed·기존 composer 21 passed·wheel 금지파일 0개가 없다 |
| 9-6. 화면 연결 (같은 날 후속 2) | 누락 | `_catalog_card`, 인스턴스 생성·삭제, dry-run, `pending_restart`, UI 127 passed가 없다 |
| 9-7. 두 운영 방식 선택 (2026-08-30) | 일부 | `wiki/decisions/D-007-central-config-store.md`; direct/central 선택은 있으나 `X-Deployment-Id`, 화면의 현재 방식 표시, sample 443·UI 131 passed가 없다 |
| 9-5. 남은 것 | 일부 | `wiki/delivery/open-items.md`; 패키지 이름·cs 통합은 있으나 사설 index/릴리스 절차 미결정이 없다 |

**빠진 것 요약:** 허용된 두 wiki에는 결정의 일부만 있고, 패키지 생성·UI 교체·결함 2건·검증 수치·화면 연결 등 실제 조치 증거는 통째로 없다.

===== DOC: A-COP_스프린트_에픽_설계.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 한 줄 요약 | 반영 | `wiki/delivery/ticket-structure.md`, `delivery/timeline.md` |
| 결론 — 왜 이렇게 끊었나 | 일부 | `delivery/ticket-structure.md`, `delivery/timeline.md`; 4개 스프린트 선택은 있으나 19·13·16·12일 표와 S2/S3 날짜 교정 이유가 없다 |
| 안 A(부트캠프 주차 그대로 9개)를 안 고른 이유 | 일부 | `delivery/ticket-structure.md`; 기각 사실만 있고 4일~11일 변동·10/21 중복·번다운 왜곡 이유가 없다 |
| 안 C(수행단계별 6개)를 안 고른 이유 | 일부 | `delivery/ticket-structure.md`; 기각 사실만 있고 단계 길이 편차와 병행 작업을 표현하지 못한다는 이유가 없다 |
| 지금 이미 된 것 | 일부 | `delivery/timeline.md`, `delivery/dod.md`; 완료 항목은 있으나 당시 DoD 26 통과·3 부분·1 무판정과 미커밋 상태가 없다 |
| 에픽 13개 | 일부 | `delivery/ticket-structure.md`; E01~E13 및 E14 분리는 언급되지만 담당·목표 스프린트·산출물·완료 판정 전체 표가 없다 |
| 의존성 | 누락 | E01~E03→E05~E09, E02→E07~E09, E06→E09, E10→E11 등 6행 의존성 표가 없다 |
| 확인하지 못한 것 | 반영 | `delivery/ticket-structure.md`; TEAM4/6팀 문제도 현재 판정과 함께 남아 있다 |
| TeamFlow 등록 상태 | 일부 | `delivery/ticket-structure.md`; 운영 상태의 일부만 있고 날짜별 권한·등록 이력이 없다 |
| 최초 시도 — 권한을 켜기 전 | 일부 | `delivery/ticket-structure.md`; 토큰 제약은 있으나 401/403별 요청표와 `projectId`·`id` 쿼리스트링 규칙이 없다 |
| 2026-08-28 진행 결과 | 일부 | `delivery/ticket-structure.md`; 토큰으로 생성만 된다는 요약은 있으나 에픽 13건 `ST4F-3~15`, CRUD 실측, `ST4F-46` 삭제 검증이 없다 |
| 2026-08-29 스프린트 권한 상태 | 누락 | 401→403 변화, 관리자 설정, `{name,start,end,goal}` payload가 없다 |
| 2026-08-29 등록 완료 | 일부 | `delivery/ticket-structure.md`, `delivery/timeline.md`; 4스프린트·13에픽은 있으나 스프린트별 ST4F 배정표와 PUT 전체교체 함정이 없다 |
| 이슈 키가 3번부터 시작하는 이유 (다시 만들지 않는다) | 누락 | 삭제한 1·2번, `ST4F-47`, 새 프로젝트 대가, “그대로 둔다” 결정과 이유가 없다 |
| 정리한 시험 흔적 | 누락 | 삭제한 `ST4F-16·17·22·24`, 보존한 `ST4F-42`, TeamFlow 필드·인코딩 함정이 없다 |
| 2026-08-30 에픽 시작일과 상태 반영 | 일부 | `delivery/ticket-structure.md`에 배정 불일치만 열린 항목으로 남았고 13건의 start·due·status 표와 두 해결안이 없다 |
| 담당자 (2026-08-30 확정) | 누락 | 사람 6명·TeamFlow 계정·모듈별 담당·하위 작업 `ST4F-62~65` 표가 없다 |
| 티켓 작성 규칙 (2026-08-30) | 일부 | `delivery/ticket-structure.md`; 처음 보는 사람 기준과 용어 풀이는 있으나 제목·완료 판정·참고 파일·문장 규칙이 빠졌다 |
| 계층과 크기 (2026-08-31) | 일부 | `delivery/ticket-structure.md`; 3층과 날짜 원칙은 있으나 2~4주·1~3점·0.1~0.5점 표, 시작 전 생성, `S` 중복 의미 등의 규칙이 없다 |

**빠진 것 요약:** 대안 A·C의 구체적 기각 이유와 TeamFlow의 이슈 키·권한·담당자·시험 흔적이 크게 빠졌고, 에픽 표와 일정 변경도 요약만 남았다.

===== DOC: 2026-08-31_1154_테스트_사각지대_회귀테스트_설계.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 왜 하나 | 누락 | `final_project_cs/wiki/quality/blind-spots.md`는 현재 49/48/0 결과만 담고 원문의 39개·21검출·18생존·424통과 측정을 보존하지 않는다 |
| 1. 범위 | 누락 | 테스트만 추가하고 `app/`은 바꾸지 않으며 실제 결함 판정은 별도 리포트로 넘긴다는 계획 범위가 없다 |
| 2. 대상 18건과 배치 | 누락 | INV 18개와 `tests/security`·`unit/core`·`contract`·`unit/voc`·`unit/teams`·`integration` 배치 표가 없다 |
| 3. 완료 기준 | 일부 | `quality/blind-spots.md`에 결함을 심어 테스트가 우는지 확인하는 원칙은 있으나 기준 코드 통과·dojo 재확인·전체 회귀·evidence/report 기록의 4조건이 없다 |
| 4. 이 계획에서 하지 않는 것 | 누락 | `app/` 수정 금지와 INV-STATE-001 원인 규명 제외가 없다 |
| 5. 범위 변경 — 2026-09-01 | 누락 | `transition.py`의 version 대조 위에 주석 5줄만 추가하기로 한 결정과 이유가 없다 |
| 6. 2차 — 2026-09-01 | 일부 | `quality/blind-spots.md`에 INV-CLASS-002 후속 사실만 있으나 INV-TEAM-004·INV-STATE-006·INV-STATE-007을 포함한 4행 계획이 없다 |
| 6-1. INV-STATE-007 은 행동 테스트로 잡을 수 없다 | 누락 | Python 가드가 SQL 결함을 가리고 동시성 시험이 5회 중 1회 실패해 UPDATE문의 version 조건을 구조적으로 단언한다는 결론이 없다 |

**빠진 것 요약:** 최초 18건 배치표, 테스트 전용 범위, 주석 변경 결정, SQL version 조건의 구조적 단언이 거의 전부 누락됐다.

===== DOC: _주말작업_요약_2026-08-29~30.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 한눈에 | 누락 | 커밋 38개·파일 373개·+22,180/-721 및 저장소별 집계가 없다 |
| 무엇을 했나 | 일부 | 하위 작업별 wiki는 있으나 주말 작업 전체를 한데 묶은 요약이 없다 |
| 1. 중앙 설정 저장소 (주말 최대 작업) | 일부 | `wiki/decisions/D-007-central-config-store.md`; 중앙 DB·direct/central 결정과 이유는 있으나 `ConfigStore`·`AuditStore`·마이그레이션 2개·통합 테스트 5개가 없다 |
| 2. Composer 카탈로그와 인스턴스 관리 | 일부 | `final_project_cs/wiki/decisions/D-CS-003-composer-scope.md`, `D-CS-004-composer-boundary.md`; 카탈로그·인스턴스 개념은 있으나 sample·UI·공용 클라이언트의 실제 위치와 이식 결과가 없다 |
| 3. DoD-28 파인튜닝 | 일부 | `wiki/evaluation/finetuning.md`, `final_project_cs/wiki/decisions/D-CS-002-finetuned-model-not-adopted.md`; 1,500건·376스텝·22건·0%는 있으나 holdout Proposed 16.7%, 손실 1.65→1.48, 정확도 0.67→0.71, 당시 16건 상한이 없다 |
| 4. 산출물 문서 | 누락 | 화면설계서·시스템 구성도·19장 중간발표 자료의 생성 방식과 주말 작업표가 없다 |
| 5. 일정 관리 | 일부 | `wiki/delivery/timeline.md`, `ticket-structure.md`; 4스프린트·13에픽 결정은 있으나 TeamFlow 권한 변화와 이슈 키 유지 이유가 없다 |
| 찾아서 고친 결함 | 일부 | `evaluation/metrics.md`, `evaluation/finetuning.md`, `final_project_cs/wiki/teams/response-review.md`; 평가 채점기와 프롬프트 결함은 있으나 모듈 토글 3경로와 도표 잘림을 포함한 4건 표가 없다 |
| 숨기지 않고 적는 것 | 반영 | 이어지는 두 결론이 `evaluation/finetuning.md`, `evaluation/metrics.md`에 반영돼 있다 |
| 파인튜닝은 실패가 아니라 안 쓰기로 판정한 것이다 | 반영 | `final_project_cs/wiki/decisions/D-CS-002-finetuned-model-not-adopted.md` |
| 평가 수치는 아직 믿을 수 없다 | 반영 | `wiki/evaluation/metrics.md`, `delivery/release-gate.md` |
| 남은 일 | 일부 | `wiki/delivery/open-items.md`; 네이버 누락·VOC·평가·파인튜닝 항목 일부는 있으나 택배 제출본 병합과 VOC 924MB 등 원래 5행이 온전히 남지 않았다 |
| 근거가 되는 커밋 목록 | 누락 | 날짜별 커밋 제목 목록의 색인이 없다 |
| 8월 29일 토요일 | 누락 | 화면·Composer·중앙 저장소·harness·VOC의 9개 커밋 요약이 없다 |
| 8월 30일 일요일 | 누락 | 파인튜닝·중앙 설정·자료·토글의 9개 커밋 요약이 없다 |

**빠진 것 요약:** 주말 커밋 집계와 날짜별 커밋 목록, 산출물 문서 작업은 누락됐고 중앙 설정·Composer·파인튜닝·결함 표는 결론만 일부 남았다.

===== DOC: release_checklist.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 지금 상태 요약 | 일부 | `wiki/delivery/release-gate.md`, `delivery/dod.md`; RC 아님은 있으나 원문의 evidence 18/18·통과 16·부분 2·M1~M3 도달 수치가 없다 |
| 1. 빌드·테스트 | 일부 | `wiki/delivery/release-gate.md`, `final_project_cs/wiki/quality/evidence.md`; 실패·skip·flaky 0 기준은 있으나 172 passed·4회 연속·시계 의존 flaky 사례가 없다 |
| 2. 안전 (되돌릴 수 없는 것) | 반영 | `final_project_cs/wiki/runtime/case-lifecycle.md`, `actions/`, `external/mcp-tools.md`, `operations/unknown-state.md` |
| 3. 데이터·격리 | 반영 | `final_project_cs/wiki/data/tenancy.md`, `external/auth-boundary.md`, `quality/invariants.md` |
| 4. 배포 산출물 | 일부 | `wiki/delivery/release-gate.md`; `publish_public` 검사는 있으나 공개 183개·스크럽 21개·identity·워킹 트리 복구 수치와 결과가 없다 |
| 4-1. 배포 전 선언 변경 | 반영 | `final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md` |
| 5. ★RC 를 막고 있는 것 | 반영 | `wiki/delivery/release-gate.md` |
| 5-1. judge agreement 미측정 (DoD-15) | 반영 | `wiki/delivery/release-gate.md`, `evaluation/judge.md` |
| 5-2. 평가 결과의 일반화 한계 (DoD-15 · v5 §15-8) | 반영 | `wiki/delivery/release-gate.md`, `evaluation/protocol.md` |
| 5-3. 미해결 (차단은 아님) | 일부 | `wiki/delivery/release-gate.md`에 같은 4항목이 있으나 모두 미해결로 적혀 있어 원문의 해소 결과·원인·14개 테스트·24장 캡처·E2E 5건이 빠지고 상태도 낡았다 |
| 6. 환경 (재현하려는 사람에게) | 반영 | `final_project_cs/wiki/operations/local-setup.md`, `operations/troubleshooting.md`, `wiki/architecture/tech-stack.md` |
| 7. 판정 | 반영 | `wiki/delivery/release-gate.md` |

**빠진 것 요약:** RC 차단 판단과 안전·격리·환경은 반영됐지만 빌드·배포의 과거 수치가 빠졌고, 비차단 4항목은 wiki가 해소 전 상태로 남아 있다.

===== 전체 =====

| 원본 | 절 수 | 반영 | 일부 | 누락 |
|---|---:|---:|---:|---:|
| `A-COP_구현계획서_v8.md` | 99 | 70 | 25 | 4 |
| `07_모듈화_구조.md` | 7 | 0 | 4 | 3 |
| `02_DB_스키마.md` | 10 | 8 | 2 | 0 |
| `_컴포저_UI배포구조_점검_2026-08-29.md` | 22 | 0 | 14 | 8 |
| `A-COP_스프린트_에픽_설계.md` | 19 | 2 | 12 | 5 |
| `2026-08-31_1154_테스트_사각지대_회귀테스트_설계.md` | 8 | 0 | 2 | 6 |
| `_주말작업_요약_2026-08-29~30.md` | 15 | 3 | 7 | 5 |
| `release_checklist.md` | 12 | 8 | 4 | 0 |
| **합계** | **192** | **91** | **70** | **31** |