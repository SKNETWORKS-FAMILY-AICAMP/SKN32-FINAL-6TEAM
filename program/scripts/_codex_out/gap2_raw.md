## `final_project_cs/docs/handoff/01_계약_Pydantic.md`

| 절 제목 | 판정 | wiki 반영 위치·누락 내용 |
|---|---|---|
| 0. 전 모델 공통 규칙 | 일부 | `final_project_cs/wiki/teams/team-contract/index.md`, `teams/team-registry.md` — `extra='forbid'`와 major 호환은 있으나 Enum 외 문자열 거부와 “optional field 추가만 호환” 조건이 불완전하다. |
| 1. Enum | 반영 | `final_project_cs/wiki/teams/team-contract/index.md`, `runtime/case-lifecycle.md` |
| 2. Evidence — 모든 주장에 출처를 붙인다 | 일부 | `final_project_cs/wiki/actions/evidence-check.md`, `teams/team-contract/index.md` — 근거 대조 원칙은 있으나 `Evidence`의 7개 필드·confidence 범위·5종 `source_type`과 `policy` source ID 형식이 없다. |
| 3. ContextPack | 반영 | `final_project_cs/wiki/teams/team-contract/index.md`, `context/context-broker.md`, `context/context-budget.md` |
| 4. TeamTask | 일부 | `final_project_cs/wiki/teams/team-contract/index.md`, `runtime/conflict-retry.md`, `teams/team-registry.md` — 필드와 `case_version` 의미는 있으나 `resume_node` 허용값 3종이 없다. |
| 5. ActionProposal — Team 은 제안까지만 한다 | 일부 | `final_project_cs/wiki/actions/action-proposal.md`, `actions/idempotency.md`, `teams/team-boundary.md` — 필드·제안 전용 경계·키 산식은 있으나 “서버 재계산값이 최종”이 명확하지 않고 wiki는 Team이 생성하고 Core가 검사한다고 적는다. |
| 6. TeamResult | 일부 | `final_project_cs/wiki/teams/team-contract/index.md`, `runtime/case-lifecycle.md` — 필드는 있으나 일관성 표 5행 중 `respond→answer`, `escalate→failure_code 또는 warnings`가 빠졌다. `answer`가 있는데 evidence가 비면 거부한다는 규칙도 없다. |
| 7. TeamManifest | 일부 | `final_project_cs/wiki/teams/team-contract/index.md`, `teams/team-registry.md`, 개별 `teams/*.md` — 일부 manifest 필드와 major 호환은 있으나 전체 스키마, `implementation_revision`, `default_capability`, `select_capability()` 우선 선택 규칙이 없다. |
| 8. TeamModule Protocol — Core 가 Team 을 보는 유일한 창 | 반영 | `final_project_cs/wiki/teams/team-contract/index.md`, `teams/team-boundary.md`, `teams/team-registry.md` |
| 9. Port (Phase 2 교체 지점) | 일부 | `final_project_cs/wiki/runtime/message-broker.md`, `actions/idempotency.md`, `wiki/architecture/pack-model.md` — 교체 개념과 outbox/Redis 후보는 있으나 `MessageBrokerPort.publish/ack` 시그니처가 없고 wiki는 `MessageBusPort`로 기술한다. |
| 10. 예외 | 일부 | `final_project_cs/wiki/actions/tool-gateway.md`, `runtime/conflict-retry.md`, `external/auth-boundary.md` — `StateConflict`, `ToolNotAllowed`, `GuardrailExceeded`, `ScopeDenied`는 있으나 `ContractViolation`과 5종 전체 목록이 없다. |

**빠진 것 요약:** Evidence 전체 계약, TeamResult 검증 2행, `default_capability`·`select_capability`, Port 시그니처와 `ContractViolation`이 불완전하다.

## `final_project_cs/docs/handoff/02_DB_스키마.md`

