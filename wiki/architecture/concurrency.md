---
type: concept
title: 경합과 동시성 책임
description: 여덟 종류의 경합을 누가 처리하는가. 담당이 겹치면 아무도 안 한다
status: draft
tags: [architecture, state]
owners: [human:미배정]
domain: neutral
---

# 경합과 동시성 책임

`[실측]` v8 §8-C에서 이관. **v11 §6 이 그대로 승계한다** — 낙관적 동시성·idempotency·이벤트 순서·outbox 제약 넷은 "바꾸면 코어를 다시 검증해야 한다"고 못 박혀 있다.

★**이 문서는 도메인이 바뀌어도 안 바뀐다.** 경합의 종류는 주문이든 여행 일정이든 같다.

## 원칙

**Coordination이 조정하고, Shared State와 Tool Layer가 조정 실패에 대비한다.**

조정이 실패하거나 동시에 요청이 들어와도 **상태와 실제 Action의 일관성이 깨지지 않아야 한다.**

## 여덟 종류

| 경합 | 담당 |
|---|---|
| Team A vs Team B 실행 충돌 | **Coordination** |
| 동일 Case의 ownership / scheduling | **Coordination** |
| Message 중복 / retry / delivery | Coordination 정책 + Message Broker |
| **Team 내부 Agent A vs Agent B** | **각 Agent Team 내부** |
| 같은 Shared State 동시 수정 | State Repository / DB (version, CAS) |
| 같은 Action 중복 실행 | Tool / Action Layer (idempotency key) |
| DB 레코드 동시 변경 | Transaction / CAS / Lock |
| 여러 Team 결과 병합 | **Coordination** |

## ★ Team 내부는 Controller가 관리하지 않는다

**Team을 하나의 실행 단위로 본다.**

Team 안에 Agent가 몇이든 그 안의 경합은 Team이 알아서 한다. Controller가 들여다보면 Team 내부 자유도가 사라진다.

→ [core-vs-team.md](core-vs-team.md)

## 왜 Controller를 거치게 바꿨나

`[실측]` 흐름이 한 번 바뀌었다.

```
변경 전   Team → Core2 Action → Core1 State
변경 후   Team → Core1 Controller → Core2 Action → Core1 State
```

**세 가지가 좋아진다.**

| | |
|---|---|
| 토큰 예산 통제 | Context Broker가 한 곳에서 관리 |
| 중복 조회 방지 | 같은 자료를 두 번 안 읽는다 |
| **평가 입력 고정** | 같은 입력이 같은 결과를 내야 비교가 된다 |

그리고 **Team 개발자가 Action Layer 인터페이스를 직접 볼 필요가 없다.**

## 읽기와 쓰기 둘 다 Team을 거치지 않는다

| | Team이 하는 것 | 실제로 하는 쪽 |
|---|---|---|
| 읽기 | `required_context` 선언 | **Context Broker**가 미리 조회해 `ContextPack`에 넣는다 |
| 부족하면 | `need_more_context` 반환 | Controller가 보강해 재실행 |
| 쓰기 | `ActionProposal` 반환 | Controller가 Action Layer에 위임 |

→ [`team-boundary.md`](../../final_project_cs/wiki/teams/team-boundary.md) · [sample](../../final_project_sample/wiki/teams/team-boundary.md)

## CONFLICT 처리

```
Coordination 이 CONFLICT 를 받으면
  → 최신 State 재로드
  → 결과가 아직 유효하면  Retry
  → 아니면                Replan
```

**"아직 유효한가"를 판단하는 게 핵심이다.** 무조건 재시도하면 낡은 판단을 다시 쓴다.

→ [`conflict-retry.md`](../../final_project_cs/wiki/runtime/conflict-retry.md) · [sample](../../final_project_sample/wiki/runtime/conflict-retry.md)

## 담당이 겹치면 안 된다

**이 표의 값은 "누가 하는가"가 아니라 "누가 안 하는가"에 있다.**

같은 경합을 두 곳이 처리하면 둘 다 상대가 할 거라 여기거나, 둘 다 처리해 이중으로 막는다. 후자는 성능이 죽고 전자는 사고가 난다.

## 관계

- [core-design.md](core-design.md) — Core 8개 구성요소
- [core-vs-team.md](core-vs-team.md) — Team 경계
- [`shared-state.md`](../../final_project_cs/wiki/runtime/shared-state.md) · [sample](../../final_project_sample/wiki/runtime/shared-state.md) — CAS
- [`idempotency.md`](../../final_project_cs/wiki/actions/idempotency.md) · [sample](../../final_project_sample/wiki/runtime/idempotency.md) — 중복 실행 방지
