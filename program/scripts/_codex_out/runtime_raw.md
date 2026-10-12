===== FILE: case-lifecycle.md =====
---
type: concept
title: Case 생명주기와 상태 전이
description: Case 상태의 종류와 확인된 전이 규칙, 상태를 쓸 수 있는 주체를 설명한다.
status: draft
tags: [architecture, state, contract]
---

Case 상태는 12개다. 상태 변경은 이벤트를 순수 리듀서에 적용한 뒤 `transition_case()`를 통해 저장하는 방식이다. [실측] `core/contracts.py:53`, `core/transition.py:119`

## 상태

[실측] `CaseStatus`에 선언된 상태는 다음과 같다. `core/contracts.py:53-65`

| 상태 | 의미를 코드에서 확인한 범위 |
|---|---|
| `new` | 새 projection의 초기 상태다. `tests/unit/core/test_case_reducer.py:25-26` |
| `classifying` | `created` 이벤트 뒤의 상태다. `tests/unit/core/test_case_reducer.py:32-35` |
| `routing` | 분류 뒤 Controller가 Team을 선택하는 상태다. `application/controller.py:115-127` |
| `running` | Team 실행이 가능한 상태다. `tests/unit/core/test_case_reducer.py:38-48` |
| `waiting_input` | 고객 입력을 기다린다. `application/controller.py:230-234` |
| `waiting_approval` | 제안된 action의 승인을 기다린다. `application/controller.py:235-253` |
| `waiting_external` | Enum에는 존재한다. 이 상태로 들어가거나 나오는 실행 경로는 지정된 코드와 테스트에서 확인하지 못했다. [미확보] |
| `resuming` | 입력 또는 승인 뒤 실행 재개를 준비한다. `application/controller.py:132-139` |
| `resolved` | 완료 이벤트를 적용한 결과다. `tests/unit/core/test_case_reducer.py:126-135` |
| `escalated` | 분류·라우팅·대기 등의 실패를 상위 처리로 넘긴 결과다. `tests/unit/core/test_case_reducer.py:86-94`, `tests/integration/controller/test_controller_integration.py:332-340` |
| `failed` | Enum에는 존재한다. 이 상태로 들어가거나 나오는 실행 경로는 지정된 코드와 테스트에서 확인하지 못했다. [미확보] |
| `cancelled` | 사용자 취소 결과이며, 적어도 `created` 이벤트를 더 적용할 수 없는 종료 상태다. `tests/unit/core/test_case_reducer.py:57-61` |

## 확인된 전이

아래 표는 지정된 코드와 테스트에서 확인된 전이만 담는다. 전체 리듀서 전이표는 제공된 읽기 범위에 없으므로 이 표 밖의 전이는 [미확보]다.

| 현재 상태 | 이벤트 | 다음 상태 | 근거 |
|---|---|---|---|
| `new` | `created` | `classifying` | [실측] `tests/unit/core/test_case_reducer.py:32-35` |
| `new` | `cancelled_by_user` | `cancelled` | [실측] `tests/unit/core/test_case_reducer.py:57-61` |
| `classifying` | `classified` | `routing` | [실측] `tests/unit/core/test_case_reducer.py:38-48`, `application/controller.py:115-121` |
| `classifying` | `classification_failed` | `escalated` | [실측] `tests/unit/core/test_case_reducer.py:86-94` |
| `routing` | `routed` | `running` | [실측] `tests/unit/core/test_case_reducer.py:38-48` |
| `routing` | `routing_failed` | `escalated` | [실측] `application/controller.py:122-126`, `tests/integration/controller/test_controller_integration.py:332-340` |
| `running` | `missing_input` | `waiting_input` | [실측] `application/controller.py:230-234`, `tests/integration/controller/test_controller_integration.py:210-234` |
| `waiting_input` | `valid_input` | `resuming` | [실측] `application/controller.py:289-295`, `tests/integration/controller/test_controller_integration.py:210-234` |
| `waiting_input` | `wait_expired` | `escalated` | [실측] `application/controller.py:267-288`, `tests/integration/controller/test_controller_integration.py:237-250` |
| `running` | `approval_required` | `waiting_approval` | [실측] `application/controller.py:235-253`, `tests/integration/controller/test_controller_integration.py:178-207` |
| `waiting_approval` | `approved` | `resuming` | [실측] `tests/unit/core/test_case_reducer.py:115-123`, `tests/integration/controller/test_controller_integration.py:178-207` |
| `waiting_approval` | `rejected` | `escalated` | [실측] `tests/unit/core/test_case_reducer.py:151-155` |
| `waiting_approval` | `wait_expired` | `escalated` | [실측] `tests/unit/core/test_case_reducer.py:158-161` |
| `resuming` | `resumed` | `running` | [실측] `tests/unit/core/test_case_reducer.py:115-123`, `tests/integration/controller/test_controller_integration.py:201-207` |
| `running` | `completed` | `resolved` | [실측] `tests/unit/core/test_case_reducer.py:115-135` |

