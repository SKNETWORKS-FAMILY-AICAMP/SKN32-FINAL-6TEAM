# A-COP — 작업 규칙 (도메인)

**A-COP**(AI Customer Operations Platform)는 고객 메시지를 업무 **Case** 로 바꾸고,
현재 상태·정책·이력·피드백 분류를 **Context Pack** 으로 조합하여
**Billing/Subscription** 과 **Technical Entitlement** 업무를 **Agent Team** 이 처리하는
AI 연동형 고객운영 플랫폼이다. 개인 AI(ChatGPT·Claude·Gemini)가 REST/MCP 로 접속한다.

기준선 문서: `../program/plan/A-COP_구현계획서_v8.md` (**읽기 전용 · 수정 금지**)
v5~v7 등 이전 버전은 `../program/plan/archive/`에 보존본으로 있으며 수정하지 않는다. ★**DoD 는 18 → 29 항목이다**(v8 §27).

## 응답 언어

사용자가 쓰는 언어에 맞춰 답변한다. 사용자가 한국어로 말하면 한국어로, 영어로 말하면 영어로 답한다.
코드·커밋 메시지·식별자는 이 규칙과 무관하게 프로젝트 관례(영문)를 따른다.

## 작업 시작 진입 규칙

**모든 작업은 파일을 변경하기 전에 루트 `RULE.md` 전체를 반드시 읽고 따른다.**
이 문서는 **도메인 안전 원칙**을, `RULE.md` 는 **계획·검증·리포트·분업 절차**를 정한다.
작업 대상과 직접 관련된 `docs/handoff/` 계약도 함께 확인하며,
적용 문서를 확인하지 못하면 변경을 시작하지 않는다.

---

## 0. 가장 중요한 규칙 — 근거 없이 확정하지 않고, 승인 없이 실행하지 않는다

이 서비스는 **"환불됩니다"라고 잘못 말하면 고객이 손해를 보고**,
**승인 없이 결제를 건드리면 되돌릴 수 없다.** 그래서 다른 어떤 규칙보다 이것이 앞선다.

### 0.1 근거(Evidence) 없으면 답하지 않는다
- **정책 근거를 못 대면 확정 답변을 만들지 않는다.** `waiting_input` 또는 `escalated` 가 정답인 경우가 있다.
- 모든 핵심 주장에는 `Evidence`(`source_type` · `source_id` · `observed_at`)가 붙어야 한다.
  근거 없는 문장은 답변에 넣지 않는다.
- RAG 가 죽었을 때 조용히 일반 지식으로 메우지 않는다 →
  `ContextPack.degraded=true` + `omissions` 기록. **신호 없는 축소는 폴백이다**(`RULE.md` §3.2).

### 0.2 side effect 는 제안(proposal)까지만이다
- **Team 은 side effect 를 실행하지 않는다.** `ActionProposal` 만 반환한다.
- 환불·구독 변경·권한 부여는 **Human Approval** 을 거친다. 승인자는 `action:approve` scope 가 있어야 한다.
- **MCP 는 read-only 다.** `open_support_case` 는 Case 생성·분류 시작까지이고,
  결제·환불·구독 변경을 하지 않는다. 쓰기는 REST + 승인 경로로만 간다.
- provider timeout 을 **성공으로 추정하지 않는다.** `unknown` 으로 남기고 자동 재실행하지 않는다.

### 0.3 상태는 한 문으로만 바뀐다
- `customer_cases` 를 직접 `UPDATE` 하지 않는다. **`transition_case()` 만이 진입점이다.**
- `case_events` 는 append-only 다. `UPDATE`/`DELETE` 하지 않는다.
- LangGraph checkpoint 로 **업무 상태를 되돌리지 않는다.** checkpoint 는 실행 snapshot,
  `customer_cases` 는 업무 상태의 권위 있는 projection 이다.

---

## 1. 데이터 원칙

### 지어내지 않는다
값을 모르면 **비워 둔다.** 추정으로 채우면 그 오류가 조용히 고객 답변까지 간다.
채운다면 무엇을 근거로 채웠는지 필드에 남긴다.

