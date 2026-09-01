---
type: concept
title: Core와 Team의 경계
description: 새 기능이 Core인가 Team인가를 판정하는 기준. 잘못 판정하면 Team 추가가 리팩토링이 된다
status: draft
tags: [architecture]
owners: [human:미배정]
---

# Core와 Team의 경계

## 판정 기준 한 줄

> **도메인 지식이 필요하면 Team(Pack), 도메인과 무관하면 Core.**

## Core가 갖는 것

도메인을 몰라도 되는 공통 실행 기반.

| 책임 | 왜 Core인가 |
|---|---|
| Case 생명주기 | 환불이든 배송이든 상태 기계는 같다 |
| Controller (라우팅·재계획) | capability로 찾을 뿐 업무 내용을 모른다 |
| Team Registry | 등록·해석만 한다 |
| Shared State + CAS | 동시성 문제는 도메인 무관 |
| 승인 경계 | 위험도 판정 기준은 정책이지 도메인이 아니다 |
| idempotency | 중복 실행 방지는 도메인 무관 |
| 감사·평가 | 측정 방식은 도메인 무관 |
| Port (Graph·MessageBus·Tool) | 교체 지점 |

## Team이 갖는 것

도메인 지식이 필요한 것.

| 책임 | 왜 Team인가 |
|---|---|
| "환불 가능한가" 판단 | 반품 규정을 알아야 한다 |
| 배송 지연 원인 분류 | 배송 도메인 지식 |
| 응답 문장 생성·검토 | 업무 맥락 |
| 이상 징후 판정 | 무엇이 정상인지 알아야 한다 |

## Team이 하지 않는 것 셋

이게 경계의 실체다. 셋 다 테스트가 강제한다.

**1. side effect를 실행하지 않는다.** `ActionProposal`만 반환한다.

Team이 직접 실행하면 세 가지가 무너진다 — 승인 경계를 우회할 수 있고, 같은 요청이 두 번 실행될 수 있고, 감사 기록이 안 남는다.

**2. read Tool을 직접 호출하지 않는다.** Context Broker가 `required_context`에 따라 읽어서 `ContextPack`에 넣어준다. 부족하면 `need_more_context`로 요청한다.

이렇게 하는 이유는 **읽기 예산을 Core가 통제**하기 위해서다. Team이 직접 읽으면 컨텍스트가 무한정 커진다.

**3. 다른 Team을 직접 호출하지 않는다.** Controller가 Task로 변환해 수행한다.

Team 간 직접 호출을 허용하면 의존 그래프가 생기고 교체가 불가능해진다.

## Core가 하지 않는 것

**Team 내부를 import하지 않는다.** `TeamManifest`와 표준 Contract만 사용한다.

Core가 Team의 graph·prompt·retrieval을 import하는 순간 Pack 교체가 불가능해진다.

**Core 계층에 도메인 어휘를 넣지 않는다.** 테스트가 막는다.

```python
DOMAIN_WORDS = (
    "payment", "subscription", "entitlement", "refund", "invoice",
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

예외는 `app/core/redaction.py` 하나다. PII 마스킹은 결제 식별자 **모양**을 알아야 가릴 수 있는데, 이건 도메인 로직이 아니라 **보안 규칙**이다. 예외에는 반드시 이유를 적는다.

## Team을 만들 자격

Team은 다음이 **전부** 독립될 때 만든다.

| 축 | 질문 |
|---|---|
| Capability | 처리하는 업무 종류가 다른가 |
| 책임 | 실패했을 때 책임 소재가 다른가 |
| 권한 | 쓸 수 있는 도구가 다른가 |
| 지식 | 알아야 할 정책·규정이 다른가 |
| 경계 | 건드리는 데이터 범위가 다른가 |

하나라도 안 갈리면 기존 Team의 capability를 늘린다.

### VOC가 Team인 이유

VOC & Store Manager는 "집계만 하는데 왜 Team인가"라는 질문을 받는다.

**Team 자격의 핵심은 고정 공식으로 급증을 계산하는 데 있지 않다.** 급증 이후 고객 문장·리뷰·Case history에서 **원인 축을 판별하고, 위임 대상과 필요한 증거를 결정하는 업무 판단**에 있다.

급증 공식은 착수 시점의 내부 구현 선택이며 자격과 무관하다.

Controller가 전역 조정 책임을 갖는 것과 달리 **VOC는 업무 판단을 수행한다.** 그래서 Team이다.

## 잘못 판정하면

| 잘못 | 증상 |
|---|---|
| Team 것을 Core에 넣음 | 도메인 테스트가 실패. Pack 교체 불가 |
| Core 것을 Team에 넣음 | Team마다 같은 코드가 반복. 일관성 깨짐 |
| Team을 너무 잘게 쪼갬 | Controller 라우팅이 복잡해지고 평가 축이 늘어남 |
| Team을 너무 크게 만듦 | 권한 경계가 넓어져 승인 우회 위험 |

**Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.** Registry 등록만으로 끝나야 한다.

## 불변식

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ARCH-001` | Core 계층은 도메인 어휘에 의존하지 않는다 | automated | `tests/architecture/test_basement_is_domain_free.py` |
| `INV-CS-ARCH-002` | Core는 Team 내부를 import하지 않는다 | automated | `tests/architecture/` |
| `INV-CS-ACT-001` | Team은 side effect를 실행하지 않는다 | automated | `tests/architecture/` |

## 관계

- [pack-model.md](pack-model.md) — Pack 단위 교체
- [`team-contract.md`](../../final_project_cs/wiki/teams/team-contract.md) — 계약 상세
- [`team-boundary.md`](../../final_project_cs/wiki/teams/team-boundary.md) — 구현 관점 경계
- [../product/glossary.md](../product/glossary.md) — 용어
