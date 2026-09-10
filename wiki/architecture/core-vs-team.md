---
type: concept
title: Core와 Team의 경계
description: 새 기능이 Core인가 Team인가를 판정하는 기준. 잘못 판정하면 Team 추가가 리팩토링이 된다
status: draft
tags: [architecture]
owners: [human:미배정]
domain: travel
---

# Core와 Team의 경계

## 판정 기준 한 줄

> **도메인 지식이 필요하면 Team(Pack), 도메인과 무관하면 Core.**

## Core가 갖는 것

도메인을 몰라도 되는 공통 실행 기반.

| 책임 | 왜 Core인가 |
|---|---|
| Case 생명주기 | 환불이든 일정 조정이든 상태 기계는 같다 |
| Controller (라우팅·재계획) | capability로 찾을 뿐 업무 내용을 모른다 |
| Team Registry | 등록·해석만 한다 |
| Shared State + CAS | 동시성 문제는 도메인 무관 |
| 승인 경계 | 위험도 판정 기준은 정책이지 도메인이 아니다 |
| idempotency | 중복 실행 방지는 도메인 무관 |
| 감사·평가 | 측정 방식은 도메인 무관 |
| Port (Graph·MessageBus·Tool) | 교체 지점 |

## Team이 갖는 것

도메인 지식이 필요한 것.

`[실측]` v11 §5 — 여행 Team 넷의 값으로 적는다. **오른쪽 칸이 도메인마다 통째로 갈린다.**

| 책임 | 왜 Team인가 |
|---|---|
| "이 액티비티 예약이 성립하는가" 판단 | 취소·환급 규정과 날씨 조건을 알아야 한다 |
| "이 식사가 성립하는가" 판단 | 영업시간·휴무·할랄/채식 조건을 알아야 한다 |
| 구간 이동이 되는가 판단 | 환승·막차 도메인 지식 |
| 승인이 필요한 업체 건 특정 | 예약 종류별 변경 규정을 알아야 한다 |
| 재계획 후보 생성 | 그 도메인에서 무엇이 대안인지 알아야 한다 |

<details>
<summary>v9(쇼핑몰) 시절 값 — 무엇이 갈렸는지 보려고 남긴다</summary>

| 책임 | 왜 Team인가 |
|---|---|
| "환불 가능한가" 판단 | 반품 규정을 알아야 한다 |
| 배송 지연 원인 분류 | 배송 도메인 지식 |
| 응답 문장 생성·검토 | 업무 맥락 |
| 이상 징후 판정 | 무엇이 정상인지 알아야 한다 |

★**왼쪽 칸(책임의 모양)은 두 도메인이 거의 같다.** 갈리는 것은 "무엇을 알아야 하는가"뿐이다. 이게 Core/Team 경계가 도메인 교체를 견디는 이유다.

</details>

## Team이 하지 않는 것 셋

이게 경계의 실체다. 셋 다 테스트가 강제한다.

**1. side effect를 실행하지 않는다.** `ActionProposal`만 반환한다.

Team이 직접 실행하면 세 가지가 무너진다 — 승인 경계를 우회할 수 있고, 같은 요청이 두 번 실행될 수 있고, 감사 기록이 안 남는다.

**2. read Tool을 직접 호출하지 않는다.** Context Broker가 `required_context`에 따라 읽어서 `ContextPack`에 넣어준다.

★`[실측 2026-09-10 작업 트리]` **여행 코드가 이 원칙과 다르게 돈다** — Team 이 `_read()` 로 read 도구를 부르고, 허용 목록과 단계 예산은 `ReadToolbox.call()` 이 강제한다. **통제는 남았고 자리가 Broker 앞에서 도구 게이트로 옮겨 갔다.** 원칙이 낡았는지 코드가 어겼는지는 `[미확보]` → [`cs/teams/team-boundary.md`](../../final_project_cs/wiki/teams/team-boundary.md) §2 부족하면 `need_more_context`로 요청한다.

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

### ★ [2026-09-09] 이 목록에 여행 어휘가 없다

`[실측]` `tests/architecture/test_basement_is_domain_free.py`. **`trip`·`itinerary`·`booking`·`reservation`·`activity` 가 0개다.**

