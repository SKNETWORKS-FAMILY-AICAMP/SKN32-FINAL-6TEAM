---
type: concept
title: Tool Gateway
description: 어떤 도구를 누가 쓸 수 있는가. Registry가 manifest 밖의 호출을 거부한다
status: draft
tags: [security, architecture]
owners: [human:미배정]
---

# Tool Gateway

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/tools/` · `app/core/registry.py`

## 책임

도구 호출의 **단일 통로**다. 누가 무엇을 쓸 수 있는지 여기서 판정한다.

## 허용 목록은 manifest에 있다

**Team은 `TeamManifest.allowed_tools` 밖의 도구를 호출할 수 없다. Registry가 거부한다.**

`[실측]` 현재 Team별 허용 도구.

| Team | 허용 도구 |
|---|---|
| Procurement + Order & Payment | `read.order` `read.account` `read.policy` `read.catalog` |
| Return & Refund | `read.order` `read.return` `read.policy` |
| Fulfillment & Logistics | `read.order` `read.shipment` `read.policy` |
| Catalog & Verification | `read.catalog` `read.order_items` `read.policy` |
| Response Review | `read.policy` |

**read 도구는 7종뿐이고 결제 조회는 없다.**

```
read.order · read.order_items · read.shipment · read.return
read.catalog · read.policy · read.account
```

Team 이름에 "Payment"가 있지만 실제 권한이 없다. → [../../../wiki/decisions/D-001-payment-ownership.md](../../../wiki/decisions/D-001-payment-ownership.md)

## ★ 그런데 Team은 read 도구를 직접 안 부른다

**허용 목록은 있지만 호출은 Context Broker가 한다.**

```
Team: required_context 선언
  ↓
Context Broker: allowed_tools 안에서 도구 호출
  ↓
ContextPack: Team에게 전달
```

`allowed_tools`는 **Broker가 이 Team을 위해 무엇까지 읽어도 되는지**의 상한이다.

→ [../context/context-broker.md](../context/context-broker.md) · [../teams/team-boundary.md](../teams/team-boundary.md)

## 쓰기 도구

**Team은 쓰기 도구를 안 갖는다.** `ActionProposal`을 반환하고 Core가 실행한다.

```
ActionProposal → 근거 대조 → 승인 판정 → Tool Gateway 실행 → Outbox
```

## ToolNotAllowed

`app/core/contracts.py`에 예외가 정의돼 있다.

```python
class ToolNotAllowed(Exception): ...
class ScopeDenied(Exception): ...
class GuardrailExceeded(Exception): ...
```

**조용히 빈 결과를 주지 않는다.** 거부는 예외로 드러낸다.

## MCP 도구는 3개로 고정

`[실측]` `INV-CS-SEC-008`이 검사한다.

```
tests/security/test_scope_contract.py::test_mcp_has_exactly_three_read_scoped_tools
```

**전부 `mcp:read`다. MCP는 read-only다.**

`open_support_case`는 Case 생성·분류 시작까지이고 결제·환불·구독 변경을 하지 않는다. 쓰기는 REST + 승인 경로로만 간다.

**도구를 늘리려면 이 테스트를 같이 고쳐야 한다.** 그게 의도적 결정임을 강제한다.

## scope

`[실측]` scope 10개는 guardrail이 소유한다(`INV-CS-SEC-007`). 코드에 흩어 놓지 않는다.

| 불변식 | 무엇 |
|---|---|
| `INV-CS-SEC-002` | scope 없는 principal 거부 |
| `INV-CS-SEC-003` | 다른 scope를 가진 principal도 거부 |

**"scope가 있기만 하면 통과"가 아니라 "맞는 scope여야 통과"다.**

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-SEC-007` | scope 10개는 guardrail이 소유한다 | automated | `tests/security/test_scope_contract.py::test_ten_scopes_are_guardrail_owned` |
| `INV-CS-SEC-008` | MCP는 정확히 3개의 read scope 도구를 갖는다 | automated | `tests/security/test_scope_contract.py::test_mcp_has_exactly_three_read_scoped_tools` |
| `INV-CS-TEAM-002` | manifest scope는 정확히 선언된다 | automated | `tests/contract/test_team_contract.py::test_manifest_scopes_are_exact` |

## 관계

- [action-proposal.md](action-proposal.md) — 쓰기 제안
- [approval.md](approval.md) — 실행 전 승인
- [idempotency.md](idempotency.md) — 실행 중복 방지
- [../context/context-broker.md](../context/context-broker.md) — read 도구를 실제로 부르는 쪽
- [../teams/team-registry.md](../teams/team-registry.md) — 허용 목록 판정
- [../external/mcp-tools.md](../external/mcp-tools.md) — MCP 도구 3종
