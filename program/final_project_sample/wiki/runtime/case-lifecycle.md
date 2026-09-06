---
type: concept
title: Case 생명주기와 상태 전이
description: Case 상태의 종류와 확인된 전이 규칙, 상태를 쓸 수 있는 주체를 설명한다.
status: draft
tags: [architecture, state, contract]
---

Case 상태는 12개다. 상태 변경은 이벤트를 순수 리듀서에 적용한 뒤 `transition_case()`를 통해 저장하는 방식이다. `[실측]` `core/contracts.py:53`, `core/transition.py:119`

## 상태

`[실측]` `CaseStatus`에 선언된 상태는 다음과 같다. `core/contracts.py:53-65`

| 상태 | 의미를 코드에서 확인한 범위 |
|---|---|
| `new` | 새 projection의 초기 상태다. `tests/unit/core/test_case_reducer.py:25-26` |
| `classifying` | `created` 이벤트 뒤의 상태다. `tests/unit/core/test_case_reducer.py:32-35` |
| `routing` | 분류 뒤 Controller가 Team을 선택하는 상태다. `application/controller.py:115-127` |
| `running` | Team 실행이 가능한 상태다. `tests/unit/core/test_case_reducer.py:38-48` |
| `waiting_input` | 고객 입력을 기다린다. `application/controller.py:230-234` |
| `waiting_approval` | 제안된 action의 승인을 기다린다. `application/controller.py:235-253` |
| `waiting_external` | Enum에는 존재한다. 이 상태로 들어가거나 나오는 실행 경로는 지정된 코드와 테스트에서 확인하지 못했다. `[미확보]` |
| `resuming` | 입력 또는 승인 뒤 실행 재개를 준비한다. `application/controller.py:132-139` |
| `resolved` | 완료 이벤트를 적용한 결과다. `tests/unit/core/test_case_reducer.py:126-135` |
| `escalated` | 분류·라우팅·대기 등의 실패를 상위 처리로 넘긴 결과다. `tests/unit/core/test_case_reducer.py:86-94`, `tests/integration/controller/test_controller_integration.py:332-340` |
| `failed` | Enum에는 존재한다. 이 상태로 들어가거나 나오는 실행 경로는 지정된 코드와 테스트에서 확인하지 못했다. `[미확보]` |
| `cancelled` | 사용자 취소 결과이며, 적어도 `created` 이벤트를 더 적용할 수 없는 종료 상태다. `tests/unit/core/test_case_reducer.py:57-61` |

## 확인된 전이

아래 표는 지정된 코드와 테스트에서 확인된 전이만 담는다. 전체 리듀서 전이표는 제공된 읽기 범위에 없으므로 이 표 밖의 전이는 `[미확보]`다.

| 현재 상태 | 이벤트 | 다음 상태 | 근거 |
|---|---|---|---|
| `new` | `created` | `classifying` | `[실측]` `tests/unit/core/test_case_reducer.py:32-35` |
| `new` | `cancelled_by_user` | `cancelled` | `[실측]` `tests/unit/core/test_case_reducer.py:57-61` |
| `classifying` | `classified` | `routing` | `[실측]` `tests/unit/core/test_case_reducer.py:38-48`, `application/controller.py:115-121` |
| `classifying` | `classification_failed` | `escalated` | `[실측]` `tests/unit/core/test_case_reducer.py:86-94` |
| `routing` | `routed` | `running` | `[실측]` `tests/unit/core/test_case_reducer.py:38-48` |
| `routing` | `routing_failed` | `escalated` | `[실측]` `application/controller.py:122-126`, `tests/integration/controller/test_controller_integration.py:332-340` |
| `running` | `missing_input` | `waiting_input` | `[실측]` `application/controller.py:230-234`, `tests/integration/controller/test_controller_integration.py:210-234` |
| `waiting_input` | `valid_input` | `resuming` | `[실측]` `application/controller.py:289-295`, `tests/integration/controller/test_controller_integration.py:210-234` |
| `waiting_input` | `wait_expired` | `escalated` | `[실측]` `application/controller.py:267-288`, `tests/integration/controller/test_controller_integration.py:237-250` |
| `running` | `approval_required` | `waiting_approval` | `[실측]` `application/controller.py:235-253`, `tests/integration/controller/test_controller_integration.py:178-207` |
| `waiting_approval` | `approved` | `resuming` | `[실측]` `tests/unit/core/test_case_reducer.py:115-123`, `tests/integration/controller/test_controller_integration.py:178-207` |
| `waiting_approval` | `rejected` | `escalated` | `[실측]` `tests/unit/core/test_case_reducer.py:151-155` |
| `waiting_approval` | `wait_expired` | `escalated` | `[실측]` `tests/unit/core/test_case_reducer.py:158-161` |
| `resuming` | `resumed` | `running` | `[실측]` `tests/unit/core/test_case_reducer.py:115-123`, `tests/integration/controller/test_controller_integration.py:201-207` |
| `running` | `completed` | `resolved` | `[실측]` `tests/unit/core/test_case_reducer.py:115-135` |

`new`에서 `completed`를 바로 적용하면 `InvalidTransition`이 발생한다. 즉, 상태 이름을 직접 지정하는 방식이 아니라 현재 상태에서 허용된 이벤트인지 검사한다. `[실측]` `tests/unit/core/test_case_reducer.py:51-54`, `core/transition.py:151-154`

이벤트별 필수 payload도 검증한다. 예를 들어 `classified`에는 `intent`, `issue_code`, `sentiment`가 모두 필요하다. `[실측]` `tests/unit/core/test_case_reducer.py:67-80`

입력·승인·외부 콜백의 재개 지점은 각각 `validate_input`, `execute_approved_action`, `verify_external_result`로 매핑된다. `[실측]` `core/contracts.py:78-86`

전이가 성공할 때마다 version이 1 증가하며, 테스트된 이벤트 재생에서는 version이 적용한 이벤트 수와 같다. `[실측]` `core/transition.py:61-69`, `tests/unit/core/test_case_reducer.py:142-145`

## 쓰기 주체

Case projection을 저장하는 단일 진입점은 `transition_case()`다. 모듈 계약상 Controller, API, worker는 `customer_cases`를 직접 갱신하지 않고 이 함수를 사용한다. `[실측]` `core/transition.py:1-13`

Controller는 라우팅, 재개, 완료, 대기, 에스컬레이션 이벤트를 `transition_case()`로 기록한다. `[실측]` `application/controller.py:120-124`, `application/controller.py:135-155`, `application/controller.py:166-170`, `application/controller.py:283-296`

Team은 `TeamResult`와 `ActionProposal`을 반환한다. 제안된 side effect를 Team이 직접 실행하는 계약은 아니다. `[실측]` `core/contracts.py:201-215`, `core/contracts.py:223-295`

`transition_case()`의 `actor_type`은 제한된 Enum이 아니라 임의 문자열이고 `actor_id`도 선택값이다. 함수 내부에는 호출 주체 allowlist 검사가 없다. 따라서 실제 호출 권한을 누가 검사하는지는 지정된 읽기 범위에서 확인하지 못했다. `[실측]` `core/transition.py:119-130` `[미확보]`

## 관계

- [shared-state.md](shared-state.md)
- [conflict-retry.md](conflict-retry.md)
- [idempotency.md](idempotency.md)
