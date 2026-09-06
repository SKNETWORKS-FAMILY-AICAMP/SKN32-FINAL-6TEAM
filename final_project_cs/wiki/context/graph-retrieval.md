---
type: concept
title: Graph 관계 탐색
description: Case·Issue·Policy·Team·Action 사이를 SQL 재귀 질의로 잇는다. 별도 Graph DB는 없다
status: draft
tags: [data, architecture]
owners: [human:미배정]
---

# Graph 관계 탐색

`app/core/graph_retrieval/port.py` (`GraphStorePort`) · `app/infrastructure/graphstore/sql_adapter.py` (`SqlGraphAdapter`)

## 무엇인가

**Case가 어떤 이슈이고, 그 이슈를 어느 정책이 다루며, 누가 처리했고, 어떤 제안이 나왔는지를 관계로 걷는다.**

별도 Graph DB(Neo4j·AGE)는 없다. PostgreSQL 위에서 `WITH RECURSIVE` + JOIN으로 구현했다. 관계가 이미 FK로 정형화돼 있어서 다시 추출할 이유가 없다는 판단이다. → [D-002](../../../wiki/decisions/D-002-graph-store-gate.md)

## Port로 교체된다

```
GraphStorePort            app/core/graph_retrieval/port.py     Protocol
└─ SqlGraphAdapter        app/infrastructure/graphstore/       MVP 구현체
```

`[실측]` Graph DB를 나중에 넣더라도 Port만 갈아 끼운다. A2A 경계와 달리 저장소 교체 문제라 **구현을 미룰 수 있는 종류**다.

## 세 축

`[실측]` [DoD-21](../../docs/evidence/DoD-21_Graph_관계질의.md)이 요구하는 관계 질의 세 종류와, 그걸 위해 투영한 edge.

| 축 | edge | 어디서 오나 |
|---|---|---|
| Case → Issue → Policy | `has_issue` · `governed_by` | `customer_cases.issue_code` → `issue:{code}` → `knowledge_documents` (scope로 연결) |
| Issue → Team | `handled_by` | `issue:{code}` → `team:{owner_team_id}` |
| Case → Action | `proposed` | `action_requests` — **처음부터 있었다** |

**앞 두 축의 edge 셋은 처음엔 없었다.** `issue_code`와 `owner_team_id`가 `customer_cases`의 **컬럼**이라, 노드로 투영하지 않으면 그래프에 나타나지 않았다. 없던 기능이 아니라 **노출을 안 한 것**이었다.

## 함께 지키는 것

| 성질 | 실측 |
|---|---|
| 재귀 순회에 깊이 제한 | 사이클에서 멈춘다 (`test_recursive_walk_respects_depth_limit_on_cycle`) |
| tenant 격리 | 남의 tenant로 조회 → `[]` |
| Case → evidence chunk → document 홉 | `test_path_returns_case_evidence_chunk_document_hops` |

## ★ 두 축은 보이는 것보다 약하다

`[실측]` 원문이 한계로 적어 둔 것이고, 이 질의를 쓰는 쪽이 알아야 한다.

| 축 | 실제로 잇는 기준 | 뜻 |
|---|---|---|
| **Issue → Policy** | `knowledge_documents.scope`가 Case의 `intent`와 **문자열로 겹치는지** | **의미적 연결이 아니다.** 그 정책이 그 이슈를 실제로 다루는지는 보지 않는다 |
| **Issue → Team** | **과거에 그 이슈를 처리한 Team** | manifest의 `accepted_case_types` **선언**이 아니라 **실적**이다. 처리 이력이 없는 이슈는 edge도 없다 |

두 번째가 놓치기 쉽다. "이 이슈는 누가 담당하나"를 물으면 **담당하기로 한 Team이 아니라 담당했던 Team**이 나온다.

## ★ "일반 질의가 되니 특정 질의도 된다"는 추정이었다

`[실측]` 최초 검토는 부분 통과였다. 임의 노드 경로 순회는 됐지만 v7이 **이름으로 지정한 세 축**의 assertion이 없었다. 실제로 세 축 중 둘은 투영이 없어서 **안 됐다.** 일반화된 기능이 있다는 것과 요구된 질의가 된다는 것은 다르다.

## 안 잰 것

`[미확보]`

- 성능. 재귀 CTE가 큰 그래프에서 어떻게 되는지 모른다
- GraphRAG로서의 검색 품질(v7 §9-D)은 이 항목 밖이다 → [../../../wiki/research/graphrag.md](../../../wiki/research/graphrag.md)

`[실측]` 테스트 fixture 라벨은 옛 식별자다 — `post_cancel_charge`(옛 이슈 코드), `order_shipping`(퇴역 Team). 어댑터가 도메인 무관이라 판정은 유효하지만, evidence 출력의 `team:billing_subscription`과도 다르다. → [../quality/dod-evidence-drift.md](../quality/dod-evidence-drift.md)

## 관계

- [context-broker.md](context-broker.md) — 관계 탐색 결과를 받는 쪽
- [rag-retrieval.md](rag-retrieval.md) — 벡터 검색. 이건 관계, 저건 유사도
- [../../../wiki/decisions/D-002-graph-store-gate.md](../../../wiki/decisions/D-002-graph-store-gate.md) — 별도 Graph DB를 안 쓰는 결정
- [../data/schema/fields.md](../data/schema/fields.md) — `agent_runs.graph_revision` 등 컬럼