`new`에서 `completed`를 바로 적용하면 `InvalidTransition`이 발생한다. 즉, 상태 이름을 직접 지정하는 방식이 아니라 현재 상태에서 허용된 이벤트인지 검사한다. [실측] `tests/unit/core/test_case_reducer.py:51-54`, `core/transition.py:151-154`

이벤트별 필수 payload도 검증한다. 예를 들어 `classified`에는 `intent`, `issue_code`, `sentiment`가 모두 필요하다. [실측] `tests/unit/core/test_case_reducer.py:67-80`

입력·승인·외부 콜백의 재개 지점은 각각 `validate_input`, `execute_approved_action`, `verify_external_result`로 매핑된다. [실측] `core/contracts.py:78-86`

전이가 성공할 때마다 version이 1 증가하며, 테스트된 이벤트 재생에서는 version이 적용한 이벤트 수와 같다. [실측] `core/transition.py:61-69`, `tests/unit/core/test_case_reducer.py:142-145`

## 쓰기 주체

Case projection을 저장하는 단일 진입점은 `transition_case()`다. 모듈 계약상 Controller, API, worker는 `customer_cases`를 직접 갱신하지 않고 이 함수를 사용한다. [실측] `core/transition.py:1-13`

Controller는 라우팅, 재개, 완료, 대기, 에스컬레이션 이벤트를 `transition_case()`로 기록한다. [실측] `application/controller.py:120-124`, `application/controller.py:135-155`, `application/controller.py:166-170`, `application/controller.py:283-296`

Team은 `TeamResult`와 `ActionProposal`을 반환한다. 제안된 side effect를 Team이 직접 실행하는 계약은 아니다. [실측] `core/contracts.py:201-215`, `core/contracts.py:223-295`

`transition_case()`의 `actor_type`은 제한된 Enum이 아니라 임의 문자열이고 `actor_id`도 선택값이다. 함수 내부에는 호출 주체 allowlist 검사가 없다. 따라서 실제 호출 권한을 누가 검사하는지는 지정된 읽기 범위에서 확인하지 못했다. [실측] `core/transition.py:119-130` [미확보]

## 관계

- [shared-state.md](shared-state.md)
- [conflict-retry.md](conflict-retry.md)
- [idempotency.md](idempotency.md)

===== FILE: shared-state.md =====
---
type: concept
title: Case 공유 상태의 동시 쓰기
description: 같은 Case를 두 실행 주체가 동시에 변경할 때 충돌을 감지하고 일관성을 지키는 방법을 설명한다.
status: draft
tags: [architecture, state, data]
---

두 쓰기 주체가 같은 version의 Case를 동시에 변경하면 하나만 성공한다. 다른 하나는 `StateConflict`를 받으며, 먼저 성공한 변경을 덮어쓰지 않는다. [실측] `core/transition.py:61-69`, `tests/integration/controller/test_controller_integration.py:432-449`

## 동시성 게이트

각 Case projection에는 version이 있다. 호출자는 자신이 읽은 version을 `expected_version`으로 전달한다. [실측] `core/transition.py:119-136`

`transition_case()`는 먼저 현재 projection을 읽고 현재 version과 `expected_version`을 비교한다. 이미 다르면 DB 변경 전에 `StateConflict`를 발생시킨다. [실측] `core/transition.py:100-116`, `core/transition.py:143-149`

첫 검사 뒤 다른 쓰기 주체가 끼어드는 경우도 막는다. 실제 `UPDATE`는 다음 세 조건을 모두 만족하는 행만 변경한다. [실측] `core/transition.py:61-69`

- 같은 `tenant_id`
- 같은 `case_id`
- 같은 `expected_version`

