---
type: concept
title: 시스템 경계
description: 누가 A-COP과 대화하는가. 외부 행위자와 진입 경로 3종
status: draft
tags: [architecture, security]
owners: [human:미배정]
domain: travel
---

# 시스템 경계

## 외부 행위자

| 행위자 | 무엇을 하나 | 경로 |
|---|---|---|
| 고객 (인바운드 여행자) | 일정을 제출하고 사건을 신고한다 | 여행 채널(앱·웹) → REST |
| 상담원·운영자 | 검토·승인·감독한다 | 운영 UI |
| **개인 에이전트 · 외부 LLM** | **일정을 만들어 넘긴다.** 고객 대신 조회·문의도 한다 | **MCP** |
| 기업 Agent System | 업무를 위임받는다 | **A2A** |
| 공급자 (액티비티·식당·교통·숙박) | 운영 정보와 예약 상태를 제공한다 | REST · Mock |

★**계획을 만드는 것은 우리 일이 아니다**(v11 §4-A). 개인 에이전트가 만든 일정을 받아 **성립하는지 검증하고 여행 종료까지 지켜본다.** 그래서 위 표에서 개인 AI 가 단순 조회자가 아니라 **입력 생산자**다 — v9(쇼핑몰) 시절과 달라진 자리다.

## 진입 경로 3종

```text
개인 에이전트 ─ MCP ──┐
                      │
기업 Agent ── A2A ────┼──→ Agent Gateway ──→ Core
                      │    (Trust Boundary)
여행 채널·UI ─ REST ──┘
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
| 공급자 | 장소·운영 조회 / 이동 시간 조회 / 기상 조회 (v11 §5-A) | 읽기다. **쓰기는 [D-005](../decisions/D-005-write-gate.md) 승인 경로** |
| 업체 예약 | 변경 링크 생성. 시연 모드 한정 Mock 변경 | **승인 없이 실행하지 않는다** → [`booking-handoff.md`](../../final_project_cs/wiki/teams/booking-handoff.md) |
| 알림 채널 | 고객·운영자 알림 **두 종류** — 변경 통지 · **일정 안내** | Outbox 경유 → [`notifications.md`](notifications.md) |
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
| **일정 생성** | v11 §4-A — 외부 에이전트·LLM 의 일이다. 우리는 검증하고 지켜본다 |
| 결제 실행 | [D-001](../decisions/D-001-payment-ownership.md). 여행에서도 실결제는 구현 단계 4다 (v11 §4-C) |
| 실제 업체 예약 변경 | 협약 전까지 Mock. `supplier.tier == 'simulated'` 게이트 |
| 음성 처리 (STT/TTS) | `[미확보]` 원가 미산정 |
| OCR·영상 | 범위 밖 |

## 관계

- [core-vs-team.md](core-vs-team.md) — 안쪽 구조
- [repository-map.md](repository-map.md) — 저장소 간 경계
- [`external/index.md`](../../final_project_cs/wiki/external/index.md) · [sample](../../final_project_sample/wiki/composer/index.md) — 구현
- [../product/scope.md](../product/scope.md) — 범위
