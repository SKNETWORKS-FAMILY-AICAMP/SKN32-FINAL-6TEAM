---
type: guide
title: External
description: 바깥과 만나는 면. REST·MCP·A2A와 Trust Boundary
status: draft
---

# External

`app/presentation/`

**Agent Gateway가 유일한 진입점이다.** 여기가 Trust Boundary다.

## 진입 경로 3종

```text
개인 AI ──── MCP ─────┐
                      │
기업 Agent ── A2A ────┼──→ Agent Gateway ──→ Core
                      │    (Trust Boundary)
쇼핑몰·UI ── REST ────┘
```

## 각 문서

| 문서 | 답하는 질문 | 코드 |
|---|---|---|
| [rest-api.md](rest-api.md) | 엔드포인트와 스키마 | `app/presentation/api/` |
| [mcp-tools.md](mcp-tools.md) | 개인 AI가 쓰는 도구 3종 | `app/presentation/mcp/` |
| [a2a-protocol.md](a2a-protocol.md) | 기업 Agent에 업무 위임 | `app/presentation/a2a/` |
| [auth-boundary.md](auth-boundary.md) | 인증·스코프·PII | `app/core/access_action/auth/` |

## 코드 구조

```text
app/presentation/
├─ api/       REST
├─ mcp/       MCP
├─ a2a/       A2A
├─ schemas/   요청·응답 스키마
├─ ui/        운영 UI
└─ web/       웹
```

## MCP와 A2A를 가르는 기준

| | MCP | A2A |
|---|---|---|
| 무엇 | 도구 호출·자원 접근 | **장기 실행 업무 위임** |
| 상대 | 개인 AI | 독립 배포된 Agent System |
| 있어야 할 것 | — | Agent Card, Task lifecycle, Artifact |

**단순 데이터 조회는 A2A가 아니다.** REST다.

근거는 [../../../program/wiki/research/a2a-adoption.md](../../../wiki/research/a2a-adoption.md).

## 이 영역의 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-SEC-001` | 유효하지 않은 토큰은 인증되지 않는다 | automated |
| `INV-CS-SEC-002` | scope 없는 principal은 거부된다 | automated |
| `INV-CS-SEC-007` | scope 10개는 guardrail이 소유한다 | automated |
| `INV-CS-SEC-008` | MCP는 정확히 3개의 read scope 도구를 갖는다 | automated |

**`INV-CS-SEC-008`이 MCP 범위를 고정한다.** 도구를 늘리려면 이 테스트를 같이 고쳐야 하고, 그게 의도적 결정임을 강제한다.

## 나가는 방향

| 대상 | 경계 |
|---|---|
| 검증 쇼핑몰 | **결제는 쇼핑몰이 실행** → [D-001](../../../wiki/decisions/D-001-payment-ownership.md) |
| 알림 채널 | Outbox 경유 |
| A2A Remote Agent | Artifact 근거를 Context/DB와 대조 |

**나가는 모든 것은 [../actions/index.md](../actions/index.md)를 거친다.**

## 인접 영역

- [../actions/index.md](../actions/index.md) — 나가는 경로
- [../runtime/index.md](../runtime/index.md) — 들어온 요청이 Case가 되는 곳
- [../../../program/wiki/architecture/system-context.md](../../../wiki/architecture/system-context.md) — 시스템 경계