성공한 `UPDATE`는 version을 1 증가시킨다. 조건에 맞는 행이 없어 `RETURNING` 결과가 없으면 `StateConflict`가 발생한다. [실측] `core/transition.py:66-69`, `core/transition.py:171-176`

같은 `expected_version`으로 두 스레드가 전이한 통합 테스트에서는 결과가 정확히 `success` 1건과 `conflict` 1건이었다. [실측] `tests/integration/controller/test_controller_integration.py:432-449`

## 함께 저장되는 상태

성공한 전이는 다음 세 쓰기를 순서대로 수행한다. [실측] `core/transition.py:156-206`

1. `customer_cases` projection 갱신
2. 새 version을 `aggregate_version`으로 갖는 `case_events` 추가
3. 요청된 outbox 메시지 추가

`transition_case()`는 직접 commit하지 않는다. 이미 transaction이 열린 연결을 받고, transaction 경계와 commit은 호출자가 책임진다. [실측] `core/transition.py:131-137`

Controller는 Case 실행을 transaction 안에서 처리한다. [실측] `application/controller.py:109-114`

주입된 예외로 transaction을 실패시킨 통합 테스트에서는 해당 version의 이벤트와 outbox 레코드가 모두 남지 않았다. projection까지 직접 조회해 검증하는 assertion은 이 테스트에 없다. [실측] `tests/integration/controller/test_controller_integration.py:374-387` [미확보]

## projection과 이벤트

projection 변경 전에 payload는 `mask_json()`으로 처리되고, 같은 안전화된 payload가 리듀서와 이벤트 저장에 사용된다. [실측] `core/transition.py:151-154`, `core/transition.py:179-189`

`state_patch`는 기존 `state_json`을 지우지 않고 병합된다. 테스트에서는 첫 이벤트의 `a`와 다음 이벤트의 `b`가 모두 남으며 `last_event`도 갱신된다. [실측] `tests/unit/core/test_case_reducer.py:97-109`

이벤트는 `aggregate_version` 순으로 다시 접어 projection을 복원한다. 저장된 projection은 replay 입력으로 사용하지 않는다. [실측] `core/transition.py:92-97`, `core/transition.py:218-230`

테스트된 이벤트 열에서는 단계별 적용 결과와 replay 결과가 같고, 같은 이벤트 열을 반복 재생해도 결과가 같다. [실측] `tests/unit/core/test_case_reducer.py:115-145`

## outbox 중복

outbox 쓰기는 `(tenant_id, topic, dedupe_key)` 충돌 시 새 행을 만들지 않는다. 중복이면 `TransitionResult.published`에도 새 message ID가 추가되지 않는다. [실측] `core/transition.py:81-90`, `core/transition.py:193-206`

같은 topic과 dedupe key를 두 번 발행한 통합 테스트에서는 worker가 메시지를 한 번만 전달했다. [실측] `tests/integration/controller/test_controller_integration.py:390-402`

## 보호 범위

version 비교는 같은 Case의 projection 손실 갱신을 막는다. 서로 다른 Case 사이의 업무 불변식이나 여러 Case를 아우르는 잠금은 지정된 코드에서 확인하지 못했다. [미확보]

충돌 이후 다시 시도할지 여부는 `transition_case()`가 아니라 호출자가 정한다. [실측] `core/transition.py:145-176`, `application/controller.py:91-105`

## 관계

- [case-lifecycle.md](case-lifecycle.md)
- [conflict-retry.md](conflict-retry.md)
- [idempotency.md](idempotency.md)

===== FILE: conflict-retry.md =====
---
type: concept
title: 상태 충돌의 재시도와 포기 조건
description: optimistic concurrency 충돌 뒤 Controller가 재시도하는 횟수와 중단 조건을 설명한다.
status: draft
tags: [architecture, state, testing]
---

`transition_case()` 자체는 충돌을 재시도하지 않는다. Controller의 일부 전이만 `_transition_with_retry()`를 사용하며, 설정된 재계산 횟수만큼 다시 시도한 뒤 마지막 `StateConflict`를 그대로 올린다. [실측] `core/transition.py:143-176`, `application/controller.py:91-105`

## 충돌 조건

다음 경우 `StateConflict`가 발생한다. [실측]

