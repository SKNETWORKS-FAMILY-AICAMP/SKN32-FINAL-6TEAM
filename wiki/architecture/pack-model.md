---
type: concept
title: Pack 모델
description: 하나의 Runtime 위에 도메인 Pack을 교체·확장하는 구조. 2026-09-08 여행 판올림이 이 구조의 첫 실증이다
status: draft
tags: [architecture]
owners: [human:미배정]
domain: travel
---

# Pack 모델

## ★ 「Pack」은 이 wiki 의 낱말이지 v10 의 낱말이 아니다

`[실측 2026-09-09]` **`Pack` 문자열은 `A-COP_구현계획서_v10.md` 에 0회다.** v8 이 쓰던 낱말이고 계획서는 이제 안 쓴다.

**그래도 이 문서를 지우지 않는다.** 낱말이 사라졌을 뿐 **기제는 v10 이 그대로 전제하고 있다** — v10 §0-2 가 "코어는 승계하고 Team 만 갈아 끼운다"로 판올림 전체를 정의하는데, 그게 성립하려면 아래 「교체가 성립하는 조건」 넷이 필요하다. 여기가 그 조건을 적어 두는 자리다.

읽을 때 이렇게 옮긴다.

| 이 문서 | v10 |
|---|---|
| Runtime (Core) | §6 승계하는 코어 규칙 · 코어 1·2 |
| 도메인 Pack | §5 Team 모듈 구성 + §5-A 코어에서 바뀌는 것 |
| Pack 교체 | §0-2 판올림 표 · [../../final_project_cs/wiki/domain-swap.md](../../final_project_cs/wiki/domain-swap.md) |

## 구조

`[실측]` v10 §5·§5-A.

```text
              A-COP Runtime (Core)  ← 도메인을 모른다
   Case · Controller · Registry · Port · 승인 경계 · 감사 · 평가
                        │
        ┌───────────────┴───────────────┐
   여행 도메인 Pack                 (다음 도메인)
   Activity        MVP 필수          갈아 끼우는 자리
   Booking Handoff MVP 필수
   Dining          4주차
   Mobility        5주차
   Lodging/Flight  등록만
```

★**2026-09-08 에 이 그림의 오른쪽이 실제로 한 번 갈렸다.** 왼쪽 커머스 Pack(VOC & Store Manager · Response Gen & Review · Procurement+Order · Fulfillment · Return · Catalog)이 통째로 빠지고 여행 Team 다섯이 들어왔다. **이 문서가 주장하던 것이 처음으로 시험대에 올랐다** — 결과는 아래 「2026-09-08 판올림이 이 구조를 시험했다」.

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

## ★ 2026-09-08 판올림이 이 구조를 시험했다

★**교체가 실제로 일어났고, 판정이 났다.** 이 절이 기다리던 시험이다.

`[실측 2026-09-09]` 여행 Team 여섯이 코드에 붙었다.

| 항목 | 실측 |
|---|---|
| `config/project.yaml` 등록 Team | **여행 6종** — `activity`·`booking_handoff`·`mobility`·`dining`·`lodging`·`flight`. 커머스 6종은 **등록에서 빠졌다**(소스는 `app/modules/customer_ops/` 에 남아 있다) |
| 모듈 | `app/modules/travel_ops/` 7파일 |
| v10 이 계약을 바꿨나 | **안 바꿨다** — §0-2 "통합 계약 승계. 필드 변경 없음" |

### ★ 판정 — 「Registry 등록만으로 끝난다」는 그대로는 못 쓴다

`[실측 2026-09-09]` **`app/core/` 파일 둘을 고쳐야 했다.**

| 파일 | 무엇을 | 왜 |
|---|---|---|
| `app/core/project_config.py` | `KNOWN_IMPLEMENTATION_REFS` 에 여행 6종의 **모듈 경로를 손으로 넣었다** | Composer 쓰기채널이 **허용 목록에 없는 ref 를 422 로 거부**한다. 안 넣으면 조립은 뜨는데 선언을 저장할 수 없다 |
| `app/core/settings.py` | 외부 소스 자격증명 칸 4개(`weather_provider`·`kma_api_key`·`tour_api_key`·`odsay_api_key`) | 여행 Team 이 부르는 바깥이 커머스와 다르다 |

