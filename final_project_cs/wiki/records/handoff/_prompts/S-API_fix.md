# Codex 작업 지시 — S-API **수정**: API 가 전혀 동작하지 않는다

## 0. 판정 결과

**통과한 것 (그대로 두어라):**
- route 가 정확히 5개 + `/health` — `/openapi.json` 확인함
- MCP tool 이 정확히 3개이고 `required_scope` 가 전부 `mcp:read`
- 테스트 후 `tenants=1` (격리 유지됨)

**거부 — ★API 가 실행되지 않는다:**

### 결함 1 (치명) — 설정을 `os.getenv` 로 읽어서 인증이 항상 500 이다

`app/presentation/security.py:26`

```python
tenant = os.getenv("ACOP_TENANT_ID")
...
raise RuntimeError("ACOP_TENANT_ID is required")
```

★**`.env` 는 `os.environ` 에 들어가지 않는다.** `app/core/settings.py` 의 pydantic-settings 가
`Settings` 객체로 읽는다. 실측:

```
os.environ 에 ACOP_ 키: []
_configured_keys() -> RuntimeError: ACOP_TENANT_ID is required
GET /v1/cases (Bearer bogus) -> 500
```

**인증이 필요한 모든 요청이 500 이다. 5개 endpoint 중 어느 것도 성공한 적이 없다.**
`RULE.md` §3.1 이 정한 설정 단일 진입점(`app/core/settings.py`)을 우회한 결과다.

**고치는 법**: `os.getenv` 를 전부 없애고 `app.core.settings.get_settings()` 를 쓴다.
API key 관련 필드가 `Settings` 에 없으면 — `app/core/settings.py` 는 **당신 소유가 아니므로**
직접 고치지 말고, `.env` 에서 읽을 필드 이름을 리포트에 적고
**`get_settings()` 에 이미 있는 것만으로 동작하도록** 구성하라
(`tenant_id`, `secret_key` 는 이미 있다). 개발용 키는 `secret_key` 로 파생시켜도 된다.

### 결함 2 (치명) — 오류 응답이 렌더링되지 않는다

```
TypeError: '<' not supported between instances of 'dict' and 'int'
  starlette/responses.py:72 in init_headers
```

`HTTPException` 의 `detail` 에 dict 를 넣고, 예외 핸들러에서 그 dict 를 **status_code 자리**로
넘기고 있다. 그래서 **403/404/409 를 내려 하면 500 이 된다.**

`wiki/records/handoff/03_REST_MCP_인터페이스.md` §2 의 오류 표대로 body 를
`{"error": {"code": "...", "message": "..."}}` 로 만들되, **status_code 는 정수**여야 한다.

### 결함 3 — 테스트가 정적 단언 3건뿐이다

| 계약이 요구한 것 | 현재 |
|---|---|
| unauthorized matrix (scope 6 × endpoint) 전수 | **없음** |
| 동일 요청 10회 → `action_requests` 1행 (DoD 11) | **없음** |
| 남의 Case 조회 → 404 (403 아님) | **없음** |
| MCP 가 write action 을 노출하지 않음 (동작 검증) | 이름·메타데이터만 확인 |
| `/openapi.json` path 집합 | 있음 ✅ |

★현재 3개 테스트는 **HTTP 호출도 DB 접근도 하지 않는다.** 그래서 결함 1·2 를 못 잡았다.
**돌아가는 것을 증명하지 못하는 테스트는 통과로 세지 않는다**(RULE.md §1.2).

## 1. 소유 범위

```
app/presentation/**        ← 수정 대상
tests/security/**
tests/integration/api/**
wiki/records/reports/ , wiki/records/history/
```

★`app/core/**`, `app/domain/**`, `app/infrastructure/**`, `knowledge/**`, `scripts/**` **금지**.
특히 `knowledge/` 는 **지금 다른 세션이 작업 중이다. 절대 열지 마라.**

## 2. 할 일

1. **결함 1 수정** — `os.getenv` 전부 제거, `get_settings()` 사용
2. **결함 2 수정** — 오류 응답이 실제로 403/404/409/422 로 나가게
3. **테스트 보강** — 아래를 **실제 HTTP 호출로** 검증:

   a. **unauthorized matrix**: scope 6종 각각을 가진 key 로 5개 endpoint + MCP 3 tool 을 호출해
      기대 status(200/201/403/404)를 전수 검사. 표를 테스트 코드에 두고 `parametrize` 한다

   b. **idempotency (DoD 11)**: 같은 요청 **10회** → `action_requests` **1행**.
      DB 를 직접 세어 확인한다

   c. **소유권 (DoD 14)**: 다른 customer 의 case_id 로 `GET /v1/cases/{id}` → **404**
      (403 이면 존재를 알리는 것이라 실패다)

   d. **MCP 경계 (DoD 13)**: `open_support_case` 가 Case 를 만들되
      **결제·환불·구독 변경을 하지 않음**을 DB 로 확인
      (`action_requests`·`payments`·`subscriptions` 가 변하지 않아야 한다)

   e. **정상 경로**: `POST /v1/cases` → 201 + `status='classifying'`(또는 분류 실패 시 escalated),
      `GET /v1/cases/{id}` → 200

★테스트는 **테스트 전용 tenant**를 쓰고 teardown 에서 자기 행을 지운다.
`demo` tenant 를 오염·삭제하지 마라. `tests/integration/db/` 방식을 그대로 따른다.

## 3. 완료 조건

```powershell
python -m pytest tests -q
python -m pytest tests/security tests/integration/api -q
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

★기존 57건이 계속 통과해야 하고, `tenants=1` 이어야 한다.
★**테스트 수가 늘어야 한다.** matrix 전수면 수십 건이 된다.

그리고 **직접 서버를 띄워 한 번 호출해 봐라.** 리포트에 출력을 붙여라:

```powershell
Start-Process -NoNewWindow python -ArgumentList "-m","uvicorn","app.presentation.api.app:app","--port","8010"
Start-Sleep 3
curl.exe -s -o NUL -w "health=%{http_code}\n" http://127.0.0.1:8010/health
curl.exe -s -o NUL -w "noauth=%{http_code}\n" "http://127.0.0.1:8010/v1/cases?customer_id=cust_01"
curl.exe -s -o NUL -w "badkey=%{http_code}\n" -H "Authorization: Bearer bogus" "http://127.0.0.1:8010/v1/cases?customer_id=cust_01"
```

기대: `health=200`, `noauth=401`, `badkey=401` (**500 이면 안 고쳐진 것이다**)

## 4. 리포트

`wiki/records/reports/2026-08-12_S-API_수정_리포트.md` — 결함 1·2·3 대응, §3 명령의 **실제 출력 원문**,
unauthorized matrix 표, `app/core/settings.py` 에 추가가 필요한 필드 목록.
`wiki/records/history/2026-08-12_S-API_fix.md` 이력 추가.

## 5. 하지 말 것

- ❌ `os.getenv` 로 설정 읽기
- ❌ `app/core/**` 수정 (필요하면 리포트에 요청)
- ❌ `knowledge/` 열기 (다른 세션 작업 중)
- ❌ HTTP 를 타지 않는 정적 단언으로 테스트 채우기
- ❌ 인증 실패를 통과시키는 개발모드 우회
- ❌ 서버를 실제로 띄워보지 않고 "동작함" 이라고 쓰기
