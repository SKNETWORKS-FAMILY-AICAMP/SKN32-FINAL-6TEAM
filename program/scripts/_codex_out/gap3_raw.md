===== DOC: 06_가드레일_수치.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 규칙 | 반영 | `quality/guardrails.md` — `config/guardrails.yaml` 단일 출처와 `app.core.settings.guardrails` 사용 규칙 |
| 1. 토큰 예산 (v5 §9-1) | 반영 | `quality/guardrails.md`, `context/context-budget.md` — 12,000 토큰 배분, 축출 순서, 보호 항목, 선정 이유 |
| 2. 신뢰성 가드레일 (v5 §11) | 반영 | `quality/guardrails.md` — 시간·횟수·비용 상한과 동일 signature 2회 제한 |
| 3. RAG (v5 §9-2) | 반영 | `quality/guardrails.md`, `context/rag-retrieval.md` — 문서·청크·top-k·1536차원·HNSW·Phase 2 조건 |
| 4. VOC 급증 정의 (v5 §14-3) — 문구 그대로 | 일부 | `quality/guardrails.md`에 공식·00:10 UTC·금지 기법은 있다. 전일과 직전 7일의 `intent`·`issue count`, negative ratio, unresolved ratio를 집계한다는 내용이 빠졌다 |
| 5. Scope (v5 §12) | 일부 | `external/rest-api.md`, `external/mcp-tools.md`, `external/auth-boundary.md`에 endpoint별 `case:*`·`action:approve`·`mcp:read`와 MCP 제한은 있다. 원본 scope 목록의 `order:read`, `return:read`가 없다 |
| 6. Resume token (v5 §5-4) | 반영 | `quality/guardrails.md`, `external/rest-api.md` — 24시간·일회성·hash 저장·event 멱등성·만료 시 escalation |
| 7. Optimistic concurrency (v5 §6-1) | 반영 | `quality/guardrails.md`, `runtime/conflict-retry.md` — 최대 2회 재계산, active run 1개, version CAS와 `StateConflict` |
| 8. 평가 (v5 §15) | 반영 | `quality/guardrails.md`, `evaluation/protocol.md`, `evaluation/judge.md` — 60/20·3회·seed 7·bootstrap 10,000·McNemar·judge 통과식 |
| 9. 보존·감사 (v5 §12) | 반영 | `quality/guardrails.md`, `external/auth-boundary.md` — 90일, actor/action/before-after hash, 원문 금지 항목 |

**빠진 것 요약:** VOC 집계 대상 네 지표와 scope 목록의 `order:read`·`return:read`가 빠졌다.

