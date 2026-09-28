# Codex — 스트림 S-CTRL (Controller · WAIT/RESUME · Outbox Worker)

이 스트림이 **모든 조각을 이어 붙여 end-to-end 를 완성**한다. v5 §5-4, §6-3, §6-4, §10.

## 0. 먼저 읽을 것
1. `RULE.md` §3.1 §3.2 §3.4
2. `CLAUDE.md` ★§0.2(승인 없이 실행 안 함) ★§0.3(상태는 `transition_case()` 로만) §3
3. `wiki/records/handoff/01_계약_Pydantic.md` · `04_Team_모듈_계약.md` · `06_가드레일_수치.md` **§2 §6 §7**
4. **구현 완료 (읽어라. 절대 고치지 마라):**
   - `app/core/transition.py` — `transition_case()`, `replay_case()`, `OutboxMessage`
   - `app/domain/events.py` — 전이표 · `REQUIRED_PAYLOAD_KEYS`
   - `app/domain/case.py` — 순수 리듀서
   - `app/core/context.py` — `ContextBroker`, `ContextInputs`, `PolicyChunk`
   - `app/core/contracts.py` — 계약·예외
   - `app/modules/customer_ops/{billing,technical}.py` — 두 TeamModule (`tools`, `llm` 주입)
   - `app/tools/` — ReadToolbox
   - `app/infrastructure/rag/retriever.py` — `search_policy()`
   - `app/infrastructure/db/{session,repository}.py`
   - `app/presentation/api/**` — REST 5 + MCP 3
5. `../A-COP_구현계획서_v5.md` §4-3, §5, §6, §10 — 읽기 전용, **수정 금지**