| 절 제목 | 판정 | wiki 반영 위치·누락 내용 |
|---|---|---|
| 0. 실행 환경 (실측 2026-08-12) | 일부 | `final_project_cs/wiki/operations/local-setup.md`, `data/migrations.md` — PostgreSQL 16.14·포트·conda·Docker 없음은 있으나 extension 세부 버전, 기존 DB 보호 경고, 최초 DB 생성 명령이 없다. |
| 1. DDL 전문 (v5 §8) | 일부 | `final_project_cs/wiki/data/schema/index.md`, `data/migrations.md` — 14개 Core 테이블과 핵심 관계·제약은 있으나 DDL 전문의 컬럼·타입·default·FK·인덱스 정의는 옮기지 않았다. |
| 2. ★빠뜨리면 시스템이 무너지는 제약 3개 | 반영 | `final_project_cs/wiki/data/schema/index.md`, `data/migrations.md`, `actions/idempotency.md` |
| 3. 쓰기 규칙 (전 스트림 필수) | 반영 | `final_project_cs/wiki/data/schema/index.md`, `data/tenancy.md`, `runtime/case-lifecycle.md` |
| optimistic concurrency (v5 §6-1) — 이 문 그대로 | 일부 | `final_project_cs/wiki/runtime/conflict-retry.md` — CAS SQL은 있으나 `owner_team_id` 갱신과 충돌 후 최대 2회 재계산 규칙이 없다. |
| outbox worker claim (v5 §6-4) | 일부 | `final_project_cs/wiki/runtime/conflict-retry.md`, `actions/outbox.md` — `FOR UPDATE SKIP LOCKED`와 timeout 원칙은 있으나 pending/available 조건, 정렬, `LIMIT :batch`가 포함된 전체 SQL이 없다. |
| RAG 검색 (v5 §9-2) | 일부 | `final_project_cs/wiki/context/rag-retrieval.md`, `data/tenancy.md` — tenant·scope·top-k 8은 있으나 cosine score 계산, JOIN, 정렬을 포함한 SQL이 없다. |
| 4. seed 데이터 (`scripts/seed.py`, S-DB 소유) | 누락 | customer 10·구독 10·결제 30+·entitlement 10·incident 3과 두 결함 시나리오로 구성된 seed 표가 wiki에 없다. |
| ★테스트는 seed 데이터를 오염시키지 않는다 | 일부 | `final_project_cs/wiki/data/tenancy.md` — 테스트 후 `tenants=1`을 세는 원칙은 있으나 전용 tenant·fixture teardown과 오염 당시 19행 사례가 없다. |
| 5. 검증 (DoD 근거로 `docs/evidence/` 에 남긴다) | 누락 | `\dt`·`\di`·`\dx` 명령과 테이블·인덱스·extension 기대 건수가 wiki에 없다. |

**빠진 것 요약:** seed 6행 표와 DB 검증 명령이 통째로 없고, DDL·CAS·outbox·RAG SQL은 요약만 남았다.

## `final_project_cs/docs/handoff/03_REST_MCP_인터페이스.md`

