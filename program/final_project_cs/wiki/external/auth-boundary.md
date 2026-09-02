---
type: concept
title: Trust Boundary
description: 인증·scope·PII 마스킹. 외부 요청이 내부로 들어오는 유일한 문
status: draft
tags: [security, api]
owners: [human:미배정]
---

# Trust Boundary

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/infrastructure/auth/` · `app/presentation/security.py`

**Agent Gateway가 유일한 진입점이다.** 여기를 통과한 것만 내부로 간다.

## 세 겹

```text
① 인증    이 요청이 누구인가
② scope   이 사람이 이걸 해도 되는가
③ 격리    이 사람의 데이터만 보이는가
```

셋 다 통과해야 한다. **하나라도 빠지면 나머지가 무의미하다.**

## ① 인증

`[실측]` 부분 일치를 막는다.

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-SEC-001` | 유효하지 않은 토큰은 인증되지 않는다 | `tests/security/test_auth_and_scope_guards.py::test_any_seven_character_prefix_must_not_authenticate` |

**테스트 이름이 무엇을 막는지 정확히 말한다.** 앞 7글자만 맞아도 통과하면 안 된다.

`[실측]` dojo가 **Bearer 형식 검사를 지우는 결함**을 심었고 이 테스트가 잡았다.

## ② scope

`[실측]` scope 10개는 guardrail이 소유한다. 코드에 흩어 놓지 않는다.

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-SEC-002` | scope 없는 principal은 거부된다 | `tests/security/test_auth_and_scope_guards.py::test_scope_guard_denies_a_principal_with_no_scopes` |
| `INV-CS-SEC-003` | 다른 scope를 가진 principal도 거부된다 | `tests/security/test_auth_and_scope_guards.py::test_scope_guard_denies_a_principal_holding_another_scope` |
| `INV-CS-SEC-007` | scope 10개는 guardrail이 소유한다 | `tests/security/test_scope_contract.py::test_ten_scopes_are_guardrail_owned` |

**003이 중요하다.** "scope가 있기만 하면 통과"가 아니라 **"맞는 scope여야 통과"**다.

`ScopeDenied` 예외가 `app/core/contracts.py`에 있다.

### 주요 scope

`[실측]` v8 §24가 정한 **네 축**.

| scope | 무엇 |
|---|---|
| `case:read` | 조회 |
| `case:write` | 생성·수정 |
| **`action:approve`** | **승인** |
| `mcp:read` | MCP 도구 3종 |

`+ ops:introspect` 등 총 10개. guardrail이 소유한다.

**읽기와 쓰기와 승인을 나눈 게 핵심이다.** 하나로 묶으면 조회 권한만 주고 싶어도 승인까지 열린다.

### API key 저장

```
tenant · client · scope 와 함께 저장
원문을 로그에 남기지 않는다
```

**환불·구독 변경·권한 변경**은 `action:approve` scope와 **evidence를 확인하고 before/after hash를 audit**한다.

## ③ 격리

**모든 query에 `tenant_id`와 `customer_id`(또는 `case_id`) 조건을 적용한다.**

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-SEC-005` | 같은 tenant 안에서도 customer 간 누출이 없다 | `tests/security/test_query_scope.py::test_case_list_does_not_leak_across_customers_in_one_tenant` |
| `INV-CS-SEC-006` | customer 미지정 조회도 tenant를 벗어나지 않는다 | `tests/security/test_query_scope.py::test_case_list_without_customer_stays_inside_the_tenant` |

**조건 없는 조회 쿼리는 그 자체가 보안 결함이다.**

**006이 미묘하다.** `customer_id`를 안 넘겨도 tenant는 벗어나면 안 된다. 필터가 하나 빠졌을 때 전체가 열리는 걸 막는다.

남의 Case를 요청하면 **404**다. 403이 아니다 — 존재 여부를 알려주지 않는다.

## PII

**원문 PII는 마스킹 후 저장하고, LLM에는 masked text만 전달한다.**

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-SEC-004` | PII는 DB·API·audit 전부에서 마스킹된다 | `tests/security/test_pii_redaction_runtime.py::test_case_message_is_redacted_in_db_api_and_audit` |

**셋을 한 번에 본다.** DB에만 마스킹하고 audit에 원본이 남는 실수를 막는다.

**audit log에 API key 원문·결제 식별자 원문을 기록하지 않는다.** 근거 대조 실패 기록도 값이 아니라 hash를 남긴다.

### ★ 실데이터 규칙

`[실측]` v8 §24 [v7.1]. **실제 고객 데이터를 쓸 때 추가로 지킨다.**

| 규칙 | 왜 |
|---|---|
| 저장·LLM 전달 전 **가명화·마스킹** | 원문이 모델에 들어가면 회수 불가 |
| **join key를 업무 데이터와 분리 보관** | 마스킹해도 조인하면 복원된다 |
| `ContextPack`에 **최소 증거만** | 넣은 만큼 새어 나갈 면적이 는다 |
| 집계 alert에 **재식별 방지 최소 기준** | "그 동네 그 주문" 하나면 특정된다 |
| 골든셋에는 **비식별 fixture와 해시만** | 평가 데이터가 가장 오래 남는다 |

**두 번째가 놓치기 쉽다.** 이름을 가려도 `customer_id`가 그대로면 다른 표와 붙여서 되살릴 수 있다.

### 자유문은 두 가지를 함께 검사한다

**리뷰·문의 자유문**은 `prompt injection`과 **개인정보 포함 여부**를 같이 본다.

**고객이 쓴 문장이 우리 시스템에 대한 지시가 되면 안 된다.**

### 감사에 남기는 것

```
Action approval · provider result · before/after hash · actor
```

**append-only다.** 고치지 않는다.

### redaction.py가 Core 격리의 유일한 예외

`app/core/redaction.py`가 `INV-CS-ARCH-001`(도메인 어휘 금지)의 예외다.

**PII 마스킹은 결제 식별자 모양을 알아야 가릴 수 있다.** 도메인 로직이 아니라 보안 규칙이라 예외로 뒀고, 이유가 코드 주석에 적혀 있다.

`INV-CS-ARCH-004`가 **예외 목록의 크기 자체**를 검사한다. 예외가 늘면 그게 설계 붕괴의 신호다.

## 실패 사례

`[실측]` **인증 전 요청이 500을 냈다.** `os.getenv`로 설정을 읽어서였다. 인증 실패가 401이 아니라 500이면 공격자에게 내부 상태를 알려준다.

`[실측]` **`/ui/composer`가 인증 없이 열려 있었다.** 2026-08-18에 폐기했다.

**둘 다 "설정을 어떻게 읽는가"와 "무엇이 어디 물려 있는가"의 문제였다.** 인증 로직 자체의 버그가 아니었다.

## 관계

- [rest-api.md](rest-api.md) — 쓰기 경로
- [mcp-tools.md](mcp-tools.md) — 읽기 경로
- [a2a-protocol.md](a2a-protocol.md) — 위임 경로
- [../data/tenancy.md](../data/tenancy.md) — 저장 계층 격리
- [../actions/approval.md](../actions/approval.md) — `action:approve`
