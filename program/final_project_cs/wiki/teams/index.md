---
type: guide
title: Teams
description: 업무 책임 단위. Registry 등록형이라 추가해도 Core가 안 바뀐다
status: draft
---

# Teams

`app/modules/customer_ops/`

**Team을 늘리는 일이 리팩토링이 되면 설계가 잘못된 것이다.** Registry 등록만으로 끝나야 한다.

## 읽기 순서

1. [team-contract.md](team-contract.md) — 무엇을 구현해야 하는가
2. [team-boundary.md](team-boundary.md) — **무엇을 하면 안 되는가**
3. [team-registry.md](team-registry.md) — 어떻게 등록되는가

## 계약·구조

| 문서 | 답하는 질문 | 코드 |
|---|---|---|
| [team-contract.md](team-contract.md) | `TeamTask` / `TeamResult` 모양 | `app/core/contracts.py` |
| [team-boundary.md](team-boundary.md) | Team이 하면 안 되는 것 셋 | — |
| [team-registry.md](team-registry.md) | capability → Team 해석 | `app/core/registry.py` |
| [remote-team-a2a.md](remote-team-a2a.md) | A2A Remote Team 실행 | `app/core/remote_team/` |

## 구현된 Team

`[실측]` `app/modules/customer_ops/`

| Team | 파일 | Pack | 상태 |
|---|---|---|---|
| [voc-store-manager.md](voc-store-manager.md) | `voc_store_manager.py` | CS | **10주 착수 확정** |
| [response-review.md](response-review.md) | `response_review.py` | CS | **10주 착수 확정** |
| [procurement-order.md](procurement-order.md) | `procurement_order_payment.py` | Commerce | 일정 따라 조정 |
| [fulfillment-logistics.md](fulfillment-logistics.md) | `fulfillment_logistics.py` | Commerce | 동 |
| [return-refund.md](return-refund.md) | `return_refund.py` | Commerce | 동 |
| [catalog-verification.md](catalog-verification.md) | `catalog_verification.py` | Commerce (A2A Remote) | 동 |
| — | `feedback.py` | CS | 인라인 분류 |

정책 파일이 따로 있다.

| 파일 | 무엇 |
|---|---|
| `response_review_policy.py` | 검토 정책 |
| `verification_policy.py` | 검증 정책 |

## Team이 하지 않는 것 셋

**이게 경계의 실체다.**

| 규칙 | 왜 |
|---|---|
| side effect를 실행하지 않는다 | 승인 경계 우회, 이중 실행, 감사 누락을 막는다 |
| read 도구를 직접 호출하지 않는다 | Context Broker가 읽기 예산을 통제한다 |
| 다른 Team을 직접 호출하지 않는다 | 의존 그래프가 생기면 교체가 불가능해진다 |

상세는 [team-boundary.md](team-boundary.md).

## Team의 read 도구

`[실측]` Team별 `allowed_tools`

| Team | 허용 도구 |
|---|---|
| Procurement + Order & Payment | `read.order`, `read.account`, `read.policy`, `read.catalog` |
| Return & Refund | `read.order`, `read.return`, `read.policy` |
| Fulfillment & Logistics | `read.order`, `read.shipment`, `read.policy` |
| Catalog & Verification | `read.catalog`, `read.order_items`, `read.policy` |
| Response Review | `read.policy` |

**결제 조회 도구는 없다.** Team 이름에 "Payment"가 있지만 실제 권한은 없다. → [D-001](../../../wiki/decisions/D-001-payment-ownership.md)

## 이 영역의 불변식

| ID | 불변식 | 판정 |
|---|---|---|
| `INV-CS-TEAM-001` | Team manifest는 프로토콜을 구현한다 | automated |
| `INV-CS-TEAM-002` | manifest의 scope는 정확히 선언된다 | automated |
| `INV-CS-TEAM-003` | Team은 side effect를 실행하지 않는다 | **review** |
| `INV-CS-TEAM-004` | Team은 read 도구를 직접 호출하지 않는다 | **review** |
| `INV-CS-TEAM-005` | Team은 다른 Team을 직접 호출하지 않는다 | **review** |

`[미확보]` **003~005가 자동 판정이 아니다.** 설계의 핵심 규칙인데 사람이 리뷰에서 잡아야 한다.

## sample의 Team

`final_project_sample`에 Billing/Technical 2종이 있다. **10주 착수 목록에 없다.**

Team-플러그인 아키텍처가 실제로 동작한다는 증거(Core 격리 위반 0)로만 남긴다.

## 인접 영역

- [../runtime/agentic-controller.md](../runtime/agentic-controller.md) — Team을 호출하는 쪽
- [../context/index.md](../context/index.md) — Team의 입력을 만드는 곳
- [../actions/action-proposal.md](../actions/action-proposal.md) — Team의 출력이 가는 곳
- [../../../program/wiki/architecture/core-vs-team.md](../../../wiki/architecture/core-vs-team.md) — Team 자격 판정