```
intent        분류 성공 시에만 채운다. 실패하면 NULL + classification_failed 이벤트
sentiment     동
issue_code    동
degraded      ContextPack 이 축소됐으면 true (숨기지 않는다)
omissions     무엇을 뺐는지 이름으로 남긴다
```

★**분류 실패는 조용히 넘기지 않는다.** v6 §3-A — Case 생성 경로에서 감성·의도·이슈 분류가 실패하면
`classification_failed` 를 남기고 `escalated` 로 전환한다. 인라인 분류는 선택 기능이 아니다.

### tenant / customer 격리
모든 query 에 `tenant_id` 와 `customer_id`(또는 `case_id`) 조건을 적용한다.
조건 없는 조회 쿼리는 그 자체가 보안 결함이다 — `tests/security/` 가 검사한다.

### PII 는 저장 시 masking, LLM 에는 masked 만
원문 PII 는 masking 후 저장하고, LLM 에는 masked text 만 전달한다.
audit log 에 **API key 원문·결제 식별자 원문을 기록하지 않는다.**

### 산출물에 버전을 박는다
같은 입력이라도 프롬프트·모델이 바뀌면 결과가 달라진다. 덮어쓰지 않고 공존시킨다.

```
prompts        (prompt_key, version) UNIQUE + sha256 immutable
llm_calls      prompt_id FK 로 어떤 프롬프트가 만든 답인지 추적
eval/reports/  run_id + seed + model + prompt snapshot 을 파일명·메타에 박는다
```

---

## 2. 계약 원칙

- `app/core/contracts.py` 는 `docs/handoff/01_계약_Pydantic.md` 의 **구현체**다. 둘이 어긋나면 결함이다.
- 모든 계약 모델은 `model_config = ConfigDict(extra='forbid')` 를 쓴다. 조용한 필드 유입을 막는다.
- **Core 는 Team 내부를 import 하지 않는다.** `TeamManifest` 와 `execute()` 만 쓴다.
- Team 은 `TeamManifest.allowed_tools` 밖의 tool 을 호출할 수 없다. Registry 가 거부한다.

---

## 3. 코드 원칙

- **오진 위에 수정을 쌓지 않는다.** 하나 고치면 그것만 검증하고 다음으로 간다.
- **조용한 스킵을 만들지 않는다.** `except: continue` 는 실패를 세어 보고해야 한다.
  세지 않으면 분모가 줄어 성공률이 실제보다 좋아 보인다.
- **회귀가 의심되면 옛 커밋을 먼저 실행한다.** 추측보다 빠르다.
- **오진했던 내용을 주석에 남긴다.** 다음 사람이 되풀이하지 않도록.
- 오류 메시지가 사실을 잘못 전하지 않게 한다 (상태 충돌을 "LLM 실패"로 보고하면 한참 헤맨다).
- 가드레일 수치는 `config/guardrails.yaml` 한 곳에만 둔다 (`RULE.md` §3.1).

---

## 4. 검증 원칙

- **백엔드·테스트 통과만으로 "구현 완료"라 하지 않는다.** UI 가 있으면 매 단계 **실제로 열어서** 확인한다.
- **표본이 작으면 작다고 말한다.** golden 60건 × 3회는 **방향성과 불확실성**을 말할 뿐,
  모집단 일반화·장기 drift·실제 손실률·SLA 를 증명하지 않는다(v6 §15-8).
- 평균만 보고하지 않는다. **paired bootstrap 95% CI 와 McNemar** 를 함께 낸다.
- **holdout 20건으로 프롬프트를 고치지 않는다.** 만지는 순간 holdout 이 아니다.
- 중요한 판단은 **Codex 와 교차검증**한다. 반박당하면 실측으로 가린다.
- **동일 요청 10회 → side effect 1회**. idempotency 는 말이 아니라 테스트로 증명한다.

---

## 5. 지금 상태 (2026-08-17)

> ★상태표의 숫자는 **문서가 아니라 디스크·DB 를 세어** 갱신한다.

