# Codex 작업 지시 — 스트림 S-API (REST 5 + MCP read-only 3 + scope)

당신은 A-COP 프로젝트의 **S-API 스트림**을 담당한다.

## 0. 먼저 읽을 것 (필수)

1. `RULE.md` — §3.1(하드코딩 금지) · §3.2(폴백 금지) · §3.3(YAGNI) · §3.4(리포트 의무)
2. `CLAUDE.md` — ★§0.2(승인 없이 실행하지 않는다) · §0.3(상태는 transition_case 로만) · §1(tenant 격리·PII)
3. `wiki/records/handoff/03_REST_MCP_인터페이스.md` — ★**이번 작업의 계약**
4. `wiki/records/handoff/06_가드레일_수치.md` §5(scope 매핑) · §2(가드레일)
5. `wiki/records/handoff/01_계약_Pydantic.md` — 계약 모델
6. **이미 구현돼 있는 것 (읽어라. 고치지 마라):**
   - `app/core/contracts.py` — 계약·예외
   - `app/core/transition.py` — ★`transition_case()` **상태 변경의 유일한 진입점**
   - `app/domain/events.py` — 이벤트·전이표 · `REQUIRED_PAYLOAD_KEYS`
   - `app/core/settings.py` — `get_settings()`, `get_guardrails()`
   - `app/infrastructure/db/session.py`, `repository.py` — 연결·저장소
7. `../A-COP_구현계획서_v5.md` §12(보안), §13(외부 AI 연동) — 읽기 전용. **수정 금지**

## 1. 소유 범위 — 여기에만 쓴다

```
app/presentation/api/**          (cases.py, actions.py, mcp.py, app.py 등)
app/presentation/security.py
tests/security/**
tests/integration/api/**
wiki/records/reports/ , wiki/records/history/    (자기 리포트만)
```

★`app/core/**`, `app/domain/**`, `app/infrastructure/**`, `knowledge/**`, `scripts/**` 를
**건드리지 마라.** 다른 스트림이 동시에 작업 중이다.

## 2. 만들 것

### 2-1. REST 5 endpoint (`wiki/records/handoff/03` §1) — **정확히 5개**

| Method | Path | scope |
|---|---|---|
| POST | `/v1/cases` | `case:write` |
| GET | `/v1/cases` | `case:read` |
| GET | `/v1/cases/{case_id}` | `case:read` |
| POST | `/v1/cases/{case_id}/messages` | `case:write` |
| POST | `/v1/cases/{case_id}/actions/{action_id}/approve` | `action:approve` |

★**편의 endpoint 를 늘리지 마라.** v5 §3 In 경계다. (`/health` 는 예외로 허용)

요청·응답 JSON 형태는 `wiki/records/handoff/03` §1-1~1-5 예시 그대로.

### 2-2. 인증·scope (`app/presentation/security.py`)

- `Authorization: Bearer <api_key>` · **API key 는 hash 로 저장**한다 (평문 저장 금지)
- scope 6종은 `get_guardrails().get("security.scopes")` 에서 읽는다. ★**하드코딩 금지**
- scope 부족 → `403 scope_denied`
- ★**남의 Case 는 존재 사실도 알리지 않는다** → `404 not_found` (403 과 구분해 정보를 흘리지 마라)
- ★오류 body 에 stack trace·SQL·내부 경로를 넣지 마라
- OAuth2/OIDC 는 **Phase 2 다. 구현하지 마라**(v5 §3 Out)

API key 를 담을 테이블이 필요하면 `app/infrastructure/db/` 는 당신 소유가 아니므로
**마이그레이션을 만들지 말고**, 리포트에 "S-DB 에 이런 테이블이 필요하다"고 적어라.
그 전까지는 `.env` 기반 개발용 키 로딩으로 두되 **평문 비교를 하지 말고 hash 비교**를 하라.

### 2-3. ★상태 변경은 `transition_case()` 로만

```python
from app.core.transition import transition_case, OutboxMessage
from app.domain.events import EventType
```

- Case 생성: `repository.create_case(...)` (status='new', version=0) → `transition_case(EventType.CREATED)`
- ★**`customer_cases` 를 직접 UPDATE 하지 마라.** 이건 이 프로젝트의 1순위 규칙이다
- `StateConflict` → `409 state_conflict` / `InvalidTransition` → `422 invalid_transition`
- 호출자가 `with conn.transaction():` 으로 경계를 잡는다 (`transition_case` 는 commit 하지 않는다)

### 2-4. ★idempotency (v5 §10-1, DoD 11)

```
idempotency_key = sha256(tenant_id + request_id + action_type + business_subject)
```

