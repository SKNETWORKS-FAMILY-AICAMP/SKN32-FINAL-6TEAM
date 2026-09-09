---
type: plan
title: Team 을 어느 순서로 만드나
description: 여섯 중 무엇을 먼저 하나. 2번이 기준 Team 인 이유와 1번의 함정
status: draft
tags: [architecture, contract]
domain: commerce
---

# Team 을 어느 순서로 만드나

`[실측]` `A-COP_예제Team모듈_확충설계.md` §4 에서 이관. **순서에 이유가 있다.**

| # | Team | 왜 이 순서 |
|---|---|---|
| 1 | **Response Generation & Review** | **구현이 끝나 있다.** 등록·prompt 만 보완하면 가장 빨리 데모된다 |
| 2 | **Return & Refund (Mock)** | **외부 연동 없이** 주문·반품·환불 전 흐름을 보인다. **금융 side effect 를 fixture 로 격리** |
| 3 | Procurement + Order & Payment | 2번의 **주문·금액·승인 검증 패턴을 재사용** |
| 4 | Fulfillment & Logistics | 주문·배송 fixture 가 필요. `read.shipment` 만으로 조회 데모는 독립 가능 |
| 5 | VOC & Store Manager 보완 | 이미 등록돼 있으므로 **전체 흐름의 회귀 기준**으로 쓴다 |
| 6 | **Catalog & Verification** | **마지막.** A2A transport·인증·poll·timeout 검증이 필요하다 |

### 2번이 기준 Team 인 이유

**외부 연동 없이 승인 경계 전체를 보여줄 수 있는 유일한 Team 이다.**

```
ContextPack  →  ActionProposal  →  승인 대기
```

**금융 side effect 가 fixture 로 격리되므로 실수해도 돈이 안 나간다.**

### 1번에 함정이 있다

`[실측]` **"구현됐다"와 "선택된다"가 다르다.**

> `response_generation_review` 는 구현되어 있지만 **Registry 가 선택할 수 없는 상태**다.

원인은 `accepted_case_types=[]` 다. **등록만으로 끝나지 않는다.**

### 6번을 마지막에 두는 이유

**local canonical 결과와 승인 경계를 먼저 고정해야** 원격이 그것과 같은지 잴 수 있다.

**원격을 먼저 하면 무엇과 비교할지가 없다.**



## 관계

- [index.md](index.md) — Team 영역
- [common-utils.md](common-utils.md) — 공통 뼈대
