---
type: decision
title: Graph Store는 채택 게이트 통과 시에만
description: MVP는 SqlGraphAdapter다. 별도 Graph DB는 정확도·비용·지연 게이트를 통과할 때만 도입한다
status: draft
tags: [architecture, data]
owners: [human:미배정]
---

# D-002 Graph Store는 채택 게이트 통과 시에만

## 맥락

Case·Issue·Policy·Team·Action 사이의 관계 탐색이 필요하다. GraphRAG나 별도 Graph DB(Neo4j, AGE)를 쓸지 판단해야 했다.

## 결정

> **MVP 구현체는 `SqlGraphAdapter`다. 별도 Graph Store는 채택 게이트를 통과할 때만 선택한다.**

`GraphStorePort`를 두고 구현을 교체 가능하게 만든다.

## 선택지와 이유

| 안 | 채택 | 이유 |
|---|---|---|
| **SqlGraphAdapter (PostgreSQL)** | ✅ MVP | 관계가 이미 FK로 정형화돼 있다 |
| Neo4j / AGE | 게이트 통과 시 | 운영 비용과 Projection 동기화 부담 |
| 비정형 문서에서 LLM으로 그래프 추출 | ❌ | 아래 참조 |

### LLM 그래프 추출을 안 하는 이유

우리 관계는 **PostgreSQL FK로 이미 정형화돼 있다.** 다시 추출할 이유가 없다.

`[외부]` 외부 리서치에서는 Vector RAG 대비 3~5배 비용, 엔티티·관계 환각 위험, 엔터프라이즈 RAG 구현의 72~80%가 프로덕션에 도달하지 못했다는 분석이 보고됐다. **이 수치는 외부 인용이며 우리 환경 측정치가 아니다.**

### 별도 Graph Store의 숨은 비용

`[추정]` 25~40인·일. Graph DB를 띄우는 비용이 아니라 **Projection 동기화와 검증**을 포함한 추가 작업량이다.

## 채택 게이트

셋 다 통과해야 도입한다.

| 축 | 기준 |
|---|---|
| 정확도 | SqlGraphAdapter 대비 유의미한 개선 |
| 비용 | 추가 운영 비용이 개선에 비례 |
| 지연 | p95가 악화되지 않음 |

`[미확보]` 구체 임계값은 8~9주차 비교 실험에서 정한다.

## 결과

- `GraphStorePort` 인터페이스를 먼저 만든다
- MVP는 SQL로 간다
- **실패하면 버린다.** 게이트를 못 넘으면 그냥 SQL로 남는다

## 못 하게 되는 것

- 깊은 다중 홉 관계 탐색은 MVP에서 못 한다
- 그래프 기반 추천·유사 케이스 탐색은 범위 밖

## 왜 Port를 지금 만드는가

**A2A 경계와 다르다.** A2A는 나중에 넣으면 Controller·Registry·계약·상태 매핑을 전부 다시 건드려야 한다. 실행 경로가 코드 전반에 퍼지기 때문이다.

**반면 `GraphStorePort`는 저장소 교체 문제라 Port만 두면 구현을 뒤로 미룰 수 있다.**

## 관계

- [../research/graphrag.md](../research/graphrag.md) — 조사 원본
- [../architecture/index.md](../architecture/index.md) — Port/Adapter 구조