- ★**서버가 재계산**한다. 클라이언트가 준 값을 그대로 믿지 마라
- `action_requests` 의 `UNIQUE(tenant_id, idempotency_key)` 가 실체다
- 같은 키의 재요청은 **새로 만들지 않고 기존 결과를 반환**한다
- ★**동일 요청 10회 → side effect 1회**. 테스트로 증명해라

### 2-5. 인라인 분류 자리 (★건너뛰지 마라)

`POST /v1/cases` 는 Case 생성 후 **반드시 분류를 시도**한다(v5 §2).
분류기 본체는 **S-VOC 스트림이 만든다**(`app/modules/customer_ops/feedback.py`).
아직 없으므로 다음과 같이 한다:

- 분류 함수를 **주입 가능한 의존성**으로 두고, 없으면 `classification_failed` 이벤트 + `escalated`
- ★**분류를 건너뛴 채 201 을 돌려주지 마라.** 조용한 스킵 금지
- 분류가 되면 `EventType.CLASSIFIED` payload 에 `intent`/`issue_code`/`sentiment` 3개 전부

### 2-6. MCP read-only 3 tool (`app/presentation/api/mcp.py`)

FastMCP 로 **정확히 3개**: `get_my_cases`, `get_case_detail`, `open_support_case`

- 세 tool 모두 **`mcp:read` 만** 요구. 다른 scope 를 요구하거나 부여하지 마라
- ★`open_support_case` 는 **Case 생성·분류 시작까지**. 결제·환불·구독 변경을 **하지 않는다**
- ★DB/SQL 접근·임의 tool·write action 을 노출하지 마라
- `customer_id` **소유 검사를 매 호출** 수행
- 응답은 REST 와 동일하게 **masked**

### 2-7. 테스트

`tests/security/` — ★**unauthorized matrix**: scope 6종 × endpoint 5개(+MCP 3) 전수.
각 조합이 200/403/404 중 무엇이어야 하는지 표로 두고 전부 검사한다 (DoD 14)

`tests/integration/api/` —
1. 5개 endpoint 정상 경로
2. ★**동일 요청 10회 → action_requests 1행** (DoD 11)
3. ★**남의 Case 조회 → 404** (403 아님)
4. ★**MCP 3 tool 이 mcp:read 만 쓰고, write action 이 노출되지 않음** (DoD 13)
5. `/openapi.json` 의 path 집합이 **정확히 5개 + /health** 임을 검사

★**테스트는 테스트 전용 tenant 를 쓰고 teardown 에서 자기 행을 지운다.**
`demo` tenant 데이터를 지우지 마라 — seed 다. (S-DB 가 이미 이 방식을 쓴다. `tests/integration/db/` 참고)

## 3. 환경

- PostgreSQL 16.14 `127.0.0.1:5433` DB `acop` (스키마·seed 적재 완료)
- `python -m scripts.check_env` 로 확인
- 서버 기동은 `uvicorn`. 포트는 **8000 이 아닌 8010** 을 기본으로 (다른 프로젝트와 충돌 회피),
  ★**하드코딩하지 말고** `.env` 의 값을 읽되 없으면 기본 8010

## 4. 완료 조건 — 실제로 실행하고 출력을 리포트에 붙인다

```powershell
python -m pytest tests -q                    # 전체. 기존 57건이 계속 통과해야 한다
python -m pytest tests/security -q
python -m pytest tests/integration/api -q
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

★마지막 명령이 **`tenants=1`** 이어야 한다 (테스트 격리 확인).

## 5. 리포트

`wiki/records/reports/2026-08-12_S-API_REST_MCP_리포트.md`:
1. 작업 목표 — 실행계획서 P6
2. 만든 파일 목록
3. **§4 명령의 실제 출력 원문**
4. unauthorized matrix 표 (scope × endpoint × 기대 응답)
5. S-DB 에 요청할 것 (API key 테이블 등)
6. 미해결 이슈

`wiki/records/history/2026-08-12_S-API.md` 이력 추가.

## 6. 하지 말 것

- ❌ `customer_cases` 직접 UPDATE / `case_events` 변경
- ❌ endpoint 5개 초과 (`/health` 제외)
- ❌ MCP 에 write action·DB 접근 노출
- ❌ scope·포트·키를 코드에 하드코딩
- ❌ 인증 실패 시 통과시키는 폴백 / 개발모드 우회
- ❌ 403 이어야 할 곳에 200, 404 여야 할 곳에 403
- ❌ 분류를 건너뛴 채 Case 생성 성공 반환
- ❌ 소유 범위 밖 파일 수정
- ❌ 테스트가 `demo` tenant 를 오염·삭제
- ❌ 테스트를 돌리지 않고 "동작함" 이라고 쓰기
