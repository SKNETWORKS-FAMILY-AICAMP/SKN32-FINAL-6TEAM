# 03 — REST / MCP 인터페이스

- 개정 이력: 2026-08-12 15:07 최초 작성 (v5 §13)
- 소유: **S-API** (`app/presentation/api/**`, `app/presentation/security.py`)
- 사용: S-UI, S-EVAL, 외부 개인 AI

## 0. 경계 원칙 — 이것이 차별화의 핵심이자 위험 지점

```
개인 AI (ChatGPT/Claude/Gemini)
   ├── MCP (read-only, mcp:read)  ──> 내 Case 읽기 · 지원 Case 열기까지
   └── REST (scope 분리)          ──> 쓰기는 proposal → Human Approval → idempotent action
```

★**MCP 로는 결제·환불·구독 변경·권한 부여를 할 수 없다.** DB/SQL·임의 tool·write action 을 노출하지 않는다.
★쓰기 경로는 반드시 `ActionProposal` → 승인(`action:approve`) → 실행 순서를 지난다.

## 1. REST 엔드포인트 5개

| # | Method | Path | scope | 목적 |
|---:|---|---|---|---|
| 1 | POST | `/v1/cases` | `case:write` | Case 생성 · 분류 시작 |
| 2 | GET | `/v1/cases` | `case:read` | 내 Case 목록 |
| 3 | GET | `/v1/cases/{case_id}` | `case:read` | Case 상세 · 증거 · 상태 |
| 4 | POST | `/v1/cases/{case_id}/messages` | `case:write` | 추가 정보 · resume |
| 5 | POST | `/v1/cases/{case_id}/actions/{action_id}/approve` | `action:approve` | 승인 |

★**5개다.** 편의 endpoint 를 임의로 늘리지 않는다(v5 §3 In 경계).

### 1-0. ★"5개"가 세는 것은 `/v1/*` 뿐이다 (2026-08-12 명확화)

계약이 세는 대상은 **외부 AI 가 쓰는 REST API 표면**, 즉 `/v1/` 로 시작하는 경로다.
다음은 이 5개에 포함되지 않으며 추가해도 위반이 아니다.

| 경로 | 성격 |
|---|---|
| `/health` | 상태 확인 |
| `/ui/*` | **운영 화면**(Case/Trace/Approval/VOC). v5 §3 In 항목이며 S-UI 소유 |
| `/openapi.json`, `/docs`, `/redoc` | FastAPI 기본 제공 |

★단 **`/ui/*` 는 쓰기를 직접 하지 않는다.** 승인은 `/v1/.../approve` 를 호출한다.
★`/v1/` 아래에 6번째 경로가 생기면 그것은 위반이다 — `tests/integration/api/test_openapi_surface.py` 가 검사한다.

> 개정 사유: 최초 계약이 UI 를 고려하지 않아 "path 집합 == 5개 + /health" 로 못박혀 있었고,
> S-UI 라우터를 등록하자 그 테스트가 깨졌다. 세는 대상을 `/v1/*` 로 명확히 한다.

### 1-1. `POST /v1/cases`

요청:
```json
{"request_id":"req_01","idempotency_key":"idem_01","tenant_id":"demo",
 "customer_id":"cust_01","message":"배송완료로 떴는데 상품을 못 받았어요","channel":"personal_ai"}
```

응답 `201`:
```json
{"case_id":"case_01","status":"classifying","version":1,
 "intent":"shipping","issue_code":"shipping_delivered_not_received","sentiment":"negative",
 "links":{"self":"/v1/cases/case_01"}}
```

- `channel` 은 `personal_ai | mcp | web | api` 중 하나.
- ★인라인 분류는 **선택이 아니다.** 실패하면 `classification_failed` 이벤트 + `escalated`
  (v5 §2, `CLAUDE.md` §1). 분류를 건너뛴 채 201 을 돌려주지 않는다.
- ★**응답 필드는 위 일곱 개로 고정이다**(2026-09-01). `run_id`·`next_action`·
  `resume_token` 은 **들어가지 않는다.**

  전에는 이 라우트가 에이전트 실행(`run_case`)까지 기다린 뒤 그 결과를 응답에
  얹었다 — 실측 p50 20~34초 · p95 32~51초. 지금은 실행을 응답 뒤로 떼어냈고
  (v8 §3-A [2026-09-01 교정]), 진행 상황은 **`GET /v1/cases/{case_id}`** 로
  확인한다.

  ★있다가 없다가 하는 필드를 두지 않는 이유: 실행이 아직 안 끝나 필드가 없는
  것과 실행이 실패해 없는 것을 클라이언트가 구분할 수 없다. "없으면 실패" 로
  읽히면 그게 곧 잘못된 안내가 된다.

  ★`status` 는 접수 시점의 값이다(분류 성공이면 `routing`, 실패면 `escalated`).
  그 뒤 상태는 GET 으로 본다.
- ★`idempotency_key` 는 **서버가 재계산**한다(`06` §…, v5 §10-1). 클라이언트 값은 `request_id` 재료일 뿐이다.
  같은 키의 재요청은 **기존 결과를 그대로 반환**한다(새 Case 를 만들지 않는다).