★**둘 다 Team 로직이 아니라 경계 설정이다.** 판정 규칙·재계획·프롬프트는 한 줄도 코어에 안 들어갔다. 그래도 **"Core 파일을 하나라도 고쳐야 하면 실패다"** 라는 아래 문장을 문자 그대로 지키지는 못했다.

`[실측]` `tests/architecture/test_basement_is_domain_free.py:53` 이 이 허용 목록을 **이미 예외로 뚫어 놨다**(2026-08-24). 도메인 어휘가 코어에 들어오는 것을 아는 채로 허용한 자리다.

| 갈래 | 무엇 |
|---|---|
| ① 그대로 둔다 | 허용 목록은 보안 장치다. 도메인마다 손으로 넣는 값이 맞다 |
| ② 선언으로 뺀다 | 목록을 `config/` 로 옮긴다. 그러면 코어를 안 고친다. **쓰기채널 보안이 선언 파일에 걸린다** |
| ③ 문장을 고친다 | "Core **로직**을 고쳐야 하면 실패다"로 좁힌다 |

`[미확보]` **안 정했다.** ②는 보안 경계를 옮기는 결정이라 [D-005](../decisions/D-005-write-gate.md)·[D-011](../decisions/D-011-composer-v3-gap.md) 과 함께 봐야 한다.

`[미확보]` 이 판정을 자동으로 하는 검사가 없다. `test_engine_serves_another_domain.py` 가 가장 가깝지만 **코어를 안 고치고 꽂혔는지는 안 본다.**

## ★ 확장 판단은 "만들 수 있는가"가 아니다

`[실측]` v8 §8-B (v10 §8 이 평가 대상만 여행 시나리오로 바꿨고, 이 판단 기준 자체는 안 바꿨다)

> Team이 늘면 golden set과 라우팅 평가 축이 함께 늘어난다. 확장 판단은 **"만들 수 있는가"가 아니라 "채점할 수 있는가"**로 한다.

**Team 하나를 더 만드는 비용보다 그 Team을 평가하는 비용이 크다.**

**Team 개수는 고정 상한이 아니다.** 확장 시 바뀌는 것은 Registry 레코드와 설정뿐이고 Core 코드는 안 바뀐다.

### 필요 Team과 착수 Team을 구분한다

| | |
|---|---|
| **기능상 필요** | Activity · Dining · Mobility · Booking Handoff · Lodging/Flight … |
| **착수** | **Activity · Booking Handoff 둘** (v10 §9-B). 나머지는 4·5주차 |

**몇 개를 만들 것인가는 아키텍처 제약이 아니라 일정 문제다.**

## Port 3종을 같은 원칙으로 둔다

`[실측]` 모듈형 Basement의 실행 경계. **2026-09-01 기준 셋 다 구현돼 있다.**

| Port | 무엇을 가른다 | 구현 위치 |
|---|---|---|
| `TeamExecutorPort` | **Team을 어디서 실행하는지**와 Controller 판단 | `app/core/remote_team/executor.py` · `a2a_executor.py` |
| `MessageBusPort` | 배달 계약과 구현 | `app/infrastructure/messaging/ports.py` |
| `GraphStorePort` | 관계 조회와 저장소 | `app/core/graph_retrieval/` · `app/infrastructure/graphstore/` |

`+ app/presentation/a2a/agent_card.py` — 우리가 A2A **서버**로서 발행하는 capability 문서

### MVP가 여기까지인 이유

**Port와 어댑터까지만 만들고 본체는 안 만든다.**

| 안 만드는 것 | 왜 |
|---|---|
| Graph 저장소 본체 | **"현재 규모에서는 JOIN이 맞다"** → [D-002](../decisions/D-002-graph-store-gate.md) |
| 완전한 A2A 서버 | **MVP는 경로 분리와 Port 확보다.** 개인 AI는 MCP(완료), 기업 Agent는 A2A(골격) |

