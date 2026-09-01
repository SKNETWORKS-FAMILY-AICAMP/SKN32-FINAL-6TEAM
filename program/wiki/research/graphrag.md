---
type: research
title: GraphRAG와 Graph Store 검토
description: 관계 탐색에 별도 Graph DB가 필요한지 조사. D-002로 이어졌다
status: draft
tags: [architecture, data]
owners: [human:미배정]
---

# GraphRAG와 Graph Store 검토

조사 시점 `[미확보]` 정확한 날짜 미기록. 2026-08 중.

**결정은 [../decisions/D-002-graph-store-gate.md](../decisions/D-002-graph-store-gate.md)에 있다.** 여기는 재료다.

## 조사한 것

Case·Issue·Policy·Team·Action 사이의 관계 탐색에 무엇을 쓸지.

| 선택지 | 검토 결과 |
|---|---|
| PostgreSQL (SqlGraphAdapter) | 관계가 이미 FK로 정형화돼 있음 |
| Neo4j / Apache AGE | 운영 비용 + Projection 동기화 부담 |
| 비정형 문서에서 LLM 그래프 추출 | 우리 상황에 불필요 |

## 외부 리서치 수치

**`[외부]` 아래는 전부 외부 인용이며 우리 환경 측정치가 아니다.**

| 주장 | 출처 성격 |
|---|---|
| GraphRAG는 Vector RAG 대비 3~5배 비용 | 외부 분석 |
| 엔티티·관계 환각 위험 | 외부 분석 |
| 엔터프라이즈 RAG 구현의 72~80%가 프로덕션 미도달 | 외부 분석 |

**이 수치를 우리 결과처럼 쓰면 안 된다.** 심사에서 "직접 재보셨나요"에 답할 수 없다.

## 왜 LLM 그래프 추출이 불필요한가

**우리 관계는 PostgreSQL FK로 이미 정형화돼 있다.**

```
tenants → customers → customer_cases → case_events
customer_cases → agent_runs → team_tasks
customer_cases → action_requests → action_approvals
knowledge_documents → knowledge_chunks
```

비정형 문서에서 관계를 추출하는 기법은 **관계가 정형화돼 있지 않을 때** 쓰는 것이다. 우리는 이미 있다.

## 별도 Graph Store의 숨은 비용

`[추정]` 25~40인·일.

**Graph DB를 띄우는 비용이 아니다.** Projection 동기화와 검증을 포함한 추가 작업량이다.

| 작업 | 성격 |
|---|---|
| Projection 설계 | PostgreSQL → Graph 동기화 |
| 동기화 검증 | 두 저장소가 어긋나지 않는지 |
| 운영 | 백업·복구·모니터링 |

**이중 저장소는 이중 장부 위험을 만든다.** 어느 쪽이 진짜인지 판정해야 한다.

## 채택 게이트

세 축을 전부 통과해야 도입한다.

| 축 | 기준 |
|---|---|
| 정확도 | SqlGraphAdapter 대비 유의미한 개선 |
| 비용 | 추가 운영 비용이 개선에 비례 |
| 지연 | p95가 악화되지 않음 |

`[미확보]` 구체 임계값은 8~9주차 비교 실험에서 정한다.

## 결론

`GraphStorePort`를 두고 MVP는 SQL로 간다. **실패하면 버린다.**

Port를 지금 만드는 이유는 저장소 교체가 나중에 가능하도록 하기 위해서다. A2A 경계와 달리 **구현을 뒤로 미룰 수 있는 종류의 문제**다.

## 관계

- [../decisions/D-002-graph-store-gate.md](../decisions/D-002-graph-store-gate.md) — 이 조사로 내린 결정
- [../architecture/index.md](../architecture/index.md) — Port/Adapter 구조
- [../governance/evidence-grades.md](../governance/evidence-grades.md) — `[외부]` 표기 규칙
