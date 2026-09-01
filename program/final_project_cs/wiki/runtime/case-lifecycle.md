---
type: contract
title: Case 생명주기
description: Case가 지나는 12개 상태와 허용 전이. 실패는 조용히 성공이 되지 않는다
status: draft
tags: [state, architecture]
owners: [human:미배정]
---

# Case 생명주기

`app/domain/events.py` · `app/core/transition.py` (232줄)

## 12개 상태

`[실측]` `INV-CS-RT-012`가 정확히 12개임을 검사한다.

| 상태 | 뜻 |
|---|---|
| `new` | 막 생성됨 |
| `classifying` | 감성·의도·이슈 분류 중 |
| `routing` | Team 선택 중 |
| `running` | Team 처리 중 |
| `waiting_input` | 고객 추가 입력 대기 |
| `waiting_approval` | 사람 승인 대기 |
| `waiting_external` | 외부 callback 대기 |
| `resuming` | 대기 해제 후 재개 중 |
| `resolved` | 해결 |
| `escalated` | 사람에게 넘김 |
| `failed` | 실패 |
| `cancelled` | 취소. **종단** |

## 허용 전이

`[실측]` 전이표 전문.

```text
new             → classifying · cancelled
classifying     → routing · escalated
routing         → running · escalated
running         → waiting_input · waiting_approval · waiting_external
                  resolved · failed · escalated
waiting_input   → resuming · escalated
waiting_approval→ resuming · escalated
waiting_external→ resuming · escalated
resuming        → running · escalated
resolved        → cancelled
escalated       → cancelled
failed          → escalated
cancelled       → (없음)
```

**세 가지 성질이 보인다.**

1. **어느 상태에서든 `escalated`로 갈 수 있다.** 막히면 사람에게 넘기는 게 항상 가능하다
2. **대기 상태는 `resuming`을 거쳐야 `running`으로 돌아간다.** 직접 못 간다
3. **`failed`는 종단이 아니다.** `escalated`로 간다. 실패를 방치하지 않는다

## ★ 전이표 자체를 테스트한다

`[실측]` `tests/contract/test_case_state_table.py`의 주석이 이유를 밝힌다.

> 코드의 전이표는 조용히 늘어난다. "이 전이도 필요하겠지" 하고 하나 추가하면 상태 기계가 계획서와 어긋나는데 **기존 테스트는 전부 통과한다.** 그래서 **표 자체를 검사**한다.

그리고 대조 기준을 **코드에서 가져오지 않는다.**

> 계획서를 보고 손으로 옮겨야 대조가 성립한다.

**이게 좋은 테스트 설계다.** 코드에서 기대값을 읽으면 언제나 통과한다.

## 조용히 넘어가지 않는다

이 상태 기계의 핵심 성질이다. 넷 다 테스트가 강제한다.

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-RT-017` | **분류 실패는 조용히 진행하지 않고 escalate한다** | `tests/contract/test_case_state_table.py::test_classification_failure_escalates_not_silently_continues` |
| `INV-CS-RT-018` | **대기 만료는 자동 resolve하지 않고 escalate한다** | `tests/contract/test_case_state_table.py::test_wait_expiry_escalates_not_auto_resolves` |
| `INV-CS-RT-019` | 반려된 승인은 resume하지 않는다 | `tests/contract/test_case_state_table.py::test_rejection_does_not_resume` |
| `INV-CS-RT-020` | 분류 실패 시 라벨을 비운다 | `tests/unit/core/test_case_reducer.py::test_classification_failure_leaves_labels_empty` |

**`INV-CS-RT-018`이 특히 값지다.** 대기가 만료됐을 때 "그냥 완료 처리"하면 **고객은 답을 못 받았는데 시스템은 해결됐다고 본다.** 이걸 테스트가 막는다.

## 상태 기계 불변식

| ID | 불변식 | 실행 위치 |
|---|---|---|
| `INV-CS-RT-012` | 상태는 정확히 12개다 | `tests/contract/test_case_state_table.py::test_all_twelve_statuses_exist` |
| `INV-CS-RT-013` | `cancelled`는 종단 상태다 | `tests/contract/test_case_state_table.py::test_cancelled_is_terminal` |
| `INV-CS-RT-014` | 허용 전이 표가 기준과 일치한다 | `tests/contract/test_case_state_table.py::test_allowed_next_statuses_match_v5` |
| `INV-CS-RT-015` | 불법 전이는 거부된다 | `tests/unit/core/test_case_reducer.py::test_illegal_transition_is_rejected` |
| `INV-CS-RT-016` | 모든 이벤트가 전이 표에서 쓰인다 | `tests/contract/test_case_state_table.py::test_every_event_is_used_in_transition_table` |

**`INV-CS-RT-016`이 죽은 이벤트를 막는다.** 정의만 있고 아무 데도 안 쓰이는 이벤트가 남으면 나중에 혼란을 준다.

## 단일 진입점

**`customer_cases`를 직접 `UPDATE`하지 않는다.** `transition_case()`만이 진입점이다.

`case_events`는 append-only다. `UPDATE`·`DELETE`하지 않는다.

```
transition_case()  →  case_events 추가  →  customer_cases projection 갱신
```

`replay_case()`로 이벤트를 재생해 상태를 복원할 수 있다. 재생은 결정적이다(`INV-CS-RT-001`).

## LangGraph checkpoint와 구분한다

**checkpoint로 업무 상태를 되돌리지 않는다.**

| | 무엇 |
|---|---|
| LangGraph checkpoint | 실행 snapshot |
| `customer_cases` | **업무 상태의 권위 있는 projection** |

둘을 섞으면 어느 쪽이 진짜인지 알 수 없어진다.

## `TeamResult`와의 대응

Team의 `next_action`이 상태 전이를 만든다.

| `next_action` | Case 상태 |
|---|---|
| `respond` | `resolved` |
| `wait_for_input` | `waiting_input` |
| `wait_for_approval` | `waiting_approval` |
| `handoff` | `routing` (다른 Team으로) |
| `escalate` | `escalated` |
| `continue` | `running` 유지 |

계약이 조합을 강제한다. → [../teams/team-contract.md](../teams/team-contract.md)

## 관계

- [shared-state.md](shared-state.md) — 상태 저장과 버전
- [conflict-retry.md](conflict-retry.md) — 동시 전이 충돌
- [agentic-controller.md](agentic-controller.md) — 전이를 지시하는 쪽
- [../teams/team-contract.md](../teams/team-contract.md) — `next_action`
- [../quality/invariants.md](../quality/invariants.md) — 불변식 전체
