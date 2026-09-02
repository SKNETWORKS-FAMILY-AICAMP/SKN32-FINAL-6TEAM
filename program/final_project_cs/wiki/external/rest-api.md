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

## 관계

- [mcp-tools.md](mcp-tools.md) — 읽기 전용 경로
- [a2a-protocol.md](a2a-protocol.md) — 업무 위임 경로
- [auth-boundary.md](auth-boundary.md) — 인증·scope·PII
- [../actions/approval.md](../actions/approval.md) — 승인
- [../runtime/case-lifecycle.md](../runtime/case-lifecycle.md) — Case 상태