- tenant와 Case ID로 projection을 찾지 못한 경우: `core/transition.py:100-106`
- 처음 읽은 현재 version이 `expected_version`과 다른 경우: `core/transition.py:143-149`
- 읽기와 `UPDATE` 사이에 다른 쓰기가 version을 변경해 조건부 `UPDATE`가 0행을 바꾼 경우: `core/transition.py:156-176`

tenant가 다른 Case도 “찾을 수 없음”과 같은 `StateConflict`로 처리된다. [실측] `core/transition.py:100-106`

## 재시도 횟수

Controller는 `concurrency.max_recompute_attempts` 설정을 `N`으로 읽고 `range(N + 1)`만큼 `transition_case()`를 호출할 수 있다. 따라서 최초 시도는 1회이고, 충돌 후 재시도는 최대 `N`회이며, 전체 시도는 최대 `N + 1`회다. [실측] `application/controller.py:91-101`

`N`의 실제 숫자는 지정된 읽기 범위에 포함된 파일에 나타나지 않는다. [미확보]

## 재시도 과정

충돌이 나고 재시도 횟수가 남아 있으면 Controller는 repository에서 같은 tenant와 Case ID의 최신 Case를 다시 읽는다. [실측] `application/controller.py:99-105`

최신 Case가 있으면 그 version을 다음 `expected_version`으로 사용한다. `transition_case()`는 그 최신 projection에 같은 이벤트와 같은 payload를 다시 적용하므로 projection 계산은 최신 상태를 기준으로 다시 수행된다. [실측] `application/controller.py:94-105`, `core/transition.py:143-154`

재시도 사이의 sleep, 지수 backoff, jitter는 `_transition_with_retry()`에 없다. [실측] `application/controller.py:91-105`

## 포기 조건

다음 조건에서는 더 시도하지 않는다.

- 최대 재계산 횟수에 도달한 뒤 다시 `StateConflict`가 발생하면 그 예외를 다시 올린다. [실측] `application/controller.py:99-101`
- 충돌 뒤 최신 Case를 찾지 못하면 현재 `StateConflict`를 다시 올린다. [실측] `application/controller.py:102-104`
- 최신 상태에서 이벤트가 허용되지 않아 `InvalidTransition`이 발생하면 재시도하지 않는다. wrapper가 잡는 예외는 `StateConflict`뿐이다. [실측] `application/controller.py:95-105`, `core/transition.py:151-154`
- payload 검증 실패와 그 밖의 예외도 이 wrapper의 재시도 대상이 아니다. [실측] `application/controller.py:95-105`

## 적용되는 전이

Controller에서 `_transition_with_retry()` 사용이 확인되는 이벤트는 다음 세 가지다.

- `routed`: [실측] `application/controller.py:115-121`
- `routing_failed`: [실측] `application/controller.py:122-124`
- `valid_input`: [실측] `application/controller.py:289-293`

다음 경로는 `transition_case()`를 직접 호출하므로 이 wrapper의 자동 재시도를 받지 않는다.

- `resumed`: [실측] `application/controller.py:132-137`, `application/controller.py:294-296`
- wall-clock 또는 Team timeout 에스컬레이션: [실측] `application/controller.py:140-155`
- Team 결과 적용: [실측] `application/controller.py:166-170`
- 잘못된 resume token의 만료 처리: [실측] `application/controller.py:281-287`

따라서 “충돌은 항상 N회 재시도한다”는 규칙은 없다. 전이 호출 경로가 wrapper를 사용하는 경우에만 최대 `N`회 재시도한다. [실측]

## 동시 실행 검증

동일한 version 2를 기대한 두 transaction이 같은 `routed` 이벤트를 적용한 테스트에서는 한쪽만 성공하고 다른 쪽은 `StateConflict`를 받았다. [실측] `tests/integration/controller/test_controller_integration.py:432-449`

재시도 wrapper가 실제 충돌 상황에서 설정값만큼 호출되는지를 세는 테스트는 지정된 테스트 파일에서 확인하지 못했다. [미확보]

## 관계

- [shared-state.md](shared-state.md)
- [case-lifecycle.md](case-lifecycle.md)
- [idempotency.md](idempotency.md)

===== FILE: idempotency.md =====
---
type: concept
title: 중복 요청의 멱등성 키
description: 반복된 action 요청을 식별하는 서버 키의 구성과 확인된 중복 처리 결과를 설명한다.
status: draft
tags: [architecture, contract, data]
---

