# S-API REST/MCP 작업 리포트

## 1. 작업 목표

실행계획서 P6의 REST 5개 endpoint, FastMCP read-only 3개 tool, API key hash/scope 인증, tenant/customer 격리, 상태 전이 단일 진입점, 서버 계산 idempotency를 구현했다.

## 2. 만든 파일 목록

- `app/presentation/security.py`
- `app/presentation/api/app.py`
- `app/presentation/api/cases.py`
- `app/presentation/api/mcp.py`
- `tests/security/test_scope_contract.py`
- `tests/integration/api/test_openapi_surface.py`

상태 변경은 `create_case()` 뒤 `transition_case()`만 호출한다. `customer_cases`와 `case_events`의 직접 변경 코드는 추가하지 않았다.

## 3. unauthorized matrix

`200`은 해당 scope가 요구되는 정상 인증 요청, `403`은 인증은 됐지만 scope가 없는 요청이다. 다른 tenant/customer의 case는 scope가 맞아도 `404 not_found`다.

| API key scope | POST cases | GET cases | GET detail | POST messages | POST approve | MCP 3 tools |
|---|---:|---:|---:|---:|---:|---:|
| case:read | 403 | 200 | 200 | 403 | 403 | 403 |
| case:write | 200 | 403 | 403 | 200 | 403 | 403 |
| subscription:read | 403 | 403 | 403 | 403 | 403 | 403 |
| technical:read | 403 | 403 | 403 | 403 | 403 | 403 |
| action:approve | 403 | 403 | 403 | 403 | 200 | 403 |
| mcp:read | 403 | 403 | 403 | 403 | 403 | 200 |

MCP tool metadata에는 세 tool 모두 `required_scope=mcp:read`만 기록했다. 공개 tool은 정확히 3개이며 write action/SQL tool은 없다.

## 4. 검증 명령과 실제 출력

### `python -m pytest tests/security -q`

```text
..                                                                       [100%]
2 passed, 1 warning in 0.97s
```

### `python -m pytest tests/integration/api -q`

```text
.                                                                        [100%]
1 passed, 1 warning in 0.69s
```

### `python -m pytest tests -q`

```text
............................................................             [100%]
60 passed, 1 warning in 1.79s
```

### `python -m scripts.check_env`

```text
[OK  ] python              3.12.7
[OK  ] settings(.env)      env=dev tenant=demo model=gpt-4o-mini
[OK  ] openai key          len=164
[OK  ] guardrails 로드       guardrails.yaml (token_budget=12000)
[OK  ] 토큰 예산 정합            섹션 합 12000 vs token_budget 12000
[OK  ] 임베딩 차원              1536 (DDL vector(1536) 과 일치해야 함)
[OK  ] PostgreSQL 연결       PostgreSQL 16.14
[OK  ] extension vector    설치됨
[OK  ] extension pgcrypto  설치됨
[OK  ] 테이블                 public 스키마 18개
[OK  ] v4 원본 존재            sha256=b675556cf4d72e64... (21790 bytes)
실패 0건 / 전체 11건
```

### tenant count

```text
tenants=1
```

### test-only tenant idempotency smoke test

동일 요청 10회 모두 `201`을 반환했고, 테스트 tenant teardown 후 집계했다.

```text
same_request_statuses=201,201,201,201,201,201,201,201,201,201
action_requests=1
case_events=2
```

## 5. S-DB에 요청할 것

- 운영용 `api_keys` 테이블: `tenant_id`, `key_id`, `key_hash`, scope 배열/관계, active, created/expired timestamps, rotation metadata.
- 승인/재요청 결과를 별도 명시적으로 보존할 필요가 있으면 action approval idempotency 저장 컬럼 또는 결과 참조.
- API 계층이 migration을 만들지 않았으므로 S-DB 소유로 schema/migration을 추가할 것.

## 6. 미해결 이슈

- S-VOC 분류기(`app/modules/customer_ops/feedback.py`)가 아직 없어 기본 생성 경로는 의도적으로 `classification_failed → escalated`로 남긴다. 주입 classifier가 제공되면 세 필드(`intent`, `issue_code`, `sentiment`)를 검증해 `classified`로 전이한다.
- 현재 개발 인증키는 `.env`의 `ACOP_API_KEY_HASHES`와 scope 설정을 사용한다. 운영 API key 테이블 연동은 S-DB 이후 작업이다.
- MCP 호출 인증은 FastMCP transport의 인증 컨텍스트가 연결될 때까지 설정된 tenant와 `mcp:read` 검사를 사용한다. OAuth2/OIDC는 구현하지 않았다.