===== DOC: 10_도메인_교체_가이드.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. 경계 | 일부 | `architecture/core-vs-team.md`, `quickstart.md`, `quality/invariants.md`에 Core의 도메인 격리와 테스트는 있다. 원본의 경로별 5행 교체표와 예외 목록 최대 3개가 없다 |
| 1. 갈아 끼우는 것 — 순서대로 | 일부 | `architecture/pack-model.md`에 Pack 교체 원칙은 있다. 테이블→대조 선언→Team→코퍼스→평가→시연의 6단계 순서는 없다 |
| 1-1. 도메인 테이블 | 일부 | `data/migrations.md`에 Core 14종과 Commerce 4종 및 `002_domain_commerce.sql`은 있다. `002_domain_<your>.sql` 교체 규칙과 `sorted(glob("*.sql"))` 적용 방식이 빠졌다 |
| 1-2. 대조 선언 (v7 §9-E) | 일부 | `actions/evidence-check.md`에 `VerificationPolicy`·`QuantityRule`·불투명 필드 거부 개념은 있다. `CUSTOMER_OPS_POLICY`, `references`, `quantities`, `opaque`, `ignored`, `FACT_QUERIES`의 정확한 선언과 선언 외 필드 자동 거부 규칙이 없다 |
| 1-3. Agent Team | 일부 | `teams/index.md`, `decisions/D-CS-003-composer-scope.md`에 Team 가변성·`implementation_ref` 검증·설정 선언은 있다. 원본의 `{billing,technical,feedback}.py` 목록과 Composer 적용 후 `project.yaml` 기록 절차는 그대로 보존되지 않았다 |
| 1-4. 지식 코퍼스 | 반영 | `context/rag-retrieval.md`, `context/corpus-authoring.md` — 25문서·청크 수, `check_corpus`, 길이·중복·게이밍 방지 게이트 |
| 1-5. 평가 데이터 | 일부 | `quality/eval-harness.md`, `evaluation/protocol.md`에 golden 60·holdout 20과 보존 규칙은 있다. `attack_fixtures.jsonl` 15건, `expect_block`, 새 도메인 공격 fixture 4종이 없다 |
| 1-6. 시연 데이터 | 반영 | `operations/run.md` — `seed_demo_cases`, 시나리오 2종, 고정 `uuid5`, 재실행 안전성 |
| 2. 갈아 끼우지 않는 것 (basement) | 일부 | `architecture/core-vs-team.md`, `architecture/pack-model.md`, `teams/index.md`에 주요 Core·Port·계약 항목은 분산돼 있다. 원본 11행 체크리스트 중 Ports 6종, 운영 UI·Composer, 방어 지표 5종이 같은 교체 금지 계약으로 정리돼 있지 않다 |
| 3. 복사 후 첫 검증 | 일부 | `operations/run.md`, `quickstart.md`에 corpus·architecture·전체 테스트·DoD 명령은 있다. `python -m app.infrastructure.db.migrate`와 실패 파일을 `app/modules/` 또는 선언으로 옮기라는 조치가 빠졌다 |
| 4. 이 문서가 생긴 이유 | 누락 | `payment_id`·`amount` 예시를 스펙으로 오독해 Core에 구독·결제 어휘를 박았고 `order_id`가 자동 거부될 뻔했다는 발생 경위와 결론이 wiki에 없다 |

**빠진 것 요약:** 정확한 대조 선언, 공격 fixture 계약, basement 전체 체크리스트와 도메인 어휘가 Core로 샌 발생 경위가 빠졌다.

===== DOC: 04_Team_모듈_계약.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 0. Team 이 지켜야 할 3가지 | 반영 | `teams/team-boundary.md` — Protocol, side effect 금지, evidence 의무와 순수 경계 |
| 1. Order/Shipping Team | 일부 | `teams/fulfillment-logistics.md`, `teams/procurement-order.md`에 배송 시나리오와 일부 도구·context가 있다. `order_shipping`의 정확한 manifest, `order.investigate`, `refund.propose`, `refund.request` proposal 계약은 없다 |
| 2. Return/Exchange Team | 일부 | `teams/return-refund.md`에 반품·환불 책임과 승인 제안은 있다. `return_exchange`의 정확한 manifest, `return.diagnose`, `return.propose_action`, `return.accept`와 수량 초과 시나리오 전체가 없다 |
| 3. prompt 등록 규칙 — ★설계됐으나 실 런타임에 배선되지 않았다 (2026-08-17 발견) | 반영 | `teams/team-boundary.md` — 원래 설계, 당시 호출부 0건, 현재 배선 상태 정정, FK·sha256·UNIQUE·버전 규칙과 옛 프롬프트 12개 |
| 4. tool 규칙 | 일부 | `actions/tool-gateway.md`, `quality/guardrails.md`에 allowlist, `ToolNotAllowed`, Broker 호출, 2회 loop guard와 12/6/12 상한은 있다. read 범위를 `TeamTask.context`에서 받는다는 정확한 계약과 Team용 자유 SQL 금지가 빠졌다 |
| 5. 실패·대기 처리 | 일부 | `teams/team-contract/index.md`, `teams/team-contract/fields.md`, `context/rag-retrieval.md`에 enum·필수 필드·근거 부족 시 일반 지식 금지는 있다. 여섯 상황별 `outcome`·`next_action`·동반 필드 대응표가 없다 |
| 6. 검증 (DoD 8) | 일부 | `quality/test-map.md`, `teams/team-registry.md`에 contract·Core isolation 검사는 있다. `tests/unit/teams` 명령과 Team별 golden 20건 계약이 빠졌다 |

**빠진 것 요약:** 두 옛 Team의 정확한 manifest와 실패 상태 대응표, Team 단위 검증 명령·golden 수가 완전하게 옮겨지지 않았다.

===== DOC: 07_평가_하네스.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 파일 없음 | 파일 없음 | `final_project_cs/docs/handoff/07_평가_하네스.md`가 없다 |