action 제안의 최종 멱등성 키는 Team이 정하지 않는다. Controller가 tenant, 원 요청 ID, action 종류, 업무 대상을 이용해 서버 경계에서 다시 계산한다. 같은 네 입력은 같은 64자리 SHA-256 hex 키를 만든다. [실측] `core/idempotency.py:8-18`, `application/controller.py:244-252`

## 키 입력

키 입력은 순서대로 다음 네 문자열이다. [실측] `core/idempotency.py:8-18`

1. `tenant_id`
2. `request_id`
3. `action_type`
4. `business_subject`

Controller가 action request를 만들 때는 다음 값을 사용한다. [실측] `application/controller.py:247-252`

- `tenant_id`: 현재 Case의 tenant
- `request_id`: `request_id_for_case(case)` 결과
- `action_type`: Team proposal의 action 종류
- `business_subject`: 현재 `case_id`의 문자열

`request_id_for_case()`는 `state_json.request_id`가 있으면 그 값을 사용하고, 없으면 `case_id`를 fallback으로 사용한다. [실측] `core/idempotency.py:21-24`

Team이 `ActionProposal.idempotency_key`에 넣은 값은 최종 저장 키가 아니다. Controller는 이 값을 사용하지 않고 서버 키를 계산한다. [실측] `core/contracts.py:201-215`, `application/controller.py:244-252`

## 생성 알고리즘

구현은 네 원문을 그대로 이어 붙이지 않는다. 각 입력을 UTF-8로 인코딩한 뒤 각각 SHA-256 hex로 만들고, 네 개의 고정 길이 hex 문자열을 이어 붙인 뒤 다시 SHA-256을 계산한다. [실측] `core/idempotency.py:15-18`

이를 식으로 쓰면 다음과 같다.

```text
H = SHA256
key = H(H(tenant_id) || H(request_id) || H(action_type) || H(business_subject))
```

최종 키는 64자리 16진수 문자열이다. [실측] `tests/unit/core/test_idempotency.py:22-25`

각 필드를 먼저 고정 길이로 해시하므로 `("ab", "c", "d", "e")`와 `("a", "bc", "d", "e")`처럼 단순 연결 결과가 같은 입력도 다른 키를 만든다. [실측] `core/idempotency.py:11-18`, `tests/unit/core/test_idempotency.py:11-14`

같은 네 입력으로 함수를 반복 호출하면 같은 키가 나온다. [실측] `tests/unit/core/test_idempotency.py:17-19`

`action_type`이나 `business_subject`가 달라지면 키도 달라지는 것이 통합 테스트에 포함돼 있다. [실측] `tests/integration/controller/test_controller_integration.py:297-304`

## 같은 action 요청이 두 번 온 경우

Team이 실행할 때마다 임의의 proposal 키를 새로 만들어도 Controller는 같은 Case와 action 종류에 대해 동일한 서버 키를 만든다. [실측] `tests/integration/controller/test_controller_integration.py:64-74`, `application/controller.py:244-252`

승인 요청을 만들고 Case를 다시 실행해 같은 action을 제안한 통합 테스트에서는 `action_requests` 행 수가 1로 유지됐다. 저장된 키도 서버가 계산한 예상 키와 같았다. [실측] `tests/integration/controller/test_controller_integration.py:270-294`

중복 action request를 실제로 억제하는 repository SQL, DB 제약 조건 또는 충돌 처리 방식은 지정된 읽기 범위에 없다. 결과가 1행이라는 테스트는 확인했지만 내부 억제 방식은 [미확보]다.

서로 다른 두 action이 우연히 같은 `action_type`과 같은 Case를 공유하지만 arguments만 다른 경우에도 현재 키 입력은 같다. arguments는 키에 포함되지 않는다. 이때 저장 계층이 두 요청을 어떻게 구분하는지는 지정된 읽기 범위에서 확인하지 못했다. [실측] `application/controller.py:247-252` [미확보]

## resume 요청의 별도 멱등성

resume은 action 키와 별도 규칙을 사용한다. 같은 token과 같은 `event_id`를 다시 보내면 재실행하지 않고 현재 상태와 version을 `idempotent: true`로 반환한다. [실측] `application/controller.py:259-266`, `tests/integration/controller/test_controller_integration.py:253-264`