**그래서 지금 이 가드는 여행 어휘가 코어로 새는 것을 못 막는다.** 커머스 어휘만 막는다.

★**낡은 어휘를 지우면 안 된다. 더한다.** 커머스 낱말이 코어에 다시 들어와도 안 되는 것은 그대로이고, 목록은 **도메인이 바뀔 때마다 누적**된다. 이게 이 가드를 도메인 교체에 견디게 만드는 유일한 방법이다.

`[미확보]` 코드 수정은 담당 세션 몫으로 넘겼다. 이 문서는 무엇이 비었는지만 적는다.

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

### ★ [2026-09-08 재정정] VOC Team 은 v10 에서 아예 빠졌다

`[실측]` v11 §0-2 — **「VOC & Store Manager Team → 제외. 도메인이 사라졌다」.** 껍데기로 남기는 것도 아니고 목록에서 나갔다.

**아래 2026-09-03 절은 그 전 판(v8·v9)의 판정이다.** 지우지 않고 남기는 이유는 **같은 사고가 어떻게 반복됐는지**가 이 절의 요지이기 때문이다 — 이번에도 v11 §0-2 가 Team 을 뺐는데 이 문서는 하루 넘게 안 고쳐졌다.

<details>
<summary>2026-09-03 정정 (v8 기준) — 기록으로 남긴다</summary>

### [2026-09-03 정정] VOC 는 지금 껍데기다

**이 절이 v7.1 의 옛 방어를 그대로 들고 있었다.** v8 이 재판정했는데 여기만 안 고쳤다.

> **v8 §7 재판정 — 집계·급증 탐지는 코어 1 소유.** VOC & Store Manager 는 **Registry 등록·계약만 유지하는 껍데기**로 조정한다.

→ [../../final_project_cs/wiki/teams/voc-store-manager.md](../../final_project_cs/wiki/records/legacy/teams/voc-store-manager.md)

**루트 `CLAUDE.md` 도 그렇게 적고 있다.**

#### 옛 방어는 이랬다

> Team 자격의 핵심은 고정 공식으로 급증을 계산하는 데 있지 않다. 급증 이후 **원인 축을 판별하고 위임 대상과 필요한 증거를 결정하는 업무 판단**에 있다.

`[실측]` **그 업무 판단이 아직 구현되지 않았다.** 그래서 지금은 껍데기다.

**나중에 LLM 위임 판단을 실제로 넣으면 껍데기가 알맹이를 갖는다.** 그때 구조를 다시 건드리지 않으려고 슬롯을 남긴 것이다.

#### ★ 이게 바로 [drift-case-voc](../governance/drift-case-voc.md) 가 경고한 패턴이다

**같은 사고가 wiki 안에서 재발했다.**

```
v8 §7 재판정  →  cs wiki 는 반영          ✅
              →  hub wiki 는 안 고침      ❌  ← 여기
```

**정정이 한 곳에만 가고 다른 곳에 안 갔다.** 원본 사고와 똑같다.

`[실측]` **`check_wiki.py` 는 이걸 못 잡는다.** 형식과 링크만 보고 **두 문서가 서로 다른 말을 하는지는 안 본다.**

</details>

★**세 번째로 같은 일이 났다.** v10 이 2026-09-08 에 Team 목록을 통째로 갈았는데 이 폴더 10개 문서 중 **v10 을 인용하는 것이 0건**이었다(2026-09-09 실측). 그래서 이번에는 문서를 고치는 것으로 끝내지 않고 **표시를 만들었다** — [../governance/domain-axis.md](../governance/domain-axis.md).

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
- [`team-contract.md`](../../final_project_cs/wiki/teams/team-contract/index.md) · [sample](../../final_project_sample/wiki/teams/team-contract.md) — 계약 상세
- [`team-boundary.md`](../../final_project_cs/wiki/teams/team-boundary.md) · [sample](../../final_project_sample/wiki/teams/team-boundary.md) — 구현 관점 경계
- [../product/glossary.md](../product/glossary.md) — 용어
- [`cs/domain-swap.md`](../../final_project_cs/wiki/domain-swap.md) — 도메인을 갈아 끼울 때 무엇을 바꾸나
- [../governance/domain-axis.md](../governance/domain-axis.md) — 이 문서가 도메인에 묶여 있는지 표시하는 규칙