| 절 제목 | 판정 | wiki 반영 위치·누락 내용 |
|---|---|---|
| 0. 경계 원칙 — 이것이 차별화의 핵심이자 위험 지점 | 반영 | `final_project_cs/wiki/external/rest-api.md`, `external/mcp-tools.md`, `actions/index.md` |
| 1. REST 엔드포인트 5개 | 일부 | `final_project_cs/wiki/external/rest-api.md` — 5개 경로는 있으나 원본의 scope 열이 빠졌고, wiki는 “5개가 상한이 아니다”라고 반대로 적는다. |
| 1-0. ★"5개"가 세는 것은 `/v1/*` 뿐이다 (2026-08-12 명확화) | 일부 | `final_project_cs/wiki/external/rest-api.md`, `wiki/delivery/dod.md` — `/health` 제외는 있으나 `/ui/*`·FastAPI 기본 경로 구분과 “6번째 `/v1` 경로는 위반”이 없고, 오히려 추가 endpoint를 허용한다. |
| 1-1. `POST /v1/cases` | 일부 | `final_project_cs/wiki/external/rest-api.md`, `actions/idempotency.md` — 인라인 분류와 중복 방지는 있으나 요청·201 응답 스키마, channel 4종, 재요청 시 기존 결과 반환 규칙이 없다. |
| 1-2. `GET /v1/cases` | 일부 | `final_project_cs/wiki/external/rest-api.md`, `data/tenancy.md` — 소유권 격리는 있으나 필수 `customer_id`, `status`, 기본 20·최대 100, `cursor`가 없다. |
| 1-3. `GET /v1/cases/{case_id}` | 일부 | `final_project_cs/wiki/external/rest-api.md`, `external/auth-boundary.md`, `teams/team-contract/index.md` — masked·evidence 원칙은 있으나 상세 응답의 `pending_actions`·`evidence` 구조와 예시가 없다. |
| 1-4. `POST /v1/cases/{case_id}/messages` | 일부 | `final_project_cs/wiki/runtime/case-lifecycle.md`, `external/rest-api.md` — 추가 메시지와 resume 흐름은 있으나 resume token hash 저장, 24시간 TTL, 일회성, event idempotency 규칙이 없다. |
| 1-5. `POST /v1/cases/{case_id}/actions/{action_id}/approve` | 일부 | `final_project_cs/wiki/actions/approval.md`, `external/auth-boundary.md`, `actions/idempotency.md` — scope·감사 hash·10회 중복 방지는 있으나 요청 필드와 `approved\|rejected` 계약이 없다. |
| 2. 오류 응답 규약 | 일부 | `final_project_cs/wiki/data/tenancy.md`, `runtime/conflict-retry.md`, `operations/troubleshooting.md` — 남의 Case 404와 충돌 의미는 있으나 HTTP 400·401·403·404·409·422·429 전체 표와 error code, 내부 정보 비노출 규칙이 없다. |
| 3. 인증 · scope | 일부 | `final_project_cs/wiki/external/auth-boundary.md`, `wiki/delivery/dod.md` — API key·scope·unauthorized matrix는 있으나 Bearer header, OAuth2/OIDC Phase 2 판정이 없고 scope 수도 원본 6종에서 wiki 10종으로 달라졌다. |
| 4. MCP read-only 3 tool | 반영 | `final_project_cs/wiki/external/mcp-tools.md`, `actions/tool-gateway.md` |
| 5. OpenAPI | 일부 | `wiki/delivery/dod.md`, `wiki/architecture/tech-stack.md` — OpenAPI 검증 필요성만 있고 `/openapi.json`과 5개 endpoint 일치 및 `test_openapi_matches_handoff.py`가 없다. |
| 6. 검증 (DoD 근거) | 일부 | `final_project_cs/wiki/operations/run.md`, `quality/evidence.md`, `wiki/delivery/dod.md` — security 실행 명령은 있으나 API 통합·MCP scope의 정확한 두 명령과 DoD 연결이 없다. |

**빠진 것 요약:** 경로 이름은 남았지만 REST 요청·응답·오류 계약 대부분이 빠졌고, `/v1` 5개 상한은 wiki에서 정반대로 바뀌었다.

## `final_project_cs/docs/handoff/08_모듈_컴포넌트_목록.md`

