---
type: concept
title: 시스템 경계
description: 누가 A-COP과 대화하는가. 외부 행위자와 진입 경로 3종
status: draft
tags: [architecture, security]
owners: [human:미배정]
---

# 시스템 경계

## 외부 행위자

| 행위자 | 무엇을 하나 | 경로 |
|---|---|---|
| 고객 | 문의한다 | 쇼핑몰 화면 → REST |
| 상담원·운영자 | 검토·승인·감독한다 | 운영 UI |
| 개인 AI | 고객 대신 조회·문의한다 | **MCP** |
| 기업 Agent System | 업무를 위임받는다 | **A2A** |
| 검증 쇼핑몰 | 주문·결제·배송 데이터를 제공한다 | REST |

## 진입 경로 3종

```text
개인 AI ──── MCP ─────┐
                      │
기업 Agent ── A2A ────┼──→ Agent Gateway ──→ Core
                      │    (Trust Boundary)
쇼핑몰·UI ── REST ────┘
```

**Agent Gateway가 유일한 진입점이다.** 여기가 Trust Boundary다.

### MCP와 A2A를 가르는 기준

| | MCP | A2A |
|---|---|---|
| 무엇 | 도구 호출·자원 접근 | **장기 실행 업무 위임** |
| 상대 | 개인 AI (ChatGPT, Claude) | 독립 배포된 Agent System |
| 특징 | 요청-응답 | Agent Card, Task lifecycle, Artifact |

**단순 데이터 조회는 A2A가 아니다.** REST다.

구조만 보면 우리 Case는 `waiting_approval`·`waiting_input` 같은 장기 상태를 가지므로 A2A Task와 모양이 같다. 그럼에도 MVP에서 개인 AI 경로를 MCP로 두는 이유는, `[외부]` 2026년 현재 공식 통합 사례가 기업용 Agent 플랫폼에 집중돼 있고 개인 AI의 외부 연결은 MCP가 실제 경로이기 때문이다.

**개인 AI가 A2A를 영원히 지원하지 않는다는 뜻이 아니다.** MVP의 연결 대상을 구분하는 판단이다.

## 나가는 방향

| 대상 | 무엇을 | 경계 |
|---|---|---|
| 검증 쇼핑몰 | Action 실행 요청 | **결제는 쇼핑몰이 실행** → [D-001](../decisions/D-001-payment-ownership.md) |
| 알림 채널 | 고객·운영자 알림 | Outbox 경유 |
| A2A Remote Agent | Task 위임 | Artifact 근거를 Context/DB와 대조 |

**나가는 모든 것은 Action Layer를 거친다.** side effect가 일어나는 유일한 경로다.

## 경계에서 지키는 것

| 규칙 | 어디서 강제 |
|---|---|
| 인증 실패 요청은 Case를 만들지 않는다 | 계약 테스트 |
| tenant 격리 | 모든 조회에 tenant_id |
| PII 마스킹 | `app/core/redaction.py` |
| 동일 idempotency key는 1회만 실행 | Action Layer |

## 시스템 밖에 두는 것

| 대상 | 왜 |
|---|---|
| 결제 실행 | [D-001](../decisions/D-001-payment-ownership.md) |
| 포인트·쿠폰 잔액 변경 | 동 |
| 음성 처리 (STT/TTS) | `[미확보]` 원가 미산정 |
| OCR·영상 | 범위 밖 |

## 관계

- [core-vs-team.md](core-vs-team.md) — 안쪽 구조
- [repository-map.md](repository-map.md) — 저장소 간 경계
- [`external/index.md`](../../final_project_cs/wiki/external/index.md) — 구현
- [../product/scope.md](../product/scope.md) — 범위
