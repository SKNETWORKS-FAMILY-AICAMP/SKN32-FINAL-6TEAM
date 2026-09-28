---
type: concept
title: Case 공유 상태의 동시 쓰기
description: 같은 Case를 두 실행 주체가 동시에 변경할 때 충돌을 감지하고 일관성을 지키는 방법을 설명한다.
status: draft
tags: [architecture, state, data]
domain: neutral
---

두 쓰기 주체가 같은 version의 Case를 동시에 변경하면 하나만 성공한다. 다른 하나는 `StateConflict`를 받으며, 먼저 성공한 변경을 덮어쓰지 않는다. `[실측]` `core/transition.py:61-69`, `tests/integration/controller/test_controller_integration.py:432-449`

## 동시성 게이트

`[2026-09-10]` **이 문서의 `controller.py:NNN` 줄 번호는 낡았다** — Controller 가 커밋을 셋으로 나눈 뒤 밀렸다. 함수 이름으로 찾는다(`acop_basement/application/controller.py`): `_task` :79 · `_transition_with_retry` :95 · `run_case` :130 · `_apply_result` :237 · `_reject_unverified` :243 · `_event_for_result` :297 · `resume` :330. `[실측 2026-09-10]`

각 Case projection에는 version이 있다. 호출자는 자신이 읽은 version을 `expected_version`으로 전달한다. `[실측]` `core/transition.py:119-136`

`transition_case()`는 먼저 현재 projection을 읽고 현재 version과 `expected_version`을 비교한다. 이미 다르면 DB 변경 전에 `StateConflict`를 발생시킨다. `[실측]` `core/transition.py:100-116`, `core/transition.py:143-149`

첫 검사 뒤 다른 쓰기 주체가 끼어드는 경우도 막는다. 실제 `UPDATE`는 다음 세 조건을 모두 만족하는 행만 변경한다. `[실측]` `core/transition.py:61-69`

- 같은 `tenant_id`
- 같은 `case_id`
- 같은 `expected_version`

성공한 `UPDATE`는 version을 1 증가시킨다. 조건에 맞는 행이 없어 `RETURNING` 결과가 없으면 `StateConflict`가 발생한다. `[실측]` `core/transition.py:66-69`, `core/transition.py:171-176`

같은 `expected_version`으로 두 스레드가 전이한 통합 테스트에서는 결과가 정확히 `success` 1건과 `conflict` 1건이었다. `[실측]` `tests/integration/controller/test_controller_integration.py:432-449`

## 함께 저장되는 상태

성공한 전이는 다음 세 쓰기를 순서대로 수행한다. `[실측]` `core/transition.py:156-206`

1. `customer_cases` projection 갱신
2. 새 version을 `aggregate_version`으로 갖는 `case_events` 추가
3. 요청된 outbox 메시지 추가

`transition_case()`는 직접 commit하지 않는다. 이미 transaction이 열린 연결을 받고, transaction 경계와 commit은 호출자가 책임진다. `[실측]` `core/transition.py:131-137`

Controller는 Case 실행을 transaction 안에서 처리한다. `[실측]` `application/controller.py:109-114`

주입된 예외로 transaction을 실패시킨 통합 테스트에서는 해당 version의 이벤트와 outbox 레코드가 모두 남지 않았다. projection까지 직접 조회해 검증하는 assertion은 이 테스트에 없다. `[실측]` `tests/integration/controller/test_controller_integration.py:374-387` `[미확보]`

## projection과 이벤트

projection 변경 전에 payload는 `mask_json()`으로 처리되고, 같은 안전화된 payload가 리듀서와 이벤트 저장에 사용된다. `[실측]` `core/transition.py:151-154`, `core/transition.py:179-189`

`state_patch`는 기존 `state_json`을 지우지 않고 병합된다. 테스트에서는 첫 이벤트의 `a`와 다음 이벤트의 `b`가 모두 남으며 `last_event`도 갱신된다. `[실측]` `tests/unit/core/test_case_reducer.py:97-109`

이벤트는 `aggregate_version` 순으로 다시 접어 projection을 복원한다. 저장된 projection은 replay 입력으로 사용하지 않는다. `[실측]` `core/transition.py:92-97`, `core/transition.py:218-230`

테스트된 이벤트 열에서는 단계별 적용 결과와 replay 결과가 같고, 같은 이벤트 열을 반복 재생해도 결과가 같다. `[실측]` `tests/unit/core/test_case_reducer.py:115-145`

## outbox 중복

outbox 쓰기는 `(tenant_id, topic, dedupe_key)` 충돌 시 새 행을 만들지 않는다. 중복이면 `TransitionResult.published`에도 새 message ID가 추가되지 않는다. `[실측]` `core/transition.py:81-90`, `core/transition.py:193-206`

같은 topic과 dedupe key를 두 번 발행한 통합 테스트에서는 worker가 메시지를 한 번만 전달했다. `[실측]` `tests/integration/controller/test_controller_integration.py:390-402`

## 보호 범위

version 비교는 같은 Case의 projection 손실 갱신을 막는다. 서로 다른 Case 사이의 업무 불변식이나 여러 Case를 아우르는 잠금은 지정된 코드에서 확인하지 못했다. `[미확보]`

충돌 이후 다시 시도할지 여부는 `transition_case()`가 아니라 호출자가 정한다. `[실측]` `core/transition.py:145-176`, `application/controller.py:91-105`

`[정정 2026-09-10]` **Controller 실행 전체가 한 트랜잭션이 아니다** — Team 실행은 트랜잭션 밖이고 시작·결과 반영을 나눠 커밋한다 → [agentic-controller.md](agentic-controller.md).

## 관계

- [case-lifecycle.md](case-lifecycle.md)
- [conflict-retry.md](conflict-retry.md)
- [idempotency.md](idempotency.md)
