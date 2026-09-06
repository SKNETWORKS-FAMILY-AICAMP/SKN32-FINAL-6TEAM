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

### ★ 이 확장에는 순서가 있었다 — 방어가 먼저다

`[실측]` `docs/plans/2026-08-16_v7_격차해소_실행계획.md`. v7 §9-E의 제목이 **"쓰기 권한을 여는 전제 조건"**이다. 그래서 실행계획은 MCP 쓰기 확장(P7)을 **근거 대조(P1 = DoD-24)와 degraded 차단(P2 = DoD-25)이 끝난 뒤에만** 하기로 못 박았다 — 순서를 바꾸면 계획서의 전제를 거스른다.

또 하나 — **막는 코드를 먼저 만들고, 그것이 실제로 막는지 재는 수단(P4 = 방어 지표 5종)을 그다음에** 만들었다. 지표를 먼저 만들면 잴 대상이 없다.

```
P1 근거 대조 → P2 degraded 차단 → P3 REST 상한 교정 → P4 방어 지표 → … → P7 MCP 쓰기
```

P1·P2·P3·P4는 통과했다(DoD-24·25·13·28). **그래서 위 3단계가 열릴 수 있는 상태다.** `[미확보]` 실제로 `open_support_case` 외에 reversible write tool이 MCP에 붙었는지는 확인하지 않았다 — 지금 tool 3종은 전부 `mcp:read`다. 실행계획의 "진행 기록" 표는 "P1 착수"에서 멈춰 있어 낡았다.

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
| `INV-CS-SEC-007` | scope 11개는 guardrail이 소유한다(09-06 `composer:admin` 추가 전 10개) | automated | `tests/security/test_scope_contract.py::test_scopes_are_guardrail_owned` |

---

# 계약 원문에서 보강 (2026-09-03)

`[실측]` `docs/handoff/` 계약 문서와 절 단위로 대조해 **빠져 있던 필드·제약·숫자**를 채웠다. 대조 결과는 [반영률 실측](../../../wiki/governance/migration-scope/coverage.md).

## 비동기 도구 시그니처

`[실측]` 세 도구의 계약 시그니처는 `async def`다.

```python
async def get_my_cases(customer_id: str, limit: int = 20) -> list[dict]: ...
async def get_case_detail(customer_id: str, case_id: str) -> dict: ...
async def open_support_case(customer_id: str, message: str, channel: str = 'mcp') -> dict: ...
```

근거: `docs/handoff/03_REST_MCP_인터페이스.md:123-136`

## MCP ownership·응답 제약

`[실측]`

| 항목 | 제약 |
|---|---|
| ownership | 세 도구 모두 `customer_id` 소유 검사를 매 호출 수행 |
| 응답 | REST와 동일하게 masked |
| evidence | 내부 evidence 원문과 PII 노출 금지 |
| `open_support_case` | Case 생성과 분류 시작까지만 수행 |

근거: `docs/handoff/03_REST_MCP_인터페이스.md:138-148`

## ★ [2026-09-06] `open_support_case`가 분류를 시도조차 안 했다 — 고쳐졌다

`[실측]` 커밋 `7d45434`(코드 담당 세션). 계약은 두 곳(`CLAUDE.md` §0.2 · `docs/handoff/03`)에서 똑같이 "Case 생성과 **분류 시작**까지"라 했는데, 코드는 분류를 부르지 않고 `classification_unavailable`을 적었다. 실측 결과 **MCP로 연 Case는 전부** `status=escalated · intent=None · issue_code=None`, 이벤트 `['created', 'classification_failed']`였다. 라벨이 없으니 라우팅도 못 받는다 — **개인 AI로 들어온 문의는 전부 사람에게 갔다.**

왜 그랬나 — 처음엔 이 경로(모듈 수준 함수)에서 분류기를 구할 방법이 없어 정직하게 "못 한다"고 적은 것이었다. 분류 절차가 코어 1(`app/application/classification.py`)로 올라오면서 그 이유가 사라졌는데 이 자리는 안 따라갔다.

| 고친 것 | 어떻게 |
|---|---|
| 분류 호출 | 생성 트랜잭션 **밖**에서 `classify_case()` — REST 접수 경로와 같은 이유(LLM을 기다리며 잠금을 쥐지 않는다) |
| 분류기를 못 만들면 | `None`을 넘겨 `classify_case()`가 `classification_failed`를 남긴다. **전과 같은 결과지만 시도한 뒤의 실패**다 |
| 실측 | `status=routing · intent=shipping · issue_code=shipping_delayed`, 이벤트 `['created', 'classified']`. 멱등성 그대로(같은 요청 4회 → Case 1개) |
| 회귀 | `tests/contract/test_mcp_opens_a_classified_case.py` |

**계약 문서 두 곳이 같은 말을 해도 코드가 안 지키면 소용없다는 사례다.** 위 "가운데 단계" 설명은 그대로 유효하다 — 접수까지만 한다는 경계는 안 바뀌었고, 접수 안에 분류 시작이 포함된다는 걸 코드가 이제야 지킨다.

## 관계

- [rest-api.md](rest-api.md) — 쓰기 경로
- [auth-boundary.md](auth-boundary.md) — 인증·scope
- [a2a-protocol.md](a2a-protocol.md) — 기업 Agent 경로
- [../actions/tool-gateway.md](../actions/tool-gateway.md) — 내부 도구 경계
