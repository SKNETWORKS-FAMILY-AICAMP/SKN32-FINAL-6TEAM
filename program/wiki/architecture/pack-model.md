---
type: concept
title: Pack 모델
description: 하나의 Runtime 위에 도메인 Pack을 교체·확장하는 구조. Team 추가가 리팩토링이 되면 실패다
status: draft
tags: [architecture]
owners: [human:미배정]
---

# Pack 모델

## 구조

```text
              A-COP Runtime (Core)
   Case · Controller · Registry · Port · 승인 경계 · 감사 · 평가
                        │
            ┌───────────┴───────────┐
        CS Pack                 Commerce Ops Pack
   VOC & Store Manager      Procurement + Order & Payment
   Response Gen & Review    Fulfillment & Logistics
                            Return & Refund (Mock)
   (10주 착수 확정)          Catalog & Verification (A2A Remote)
                            (검증 쇼핑몰 일정에 따라 조정)
```

## 판정 기준

> **도메인 지식이 필요하면 Pack, 도메인과 무관하면 Core.**

상세는 [core-vs-team.md](core-vs-team.md).

## 왜 Pack인가

**하나의 Runtime을 여러 도메인에 팔기 위해서다.**

도입 기업이 자사 업무 Team을 추가해도 Core 코드가 안 바뀐다. 이게 [../product/positioning.md](../product/positioning.md)의 "기업이 자기 Team을 꽂아 쓰는 플랫폼"을 성립시킨다.

**상업적 주장이 구조적 성질에서 나온다.** 반대가 아니다.

## 교체가 성립하는 조건

| 조건 | 강제 방법 |
|---|---|
| Core가 Team 내부를 import하지 않는다 | `INV-CS-ARCH-002` |
| Core 계층에 도메인 어휘가 없다 | `INV-CS-ARCH-001` |
| Team은 Registry로만 해석된다 | Controller가 직접 생성 금지 |
| Team 계약이 고정돼 있다 | `TeamTask` / `TeamResult` |

**넷 중 하나라도 깨지면 Pack 교체가 불가능해진다.**

## 성공 판정

> **Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.**

새 Team 추가에 필요한 것이 이것뿐이어야 한다.

```
1. Team 모듈 작성 (TeamManifest + 계약 구현)
2. Registry에 등록
```

Core 파일을 하나라도 고쳐야 하면 실패다.

## 현재 상태

`[실측]` `final_project_sample`과 `final_project_cs`에 Billing/Technical 2종이 구현돼 있고 **Core 격리 위반 0**이다.

이 둘은 10주 착수 로드맵에 없다. **Team-플러그인 아키텍처가 실제로 동작한다는 증거로만 남긴다.**

## Pack 범위 판단

| Pack | Team | 근거 |
|---|---|---|
| CS Pack | VOC & Store Manager, Response Generation & Review | 부트캠프 주제 자체. **확정** |
| Commerce Ops Pack | Procurement+Order, Fulfillment, Return(Mock), Catalog(A2A) | 검증 쇼핑몰 운영에 필요. 일정 따라 조정 |

**6명 팀 전체가 이 구성으로 고정된다는 뜻은 아니다.**

국외 배송·해외 구매대행의 실제 Live 연동은 Mock으로 남긴다.

## Vision

지금 안 하는 것. 재고·가격·발주·배송·정산의 전면 운영 자동화.

**Pack 구조가 이걸 나중에 가능하게 만드는 장치다.** 지금 만들지는 않는다.

## 관계

- [core-vs-team.md](core-vs-team.md) — 판정 기준 상세
- [../product/scope.md](../product/scope.md) — Pack별 착수 범위
- [../product/positioning.md](../product/positioning.md) — 상업적 근거
- [`teams/index.md`](../../final_project_cs/wiki/teams/index.md) — 구현
