# DoD-21 — `SqlGraphAdapter` 관계 질의 3종의 정확성

- v7 §27 항목 21 / 검증 방법: Case→Issue→Policy, Issue→Team, Case→Action fixture assertion
- 실행: 2026-08-16
- 판정: 통과

> ★2026-09-06 낡음 확인 — evidence 출력의 `team:billing_subscription` 등은 퇴역 식별자다(지금 fixture는 `team:order_shipping`·`issue:post_cancel_charge`). 어댑터가 도메인 무관이라 판정은 유효. 대조 기록: `program/final_project_cs/wiki/quality/dod-evidence-drift.md`

## 재현 명령

```powershell
python -m pytest tests/unit/infrastructure/test_sql_graph_adapter.py -q
python -m pytest tests/unit/infrastructure/test_graph_v7_axes.py -q
```

## 실제 출력

```
tests/unit/infrastructure/test_sql_graph_adapter.py   4 passed
tests/unit/infrastructure/test_graph_v7_axes.py       4 passed

★v7 §27-21 이 지정한 세 축:
test_case_to_issue_to_policy
    case_id --has_issue--> issue:post_cancel_charge   (depth 1)
             --governed_by--> <document_id>            (depth 2)
test_issue_to_team
    issue:post_cancel_charge --handled_by--> team:billing_subscription
test_case_to_action
    case_id --proposed--> <action_id>
test_axes_are_tenant_isolated
    남의 tenant 로 조회 → []

기존 축:
test_path_returns_case_evidence_chunk_document_hops
test_recursive_walk_respects_depth_limit_on_cycle   깊이 제한, 사이클에서 멈춤
```

## 통과한 것

| 요구 | 결과 |
|---|---|
| 관계 질의가 동작한다 | **통과** — path·neighbors·subgraph |
| 재귀 순회에 깊이 제한 | **통과** — 사이클에서 멈춘다 |
| tenant 격리 | **통과** |
| Neo4j/AGE 없이 SQL 로 구현 | **통과** — `WITH RECURSIVE` + JOIN |

## ★처음엔 부분 통과였다 — 축이 달랐다

최초 검토(2026-08-16 오전)에서 이렇게 적었다:

> 질의 자체는 일반화돼 있지만(임의 노드 경로 순회), v7 이 이름으로 지정한 세 축의
> fixture assertion 이 없다. **"일반 질의가 되니 특정 질의도 될 것" 은 추정이다.**

맞았다. 그리고 **없던 기능이 아니라 노출을 안 한 것**이었다 —
`issue_code` 와 `owner_team_id` 는 `customer_cases` 의 **컬럼**이라
노드로 투영하지 않으면 그래프에 나타나지 않는다. edge 세 개를 추가했다:

| edge | 투영 |
|---|---|
| `has_issue` | `case_id` → `issue:{issue_code}` |
| `governed_by` | `issue:{issue_code}` → `document_id` (scope 로 연결) |
| `handled_by` | `issue:{issue_code}` → `team:{owner_team_id}` |

`Case → Action` 은 `proposed` edge 로 **이미 있었다.** assertion 만 없었다.

## 한계

- 성능을 재지 않았다. 재귀 CTE 가 큰 그래프에서 어떻게 되는지 모른다
- GraphRAG 로서의 검색 품질(v7 §9-D)은 이 항목의 대상이 아니다
- ★`Issue → Policy` 는 `knowledge_documents.scope` 가 Case 의 `intent` 와 겹치는지로 잇는다.
  **의미적 연결이 아니라 scope 문자열 일치다.** 그 정책이 실제로 그 이슈를 다루는지는 보지 않는다
- ★`Issue → Team` 은 **과거에 그 이슈를 처리한 Team** 이다.
  manifest 의 `accepted_case_types` 선언이 아니라 **실적**에서 온다 —
  처리 이력이 없는 이슈는 edge 도 없다