| 절 제목 | 판정 | wiki 반영 위치·누락 내용 |
|---|---|---|
| 0. 용어를 먼저 나눈다 | 반영 | `final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md`, `wiki/architecture/pack-model.md` |
| 1. 컴포넌트 (선택 불가 — 빼면 시스템이 아니다) | 일부 | `wiki/architecture/core-design.md`, `final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md` — 고정 Core 개념은 있으나 원본의 컴포넌트 9종·위치·제거 불가 이유 표는 없고 D-CS-004도 목록을 `[미확보]`로 표시한다. |
| 2. 모듈 (선택 가능 — 켜고 끌 수 있다) | 일부 | `final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md`, `wiki/architecture/pack-model.md` — 주요 모듈은 있으나 위치·제거 표면이 빠졌고 폐기된 `composer_ui`를 여전히 모듈로 세며 VOC 영향도 다르게 적는다. |
| ★2026-08-30 — 이 조항이 세 곳에서 안 지켜지고 있었다 | 누락 | MCP·VOC에 게이트가 없었던 결함, Graph 화면의 조립 경계 우회, 각각의 수정 결과와 `test_module_toggles.py`가 wiki에 없다. |
| ~~★`voc` 는 이 제품에서 끌 수 없다~~ — ★정정 (2026-09-01) | 일부 | `wiki/governance/drift-case-voc.md`, `delivery/roles.md`, `product/scope.md` — 오독 원인과 분류 책임 분리는 있으나 `voc:false`가 판단층·화면만 끈다는 결론, 집계 배치 게이트 제거, 현재 소유/게이트 표와 계약 테스트가 불완전하다. D-CS-004에는 반대 내용이 남아 있다. |
| 3. Port — 구현을 갈아 끼우는 지점 | 일부 | `wiki/architecture/pack-model.md`, `final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md` — Team executor·broker·graph 3종은 있으나 원본의 정책 검색·LLM·분류기까지 포함한 6행 표가 없다. |
| 4. 인스턴스 — 개수가 가변인 것 | 일부 | `wiki/architecture/pack-model.md`, `final_project_cs/wiki/teams/team-registry.md` — Team 수가 가변이고 Registry로 추가한다는 원칙은 있으나 원본의 현재 2개 및 “가변인 것은 이것뿐”이라는 결론은 없다. |
| 5. ★해결됨 — 구성기가 선언을 읽어 조립한다 | 일부 | `final_project_cs/wiki/teams/team-registry.md`, `decisions/D-CS-003-composer-scope.md` — YAML과 composition root가 조립한다는 내용은 있으나 `load_project_config()`·`importlib`, 하드코딩 import 해소 및 실제 배포 반영 결론이 없다. |
| 6. 구성 선언 — 실제 `config/project.yaml` (2026-08-17 기준, 더 이상 권고안이 아니다) | 일부 | `final_project_cs/wiki/decisions/D-CS-004-composer-boundary.md`, `teams/team-registry.md` — 모듈·Port 이름은 있으나 enabled 값, Port 선택값, 두 Team의 `implementation_ref`를 담은 YAML 전문이 없다. |
| 빌드 시 실패시켜야 할 것 (검증기) | 일부 | `final_project_cs/wiki/teams/team-registry.md`, `decisions/D-CS-004-composer-boundary.md` — 중복 `team_id`와 잘못된 `implementation_ref` 거부는 있으나 enabled 구현 부재, capability 중복, 꺼진 모듈 호출 경로, `active:false` 운용 규칙이 없다. |

**빠진 것 요약:** 9개 컴포넌트 표와 모듈 토글 결함 3건이 없고, Composer·VOC 관련 wiki 내용은 원본 정정과 충돌한다.

## `final_project_cs/CLAUDE.md`

