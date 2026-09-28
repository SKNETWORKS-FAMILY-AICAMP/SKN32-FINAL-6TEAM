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

## 1. REST 엔드포인트 6개 (2026-08-17: unknown 처리 1건 추가)

| # | Method | Path | scope | 목적 |
|---:|---|---|---|---|
| 1 | POST | `/v1/cases` | `case:write` | Case 생성 · 분류 시작 |
| 2 | GET | `/v1/cases` | `case:read` | 내 Case 목록 |
| 3 | GET | `/v1/cases/{case_id}` | `case:read` | Case 상세 · 증거 · 상태 |
| 4 | POST | `/v1/cases/{case_id}/messages` | `case:write` | 추가 정보 · resume |
| 5 | POST | `/v1/cases/{case_id}/actions/{action_id}/approve` | `action:approve` | 승인 |
| 6 | POST | `/v1/outbox/{message_id}/resolve` | `action:approve` | `unknown` outbox 를 사람이 결론짓는다 |

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
 "customer_id":"cust_01","message":"해지했는데 결제가 됐어요","channel":"personal_ai"}
```

응답 `201`:
```json
{"case_id":"case_01","status":"classifying","version":1,
 "intent":"billing","issue_code":"post_cancel_charge","sentiment":"negative",
 "links":{"self":"/v1/cases/case_01"}}
```

- `channel` 은 `personal_ai | mcp | web | api` 중 하나.
- ★인라인 분류는 **선택이 아니다.** 실패하면 `classification_failed` 이벤트 + `escalated`
  (v5 §2, `CLAUDE.md` §1). 분류를 건너뛴 채 201 을 돌려주지 않는다.
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

요청: `{"request_id":"req_01","message":"환불 계좌는 국민은행입니다","token":"<발급받은 resume token>"}`

- 용도: 고객 추가 정보 제출 → `waiting_input` → 검증 통과 시 재실행까지 한 번에 끝난다
- ★**버그사냥 2026-08-17 (라운드 04·06·08) — `token` 필드는 실제로 검증한다.**
  이전엔 `message` 원문을 해시해 `resume_token_hash` 라고 이름만 붙였을 뿐, Case 가
  `waiting_input` 이 될 때 실제 발급된 토큰(`resume_token`, 원래 요청의 API 응답
  또는 별도 채널로 전달됨)과 대조하지 않았다 — `case:write` scope 만 있으면
  진짜 토큰 없이도 대기 Case 를 재개시킬 수 있었다. 지금은 `Controller.resume()`
  이 `token` 을 hash·만료·일회성 전부 검증한 뒤에만 진행한다
  (`wiki/records/reports/debugs/2026-08-17_버그사냥_08_미해결3건_처리.md`).
- resume token 은 **hash 만 저장**. 24h TTL, **일회성**, 동일 `request_id`
  (내부적으로 `event_id`) 재처리는 idempotent — 같은 응답을 그대로 돌려주고
  다시 실행하지 않는다.
- 틀린 토큰·만료된 토큰·이미 쓴 토큰은 **`401 invalid_resume_token`** 이고,
  그 Case 는 `escalated` 로 전환된다(사람이 확인해야 한다 — 자동 재시도 없음).
- `expected_version` 필드는 더 이상 없다 — `Controller.resume()` 이 매번 최신
  버전을 스스로 다시 읽어 처리하므로 클라이언트가 버전을 추측해 넘길 필요가 없다.

### 1-5. `POST /v1/cases/{case_id}/actions/{action_id}/approve`

요청: `{"decision":"approved","approver_id":"op_01","note":"정책 확인함"}` (`decision`: `approved|rejected`)

- scope `action:approve` **필수**. 없으면 `403`.
- 승인 event 와 **before/after hash** 를 audit 에 기록한다.
- ★audit 에 **API key 원문·결제 식별자 원문을 기록하지 않는다**(v5 §12).
- 승인 후 실행은 idempotent. **동일 요청 10회 → side effect 1회**(DoD 11).

### 1-6. `POST /v1/outbox/{message_id}/resolve`

`outbox.status='unknown'`(provider timeout, `CLAUDE.md` §0.2) 을 사람이 결론짓는
유일한 경로. `/ops/outbox` 화면이 내부적으로 이걸 부른다.

요청: `{"resolution":"confirmed_delivered|confirmed_not_delivered|requeue","note":"...","resolved_by":"op_01"}`

- scope `action:approve` **재사용** — 새 scope 를 만들지 않는다. 불확실한
  side effect 를 사람이 결론짓는 것도 승인과 같은 급의 책임이기 때문이다.
- `note` 가 비어 있으면 `422`. **근거 없는 처리를 만들지 않는다.**
- `resolution=requeue` 만 재발행(`status='pending'`, `available_at=now()`) 한다.
  나머지 둘은 `status='resolved'` 로 끝난다 — **자동 재시도가 없다.**
- 대상 행이 있지만 `status != 'unknown'`(이미 처리됨 포함) 이면 `409`.
  행이 없거나 남의 tenant 것이면 `404` — 이 둘을 구분해 정보를 흘리지 않는다.
- 계약: `wiki/records/handoff/_prompts/S-UNKNOWN-OPS-SCREEN.md`, 런북:
  `wiki/records/manuals/2026-08-17_unknown_처리_런북.md`

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
