---
type: contract
title: MCP 도구
description: 개인 AI가 쓰는 도구 3종. 전부 mcp:read이고 개수가 테스트로 고정돼 있다
status: draft
tags: [api, security, contract]
owners: [human:미배정]
---

# MCP 도구

`app/presentation/api/mcp.py`

개인 AI(ChatGPT·Claude 등)가 A-COP에 연결하는 경로다.

## 도구 3종

`[실측]` 전문이 짧아 그대로 싣는다.

```python
mcp = FastMCP("A-COP")

@mcp.tool(meta={"required_scope": "mcp:read"})
def get_my_cases(customer_id: str, limit: int = 20) -> list[dict]: ...

@mcp.tool(meta={"required_scope": "mcp:read"})
def get_case_detail(customer_id: str, case_id: str) -> dict: ...

@mcp.tool(meta={"required_scope": "mcp:read"})
def open_support_case(customer_id: str, message: str, channel: str = "mcp") -> dict: ...
```

| 도구 | 무엇 |
|---|---|
| `get_my_cases` | 내 Case 목록 |
| `get_case_detail` | Case 상세 |
| `open_support_case` | 문의 접수 |

## ★ MCP는 read-only다

**세 개 전부 `mcp:read`다.** 쓰기 scope가 없다.

`open_support_case`가 Case를 만드는데 왜 read냐고 물을 수 있다.

**Case 생성·분류 시작까지이고 결제·환불·구독 변경을 하지 않는다.** 바깥 세계를 바꾸지 않는다는 뜻에서 read다.

**쓰기는 REST + 승인 경로로만 간다.**

## ★ 쓰기 3단계

`[실측]` v8 §9. **"read-only"를 세 단계로 구체화한 것이다. 모든 쓰기를 허용하는 변경이 아니다.**

| 단계 | 예 | 허용 경로 | 필수 조건 |
|---|---|---|---|
| **read** | Case·주문·배송·정책 조회 | MCP 또는 REST | scope, tenant/case ownership, audit |
| **reversible operational write** | Case 생성, 배송조회 요청, 철회 가능한 운영 메모 | **MCP에서 조건부 허용** | 별도 scope, idempotency key, audit, **rate limit**, 실패·재처리 규칙 |
| **financial/order-state side effect** | 결제·환불·주문상태·구독 변경·권한 부여 | **REST + 승인만** | approval, scope, idempotency, audit, **실행 직전 재검증** |

**가운데 단계가 `open_support_case`가 사는 자리다.** 되돌릴 수 있고 조건이 붙는다.

**아래 단계는 MCP로 절대 안 간다.** 결제·환불·주문상태·구독·권한 부여.

**Team의 reversible operational write도 이 경계를 우회하지 않는다.** `ActionProposal`로 Controller와 Action Layer에 보낸다.

## 보안 원칙 5가지

`[실측]` v8 §9

```
DB 직접 노출 금지
SQL 실행형 도구 금지
사용자 scope 기반 권한 제어
읽기/쓰기 도구 분리
환불·해지 등 쓰기는 승인 단계
```

**두 번째가 특히 중요하다.** "SQL을 실행하는 도구"를 주면 scope도 tenant 격리도 무의미해진다.

## 개수가 고정돼 있다

`[실측]` `INV-CS-SEC-008`

```
tests/security/test_scope_contract.py::test_mcp_has_exactly_three_read_scoped_tools
```

**도구를 늘리려면 이 테스트를 같이 고쳐야 한다.** 그게 의도적 결정임을 강제한다.

조용히 네 번째 도구가 생기는 걸 막는다. **MCP 표면은 넓어지기 쉬운 곳이다.**

## scope 확인

`[실측]` guardrails에 없으면 기동하지 않는다.

```python
if "mcp:read" not in set(get_guardrails().get("security.mcp_allowed_scopes")):
    raise RuntimeError("mcp:read is not configured")
return Principal(get_settings().tenant_id, frozenset({"mcp:read"}), "mcp")
```

**fail-closed다.** 설정이 없으면 열리는 게 아니라 죽는다.

## idempotency

`open_support_case`도 중복 방지를 거친다.

```python
idem = idempotency_key(
    tenant_id=tenant, request_id=request.request_id,
    action_type="mcp.open_support_case",
    business_subject=f"{request.customer_id}:{request.message}",
)
```

**같은 고객이 같은 메시지를 두 번 보내도 Case가 하나만 생긴다.** 개인 AI는 재시도를 자주 한다.

`business_subject`에 메시지 내용이 들어가는 게 특징이다. 다른 문의면 다른 Case가 된다.

## 무엇을 하지 않는가

| 안 함 | 어디로 |
|---|---|
| 결제·환불 | REST + 승인 |
| 구독 변경 | 동 |
| 승인 | REST 전용 엔드포인트 |
| Team 직접 호출 | 불가 |

## A2A와 다르다

| | MCP | A2A |
|---|---|---|
| 상대 | 개인 AI | 기업 Agent System |
| 무엇 | 도구 호출·자원 접근 | 장기 실행 업무 위임 |
| 있어야 할 것 | — | Agent Card, Task lifecycle, Artifact |

근거는 [../../../wiki/research/a2a-adoption.md](../../../wiki/research/a2a-adoption.md).

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-SEC-008` | MCP는 정확히 3개의 read scope 도구를 갖는다 | automated | `tests/security/test_scope_contract.py::test_mcp_has_exactly_three_read_scoped_tools` |
| `INV-CS-SEC-007` | scope 10개는 guardrail이 소유한다 | automated | `tests/security/test_scope_contract.py::test_ten_scopes_are_guardrail_owned` |

## 관계

- [rest-api.md](rest-api.md) — 쓰기 경로
- [auth-boundary.md](auth-boundary.md) — 인증·scope
- [a2a-protocol.md](a2a-protocol.md) — 기업 Agent 경로
- [../actions/tool-gateway.md](../actions/tool-gateway.md) — 내부 도구 경계