| 단계 | 상태 |
|---|---|
| 저장소 골격 | **완료** — `RULE.md`·`CLAUDE.md`·`docs/` 9개 폴더. git init(main) |
| 실행계획서 | **완료** — `docs/plans/2026-08-12_1507_A-COP_실행계획서_v1.md` (P0~P10, DoD 18항목 배분) |
| handoff 계약 | **완료** — `docs/handoff/01`~`06` + `_prompts/` |
| 환경 (실측 2026-08-12) | **PostgreSQL 16.14** `127.0.0.1:5433` (conda env `pgv`, 서비스 아님) · `vector`·`pgcrypto` **설치 완료** · **Docker 없음** · Python 3.12.7 · codex CLI 있음 |
| DB 스키마 | **완료** — `acop` DB. **18 테이블**(v6 §22 의 14 + mock 4). UNIQUE 3종·인덱스 3종·extension 2종 **DB 직접 조회로 확인**. 마이그레이션 재실행 안전 |
| seed 데이터 | **완료** — demo customers 10 · subscriptions 10 · payments 30(14일 분포) · entitlements 10 · incidents 3. 시나리오1(해지 후 결제) 2명 · 시나리오2(Pro/Free 불일치) 1명. 테스트 후 `tenants=1`(격리 확인) |
| REST / MCP | **인수** — route 정확히 5개 + `/health`, MCP tool 3개 전부 `mcp:read`. 테스트 **74건**(scope matrix 6종 parametrize · 동일요청 10회→`action_requests` 1행 · 남의 Case→404 · MCP 가 payments/subscriptions 를 안 건드림 · 409 렌더링). ★1차는 `os.getenv` 로 설정을 읽어 **인증 전 요청이 500** 이었다 → [디버그](docs/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md) |
| Core 런타임 | **완료** — 계약(v6 §21 전체)·전이표(21 이벤트/24 전이)·순수 리듀서·`transition_case()` 단일 진입점. **테스트 57건 통과** |
| RAG corpus | **완료** (2026-08-17) — **쇼핑몰 도메인 25문서 / 306청크**, Claude 가 직접 작성(코덱스 재작성이 조사 오손 3,401건을 냈다 → 재발주 대신 직접 작성으로 전환). `python -m scripts.check_corpus` **전 항목 통과**. 이 과정에서 게이트 자체의 결함 2건도 고쳤다 — 조사 검사기가 `초과`·`결과` 같은 받침 없는 한자어를 조사 오류로 오탐(예외 사전 추가), 마감 3섹션(승인/기록/범위)이 25문서 모두 같은 제목을 써 점유율 상한(50%)에 걸릴 뻔함(문서군별 제목 4종 교대) |
| Context Broker | **완료** — 12,000 토큰 tiktoken **실측** 절삭, 섹션별 예산·제거 순서, `degraded`/`omissions` 강제 |
| RAG 적재·검색 | **완료** (2026-08-17) — `knowledge_documents` 25 · `knowledge_chunks` **306** · 1536d, DB 직접 조회로 확인. 시나리오 질의(배송완료 미수령 → doc_01, 반품 수량 초과 → doc_14)가 top_k=8 안에서 검색됨, scope 필터·tenant 격리 동작. `tests/integration/rag` 4건 — 이전 세션은 옛 구독/청구 도메인 질의로 하드코딩돼 있어 붉었다, 쇼핑몰 시나리오로 재작성 |
| Agent Team | **완료** — Order/Shipping·Return/Exchange 2종(`order_shipping`·`return_exchange`, `config/project.yaml` 등록). manifest 계약 일치, LLM 주입 가능, **Core 격리 위반 0**(AST 검사). 옛 Billing/Technical은 이 프로젝트엔 없다 — `.pyc` 캐시만 남은 잔재이며 소스는 없다. 프롬프트도 옛 도메인 12개는 `legacy/final_project_sample/prompts/`로 이동됐다(§ 프롬프트 감사추적 배선 행 참조) |
| ★**프롬프트 감사추적 배선** | **완료** (2026-08-18), **단 2026-08-19 레거시 격리로 재파손 → 2026-08-30 재수정**. 2026-08-18 구현 내용: `prompts`/`llm_calls` 가 설계만 있고 실 런타임에 배선 안 돼 있던 결함(`docs/reports/debugs/2026-08-17_2340_프롬프트_감사추적_미연결.md`)을 구현, `register_prompt_files()` 키 계산 수정·advisory lock 기반 active 유일성, `OpenAITeamLLM` 이 활성 프롬프트를 조회해 쓰고 분리된 트랜잭션으로 `llm_calls` 기록, 활성 프롬프트 없으면 fail-closed. ★그 뒤 2026-08-19 레거시 팀 격리(order_shipping/return_exchange 프롬프트 제거)가 `ALLOWED_PROMPT_KEYS` 를 **완전히 비운 채 CS Pack 신규 키(response.generate/response.review_tone)로 채우지 않고 방치**해, v8 CS Pack 확정 팀인 Response Generation & Review 가 production DB-감사 경로(`connection_factory` 주입)로 호출될 때마다 `RuntimeError: no active prompt registered` 로 매번 죽고 있었다 — 이 팀의 유일한 실 LLM 테스트가 `connection_factory` 없이 생성한 LLM으로 이 경로 자체를 건너뛰어 발견이 늦었다. 2026-08-30 DoD-28 RAG 통합 설계 중 DB 직접 조회로 발견·수정: `prompts/response/generate.v1.md`·`review_tone.v1.md` 신규 작성, allowlist 갱신, `register_prompts.py` 재실행으로 DB active 확인, 재현 스크립트로 실 OpenAI 호출 성공 확인, 회귀 테스트 3건 추가/개정 — `docs/reports/2026-08-30_S-PROMPT-KEY-REGISTRATION-GAP_리포트.md` |
| Feedback Analytics | **완료** — 인라인 분류(실패 시 `classification_failed`+escalated) + 일일 배치. 급증식은 v6 §7-A 그대로. ★(2026-08-17) **이 세션 최고 심각도 결함 발견·수정**: `feedback.py::INTENTS` 가 옛 구독 어휘(`billing`/`technical`)로 남아 있었는데 이 함수가 **운영 REST API 의 기본 classifier** 였다 — 쇼핑몰 Case 는 전부 분류 실패로 떨어졌을 것. `order`/`shipping`/`return`/`exchange`/`other` 로 교체(Team `accepted_case_types` 와 일치하도록 설계), 실 LLM 호출로 `composition.build_classifier()` 종단 확인. 재발 방지로 `INTENTS ⊇ 모든 Team.accepted_case_types` 불변조건 테스트 추가. `docs/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md`. ★그 다음 실 REST API e2e 라이브 테스트(`tests/live/test_feedback_classifier_live_e2e.py`)로 수동 확인을 재실행 가능한 회귀 테스트로 전환 — 발주 계약의 잘못된 가정(`controller=None` 이 controller 실행을 막는다는 오해) 2건을 실행하며 직접 발견·수정. `docs/evidence/LIVE-CLASSIFIER-E2E_검증.md` |
| Controller · WAIT/RESUME · Outbox | **완료** — 통합테스트 8종. ★`resuming→completed` 를 상태기계가 런타임 거부해 **진짜 결함을 잡았다** → [디버그](docs/reports/debugs/2026-08-12_2230_Controller가_resuming에서_resumed를_건너뛴다.md) |
| 운영 UI | **완료** — `/ui/{cases,approvals,voc,trace}` 4개 화면 200 확인. VOC 데이터 없을 때 "없음"을 정직하게 표시. ★(2026-08-17) 실 브라우저로 승인 버튼을 여러 번 눌러 결함 2건 발견·수정 — `verification_policy.py` 가 표시용 `evidence` 필드를 거부해 승인이 409로 막힘, 승인 감사 기록이 대기 큐에 유령 항목으로 남음. 둘 다 수정, 회귀 테스트 추가 — `docs/reports/2026-08-17_2255_DoD-18_브라우저재검증_결함2건_리포트.md` |
| 평가 하네스 | **완료** — golden **60** / holdout **20**, runner 3종, judge rubric, bootstrap/McNemar. ★(2026-08-17) `eval/runners/common.py` 가 삭제된 옛 모듈(`billing.py`/`technical.py`)을 import 하고 있어 라이브 경로(`--provider openai`)가 깨져 있던 것을 발견·수정 — pytest 가 이 모듈을 안 돌려서 안 잡혔다. `docs/evidence/EVAL-RUNNER-IMPORT-FIX.md` |
| A2A / Graph (신계획서) | **완료** — `TeamExecutorPort`·`LocalTeamExecutor`·`A2ATeamExecutor`·Agent Card·`GraphStorePort`·`SqlGraphAdapter`(재귀 CTE) **7/7**. Controller 가 Port 경유(`LOCAL`↔`A2A` 교체점) |
| 모듈화 · Composer GUI | `config/project.yaml` 이 조립의 단일 입력. ★**`/ui/composer` 는 폐기됨(2026-08-18)** — 인증이 전혀 없이 고객 접근 가능한 이 앱에 물려 있던 것을 실측으로 확인, 삭제했다. 같은 기능은 별도 프로그램 `final_project_ui`가 인증된 `/composer/*` API로만 제공한다(`docs/handoff/09` 상단 참고) |
| 평가 실행 | ★**무효화됨 (2026-08-17)** — 아래 3군×180행=540관측 수치는 **옛 구독·청구 도메인**(golden/holdout 이 영어·billing/technical 이던 시절)에서 측정한 값이다. 코퍼스와 golden/holdout 이 전부 쇼핑몰 도메인으로 교체됐으므로 이 수치는 새 도메인을 대표하지 않는다. 재측정 전까지 참고용으로만 남긴다: A 0/180 · B 6/180 · Proposed 40/180, grounding 0.00 / 2.22 / 3.98(옛 도메인 기준). 재측정 명령은 `docs/reports/2026-08-17_1540_RAG적재_평가데이터셋_재작성_리포트.md` §5 |
| ablation | ★**같은 이유로 무효화됨** — 5종 모두 옛 도메인 기준. RAG·Context Broker 제거 시 grounding 3.98→0.00 이었다는 **방향성**(RAG 가 있고 없고의 차이)은 메커니즘이 안 바뀌었으므로 여전히 참고 가치가 있으나, 새 도메인에서 재측정하지 않은 수치를 근거로 쓰지 않는다 |
| judge 검증 | **부분** — 540행 전량에서 **근거 없이 grounding 점수를 받은 행 0건**(`eval/check_judge.py`, 0 아니면 exit 1). ★**사람 라벨 20건은 여전히 미측정** — 기계 검사는 agreement 를 대신하지 못한다 |
| 발표 시나리오 seed | **완료** — `scripts/seed_demo_cases.py`. ★(2026-08-17) 옛 구독 도메인(`billing_subscription`/`technical_entitlement` — 지금 없는 team_id)이던 것을 쇼핑몰 도메인으로 재작성. 시나리오1(cust_01/ORD-0101 배송완료 미수령→`order_shipping`)은 `waiting_approval` 에서 멈추고, 시나리오2(cust_02/ORD-0201 교환 기한 문의→`return_exchange`)는 `resolved` 종단. `scripts.seed` 가 만든 실제 주문·배송 행을 조회해 근거로 쓴다(하드코딩 UUID 없음). case_id 는 `uuid5` 로 고정. 실행 확인·재실행 안전(`cases_in_tenant` 불변) 실측함. ★(2026-08-17) 브라우저 재확인 완료 — 시나리오1 승인 버튼을 실제로 눌러 `waiting_approval(4)→resuming(5)` 종단 확인, 그 과정에서 찾은 결함 2건 수정 후 데모 상태는 `waiting_approval` v4 로 원복해 뒀다 — `docs/evidence/DoD-18_UI_시나리오_종단표시.md` §"2026-08-17 재검증" |
| 운영 UI 품질 | **완료** — 디자인 시스템(`app/presentation/ui/theme.py`), 상태별 의미색·다크모드·375px 가로밀림 0. ★JSON 덤프를 표·분포로. `unknown` 은 가장 센 위험색(돈이 나갔는지 모르는 상태) |
| Composer GUI | **완료** — 모듈 7 토글 · Port 3 교체 · Team 추가/제거 · **컴포넌트 9 는 잠김**. 실행 순서 10단계 구조도가 **현재 선언을 따라간다**. 계약 `docs/handoff/09` |
| 개발 서버 | **완료** — `.claude/launch.json` 의 `acop-ui`(8041, `--reload`). `/` → `/ui/cases` 307 |
| 릴리스 체크리스트 | **완료** — `docs/release_checklist.md`. ★판정은 **RC 아님** |
| ★**할루시네이션 방어** (v7 §9-E) | **완료** — 제안의 식별자·금액을 **DB 와 대조**해 실행 전 차단. 검증 2회(제안 시점 + 승인 직전). 거부 시 `escalated` + 실패필드·**hash** 감사. `app/core/verification.py`(순수) + `proposal_guard.py`(재조회) |
| **테스트 총계** | **406 passed(`-m "not live"`) · skipped 0 · failed 0** (2026-08-30 실측. `-m live` 로 live 마크 테스트 별도 실행해 통과 확인. 304(2026-08-18) → 406 은 이후 세션들의 누적 추가분 + 2026-08-30 프롬프트 키 등록 결함 수정의 신규 테스트 2건) |
| **DoD (v8 §27, 1~28항목 평가됨)** | **evidence 28/28 · 통과 24 · 부분통과 4 · 미착수 0.** ★#6(정책 25건·300~400 chunk)이 미착수→통과로 이동. 남은 부분통과 = 15(judge agreement) · 17(파일시스템 gate 재현) · 23(consumer 1종뿐) · 28(파인튜닝·방어지표). **29번(Response Generation & Review 검증)은 v8에서 신설된 항목으로 이 구현에서는 아직 평가되지 않았다.** |
| **M1·M2·M3 게이트** | **전부 도달**. ★단 **RC 는 아니다** — judge 가 사람과 얼마나 맞는지 모르는 상태로 내보낼 수 없다 |

