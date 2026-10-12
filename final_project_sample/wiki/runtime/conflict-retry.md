---
type: concept
title: 상태 충돌의 재시도와 포기 조건
description: optimistic concurrency 충돌 뒤 Controller가 재시도하는 횟수와 중단 조건을 설명한다.
status: draft
tags: [architecture, state, testing]
domain: neutral
---

`transition_case()` 자체는 충돌을 재시도하지 않는다. Controller의 일부 전이만 `_transition_with_retry()`를 사용하며, 설정된 재계산 횟수만큼 다시 시도한 뒤 마지막 `StateConflict`를 그대로 올린다. `[실측]` `core/transition.py:143-176`, `application/controller.py:91-105`

## 충돌 조건

`[2026-09-10]` **이 문서의 `controller.py:NNN` 줄 번호는 낡았다** — Controller 가 커밋을 셋으로 나눈 뒤 밀렸다. 함수 이름으로 찾는다(`acop_basement/application/controller.py`): `_task` :79 · `_transition_with_retry` :95 · `run_case` :130 · `_apply_result` :237 · `_reject_unverified` :243 · `_event_for_result` :297 · `resume` :330. `[실측 2026-09-10]`

다음 경우 `StateConflict`가 발생한다. `[실측]`

- tenant와 Case ID로 projection을 찾지 못한 경우: `core/transition.py:100-106`
- 처음 읽은 현재 version이 `expected_version`과 다른 경우: `core/transition.py:143-149`
- 읽기와 `UPDATE` 사이에 다른 쓰기가 version을 변경해 조건부 `UPDATE`가 0행을 바꾼 경우: `core/transition.py:156-176`

tenant가 다른 Case도 “찾을 수 없음”과 같은 `StateConflict`로 처리된다. `[실측]` `core/transition.py:100-106`

## 재시도 횟수

Controller는 `concurrency.max_recompute_attempts` 설정을 `N`으로 읽고 `range(N + 1)`만큼 `transition_case()`를 호출할 수 있다. 따라서 최초 시도는 1회이고, 충돌 후 재시도는 최대 `N`회이며, 전체 시도는 최대 `N + 1`회다. `[실측]` `application/controller.py:91-101`

`[실측]` **`N` 은 2다.** `config/guardrails.yaml:74`

```yaml
max_recompute_attempts: 2      # StateConflict 시 최신 Case 를 읽어 재계산
```

**따라서 전체 시도는 최대 3회다.**

## 재시도 과정

충돌이 나고 재시도 횟수가 남아 있으면 Controller는 repository에서 같은 tenant와 Case ID의 최신 Case를 다시 읽는다. `[실측]` `application/controller.py:99-105`

최신 Case가 있으면 그 version을 다음 `expected_version`으로 사용한다. `transition_case()`는 그 최신 projection에 같은 이벤트와 같은 payload를 다시 적용하므로 projection 계산은 최신 상태를 기준으로 다시 수행된다. `[실측]` `application/controller.py:94-105`, `core/transition.py:143-154`

재시도 사이의 sleep, 지수 backoff, jitter는 `_transition_with_retry()`에 없다. `[실측]` `application/controller.py:91-105`

## 포기 조건

다음 조건에서는 더 시도하지 않는다.

- 최대 재계산 횟수에 도달한 뒤 다시 `StateConflict`가 발생하면 그 예외를 다시 올린다. `[실측]` `application/controller.py:99-101`
- 충돌 뒤 최신 Case를 찾지 못하면 현재 `StateConflict`를 다시 올린다. `[실측]` `application/controller.py:102-104`
- 최신 상태에서 이벤트가 허용되지 않아 `InvalidTransition`이 발생하면 재시도하지 않는다. wrapper가 잡는 예외는 `StateConflict`뿐이다. `[실측]` `application/controller.py:95-105`, `core/transition.py:151-154`
- payload 검증 실패와 그 밖의 예외도 이 wrapper의 재시도 대상이 아니다. `[실측]` `application/controller.py:95-105`

## 적용되는 전이

Controller에서 `_transition_with_retry()` 사용이 확인되는 이벤트는 다음 세 가지다.

- `routed`: `[실측]` `application/controller.py:115-121`
- `routing_failed`: `[실측]` `application/controller.py:122-124`
- `valid_input`: `[실측]` `application/controller.py:289-293`

다음 경로는 `transition_case()`를 직접 호출하므로 이 wrapper의 자동 재시도를 받지 않는다.

- `resumed`: `[실측]` `application/controller.py:132-137`, `application/controller.py:294-296`
- wall-clock 또는 Team timeout 에스컬레이션: `[실측]` `application/controller.py:140-155`
- Team 결과 적용: `[실측]` `application/controller.py:166-170`
- 잘못된 resume token의 만료 처리: `[실측]` `application/controller.py:281-287`

따라서 “충돌은 항상 N회 재시도한다”는 규칙은 없다. 전이 호출 경로가 wrapper를 사용하는 경우에만 최대 `N`회 재시도한다. `[실측]`

## 동시 실행 검증

동일한 version 2를 기대한 두 transaction이 같은 `routed` 이벤트를 적용한 테스트에서는 한쪽만 성공하고 다른 쪽은 `StateConflict`를 받았다. `[실측]` `tests/integration/controller/test_controller_integration.py:432-449`

재시도 wrapper가 실제 충돌 상황에서 설정값만큼 호출되는지를 세는 테스트는 지정된 테스트 파일에서 확인하지 못했다. `[미확보]`

## 관계

- [shared-state.md](shared-state.md)
- [case-lifecycle.md](case-lifecycle.md)
- [idempotency.md](idempotency.md)
