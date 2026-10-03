---
type: guide
title: External
description: 바깥과 만나는 면. REST·MCP·A2A와 Trust Boundary
status: draft
domain: neutral
---

# External

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

`app/presentation/`

**Agent Gateway가 유일한 진입점이다.** 여기가 Trust Boundary다.

## 진입 경로 3종

```text
개인 AI ──── MCP ─────┐   ★`[2026-10-02]` 지금의 MCP 는 여행 도구(`/mcp/`, 사용자 키) — [mcp-tools.md](mcp-tools.md)
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
| [auth-boundary.md](auth-boundary.md) | 인증·스코프·PII | `app/infrastructure/auth/` |
| [web-screen-api.md](web-screen-api.md) | 사용자 웹 접수 화면·온보딩 알림·복구 카드의 연결 상태와 API 협의 항목 | `frontend/apps/web/src/features/intake-review/` · `onboarding/` |

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

근거는 [../../../wiki/research/a2a-adoption.md](../../../wiki/research/a2a-adoption.md).

## 이 영역의 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-SEC-001` | 유효하지 않은 토큰은 인증되지 않는다 | automated |
| `INV-CS-SEC-002` | scope 없는 principal은 거부된다 | automated |
| `INV-CS-SEC-007` | scope **12개**는 guardrail이 소유한다 `[정정 2026-09-10]` | automated |
| `INV-CS-SEC-008` | **옛** MCP 도구 셋(쇼핑몰 Case 도구 3개 — 연결된 적 없음)은 정확히 3개의 read scope 도구를 갖는다 | automated |
| `INV-CS-SEC-009` | MCP 호출자는 사용자 키가 정한다 — 키 없음·틀림 401 · 모듈 토글 끄면 404 · 도구 인자에 `customer_id` 없음 `[2026-10-02]` | automated |
| `INV-CS-SEC-010` | MCP 쓰기 도구는 `travel.mcp.write_enabled` 가 켜졌을 때만 등록된다(기본 꺼짐) `[2026-10-02]` | automated |

**`INV-CS-SEC-008`이 옛 도구 셋의 범위를 고정한다.** `[2026-10-02]` 지금의 MCP 는 새 모듈(`mcp_server.py`)이고, 범위는 **009(누가 부르나)·010(쓰기는 스위치)** 이 잡는다 — 도구를 늘리면 `tests/e2e/test_mcp_server.py` 의 도구 목록 시험이 깨져 의도적 결정임을 강제한다.

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
- [../../../wiki/architecture/system-context.md](../../../wiki/architecture/system-context.md) — 시스템 경계
- [introspection.md](introspection.md) — 조립 상태를 보여주는 read-only API

- [rest-endpoints.md](rest-endpoints.md) — 엔드포인트별 요청·응답 필드 계약