> ★**Codex 산출물은 두 번 다 검수에서 걸렸다**(범위 삭감 2건). 인수 전 `RULE.md` §3.6-3 4종 검사를 거른 적이 없어야 한다.
> ★**건수만 세는 검증은 이 프로젝트에서 두 번 실패했다.** 코퍼스는 `check_corpus.py`, seed 는 DB 직접 조회로 센다.

### 임시 파일은 한 곳에만 만든다

★**상위 폴더(`final_workspace/`)에 `.tmp_*` 를 흩뿌리지 않는다.**
문서 렌더링·변환 중간산출물이 `.tmp_jh_render`·`.tmp_lo_profile` 처럼 쌓여
작업 폴더가 어질러진 적이 있다(2026-08-16 정리).

```
final_workspace/.tmp/        ← 변환·렌더링 등 워크스페이스 임시물은 전부 여기
```

저장소 안에서 쓰는 스크래치는 저장소 밖 세션 임시 폴더를 쓰고,
**저장소에 커밋되지 않게** 한다. 남기고 싶은 산출물이면 `docs/` 아래 제자리에 둔다.

### 환경 주의사항

- **PostgreSQL 은 Windows 서비스가 아니다.** conda env `pgv` 에서 뜬 프로세스다.
  재부팅 후 안 떠 있을 수 있다 → `docs/manuals/` 참조.
