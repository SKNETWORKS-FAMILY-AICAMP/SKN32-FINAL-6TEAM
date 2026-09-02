---
type: contract
title: REST API
description: 엔드포인트 5개와 헬스체크. 쓰기는 여기로만 간다
status: draft
tags: [api, contract]
owners: [human:미배정]
---

# REST API

`app/presentation/api/cases.py`

**쓰기는 REST로만 간다.** MCP는 read-only다.

## 엔드포인트

`[실측]`

| 메서드 | 경로 | 무엇 |
|---|---|---|
| `POST` | `/v1/cases` | Case 생성 (문의 접수) |
| `GET` | `/v1/cases` | Case 목록 |
| `GET` | `/v1/cases/{case_id}` | Case 상세 |
| `POST` | `/v1/cases/{case_id}/messages` | 추가 메시지 |
| `POST` | `/v1/cases/{case_id}/actions/{action_id}/approve` | **승인** |

`+ /health`

**MVP 5개가 상한이 아니다.** 필요하면 늘리되 scope와 테스트를 함께 만든다.

## 승인은 REST 전용

**마지막 엔드포인트가 유일한 승인 경로다.** MCP에는 없다.

승인자는 `action:approve` scope가 있어야 한다. → [../actions/approval.md](../actions/approval.md)

`[실측]` **승인 엔드포인트가 읽기 권한으로 열리는 결함**을 dojo가 심어 봤고 테스트 11건이 잡았다.

## Case 생성 시 인라인 분류

`POST /v1/cases`가 감성·의도·이슈 분류를 함께 한다. **선택 기능이 아니다.**

```
분류 성공 → routing
분류 실패 → classification_failed 이벤트 + escalated
```

**조용히 넘어가지 않는다.** `INV-CS-RT-017`

`[실측]` 이 경로에서 실제 결함이 있었다. `feedback.py::INTENTS`가 옛 구독 어휘(`billing`/`technical`)로 남아 있어 **쇼핑몰 Case가 전부 분류 실패로 떨어졌을 것**이다. 재발 방지로 `INTENTS ⊇ 모든 Team.accepted_case_types` 불변조건 테스트가 추가됐다.

## Composer API는 별개다

```
/composer/*    prefix="/composer", tags=["composer-write"]
```

**제작 단계 도구다.** 인증된 경로로만 제공한다.

`[실측]` `/ui/composer`는 2026-08-18에 **폐기**됐다. 인증 없이 고객 접근이 가능한 앱에 물려 있던 것을 실측으로 확인하고 삭제했다.

## 인증

모든 요청이 Agent Gateway를 거친다. **Trust Boundary다.**

| 불변식 | 무엇 |
|---|---|
| `INV-CS-SEC-001` | 유효하지 않은 토큰은 인증되지 않는다 |
| `INV-CS-SEC-002` | scope 없는 principal은 거부된다 |
| `INV-CS-SEC-003` | 다른 scope를 가진 principal도 거부된다 |

`[실측]` **인증 전 요청이 500을 내던 결함**이 있었다. `os.getenv`로 설정을 읽어서였다. 지금은 고쳐졌다.

→ [auth-boundary.md](auth-boundary.md)

## 조회 격리

목록·상세 조회는 tenant와 customer를 벗어나지 않는다.

| 불변식 | 실행 위치 |
|---|---|
| `INV-CS-SEC-005` | `tests/security/test_query_scope.py::test_case_list_does_not_leak_across_customers_in_one_tenant` |
| `INV-CS-SEC-006` | `tests/security/test_query_scope.py::test_case_list_without_customer_stays_inside_the_tenant` |

**남의 Case를 요청하면 404다.** 403이 아니다 — 존재 여부를 알려주지 않는다.

## idempotency

`POST` 계열은 전부 idempotency key를 거친다.

**동일 요청 10회 → `action_requests` 1행.** DoD 항목이다.

→ [../actions/idempotency.md](../actions/idempotency.md)

## 감사

`[실측]` **승인 감사 기록이 대기 큐에 유령 항목으로 남는 결함**이 있었다. 브라우저로 승인 버튼을 여러 번 눌러 발견했다.

```
tests/integration/api/test_approval_audit_row_excluded_from_queue.py
tests/integration/api/test_case_create_audit_row_excluded_from_queue.py
```

**테스트만으로는 안 잡혔다.** UI를 실제로 열어야 나온 결함이다.

---

# 계약 원문에서 보강 (2026-09-03)