같은 token을 다른 `event_id`로 다시 사용하면 멱등 재전송으로 보지 않고 거부한다. [실측] `tests/integration/controller/test_controller_integration.py:261-267`

초기 Case 생성 API를 포함한 모든 외부 요청에 이 action 키 또는 resume 규칙이 공통 적용되는지는 지정된 읽기 범위에서 확인하지 못했다. [미확보]

## outbox와의 구분

outbox는 action 키와 별도로 `(tenant_id, topic, dedupe_key)` 조합을 사용한다. 같은 조합의 재삽입은 `ON CONFLICT ... DO NOTHING`으로 무시된다. [실측] `core/transition.py:81-90`

## 관계

- [shared-state.md](shared-state.md)
- [conflict-retry.md](conflict-retry.md)
- [case-lifecycle.md](case-lifecycle.md)

===== FILE: context-pack.md =====
---
type: concept
title: 모델 입력용 ContextPack 조립
description: Controller와 Context Broker가 근거 맥락을 구성하고 예산 초과 시 제거하는 순서를 설명한다.
status: draft
tags: [architecture, contract, agent]
---

Context Broker는 답변을 만들지 않고, 입력 재료를 12,000 token 예산 안의 `ContextPack`으로 조립한다. token은 문자 수로 추정하지 않고 `cl100k_base` tiktoken 인코더로 센다. [실측] `core/context.py:1-12`, `core/context.py:39-46`, `core/context.py:86-87`

## Controller가 넘기는 재료

Controller는 Team을 선택한 뒤 정책 검색과 현재 Case 상태를 모아 `ContextInputs`를 만든다. [실측] `application/controller.py:68-89`

현재 상태에는 다음 값이 들어간다. [실측] `application/controller.py:78-81`

- `case_id`
- `customer_id`
- `status`
- `version`
- `intent`
- `issue_code`
- `sentiment`
- `owner_team_id`
- 원 요청 ID 또는 Case ID fallback으로 정한 `request_id`

정책 검색은 Case의 `subject`를 query로 사용하고 Team manifest의 `knowledge_scope`를 scope로 사용한다. 검색 예외는 빈 결과와 `retrieval_failed=True`로 변환된다. [실측] `application/controller.py:68-84`

Controller가 현재 구성하는 입력에는 고정 system instruction, 현재 상태, 정책 청크가 들어간다. `history_entries`는 빈 목록으로 전달하며 tool facts와 similar cases는 기본 빈 목록을 사용한다. [실측] `application/controller.py:82-85`, `core/context.py:64-79`

## 팩 구성

`ContextInputs`가 받을 수 있는 전체 재료는 다음과 같다. [실측] `core/context.py:64-79`

- system instruction
- 현재 Case 상태
- tool facts
- 정책 RAG 청크
- 최신 우선 history 항목
- 유사 Case
- 검색 실패 신호

정책 청크는 `document_id`, `chunk_no`, 본문, similarity score, scope를 가진다. source ID는 `<document_id>#c<chunk_no>` 형식이다. [실측] `core/context.py:49-61`

유지된 정책 청크는 `source_type="policy"`인 `Evidence`로 변환된다. evidence ID는 `policy:<source_id>`이며 score는 `0.0`에서 `1.0` 사이 confidence로 제한된다. [실측] `core/context.py:219-233`

최종 `ContextPack`에는 식별자, tenant와 Team 범위, 현재 상태, evidence, history 요약, 유사 Case, token 수, degraded 신호와 omissions가 들어간다. [실측] `core/contracts.py:122-157`, `core/context.py:259-272`

system instruction은 token 계산에는 포함되지만 반환되는 `ContextPack` 필드는 아니다. Team 내부가 이 문자열을 실제 모델 system message에 어떻게 전달하는지는 지정된 읽기 범위에서 확인하지 못했다. [실측] `core/context.py:194-200`, `core/context.py:239-272` [미확보]

## 예산

전체 token 예산은 12,000이다. 이 값은 모델 context window의 크기가 아니라 건당 비용 통제, lost-in-the-middle 완화, 실험 재현성을 위한 제한으로 명시돼 있다. [실측] `core/contracts.py:122-142`, `core/context.py:1-10`

section별 예산은 runtime guardrail에서 읽는다. section 예산의 합이 전체 예산과 다르거나 필수 section이 없으면 Broker 생성 단계에서 `ContextBudgetError`가 발생한다. [실측] `core/context.py:89-106`