- **Docker 가 설치돼 있지 않다.** `docker/compose.yml` 로 DB 를 띄우는 v6 §13 전제는
  이 기계에서 성립하지 않는다. 로컬 PG 를 쓰고, compose 파일은 재현용으로만 남긴다.
- OpenAI 임베딩 `text-embedding-3-small` = **1536차원** 으로 v6 §22 DDL `vector(1536)` 과 일치한다.
  모델을 바꾸면 **DDL 과 적재분을 함께** 바꿔야 한다.

---

## 6. 자주 쓰는 명령

```powershell
# DB (conda env pgv 의 psql — PATH 에 없다)
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop

# 검증
python -m scripts.verify_dod                  # DoD + evidence 존재 검사
python -m pytest tests/contract -q            # 계약 테스트
python -m pytest tests/security -q            # scope / PII / tenant 격리
python -m pytest -q                           # 전체

# 평가 (v6 §15-7)
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```

---

## 7. 문서

- 프로세스 규칙: `RULE.md` (**작업 전 필독**)
- 기준선 계획: `../program/plan/A-COP_구현계획서_v8.md` (읽기 전용, v6은 `../program/plan/archive/`의 보존본)
- 실행계획: `docs/plans/`
- 계약: `docs/handoff/`
- 리포트: `docs/reports/` · 결함: `docs/reports/debugs/`
- DoD 검증 로그: `docs/evidence/`
- 결정 기록은 **리포트로 남긴다.** 코드 주석만으로는 "왜"가 사라진다.