`[실측]` `docs/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../wiki/governance/migration-scope/coverage.md).

## `/v1/*` 표면 상한과 scope

`[실측]` 외부 AI용 `/v1/*` endpoint는 정확히 5개다. `/v1/` 아래에 여섯 번째 경로가 생기면 계약 위반이다.

| 메서드 | 경로 | 필수 scope |
|---|---|---|
| `POST` | `/v1/cases` | `case:write` |
| `GET` | `/v1/cases` | `case:read` |
| `GET` | `/v1/cases/{case_id}` | `case:read` |
| `POST` | `/v1/cases/{case_id}/messages` | `case:write` |
| `POST` | `/v1/cases/{case_id}/actions/{action_id}/approve` | `action:approve` |

다음 경로는 5개를 셀 때 제외한다.

| 경로 | 성격 |
|---|---|
| `/health` | 상태 확인 |
| `/ui/*` | 운영 화면 |
| `/openapi.json`, `/docs`, `/redoc` | FastAPI 기본 제공 |

`/ui/*`는 쓰기를 직접 수행하지 않는다. 승인은 `/v1/cases/{case_id}/actions/{action_id}/approve`를 호출한다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:18-45`

## `POST /v1/cases` 요청·응답 필드

`[실측]`

요청:

| 필드 | JSON 타입 | 예시 | 필수 여부 |
|---|---|---|---|
| `request_id` | string | `"req_01"` | `[미확보]` |
| `idempotency_key` | string | `"idem_01"` | `[미확보]` |
| `tenant_id` | string | `"demo"` | `[미확보]` |
| `customer_id` | string | `"cust_01"` | `[미확보]` |
| `message` | string | `"배송완료로 떴는데 상품을 못 받았어요"` | `[미확보]` |
| `channel` | string | `"personal_ai"` | `[미확보]`; `personal_ai \| mcp \| web \| api` 중 하나 |

성공 응답 상태 코드는 `201`이다.

| 응답 필드 | JSON 타입 | 예시 |
|---|---|---|
| `case_id` | string | `"case_01"` |
| `status` | string | `"classifying"` |
| `version` | number | `1` |
| `intent` | string | `"shipping"` |
| `issue_code` | string | `"shipping_delivered_not_received"` |
| `sentiment` | string | `"negative"` |
| `links.self` | string | `"/v1/cases/case_01"` |

`idempotency_key`는 서버가 재계산하며 클라이언트 값은 `request_id` 재료일 뿐이다. 같은 키로 재요청하면 새 Case를 만들지 않고 기존 결과를 그대로 반환한다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:47-67`

## `GET /v1/cases` 쿼리 계약

`[실측]`

| 쿼리 필드 | 필수 | 기본값·제약 |
|---|---:|---|
| `customer_id` | 예 | 호출자의 소유 범위 검사 |
| `status` | 아니오 | `[미확보]` 허용값 |
| `limit` | 아니오 | 기본값 `20`, 최대 `100` |
| `cursor` | 아니오 | `[미확보]` 형식 |

호출자의 tenant·customer 범위 밖 Case를 반환하지 않는다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:68-71`

## `GET /v1/cases/{case_id}` 응답 계약

`[실측]`

| 필드 | 형태·예시 |
|---|---|
| `case_id` | `"case_01"` |
| `status` | `"waiting_approval"` |
| `version` | `7` |
| `answer` | `"환불 요청을 준비했습니다."` |
| `pending_actions[]` | `{"action_id":"a_01","action_type":"refund.request","approval_required":true}` |
| `evidence[]` | `{"source_type":"policy","source_id":"doc_04#c12","claim":"..."}` |

`evidence`는 masked 상태로 반환한다. 원문 PII를 응답에 싣지 않으며, `answer`가 있는데 `evidence`가 비어 있으면 계약 위반이다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:73-84`

## 추가 메시지 resume 제약

`[실측]`

| 항목 | 제약 |
|---|---|
| 상태 전이 | `waiting_input` → `resuming` |
| resume token 저장 | 원문이 아니라 hash만 저장 |
| TTL | `24h` |
| 사용 횟수 | 일회성 |
| 중복 처리 | 동일 `event_id` 재처리는 idempotent |
| TTL 만료 | 자동 진행 금지; `escalated` + 운영자 알림 |

`[미확보]` 원본은 이 endpoint의 요청 body 필드 이름을 밝히지 않는다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:86-90`

## 승인 요청·감사 계약

`[실측]`

요청:

```json
{"decision":"approved","approver_id":"op_01","note":"정책 확인함"}
```

| 필드 | 제약 |
|---|---|
| `decision` | `approved \| rejected` |
| `approver_id` | `[미확보]` 필수 여부·타입 제약 |
| `note` | `[미확보]` 필수 여부·길이 제약 |

승인 event와 before/after hash를 audit에 기록한다. audit에는 API key 원문이나 결제 식별자 원문을 기록하지 않는다. 승인 후 실행은 idempotent해야 하며 동일 요청 10회에 side effect는 1회다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:92-99`

## 오류 응답 계약

`[실측]`

| HTTP | 조건 | `error.code` |
|---:|---|---|
| `400` | 스키마 위반 | `contract_violation` |
| `401` | API key 없음 또는 무효 | `unauthenticated` |
| `403` | scope 부족 또는 ownership 불일치 | `scope_denied` |
| `404` | 존재하지 않거나 볼 권한이 없는 리소스 | `not_found` |
| `409` | optimistic concurrency 충돌 | `state_conflict` |
| `422` | 허용되지 않은 상태 전이 | `invalid_transition` |
| `429` | 일일 비용 또는 호출 상한 | `guardrail_exceeded` |

오류 body에 stack trace·SQL·내부 경로를 넣지 않는다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:101-114`

## 인증 형식

`[실측]`

| 항목 | 계약 |
|---|---|
| MVP 인증 | hashed API key + scope |
| Header | `Authorization: Bearer <api_key>` |
| OAuth2/OIDC | Phase 2; MVP에서 구현하지 않음 |
| scope 검증 | scope × endpoint 전체 unauthorized matrix 테스트 |

근거: `docs/handoff/03_REST_MCP_인터페이스.md:116-121`

## OpenAPI 일치 조건

`[실측]` `/openapi.json`은 계약된 `/v1/*` endpoint 5개와 일치해야 한다.

근거: `docs/handoff/03_REST_MCP_인터페이스.md:150-153`

## `GET /introspection`

`ops:introspect` scope 로 보호되는 read-only API 다. **무엇이 조립돼 있나를 보여주고 얼마나 돌고 있나는 안 보여준다.**

→ [introspection.md](introspection.md)

## 관계

- [mcp-tools.md](mcp-tools.md) — 읽기 전용 경로
- [a2a-protocol.md](a2a-protocol.md) — 업무 위임 경로
- [auth-boundary.md](auth-boundary.md) — 인증·scope·PII
- [../actions/approval.md](../actions/approval.md) — 승인
- [../runtime/case-lifecycle.md](../runtime/case-lifecycle.md) — Case 상태