각 section의 실제 숫자는 지정된 읽기 범위에 나타나지 않는다. [미확보]

`ContextPack` 계약은 다음 상한도 검증한다. [실측] `core/contracts.py:132-144`

- evidence: 최대 40건
- history summary: 최대 10,000자
- similar cases: 최대 3건
- `estimated_input_tokens`: 12,000 이하

Broker가 사용하는 runtime `max_evidence`, `max_similar`, `max_history_chars`의 실제 설정값은 지정된 읽기 범위에서 확인하지 못했다. [미확보]

## 버리지 않는 항목

system instruction과 Case 상태는 절삭 대상이 아니다. 각각의 section 예산을 넘으면 일부를 자르지 않고 `ContextBudgetError`를 발생시킨다. [실측] `core/context.py:191-206`

테스트에서도 지나치게 큰 system instruction과 Case 상태가 모두 예외로 거부됐다. [실측] `tests/unit/core/test_context_budget.py:39-45`

## 제거 순서

코드가 기록하는 전체 제거 순서는 다음과 같다. [실측] `core/context.py:208-217`

1. similar cases
2. history detail
3. similarity가 낮은 정책 청크
4. 오래된 tool facts

예산 테스트는 첫 omission이 `similar_cases`이고, 낮은 점수의 정책 청크가 제거되며, Case 상태 omission은 없음을 확인한다. [실측] `tests/unit/core/test_context_budget.py:21-36`

구현은 하나의 공유 잔여 예산에서 section을 차례로 빼는 방식이 아니다. 각 절삭 가능한 section을 그 section의 한도에 독립적으로 맞춘 뒤, omission 기록을 위 전역 순서로 합친다. [실측] `core/context.py:208-217`

## section 내부 규칙

### Tool facts

fact는 `observed_at` 최신순으로 정렬한다. 같은 `(source_id, claim)`은 한 건만 남기고 중복 evidence ID를 omissions에 기록한다. [실측] `core/context.py:110-124`

그 뒤 최대 evidence 수와 tool-facts section 예산 안에서 최신 fact부터 유지한다. 한도를 넘는 항목은 각각 `max_items` 또는 `budget` omission으로 기록한다. [실측] `core/context.py:126-138`

### 정책

정책 청크는 similarity score가 높은 순으로 검사한다. section 예산에 들어가지 않는 청크는 `policy_rag:low_score:<source_id>`로 기록하므로 낮은 점수의 청크가 먼저 제외되는 결과가 된다. [실측] `core/context.py:140-154`

### History

history 입력은 최신 항목 우선이라는 계약을 전제로 순서대로 유지한다. 예산에 들어가지 않는 항목은 index와 함께 `history_summary:detail` omission으로 기록한다. [실측] `core/context.py:64-77`, `core/context.py:156-170`

유지된 항목은 줄바꿈으로 합치고 runtime 최대 문자 수로 자른 뒤 token을 다시 센다. 문자 수 절삭으로 잘린 세부 범위는 별도 omission으로 추가되지 않는다. [실측] `core/context.py:167-170`

### 유사 Case

유사 Case는 runtime 최대 건수까지만 검사하고, section 예산을 넘는 Case와 최대 건수를 넘긴 Case를 omissions에 기록한다. [실측] `core/context.py:172-187`

## degraded와 omissions

검색 자체가 실패하거나, 정책 검색 결과가 없거나, 받은 정책 청크가 모두 제거되면 팩은 `degraded=True`가 된다. [실측] `core/context.py:248-257`

검색 실패는 `policy_rag:retrieval_failed`, 검색 결과 없음은 `policy_rag:no_results`로 기록한다. [실측] `core/context.py:252-257`

계약은 `degraded=True`인데 omissions가 비어 있는 팩을 거부한다. 또한 계산된 token 수가 12,000을 넘는 팩도 거부한다. [실측] `core/contracts.py:146-157`

Controller는 자신이 만든 degraded context에서 action proposal이 나오면 자동 실행 경로로 보내지 않고 guardrail 에스컬레이션 이벤트로 바꾼다. [실측] `application/controller.py:180-188`

## 관계

- [case-lifecycle.md](case-lifecycle.md)
- [shared-state.md](shared-state.md)
- [idempotency.md](idempotency.md)