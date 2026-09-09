---
type: contract
title: idempotency
description: 같은 요청이 여러 번 와도 side effect는 한 번. 재사용 가능한 consumer 계약이다
status: draft
tags: [contract, architecture]
owners: [human:미배정]
domain: neutral
domain_note: idempotency 기제는 도메인 무관이다. 예시가 환불 제안이다
---

# idempotency

`app/core/idempotency.py` (21줄) · `tests/contract/test_consumer_idempotency_contract.py`

## 왜

**환불이 두 번 나가면 되돌릴 수 없다.**

메시지는 중복 전달되고, worker는 동시에 같은 일을 집을 수 있고, 네트워크는 타임아웃된다. 셋 다 정상 상황이다.

## 키를 어떻게 만드는가

`[실측]` 결정론적으로 만든다. 랜덤이 없다.

```python
def idempotency_key(*, tenant_id, request_id, action_type, business_subject) -> str:
    hashed_parts = "".join(
        hashlib.sha256(part.encode("utf-8")).hexdigest()
        for part in (tenant_id, request_id, action_type, business_subject)
    )
    return hashlib.sha256(hashed_parts.encode("utf-8")).hexdigest()
```

네 조각이 들어간다.

| 조각 | 왜 |
|---|---|
| `tenant_id` | 다른 테넌트의 같은 요청은 다른 것 |
| `request_id` | 같은 요청인지 판정하는 축 |
| `action_type` | 같은 요청이라도 환불과 알림은 다른 것 |
| `business_subject` | 어느 주문·어느 건인지 |

**각 조각을 먼저 해시한 뒤 이어 붙여 다시 해시한다.** 조각 경계를 명확히 해서 `"ab"+"c"`와 `"a"+"bc"`가 같은 키가 되는 걸 막는다.

`request_id`가 없는 옛 Case는 `case_id`로 대체한다.

`[실측]` **이 경계 분리는 원래 없었다.** 2026-08-14 시점 코드는 `f"{a}{b}{c}{d}"`로 단순히 이어붙여 해시했다 — 위 충돌이 이론상 가능한 상태였다. 2026-08-24에 발견·수정하고 `test_idempotency_key_preserves_field_boundaries`로 고정했다. → [DoD-11](../records/evidence/DoD-11_action_idempotency_승인.md)

### ★ 처음엔 이 산식조차 아니었다

`[실측]` 2026-08-14 재측정 당시 `billing.py`의 실제 코드는 `uuid5(NAMESPACE_URL, task_id + ":refund")` — **`task_id` 기준**이었다. 계획(v5 §10-1)이 정한 `tenant_id·request_id·action_type·business_subject` 기준이 아니었다.

**차이가 실제 사고로 드러났다.** 승인 후 Controller를 재실행하자 run마다 `task_id`가 달라져 **같은 환불 제안에 새 행이 하나 더 생겼다** — `UNIQUE(tenant_id, idempotency_key)`가 못 막았다. v5 산식이었다면 네 값이 그대로라 같은 키가 되어 막혔을 것이다. 커밋 `7a6cf18`에서 지금의 산식으로 교체됐다.

**즉 생성 경로의 중복은 처음부터 막았지만, run을 가로지르는 중복은 산식을 통째로 바꾸고 나서야 막혔다.**

## ★ 재사용 가능한 계약이다

`[실측]` 테스트 파일 주석이 밝힌다.

> `consumer_contract_factories`에 등록된 **모든** consumer adapter는 같은 세 불변식을 증명해야 한다.

즉 **새 consumer를 추가하면 이 계약 테스트가 자동으로 적용된다.** 개별 테스트를 새로 쓰지 않는다.

adapter가 노출해야 하는 것은 셋뿐이다.

```
MessageBrokerPort.publish 상당
one-shot worker
status 조회
```

**계약을 작게 유지한 게 이 설계의 좋은 점이다.**

## 증명하는 세 가지

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ACT-001` | 동일 dedupe key는 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_duplicate_dedupe_key_has_one_side_effect` |
| `INV-CS-ACT-002` | 동시 claim도 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_concurrent_claims_have_one_side_effect` |
| `INV-CS-ACT-003` | timeout은 unknown이며 자동 재시도하지 않는다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_timeout_is_unknown_and_not_automatically_retried` |

