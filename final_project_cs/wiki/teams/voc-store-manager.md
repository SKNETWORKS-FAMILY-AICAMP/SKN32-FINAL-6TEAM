---
type: concept
title: VOC & Store Manager Team
description: 이상 징후를 판별하고 다른 Team에 위임을 제안한다. 집계가 아니라 업무 판단이 Team 자격의 근거다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
---

# VOC & Store Manager Team

`app/modules/customer_ops/voc_store_manager.py`

**CS Pack. 10주 착수 확정.**

## manifest

`[실측]`

```python
capabilities        = ["voc.aggregate", "voc.escalate"]
accepted_case_types = ["other"]
required_context    = ["case_state", "policy", "db_facts", "history"]
allowed_tools       = ["read.policy"]
knowledge_scope     = ["order", "shipping", "return", "exchange"]
max_steps           = 6
```

`llm`을 주입받는 두 Team 중 하나다.

```python
def __init__(self, tools: ReadToolbox, llm: Any | None = None): ...
```

## ★ [v8 재판정] 관측층과 판단층을 나눈다

`[실측]` v8 §7이 이 Team의 자격을 **다시 판정했다.** 이전 서술은 낡았다.

| 조각 | 소유 | 근거 |
|---|---|---|
| **집계·시계열·임계값·급증 탐지** | **코어 1** | 전역 관측. Controller 조정 책임과 성격이 같다. 산출물은 `feedback_analytics_reports` |
| **원인 축 판별·위임 대상 결정** | VOC Team | 실제 업무 판단. **다만 현재 구현이 없다** |

### 왜 재판정했나

v7이 VOC를 Team으로 올린 근거가 **개정 기록에 남지 않았다.**

v7.1이 방어한 자격의 핵심은 "급증 이후 원인 축을 판별하고 위임 대상과 필요 증거를 결정하는 업무 판단"인데, **착수 명세는 SQL 집계와 고정 임계값**이다. LLM 판단은 "넣는 시점에"라는 **미래형으로만** 적혀 있다.

> **아직 없는 기능을 근거로 Team 슬롯을 유지하는 것은 "슬롯을 맞추지 않고 모듈 가치로 판단한다"에 어긋난다.**

### 그래도 등록은 지우지 않는다

Billing/Technical 2종을 "아키텍처 동작 증거로만 남긴다"고 처리한 것과 **같게 다룬다.**

**나중에 LLM 위임 판단을 실제로 넣으면 껍데기가 알맹이를 갖는다.** 그때 구조를 다시 건드리지 않는다.

**Registry 등록형이라 Team 추가가 리팩토링이 아니라는 원칙이 이 미룸을 정당화한다.** → [pack-model](../../../wiki/architecture/pack-model.md)

### 지금 상태

**VOC Team은 껍데기다.** 입력은 `Case events·분류 결과·Action 결과`와 **코어 1이 만든 일일 리포트**다.

`[미확보]` 원인 축 판별 로직이 아직 없다.

## 입출력

```
입력  Case events · 분류 결과 · Action 결과      (Context Broker 경유)
출력  리포트 · 알림 · 다른 Team으로의 위임 제안   (TeamResult)
```

**다른 Team을 직접 호출하지 않는다.** Controller가 Task로 변환한다. → [team-boundary.md](team-boundary.md)

## `knowledge_scope`가 넓다

```python
knowledge_scope = ["order", "shipping", "return", "exchange"]
```

**`allowed_tools`는 `read.policy` 하나뿐인데 지식 범위는 넓다.**

이상 징후를 판별하려면 여러 업무를 알아야 하지만, **직접 조회할 권한은 필요 없다**는 설계다. 집계 자료는 Context Broker가 넣어준다.

## `accepted_case_types = ["other"]`

다른 Team이 안 받는 것을 받는다. **분류가 애매한 문의의 종착지다.**

`[실측]` 재발 방지 불변조건이 있다.

```
INTENTS ⊇ 모든 Team.accepted_case_types
```

분류기가 내는 intent에 대응 Team이 없으면 Case가 갈 곳이 없어진다. 실제로 그런 결함이 있었다. → [../external/rest-api.md](../external/rest-api.md)

## 이상의 정의

**"이상"은 수치의 절대값이 아니라 기준선 대비 정해진 변화가 생긴 상태다.**

```
내부 단계  fixture 기준선
알파부터   유형·시간대별 baseline 저장
```

`[미확보]` **정확한 임계값은 실제 분포 측정 후 확정한다.**

## 지표

`VOC precision` = 유효 alert 수 / 검토 alert 수

**alert가 많다고 좋은 게 아니다.** 운영자가 무시하기 시작하면 없는 것과 같다.

→ [../../../wiki/evaluation/metrics.md](../../../wiki/evaluation/metrics.md)

## 관계

- [team-contract.md](team-contract/index.md) — 계약
- [team-boundary.md](team-boundary.md) — 위임 규칙
- [response-review.md](response-review.md) — 같은 CS Pack
- [../../../wiki/product/personas.md](../../../wiki/product/personas.md) — 정미라가 이 alert를 본다
