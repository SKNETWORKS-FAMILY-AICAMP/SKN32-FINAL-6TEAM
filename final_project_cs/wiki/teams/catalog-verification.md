---
type: concept
title: Catalog & Verification Team
description: 상품 조회와 등록 검증. A2A Remote 후보다
status: draft
tags: [agent, customer-operations]
owners: [human:미배정]
---

# Catalog & Verification Team

`app/modules/customer_ops/catalog_verification.py` · `verification_policy.py`

**Commerce Ops Pack. A2A Remote 후보다.**

## manifest

`[실측]`

```python
capabilities        = ["catalog.lookup_sku", "catalog.verify_listing", "catalog.compliance_check"]
accepted_case_types = ["catalog"]
required_context    = ["case_state", "policy", "db_facts", "history"]
allowed_tools       = ["read.catalog", "read.order_items", "read.policy"]
knowledge_scope     = ["catalog"]
max_steps           = 6
```

`knowledge_scope`가 `["catalog"]` 하나뿐이다. **가장 좁다.**

## ★ 없는 능력을 받으면 escalate한다

`[실측]` dojo가 심은 결함이 여기서 잡혔다.

```
"계약에 없는 능력을 받아도 처리한다"
  → test_compliance_check_always_escalates_without_claiming_a_result 외 4건
```

**테스트 이름이 규칙을 그대로 말한다.** `compliance_check`는 **항상 escalate하고 결과를 주장하지 않는다.**

법령 준수 판정은 우리가 할 일이 아니다. **할 수 없는 것을 할 수 있는 척하지 않는다.**

## 왜 A2A Remote 후보인가

상품 검증은 **외부 전문 시스템**이 하는 게 자연스럽다.

| | |
|---|---|
| 장기 실행 | 검증에 시간이 걸린다 |
| 추가 입력 | 중간에 정보를 더 요구할 수 있다 |
| Artifact | `verification_report`, `evidence_manifest` |

**A2A의 세 조건을 다 만족한다.** 단순 조회가 아니다.

→ [../external/a2a-protocol.md](../external/a2a-protocol.md)

## Remote 실행 시 흐름

```
Controller → A2ATeamExecutor → 원격 Agent
                 ↓
   TeamResult(outcome="waiting", next_action="escalate",
              wait_reason="external_callback")
                 ↓
   Case → waiting_external
                 ↓
   (원격이 package_unit 등 추가 입력을 요구하면)
   Controller가 내부 Catalog Team 또는 운영 UI에 질문 전달
                 ↓
   A2A Task 에 resume 입력
                 ↓
   완료 시 Artifact 반환
```

**Artifact의 근거 식별자는 Context/DB와 대조한 뒤 Shared State에 저장한다.** 원격이라고 예외를 두지 않는다.

## 정책이 분리돼 있다

```
catalog_verification.py   실행
verification_policy.py    판정 기준
```

Response Review와 같은 구조다. **판정 기준이 자주 바뀔 것을 예상한 설계다.**

`[실측]` `verification_policy.py`가 **표시용 `evidence` 필드를 거부해 승인이 409로 막히는 결함**이 있었다. 브라우저로 승인 버튼을 눌러 발견하고 고쳤다.

## 관련 테스트

```
tests/integration/db/test_procurement_catalog.py
tests/integration/a2a/test_remote_round_trip.py
```

## 관계

- [team-contract.md](team-contract/index.md) — 계약
- [remote-team-a2a.md](remote-team-a2a.md) — 원격 실행
- [../external/a2a-protocol.md](../external/a2a-protocol.md) — 프로토콜
- [../actions/evidence-check.md](../actions/evidence-check.md) — Artifact 대조