| 절 제목 | 판정 | wiki 반영 위치·누락 내용 |
|---|---|---|
| 응답 언어 | 누락 | 사용자 언어에 맞춰 응답한다는 규칙이 없다. `wiki/governance/document-standard.md`의 한국어 문서 규칙은 다른 내용이다. |
| 작업 시작 진입 규칙 | 누락 | 변경 전에 `RULE.md` 전체와 관련 handoff 계약을 읽고, 확인하지 못하면 변경을 시작하지 않는다는 절차가 없다. |
| 0. 가장 중요한 규칙 — 근거 없이 확정하지 않고, 승인 없이 실행하지 않는다 | 반영 | `final_project_cs/wiki/actions/index.md`, `actions/evidence-check.md`, `actions/approval.md`, `teams/team-boundary.md` |
| 0.1 근거(Evidence) 없으면 답하지 않는다 | 일부 | `final_project_cs/wiki/actions/evidence-check.md`, `context/context-broker.md`, `context/rag-retrieval.md` — 근거 부족 시 중단·degraded 표시는 있으나 Evidence 필수 필드 3종을 포함한 응답 계약이 없다. |
| 0.2 side effect 는 제안(proposal)까지만이다 | 반영 | `final_project_cs/wiki/teams/team-boundary.md`, `actions/action-proposal.md`, `external/mcp-tools.md`, `actions/idempotency.md` |
| 0.3 상태는 한 문으로만 바뀐다 | 반영 | `final_project_cs/wiki/runtime/case-lifecycle.md`, `data/schema/index.md`, `runtime/shared-state.md` |
| 1. 데이터 원칙 | 반영 | `final_project_cs/wiki/data/`, `context/`, `external/auth-boundary.md`, `quality/eval-harness.md` |
| 지어내지 않는다 | 반영 | `final_project_cs/wiki/actions/evidence-check.md`, `runtime/case-lifecycle.md`, `external/rest-api.md`, `wiki/product/scope.md` |
| tenant / customer 격리 | 반영 | `final_project_cs/wiki/data/tenancy.md`, `external/auth-boundary.md` |
| PII 는 저장 시 masking, LLM 에는 masked 만 | 반영 | `final_project_cs/wiki/external/auth-boundary.md`, `quality/invariants.md` |
| 산출물에 버전을 박는다 | 반영 | `final_project_cs/wiki/data/schema/index.md`, `quality/eval-harness.md`, `wiki/evaluation/protocol.md` |
| 2. 계약 원칙 | 반영 | `final_project_cs/wiki/teams/team-contract/index.md`, `teams/team-registry.md`, `teams/team-boundary.md` |
| 3. 코드 원칙 | 일부 | `final_project_cs/wiki/operations/troubleshooting.md`, `context/context-budget.md` — 오진·회귀·주석·오류 메시지·가드레일 단일 출처는 있으나 조용한 skip을 세어 분모에 포함시키는 규칙이 없다. |
| 4. 검증 원칙 | 반영 | `final_project_cs/wiki/operations/run.md`, `quality/eval-harness.md`, `actions/idempotency.md`, `wiki/evaluation/protocol.md` |
| 5. 지금 상태 (2026-08-17) | 일부 | `final_project_cs/wiki/quality/evidence.md`, `quality/eval-harness.md`, `operations/run.md`, `wiki/delivery/release-gate.md` 등 — 상태가 여러 문서에 분산됐고 seed 구도메인 수치·프롬프트 배선 이력 등 일부가 없다. 테스트·DoD·미해결 수치는 wiki 문서끼리도 서로 다르다. |
| 임시 파일은 한 곳에만 만든다 | 반영 | `final_project_cs/wiki/operations/local-setup.md` |
| 환경 주의사항 | 반영 | `final_project_cs/wiki/operations/local-setup.md`, `data/migrations.md` |
| 6. 자주 쓰는 명령 | 반영 | `final_project_cs/wiki/operations/run.md`, `operations/local-setup.md` |
| 7. 문서 | 일부 | `wiki/architecture/repository-map.md`, `governance/migration-scope/index.md`, `final_project_cs/wiki/quality/evidence.md` — 일부 폴더와 정본 링크는 있으나 plans·handoff·reports·debugs·evidence의 전체 역할 및 “결정은 리포트로 남긴다” 규칙이 없다. |

**빠진 것 요약:** 응답 언어와 작업 시작 필독 절차가 없고, 현재 상태표와 문서 운용 규칙은 일부만 분산 이관됐다.

## `final_project_cs/RULE.md`