## 1. 소유 범위
```
app/application/controller.py
app/application/case_service.py
app/core/registry.py                  ← Team Registry (없으면 만든다)
app/infrastructure/messaging/**       (outbox.py, worker.py, ports)
scripts/run_outbox_worker.py
tests/integration/controller/**
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **금지**. 특히 §0-4 의 파일들. `eval/**`, `app/presentation/ui/**` 는 **다른 세션 작업 중**이다.
`app/application/feedback_job.py` 도 다른 스트림 소유다 — 건드리지 마라.

## 2. 만들 것

### 2-1. Team Registry (`app/core/registry.py`)
- `TeamManifest` 로 등록/조회. `capability` → Team 해석
- ★`supported_contract_versions` 확인. 같은 major 의 optional field 추가만 호환 (v5 §7-4)
- ★Registry 는 **Team 내부를 import 하지 않는다.** 주입받아 등록한다
  (`app/core/` 가 `app.modules` 를 import 하면 격리 테스트가 깨진다 — 지금 위반 0건이다)

### 2-2. Controller (`app/application/controller.py`)
Case 한 건의 실행 루프:
```
routing → ContextBroker.build() → Team.execute() → TeamResult merge → transition_case()
```
- ★**상태 변경은 전부 `transition_case()`.** `customer_cases` 직접 UPDATE 금지
- ★`StateConflict` 시 **최신 Case 를 읽어 최대 2회 재계산** (`06` §7)
- ★같은 Case 에 **active run 1개만**
- `TeamResult.next_action` → 이벤트 매핑:
  | next_action | EventType |
  |---|---|
  | respond | `COMPLETED` |
  | wait_for_input | `MISSING_INPUT` |
  | wait_for_approval | `APPROVAL_REQUIRED` (+ `action_requests` 행 생성) |
  | handoff | 다음 Team 으로 재라우팅 |
  | escalate | `GUARDRAIL_ESCALATED` 또는 `RETRY_EXHAUSTED` |
- ★가드레일 (`06` §2): graph 12 step / Team task 6 / tool call 12 / Case wall-clock 180초 /
  Team timeout 90초. 초과 → `escalated`
- ★ContextBroker 에 넘길 `policy_chunks` 는 `search_policy()` 결과.
  **검색이 예외를 던지면 `retrieval_failed=True`** 로 넘긴다 (삼키지 마라)

### 2-3. WAIT / RESUME (v5 §5-4)
- `wait_reason`: `customer_input | human_approval | external_callback`
- `resume_node`: `validate_input | execute_approved_action | verify_external_result`
- ★resume token: **평문 저장 금지, hash 만**. TTL **24시간**, **일회성**,
  동일 `event_id` 재처리 idempotent (`06` §6)
- ★TTL 만료는 자동 종료가 **아니라** `escalated` + 운영자 알림

### 2-4. Outbox Worker (`app/infrastructure/messaging/`)
- `MessageBrokerPort` 구현체 `OutboxBrokerAdapter` (`01` §9)
- worker claim: `SELECT ... FOR UPDATE SKIP LOCKED`, `available_at`/`attempts`/`dedupe_key` 기준
- 실패 row → **dead-letter 상태**로 남긴다 (삭제 금지)
- ★provider timeout 을 **성공으로 추정하지 마라** → `unknown`, 자동 재실행 금지
- `python -m scripts.run_outbox_worker --once` 로 1회 처리 가능해야 한다
- ❌ `RedisStreamsAdapter` **본체를 만들지 마라** (Phase 2, v5 §3 Out). Port 만 유지

### 2-5. LangGraph checkpoint 분리 (v5 §6-3)
- checkpoint 에는 `case_id`·`run_id`·`graph_revision`·`node_name` + 최소 runtime state 만
- ★**checkpoint rollback 으로 업무 상태를 되돌리지 마라.** 권위는 `customer_cases` projection
- graph revision 은 run 시작 시 고정

## 3. 테스트 (`tests/integration/controller/`)
1. ★**end-to-end 시나리오 1** — 해지 후 추가 결제:
   Case 생성 → classifying → routing → Billing Team → `waiting_approval` →
   REST approve → `resuming` → `running` → `resolved`
2. ★**end-to-end 시나리오 2** — Free/Pro 권한 불일치: Technical Team → 진단·절차 응답 → `resolved`
3. ★**replay 동치성** — projection 을 지우고 `replay_case()` 로 재생 → **동일 상태·version**
4. ★**outbox 원자성** — transition 중 예외를 주입해 롤백되면 `case_events`·`outbox` **둘 다 없음**
5. ★**outbox 중복 차단** — 같은 `(topic, dedupe_key)` 2회 → 행 1개, worker 전달 1회
6. ★**resume token** — 재사용 시 거부 / TTL 만료 시 `escalated`
7. ★**loop guard** — 동일 tool 2회 반복 → `escalated`
8. ★**동시 전이 경합** — 같은 `expected_version` 2요청 → 1 성공 1 `StateConflict`
- ★LLM 은 **fake 주입**으로 결정적으로. 실제 호출 금지
- ★`pytest.skip` 금지 — 데이터 없으면 **fail**
- ★테스트 전용 tenant, teardown 에서 삭제. `demo` 를 지우지 마라

## 4. 완료 조건 (실제로 돌리고 출력을 붙인다)
```powershell
python -m pytest tests -q                       # 기존 96건 계속 통과 + skip 0
python -m pytest tests/integration/controller -v
python -m scripts.run_outbox_worker --once
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select status||'='||count(*) from customer_cases group by status"
```
기대: 전부 통과, **skipped 0**, `tenants=1`.

## 5. 리포트
`wiki/records/reports/2026-08-12_S-CTRL_리포트.md` — §4 **실제 출력 원문**,
두 시나리오의 **상태 전이 순서(status·version 목록)**, outbox 원자성/중복 테스트 결과.
`wiki/records/history/2026-08-12_S-CTRL.md` 이력 추가.

## 6. 하지 말 것
- ❌ `customer_cases` 직접 UPDATE / `case_events` 변경·삭제
- ❌ §0-4 의 완료 파일 수정
- ❌ `app/core/` 에서 `app.modules` import (격리 위반)
- ❌ resume token 평문 저장 / 재사용 허용
- ❌ provider timeout 을 성공으로 처리
- ❌ `RedisStreamsAdapter` 본체 구현
- ❌ 검색 실패를 빈 리스트로 삼키기
- ❌ `pytest.skip`
- ❌ 명령을 돌리지 않고 "동작함"