### 1-2. `GET /v1/cases`

- 쿼리: `customer_id`(필수), `status`, `limit`(기본 20, 최대 100), `cursor`
- ★**호출자의 tenant/customer 범위 밖 Case 를 반환하지 않는다.** ownership 검사 필수.

### 1-3. `GET /v1/cases/{case_id}`

응답:
```json
{"case_id":"case_01","status":"waiting_approval","version":7,
 "answer":"환불 요청을 준비했습니다.",
 "pending_actions":[{"action_id":"a_01","action_type":"refund.request","approval_required":true}],
 "evidence":[{"source_type":"policy","source_id":"doc_04#c12","claim":"..."}]}
```

- ★`evidence` 는 **masked** 상태로 나간다. 원문 PII 를 응답에 싣지 않는다.
- `answer` 가 있는데 `evidence` 가 비면 계약 위반이다(`01` §6).

### 1-4. `POST /v1/cases/{case_id}/messages`

- 용도: 고객 추가 정보 제출 → `waiting_input` → `resuming`
- ★resume token 은 **hash 만 저장**. 24h TTL, **일회성**, 동일 `event_id` 재처리 idempotent.
- TTL 만료 요청은 자동 진행이 아니라 **`escalated` + 운영자 알림**.

### 1-5. `POST /v1/cases/{case_id}/actions/{action_id}/approve`

요청: `{"decision":"approved","approver_id":"op_01","note":"정책 확인함"}` (`decision`: `approved|rejected`)

- scope `action:approve` **필수**. 없으면 `403`.
- 승인 event 와 **before/after hash** 를 audit 에 기록한다.
- ★audit 에 **API key 원문·결제 식별자 원문을 기록하지 않는다**(v5 §12).
- 승인 후 실행은 idempotent. **동일 요청 10회 → side effect 1회**(DoD 11).

## 2. 오류 응답 규약

| HTTP | 조건 | body `error.code` |
|---|---|---|
| 400 | 스키마 위반 | `contract_violation` |
| 401 | API key 없음/무효 | `unauthenticated` |
| 403 | scope 부족 · ownership 불일치 | `scope_denied` |
| 404 | 존재하지 않거나 **볼 권한이 없는** 리소스 | `not_found` |
| 409 | optimistic concurrency 충돌 | `state_conflict` |
| 422 | 허용되지 않은 상태 전이 | `invalid_transition` |
| 429 | 일일 비용/호출 상한 | `guardrail_exceeded` |

★**403 과 404 를 구분해 정보를 흘리지 않는다** — 남의 Case 는 존재 사실도 알리지 않고 `404` 로 답한다.
★오류 body 에 stack trace·SQL·내부 경로를 넣지 않는다.

## 3. 인증 · scope

- MVP 인증은 **hashed API key + scope** 다. OAuth2/OIDC 는 **Phase 2**(v5 §3 Out) — 구현하지 않는다.
- header: `Authorization: Bearer <api_key>`
- scope 6종과 경로 매핑은 `06_가드레일_수치.md` §5.
- ★**unauthorized matrix 테스트**(scope × endpoint 전수)를 `tests/security/` 에 둔다. DoD 14 의 근거다.

## 4. MCP read-only 3 tool

FastMCP 서버에 **정확히 3개만** 등록한다.

```python
@mcp.tool()
async def get_my_cases(customer_id: str, limit: int = 20) -> list[dict]: ...

@mcp.tool()
async def get_case_detail(customer_id: str, case_id: str) -> dict: ...

@mcp.tool()
async def open_support_case(customer_id: str, message: str, channel: str = 'mcp') -> dict: ...
```

| 규칙 | 내용 |
|---|---|
| scope | 세 tool 모두 **`mcp:read` 만**. 다른 scope 를 요구하거나 부여하지 않는다 |
| ownership | `customer_id` 소유 검사를 **매 호출** 수행 |
| `open_support_case` | Case **생성과 분류 시작까지**. ★결제·환불·구독 변경을 **하지 않는다** |
| 노출 금지 | DB/SQL 접근, 임의 tool, write action, 내부 evidence 원문(PII) |
| 응답 | REST 와 동일하게 **masked** |

★"read-only 인데 왜 `open_support_case` 가 있나" — Case 생성은 **고객 자신의 문의 접수**이고
업무 side effect(환불·권한 변경)가 아니다. 그래서 read 경계 안이다.
이 구분이 흐려지면 MCP 로 결제를 건드릴 수 있게 된다. **경계를 넓히지 않는다.**

## 5. OpenAPI

- `/openapi.json` 이 위 5개 endpoint 와 **일치**해야 한다(DoD 13).
- ★문서와 구현이 어긋나면 결함이다. `tests/contract/test_openapi_matches_handoff.py` 가 대조한다.

## 6. 검증 (DoD 근거)

```powershell
python -m pytest tests/security -q                      # scope matrix (DoD 14)
python -m pytest tests/integration/api -q               # 5 endpoint + idempotency (DoD 11,13)
python -m pytest tests/contract/test_mcp_scope.py -q    # MCP read-only 경계 (DoD 13)
```