**빠진 것 요약:** 원본 파일이 없어 대조하지 못했다.

===== DOC: 09_Composer_GUI_계약.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. 켜고 끄기 | 누락 | `decisions/D-CS-001-composer-ui-removal.md`에는 해당 GUI를 폐기한 결정만 있다. 원본의 기본 활성 상태, `composer_ui.enabled: false`, 재기동 반영 계약은 없다 |
| ★기본값을 테스트에 묶지 마라 | 누락 | 임시 선언으로 false 동작만 검사해야 한다는 결론과 기본값을 404로 고정했던 테스트 결함이 wiki에 없다 |
| 2. 무엇을 바꿀 수 있고 무엇을 못 바꾸나 | 반영 | `decisions/D-CS-004-composer-boundary.md` — 모듈·Port·Core 경계 |
| 2-1. 모듈 — 켜고 끈다 (7종) | 반영 | `decisions/D-CS-004-composer-boundary.md` — 7종과 `grounding 3.98 → 0.00`, 자기 비활성화 경고 |
| 2-2. Port — 구현을 갈아 끼운다 (3종) | 일부 | `decisions/D-CS-004-composer-boundary.md`, `teams/index.md`에 3종 선택지와 구현 상태는 있다. 미구현 선택지를 숨기는 규칙, `a2a_executor` 선활성화 순서, 과거 `(미구현)` 오표기 결함이 없다 |
| 2-3. Team — 추가·제거한다 (개수 가변) | 일부 | `teams/index.md`, `decisions/D-CS-004-composer-boundary.md`에 가변 인스턴스와 import 실패 조건은 있다. 추가 시 `active:false`, 제거·active 체크의 정확한 UI 동작과 원본 오류 메시지가 없다 |
| 2-4. 컴포넌트 — ★끌 수 없다 (9종) | 반영 | `teams/index.md`의 필수 컴포넌트 표에 9종과 의존 이유가 있다 |
| 2-5. 구조도 — 실행 순서대로 | 누락 | Case가 지나는 10단계 구조도, 네 가지 테두리 표기, 현재 선언에서 직접 그리는 투영 규칙이 wiki에 없다 |
| 3. 저장 절차 — 검증이 먼저다 | 일부 | `decisions/D-CS-004-composer-boundary.md`에 임시 저장→정식 loader 검증→백업→원자 교체는 있다. `.composer.validation.yaml`, 네 가지 구체 검증 항목과 실패 시 임시 파일 삭제가 빠졌다 |
| 4. 실측 (브라우저 왕복) | 일부 | `decisions/D-CS-004-composer-boundary.md`에 A2A·Port·Team 추가·제거와 잘못된 ref 거부가 요약돼 있다. 조작별 YAML 결과, `shipping_support`, 정확한 import 오류가 없다 |
| 5. 한계 — 아직 못 하는 것 | 반영 | `decisions/D-CS-004-composer-boundary.md` — 재기동, 스캐폴딩 없음, 1단계 백업, 자기 비활성화 복구, manifest 편집 불가 |

**빠진 것 요약:** 기본값 테스트 결함과 10단계 동적 구조도가 통째로 없고, Port·저장·브라우저 실측의 세부 계약이 일부 빠졌다.

===== DOC: TODO_VISION.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 아직 문서화하지 않은 후보 | 누락 | Shadow mode, 스트리밍 UI, 실운영 멀티테넌시, 3번째 Team, Chatwoot/Zammad 조사 후보와 각각의 미결 조건이 wiki에 없다 |
| 폐기된 항목 | 누락 | “폐기된 항목 없음”이라는 상태가 wiki에 없다 |
| 개정 이력 | 누락 | 2026-08-13 최초 작성·비용 재산정과 2026-08-16 VISION-08·09 추가 이력이 wiki에 없다 |

**빠진 것 요약:** 세 절 모두 wiki에 반영되지 않았다.