| 절 제목 | 판정 | wiki 반영 위치·누락 내용 |
|---|---|---|
| ★ 이 문서와 `CLAUDE.md` 의 관계 | 누락 | 두 문서의 프로세스/도메인 역할 분리와 자동 로드 차이 표가 없다. |
| 충돌하면 무엇이 이기나 | 누락 | `CLAUDE.md §0` 우선, 그 밖에는 `RULE.md` 우선이라는 규칙이 없다. |
| 상위 계획서와의 관계 | 일부 | `wiki/_migration/v8/index.md`, `governance/review-policy.md` — 기준선 읽기 전용·hash 보존 취지는 있으나 원본의 v6/v4 관계와 불일치 기록 절차가 없다. |
| 1. 할루시네이션(환각) 방지 규칙 | 일부 | `wiki/governance/evidence-grades.md`, `document-standard.md`, `evaluation/metrics.md` — 근거·평가 수치 규칙은 있으나 원본 전체 하위 규칙을 포괄하지 않는다. |
| 1.1 근거 없는 주장 금지 | 일부 | `wiki/governance/evidence-grades.md`, `final_project_cs/wiki/actions/evidence-check.md` — 확인 필요 표시는 있으나 실제 파일 실행 확인과 `경로:줄번호` 의무가 없다. |
| 1.2 검증 우선 원칙 | 일부 | `final_project_cs/wiki/operations/run.md`, `quality/evidence.md` — 실행 증거 원칙은 있으나 모든 코드 변경 후 결과를 리포트에 원문 기록하는 절차가 없다. |
| 1.3 출처 표기 | 일부 | `wiki/governance/evidence-grades.md`, `document-standard.md` — source 연결은 있으나 참조 프로젝트에서 가져온 코드의 원본 프로젝트·경로 표기와 문서 하단 참조 절 의무가 없다. |
| 1.4 ★평가 수치는 분모를 함께 적는다 | 반영 | `wiki/evaluation/metrics.md`, `evaluation/protocol.md`, `governance/evidence-grades.md` |
| 1.5 ★사람이 이해하기 쉬운 문체로 설명한다 | 누락 | 결론·이유 선행, 용어 최초 풀이, 평서문 뒤 표 배치라는 세 규칙이 없다. |
| 2. 작업 루프 (Harness) | 누락 | 시작 0~2, 수행 3~5, 종료 6~8의 전체 작업 루프와 최소 검증 단위 규칙이 없다. |
| 3. 구현 원칙 | 일부 | `wiki/product/scope.md`, `final_project_cs/wiki/context/context-budget.md`, `operations/troubleshooting.md` 등에 일부 원칙만 있다. |
| 3.1 하드코딩 금지 | 일부 | `final_project_cs/wiki/context/context-budget.md`, `external/auth-boundary.md` — guardrail·scope 단일 출처는 있으나 API key·모델명·경로·DB 접속 정보 전체 금지와 예외 규칙이 없다. |
| 3.2 폴백(fallback) 금지 | 반영 | `final_project_cs/wiki/context/context-budget.md`, `context/rag-retrieval.md`, `runtime/conflict-retry.md` |
| 3.3 꼭 필요한 부분만 구현 (YAGNI) | 일부 | `wiki/product/scope.md`, `architecture/pack-model.md` — In/Out과 Port까지만 구현한다는 취지는 있으나 중복 구현 통합·legacy 보존과 참조 프로젝트 이관 규칙이 없다. |
| 3.4 리포트 제출 의무 | 누락 | 모든 세션의 리포트 제출 의무와 목표·변경 파일·검증·미해결 4항목 형식이 없다. |
| 3.5 ★계약을 코드보다 먼저 고친다 (Contract-first) | 일부 | `final_project_cs/wiki/teams/team-contract/index.md`, `data/migrations.md` — 계약 변경 시 버전·테스트는 있으나 handoff 문서를 코드보다 먼저 고치는 순서가 없다. |
| 3.6 ★Codex 에 넘기기 전에 계약을 먼저 준다 (분업 규칙) | 일부 | `wiki/delivery/roles.md`, `governance/migration.md` — 소유 디렉터리 분리와 교차검증 취지는 있으나 계약 선확정·4종 산출물 검사·별도 테스트·검수 기록의 5단계 절차가 없다. |
| 4. 폴더별 문서 규칙 | 일부 | `wiki/governance/migration-scope/index.md`, `final_project_cs/wiki/log.md` — 일부 기존 폴더의 처리 방식은 있으나 11개 폴더의 용도·갱신 시점 표가 없다. |
| 4.0 ★DoD 를 통과시켰다고 말하려면 evidence 가 있어야 한다 | 반영 | `final_project_cs/wiki/quality/evidence.md`, `wiki/delivery/dod.md` |
| 4.1 버그를 찾으면 리포트부터 쓴다 | 누락 | 수정 여부와 무관한 즉시 기록 의무 및 위치·재현·실측·위험도·잘못 보고한 수치 정정의 5항목이 없다. |
| 4.2 파일명 규칙 | 누락 | timestamp 규칙과 handoff·evidence·vision 예외, legacy 원본경로 보존 규칙이 없다. wiki의 kebab-case 규칙은 다른 체계다. |
| 4.3 history 기록 형식 | 누락 | 계획·담당·수행·검증·리포트 5행 템플릿이 없다. |
| 4.4 ★"지금은 안 한다"로 끝내지 않는다 — `docs/vision/` | 누락 | TODO_VISION 즉시 등록, 관측 가능한 도입 트리거, 실소요 일수, 폐기 조건 규칙이 없다. |
| 5. 통합 규칙 (v6 §25) | 일부 | `wiki/delivery/dod.md`, `final_project_cs/wiki/operations/run.md` — 테스트·CI 취지는 있으나 기능별 3종 테스트+로그, 동결 후 P0/P1만 허용, merge 명령 3개의 묶음이 없다. |
| 6. 금지 사항 요약 (Quick Reference) | 일부 | `wiki/product/scope.md`, `final_project_cs/wiki/teams/team-boundary.md`, `context/context-budget.md` 등 — 도메인 안전 금지는 있으나 리포트·history·Codex handoff/검수·vision 등록 등 프로세스 금지가 빠졌다. |