**001과 002는 다르다.** 001은 순차 중복, 002는 진짜 동시성이다. 테스트가 `ThreadPoolExecutor`로 실제 동시 실행을 만든다.

## ★ timeout을 성공으로도 실패로도 추정하지 않는다

`INV-CS-ACT-003`이 이 시스템에서 가장 중요한 규칙 중 하나다.

```
provider 호출 → timeout
                  ↓
        성공했나? 실패했나?  ← 모른다
                  ↓
           unknown 으로 남긴다
           자동 재시도 안 한다
           사람이 판단한다
```

**실패로 추정하고 재시도하면 이중 결제가 난다.** 성공으로 추정하면 안 나간 돈을 나갔다고 기록한다.

운영 UI에서 `unknown`은 **가장 센 위험색**으로 표시한다. 돈이 나갔는지 모르는 상태이기 때문이다.

## DB 제약이 받친다

```sql
-- 001_schema.sql
action_requests ... UNIQUE (tenant_id, idempotency_key)
-- 003_outbox_tenant_scoped_dedupe.sql
outbox ... UNIQUE (tenant_id, topic, dedupe_key)
```

★`[2026-09-08]` **근거 기록 둘이 아직 옛 제약을 싣고 있다. 그건 고치지 않는다.**
`wiki/records/evidence/DoD-23_consumer_idempotency.md:33` 은 `UNIQUE(topic, dedupe_key)`
를 **통과 근거로** 들고 있고 `wiki/records/handoff/02_DB_스키마.md:119` 는 001 DDL 만
싣는다. 둘 다 `records/` 라 **고치지 않는 것이 기록의 성질**이다(루트 `CLAUDE.md`).
대신 여기에 적는다 — **그 기록을 근거로 인용할 때는 제약이 그 뒤 바뀌었다는 것을
같이 읽는다.** 지금 값은 바로 위 스니펫이고 살아 있는 DB 로 확인한 것이다.

★`[정정 2026-09-07]` 이 스니펫은 `003_outbox_tenant_scoped_dedupe.sql` 을 가리키면서
**그 마이그레이션 전의 제약**을 싣고 있었다(`UNIQUE (topic, dedupe_key)`). 파일 이름만
새것으로 바꾸고 내용은 안 바꾼 것이다. `tenant_id` 가 빠지면 **다른 테넌트끼리 dedupe
키가 충돌한다** — 한 테넌트의 메시지가 다른 테넌트의 것 때문에 안 나간다. 보안급이라
[review-policy.md](../../../wiki/governance/review-policy.md) 의 DoD-12 항목에 결함으로
남아 있다. 살아 있는 DB 에서 확인한 값이 위의 것이다.

**애플리케이션 로직만으로는 동시성을 못 막는다.** DB 제약이 최종 방어선이다.

## 계약에서의 위치

`ActionProposal`이 키를 들고 온다.

```python
idempotency_key: str = Field(min_length=8, max_length=128)
```

**Team이 생성하고 Core가 검사한다.** Team이 키를 잘못 만들면 중복 실행이 아니라 **중복 차단 실패**가 된다.

## MCP 경로도 같은 원리를 쓴다

`[실측]` `open_support_case`(MCP)도 REST와 같은 원리의 dedupe key로 `action_requests`를 먼저 조회하고, 기존 행이 있으면 새로 만들지 않고 기존 Case를 반환한다. 동일 요청 10회 → Case 1개·`action_requests` 1행(`test_same_mcp_open_request_ten_times_has_one_case_and_action_request`). → [../external/mcp-tools.md](../external/mcp-tools.md)

## 검증 방법

**말이 아니라 테스트로 증명한다.**

```bash
pytest tests/contract/test_consumer_idempotency_contract.py -v
```

동일 요청 10회 → `action_requests` 1행. DoD 항목이기도 하다.

`[실측]` **이게 증명하는 건 발행까지다.** provider 실행 경로 자체가 이 시스템에 없다 — 자세한 경계는 [outbox.md](outbox.md)를 본다.

## 관계

- [action-proposal.md](action-proposal.md) — 키가 실려 오는 곳
- [outbox.md](outbox.md) — 발행 쪽 중복 방지
- [tool-gateway.md](tool-gateway.md) — 실행 지점
- [../runtime/conflict-retry.md](../runtime/conflict-retry.md) — 재시도해도 되는 것과 아닌 것
- [../data/schema/index.md](../data/schema/index.md) — UNIQUE 제약
