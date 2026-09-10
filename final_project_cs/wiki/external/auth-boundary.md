---
type: concept
title: Trust Boundary
description: 인증·scope·PII 마스킹. 외부 요청이 내부로 들어오는 유일한 문
status: draft
tags: [security, api]
owners: [human:미배정]
domain: neutral
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

`[실측 2026-09-10]` scope **12개**는 guardrail이 소유한다(`config/guardrails.yaml` `security.scopes`, `tests/security/test_scope_contract.py` 가 집합으로 검사). `[정정]` 이 줄은 10개로 적혀 있었다 — 같은 문서 51행은 12개였다. 코드에 흩어 놓지 않는다.

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-SEC-002` | scope 없는 principal은 거부된다 | `tests/security/test_auth_and_scope_guards.py::test_scope_guard_denies_a_principal_with_no_scopes` |
| `INV-CS-SEC-003` | 다른 scope를 가진 principal도 거부된다 | `tests/security/test_auth_and_scope_guards.py::test_scope_guard_denies_a_principal_holding_another_scope` |
| `INV-CS-SEC-007` | scope 12개는 guardrail이 소유한다(09-06 `composer:admin`·`ops:reload` 추가 전 10개) | `tests/security/test_scope_contract.py::test_scopes_are_guardrail_owned` |

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

`+ ops:introspect` · `ops:reload` 등 총 **12개**. guardrail이 소유한다. ★`[실측]` 그중 **`order:read`·`return:read` 둘은 커머스 scope 가 남은 것**이다 — 코드 담당 몫.

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

## ★ [2026-09-04] 마스킹과 제거는 다르게 처리된다

`[실측]` [DoD-07 evidence](../records/evidence/DoD-07_tenant격리_PII.md) 실제 출력에서.

| 값 종류 | 처리 | 실측 결과 |
|---|---|---|
| 전화번호 | **마스킹** | `010-****-5678` |
| 카드번호 | **마스킹** | `**** **** **** 1111` |
| API key | **제거** | `[REDACTED_API_KEY]` |
| 결제 식별자 | **제거** | `[REDACTED_PAYMENT_ID]` |

**뒤 둘은 마스킹이 아니라 통째로 지운다.** v8이 API key·결제 식별자를 "audit에 원문 기록 금지"로 정했기 때문 — 일부라도 남기면 계약 위반이다.

### 이 판정을 한 번 뒤집을 뻔했다

`[실측]` 2026-08-12 1차 실측에서 `masked` 함수는 **이미 존재했다.** 그런데도 그 시점 판정은 "부분 통과"였다 — 이유는 이렇다.

> **함수가 있다는 것과 경로마다 실제로 적용된다는 것은 다르다.**

실제로 재실측(2026-08-13)해 보니 전화·카드·API key·결제 식별자 **네 값이 전부 원문으로 저장되고 있었다.** 함수 존재를 통과로 잘못 세었으면 거짓 보고가 됐을 것이다.

### 지금도 검증 안 된 경로가 있다

`[미확보]` **DoD-07 원문이 스스로 밝힌 한계, 아직 안 채워졌다.**

| 항목 | 상태 |
|---|---|
| 저장 시 마스킹 | 확인됨 |
| **LLM 입력이 masked인가** | **미검증** — 분류기·Team·평가 경로 각각을 확인하지 않았다 |
| `demo` tenant 기존 데이터에 PII 잔존 여부 | **미검증** — 전체 검색을 돌리지 않았다 |
| API 응답의 evidence 마스킹 | 부분 — 테스트가 저장분만 본다 |

**저장이 막혔다고 LLM으로 새는 경로까지 막힌 건 아니다.** 위 `INV-CS-SEC-004`는 "DB·API·audit"을 검사하지 **LLM 입력**은 검사하지 않는다 — 이 항목은 별개로 남아 있다.

## 실패 사례

`[실측]` **인증 전 요청이 500을 냈다.** `os.getenv`로 설정을 읽어서였다. 인증 실패가 401이 아니라 500이면 공격자에게 내부 상태를 알려준다.

`[실측]` **`/ui/composer`가 인증 없이 열려 있었다.** 2026-08-18에 폐기했다.

**둘 다 "설정을 어떻게 읽는가"와 "무엇이 어디 물려 있는가"의 문제였다.** 인증 로직 자체의 버그가 아니었다.

### ★ [2026-09-06] 셋 — Composer 쓰기채널 인증이 사실상 무력화돼 있었다

`[실측]` [DoD-14](../records/evidence/DoD-14_API키_scope_구분.md) 2026-08-24 갱신. `final_project_sample`과 대조하다 **cs가 직접 만든** 우회 체인 둘이 나왔다.

| # | 결함 | 왜 뚫리나 |
|---|---|---|
| 1 | `composer_jwt_secret`·`composer_issuer_secret`에 `= ""` 기본값 — **fail-open** | 환경변수가 없어도 앱이 기동됐고 실제 `.env`에 값이 없었다. **빈 문자열을 HMAC 키로 서명한 JWT가 서명 검증을 그대로 통과**한다(알려진 JWT 위조 기법). `composer:validate`·`composer:write` scope 검사가 무의미해진다 |
| 2 | 쓰기채널에 구현체 allowlist 없음 | `composer:write`만 있으면 `implementation_ref`에 임의 문자열을 넣어 `importlib.import_module()`이 **공격자가 지정한 모듈을 그대로 import**한다 |

**둘을 이으면 인증 우회 → 임의 모듈 import 체인이다.** 이 DoD가 검증하는 "scope가 실제로 강제되는가"를 정면으로 어긴 상태였다.

고친 것 — 두 시크릿을 필수로 되돌려 값이 없으면 **기동을 거부**하고(sample과 같게), sample의 `KNOWN_IMPLEMENTATION_REFS` allowlist를 이식해 `/composer/validate`·`/composer/apply`가 항상 검사한다. **그리고 같은 날 저녁 그 사본 자체가 사라졌다**(`f2319aa`, v9 §8-D) — 이제 검증은 `acop_composer` 패키지가 하고 cs는 `app/composer_host.py`로 등록표와 인증 정책(JWT `aud`는 sample과 다른 값)만 넘긴다. 전체 교체 `/apply`는 `composer:admin`이 됐다 → [../decisions/D-CS-004-composer-boundary.md](../decisions/D-CS-004-composer-boundary.md). → [../decisions/D-CS-004-composer-boundary.md](../decisions/D-CS-004-composer-boundary.md)

**위 둘과 종류가 다르다.** 앞 둘은 설정 읽기·배선 문제였고, **이건 기본값이 안전하지 않은 쪽으로 열려 있던 것**이다. 설정이 비어 있을 때 "돌아가는 것"과 "안전한 것" 중 전자를 고른 기본값은 그 자체가 결함이다.

## ★ [2026-09-03] 계약 문서가 scope 를 6종으로 적고 있다

`[실측]` `config/guardrails.yaml` 을 직접 세었다.

```yaml
security:
  scopes:
    - case:read        - case:write      - order:read
    - return:read      - action:approve  - mcp:read
    - composer:read    - composer:validate
    - composer:write   - ops:introspect