===== DOC: 2026-08-12_1520_환경_기동절차.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 1. PostgreSQL 확인 | 일부 | `operations/local-setup.md`, `data/migrations.md`에 conda `pgv`, Windows 서비스 아님, `127.0.0.1:5433`은 있다. `Get-NetTCPConnection`, `Get-Process` 명령과 기대 프로세스 경로가 없다 |
| ★안 떠 있을 때 — 기동 절차 (2026-08-13 실측) | 누락 | 정확한 `$bin`·`$data` 경로, `pg_ctl status/start`, `-o "-p 5433"`, 5432 오기동 사례, 외부 공유 데이터 디렉터리 경고가 없다 |
| 죽었을 때 무슨 일이 일어나나 (2026-08-13 실측) | 누락 | 자동 recovery 로그, 복구 후 1·10·300·25·30건 대조, fsync 40초 대기 규칙이 없다 |
| 2. psql — PATH 에 없다 | 일부 | `operations/local-setup.md`에 정확한 `psql.exe` 위치와 `acop` 접속 명령은 있다. 함께 존재하는 `insurance_agent`·`insurance_demo`·`insurance_real`·`mall_vec` DB와 접근 금지 규칙이 없다 |
| 3. A-COP DB (최초 1회 — 2026-08-12 완료) | 일부 | `operations/local-setup.md`, `data/migrations.md`에 DB 이름과 `vector`·`pgcrypto`를 migration이 관리한다는 내용은 있다. `CREATE DATABASE acop` 명령과 extension 수동 생성 금지가 완전한 절차로 없다 |
| 4. 파이썬 의존성 | 누락 | 공유 anaconda base 주의, 설치 전 버전 확인, `pip install -r requirements.txt`, 실측 버전 3종과 `faster-whisper` 경고 설명이 없다 |
| 5. `.env` | 누락 | BOM 없는 UTF-8 저장 명령과 `﻿ACOP_DATABASE_URL` 오인식 사례가 없다 |
| 6. 점검 | 누락 | `python -m scripts.check_env`, 전 항목 OK 조건, migration 전 extension 2건 FAIL 허용 규칙이 없다 |

**빠진 것 요약:** wiki에는 환경 개요와 psql 위치만 일부 있고, 실제 DB 기동·복구·의존성·BOM·점검 절차는 대부분 빠졌다.

===== DOC: A-COP_스프린트_에픽_설계.md =====