**교체 지점만 확보하고 구현은 필요할 때 채운다.**

### `TeamExecutorPort`

```
LocalTeamExecutor   MessageBusPort 로 Task 발행 → 내부 Team Slot 이 처리
A2ATeamExecutor     A2A Adapter 로 Remote Agent System 에 위임
```

**Controller는 두 구현을 구분하지 않는다.** Registry의 `execution_type`을 보고 Executor를 고르는 일은 **Registry/Factory의 책임**이다.

**두 경로의 결과는 모두 `TeamResult`로 정규화되어 Shared State에 반영된다.**

## 성공 판정

> **Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.**

새 Team 추가에 필요한 것이 이것뿐이어야 한다.

```
1. Team 모듈 작성 (TeamManifest + 계약 구현)
2. Registry에 등록
```

Core 파일을 하나라도 고쳐야 하면 실패다.

## 현재 상태

`[실측 2026-09-09]` **여행 Team 여섯이 붙었고 커머스 여섯은 등록에서 빠졌다.** 단위·계약·아키텍처 테스트 552개 통과. **Core 격리 위반 0**은 유지된다.

★**그런데 여행 Case 가 아직 안 돈다.** 코어 1 의 분류기 어휘가 쇼핑몰(`order`·`shipping`·`return`·`exchange`·`other`)이라 여행 라벨을 넣으면 `ClassificationFailed` 로 떨어지고 **여섯 팀 중 아무도 안 불린다**(다른 세션 실측 2026-09-09). Team 이 붙은 것과 도는 것은 다르다.

★**이 문서를 "지금 이렇게 돌고 있다"로 읽으면 안 된다.** 조립은 되고 라우팅이 아직 안 된다.

## Pack 범위 판단

`[실측]` v10 §5·§9-B.

| 순서 | Team | 근거 |
|---|---|---|
| **MVP 필수** | **Activity** | 취소·변경 규정이 문서로 존재해 판정 규칙을 바로 쓴다. 예약금이 걸려 실패 비용이 크다 |
| **MVP 필수** | **Booking Handoff** | 우리 일정을 고쳐도 업체 예약을 못 바꾸면 고객이 직접 처리한다 (팀 결정 2026-09-08) |
| 4주차 | Dining | |
| 5주차 | Mobility | 선제 조정 루프와 함께 |
| 등록만 | Lodging / Flight | 잠긴 예약으로만 취급한다 |

**6명 팀 전체가 이 구성으로 고정된다는 뜻은 아니다.**

실제 업체 예약 실행은 Mock 으로 남긴다 — 실결제는 구현 단계 4다(v10 §4-C).

## Vision

지금 안 하는 것. 계획 생성 자체, 실결제, 전 도시 확장.

**Pack 구조가 이걸 나중에 가능하게 만드는 장치다.** 지금 만들지는 않는다.

★**그리고 다음 도메인 교체도 이 구조가 감당해야 한다.** 무엇을 갈아 끼우고 무엇을 안 끼우는지는 [../../final_project_cs/wiki/domain-swap.md](../../final_project_cs/wiki/domain-swap.md) 가 정본이다.

## 관계

- [core-vs-team.md](core-vs-team.md) — 판정 기준 상세
- [../product/scope.md](../product/scope.md) — Pack별 착수 범위
- [../product/positioning.md](../product/positioning.md) — 상업적 근거
- [`cs/teams/index.md`](../../final_project_cs/wiki/teams/index.md) — 도메인 Team
- [`cs/domain-swap.md`](../../final_project_cs/wiki/domain-swap.md) — **무엇을 갈아 끼우고 무엇을 안 끼우나**
- [`sample/wiki/teams/`](../../final_project_sample/wiki/teams/index.md) — **계약이 성립한다는 증거.** 예시 Team 이 여기 있다
- [../governance/domain-axis.md](../governance/domain-axis.md) — 이 문서가 도메인에 묶여 있는지 표시하는 규칙