```

**그때는 정확히 10종이었다.** `[실측 2026-09-06]` 지금은 **12종** — `composer:admin`(전체 교체·복원, `f2319aa`)과 `ops:reload`(재기동 없는 반영)가 더해졌다.

| 어디 | 적힌 수 |
|---|---|
| **이 wiki** | 10 → **12** (09-06) |
| `config/guardrails.yaml` | 10 → **12** (09-06) |
| 테스트 `test_scopes_are_guardrail_owned`(옛 이름 `test_ten_scopes_…`, 09-06 `composer:admin`·`ops:reload`가 더해져 12개가 되며 개명) | **10** |
| `wiki/records/handoff/03_REST_MCP_인터페이스.md` §3 | **6** |
| `wiki/records/handoff/06_가드레일_수치.md` §5 | **6** — 같은 옛 목록. 2026-09-06 확인 |

**계약 문서만 낡았다.** 그리고 거기 적힌 `subscription:read`·`technical:read` 는 **지금 존재하지 않는다** — 옛 구독·청구 도메인의 잔재다.

`[실측]` **테스트 함수 이름도 `six` → `ten` 으로 바뀌었다.** DoD-14 evidence 가 아직 `six` 로 적고 있다. → [../quality/blind-spots.md](../quality/blind-spots.md)

## 관계

- [rest-api.md](rest-api.md) — 쓰기 경로
- [mcp-tools.md](mcp-tools.md) — 읽기 경로
- [a2a-protocol.md](a2a-protocol.md) — 위임 경로
- [../data/tenancy.md](../data/tenancy.md) — 저장 계층 격리
- [../actions/approval.md](../actions/approval.md) — `action:approve`