| 절 | 판정 | 어디에 / 무엇이 빠졌나 |
|---|---|---|
| 한 줄 요약 | 일부 | `delivery/ticket-structure.md`에 4개 스프린트+보완 구간과 에픽 13개는 있다. 산출물 21건과 에픽이 1:1이 아니라는 결론이 없다 |
| 결론 — 왜 이렇게 끊었나 | 일부 | `delivery/ticket-structure.md`, `delivery/timeline.md`에 9개 주차·6개 단계안을 버리고 발표 경계에 맞춘 사실은 있다. 19·13·16·12일 표, 09-28/09-29 조정, 60일 무공백·무중복, 선행 11일 제외가 스프린트 설계로 보존되지 않았다 |
| 안 A(부트캠프 주차 그대로 9개)를 안 고른 이유 | 일부 | `delivery/ticket-structure.md`, `delivery/timeline.md`에 9주안 기각과 4W·8W 길이는 드러난다. 번다운 비교 불가와 10/21 중복 용량 계산 문제라는 결론이 없다 |
| 안 C(수행단계별 6개)를 안 고른 이유 | 일부 | `delivery/ticket-structure.md`, `delivery/timeline.md`에 6단계안 기각과 구현 6단계는 있다. 단계별 길이 편차와 데이터·Core 작업의 동시 진행 때문에 스프린트로 쓸 수 없다는 근거가 없다 |
| 지금 이미 된 것 | 일부 | `delivery/dod.md`, `architecture/repository-map.md`, `quality/evidence.md`에 현재 DoD와 sample→cs 관계는 있다. 2026-08-28 당시 26·3·1 판정표, 선언형 실행기·Composer CRUD와 미커밋 상태가 그대로 없다 |
| 에픽 13개 | 일부 | `delivery/ticket-structure.md`에 E01~E13과 E07→E14 분리는 있다. 에픽별 이름·담당·목표 스프린트·산출물·완료 판정 전체 표가 없다 |
| 의존성 | 누락 | E01~E03→E05~E09, E02→E07~E09, E06→E09, E10→E11, 선언형 실행기→E12, E11→GraphRAG의 6행 의존성 표가 없다 |
| 확인하지 못한 것 | 반영 | `delivery/ticket-structure.md` — TEAM4/6팀 불일치, 포인트·파인튜닝 필수 여부, 세부 스토리 미분할과 배정 불일치 |
| TeamFlow 등록 상태 | 일부 | `delivery/ticket-structure.md`에 프로젝트 id 84와 제한된 API 정보는 있다. 날짜별 권한 변화·등록·배정·정리 이력 대부분이 없다 |
| 최초 시도 — 권한을 켜기 전 | 누락 | GET/POST별 401·403 표, `projectId`·`id` 쿼리스트링 규칙과 `/api/issues/<id>` 404 함정이 없다 |
| 2026-08-28 진행 결과 | 일부 | `delivery/ticket-structure.md`에 에픽 13개와 토큰 기반 생성 사실은 있다. ST4F-3~15, 생성·삭제만 가능했던 권한표와 ST4F-46 삭제 실측이 없다 |
| 2026-08-29 스프린트 권한 상태 | 누락 | `/api/sprints` 응답이 401에서 403으로 바뀐 표, 관리자 설정과 `{name,start,end,goal}` payload가 없다 |
| 2026-08-29 등록 완료 | 누락 | 스프린트 4개별 기간·배정 에픽 표, 목록 조회 405, 생성 시 id 보관, `PUT` 전체 교체 주의가 없다 |
| 이슈 키가 3번부터 시작하는 이유 (다시 만들지 않는다) | 누락 | ST4F-1·2 삭제 원인, 번호 비재사용 실측, 새 프로젝트 대안과 “그대로 둔다” 결정이 없다 |
| 정리한 시험 흔적 | 누락 | 삭제한 ST4F-16·17·22·24, 보존한 ST4F-42, 브라우저 스크립트와 `desc`·소문자 type/priority·UTF-8·status·날짜 필드 규칙이 없다 |
| 2026-08-30 에픽 시작일과 상태 반영 | 일부 | `delivery/ticket-structure.md`가 13개 에픽의 start/due/status 불일치를 미확인 항목으로 적었다. 에픽별 날짜·상태 표와 네 에픽의 구체적 배정 불일치가 없다 |
| 담당자 (2026-08-30 확정) | 일부 | `delivery/roles.md`에 역할·책임·8개 소유 디렉터리는 있다. 6명 이름·TeamFlow 계정, 모듈별 담당, 비워 둔 티켓 3건, E09 하위 작업 ST4F-62~65가 없다 |
| 티켓 작성 규칙 (2026-08-30) | 일부 | `delivery/ticket-structure.md`에 내부 코드·줄임말을 피하고 용어 풀이를 붙인다는 원칙은 있다. 원본의 나머지 작성 규칙과 18건·3건 재작성 검증 이력이 없다 |
| 계층과 크기 (2026-08-31) | 일부 | `delivery/ticket-structure.md`에 에픽→스토리→작업 계층, 날짜·스프린트·부모 규칙은 있다. 1점=1일, 작업 0.1~0.5점, 시작 전 티켓 생성, 제목 prefix 금지, E01~E13 표기, 두 종류 `S1~S4` 충돌 규칙이 없다 |

**빠진 것 요약:** 에픽 의존성표와 TeamFlow 권한·등록 이력 대부분이 없으며, 일정 근거·담당자·티켓 규칙은 요약만 반영됐다.

===== 전체 =====

| 원본 | 절 수 | 반영 | 일부 | 누락 |
|---|---:|---:|---:|---:|
| `06_가드레일_수치.md` | 10 | 8 | 2 | 0 |
| `10_도메인_교체_가이드.md` | 11 | 2 | 8 | 1 |
| `04_Team_모듈_계약.md` | 7 | 2 | 5 | 0 |
| `07_평가_하네스.md` | 0 | 0 | 0 | 0 |
| `09_Composer_GUI_계약.md` | 11 | 4 | 4 | 3 |
| `TODO_VISION.md` | 3 | 0 | 0 | 3 |
| `2026-08-12_1520_환경_기동절차.md` | 8 | 0 | 3 | 5 |
| `A-COP_스프린트_에픽_설계.md` | 19 | 1 | 12 | 6 |
| **합계** | **69** | **17** | **34** | **18** |