**빠진 것 요약:** 작업 루프, 리포트·버그·history·파일명·vision 규칙과 `CLAUDE.md` 우선순위가 대부분 이관되지 않았다.

## `final_project_cs/docs/release_checklist.md`

| 절 제목 | 판정 | wiki 반영 위치·누락 내용 |
|---|---|---|
| 0. 지금 상태 요약 | 일부 | `wiki/delivery/release-gate.md`, `delivery/dod.md`, `final_project_cs/wiki/quality/evidence.md` — RC 아님은 있으나 원본의 v5 18/18·통과 16·부분 2 표가 없고 wiki의 상태 수치도 서로 다르다. |
| 1. 빌드·테스트 | 일부 | `final_project_cs/wiki/operations/run.md`, `quality/test-map.md` — 테스트 명령과 최신 총계는 있으나 원본의 172 passed, live 1건 제외, 4회 연속 및 시계 결함 이력이 없다. |
| 2. 안전 (되돌릴 수 없는 것) | 반영 | `final_project_cs/wiki/actions/`, `teams/team-boundary.md`, `external/mcp-tools.md`, `operations/unknown-state.md` |
| 3. 데이터·격리 | 반영 | `final_project_cs/wiki/data/tenancy.md`, `external/auth-boundary.md`, `quality/invariants.md` |
| 4. 배포 산출물 | 일부 | `wiki/delivery/release-gate.md` — `publish_public` 검사 취지는 있으나 공개 183개, 스크럽 21개, AI 흔적 0, 워킹 트리 복구와 두 실행 명령이 없다. |
| 4-1. 배포 전 선언 변경 | 반영 | `final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md`, `external/rest-api.md` |
| 5. ★RC 를 막고 있는 것 | 일부 | `wiki/delivery/release-gate.md` — judge agreement와 일반화 한계는 있으나 §5-3의 최신 해소 상태가 반영되지 않아 전체 차단/비차단 현황이 낡았다. |
| 5-1. judge agreement 미측정 (DoD-15) | 반영 | `wiki/delivery/release-gate.md`, `evaluation/judge.md`, `final_project_cs/wiki/quality/eval-harness.md` |
| 5-2. 평가 결과의 일반화 한계 (DoD-15 · v5 §15-8) | 반영 | `wiki/delivery/release-gate.md`, `evaluation/protocol.md` |
| 5-3. 미해결 (차단은 아님) | 일부 | `wiki/delivery/release-gate.md`, `final_project_cs/wiki/actions/outbox.md` — wiki에는 네 항목이 미해결로 남아 있다. 원본의 hover 좌표 변화 0, 커밋→Phase 자동 매핑, 24장 캡처, timeout→unknown E2E 완료 내용이 없다. |
| 6. 환경 (재현하려는 사람에게) | 반영 | `final_project_cs/wiki/operations/local-setup.md`, `operations/run.md`, `data/migrations.md` |
| 7. 판정 | 반영 | `wiki/delivery/release-gate.md` |

**빠진 것 요약:** 배포 파일 수·스크럽 수와 빌드 이력이 빠졌으며, 비차단 4항목은 원본에서 해결됐지만 wiki에는 미해결로 남아 있다.

===== 전체 =====

| 원본 | 절 수 | 반영 | 일부 | 누락 |
|---|---:|---:|---:|---:|
| `01_계약_Pydantic.md` | 11 | 3 | 8 | 0 |
| `02_DB_스키마.md` | 10 | 2 | 6 | 2 |
| `03_REST_MCP_인터페이스.md` | 13 | 2 | 11 | 0 |
| `08_모듈_컴포넌트_목록.md` | 10 | 1 | 8 | 1 |
| `CLAUDE.md` | 19 | 13 | 4 | 2 |
| `RULE.md` | 25 | 3 | 13 | 9 |
| `release_checklist.md` | 12 | 7 | 5 | 0 |
| **합계 — 명시된 7건** | **100** | **31** | **55** | **14** |