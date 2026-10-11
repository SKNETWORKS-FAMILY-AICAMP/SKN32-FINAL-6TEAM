---
type: concept
title: 중복 요청의 멱등성 키
description: 반복된 action 요청을 식별하는 서버 키의 구성과 확인된 중복 처리 결과를 설명한다.
status: draft
tags: [architecture, contract, data]
domain: neutral
---

action 제안의 최종 멱등성 키는 Team이 정하지 않는다. Controller가 tenant, 원 요청 ID, action 종류, 업무 대상을 이용해 서버 경계에서 다시 계산한다. 같은 네 입력은 같은 64자리 SHA-256 hex 키를 만든다. `[실측]` `core/idempotency.py:8-18`, `application/controller.py:244-252`

## 키 입력

`[2026-09-10]` **이 문서의 `controller.py:NNN` 줄 번호는 낡았다** — Controller 가 커밋을 셋으로 나눈 뒤 밀렸다. 함수 이름으로 찾는다(`acop_basement/application/controller.py`): `_task` :79 · `_transition_with_retry` :95 · `run_case` :130 · `_apply_result` :237 · `_reject_unverified` :243 · `_event_for_result` :297 · `resume` :330. `[실측 2026-09-10]`

★**sample 의 멱등 키 대상은 `case_id` 다**(`_event_for_result` 안 `idempotency_key(...)`, :318). v11 §4-E 는 **서버가 인자에서 꺼내 확인한 대상 객체 id** 로 정했다 — sample 은 그와 다른 구현이다. cs 도 아직 `case_id` 다.

키 입력은 순서대로 다음 네 문자열이다. `[실측]` `core/idempotency.py:8-18`

1. `tenant_id`
2. `request_id`
3. `action_type`
4. `business_subject`

Controller가 action request를 만들 때는 다음 값을 사용한다. `[실측]` `application/controller.py:247-252`

- `tenant_id`: 현재 Case의 tenant
- `request_id`: `request_id_for_case(case)` 결과
- `action_type`: Team proposal의 action 종류
- `business_subject`: 현재 `case_id`의 문자열 — ★`[2026-09-10]` **sample 자신의 동작이고 맞다.** cs 는 v11 §4-E 가 이 칸을 **서버가 확인한 대상 객체 id** 로 바꾸기로 정했다(한 Case 의 둘째 제안이 사라지므로 — cs 구현은 아직). **sample 은 그 사양을 따르지 않는다** — 이 코드를 cs 로 이식할 때 걸리는 자리다

`request_id_for_case()`는 `state_json.request_id`가 있으면 그 값을 사용하고, 없으면 `case_id`를 fallback으로 사용한다. `[실측]` `core/idempotency.py:21-24`

Team이 `ActionProposal.idempotency_key`에 넣은 값은 최종 저장 키가 아니다. Controller는 이 값을 사용하지 않고 서버 키를 계산한다. `[실측]` `core/contracts.py:201-215`, `application/controller.py:244-252`

## 생성 알고리즘

구현은 네 원문을 그대로 이어 붙이지 않는다. 각 입력을 UTF-8로 인코딩한 뒤 각각 SHA-256 hex로 만들고, 네 개의 고정 길이 hex 문자열을 이어 붙인 뒤 다시 SHA-256을 계산한다. `[실측]` `core/idempotency.py:15-18`

이를 식으로 쓰면 다음과 같다.

```text
H = SHA256
key = H(H(tenant_id) || H(request_id) || H(action_type) || H(business_subject))
```

최종 키는 64자리 16진수 문자열이다. `[실측]` `tests/unit/core/test_idempotency.py:22-25`

각 필드를 먼저 고정 길이로 해시하므로 `("ab", "c", "d", "e")`와 `("a", "bc", "d", "e")`처럼 단순 연결 결과가 같은 입력도 다른 키를 만든다. `[실측]` `core/idempotency.py:11-18`, `tests/unit/core/test_idempotency.py:11-14`

같은 네 입력으로 함수를 반복 호출하면 같은 키가 나온다. `[실측]` `tests/unit/core/test_idempotency.py:17-19`

`action_type`이나 `business_subject`가 달라지면 키도 달라지는 것이 통합 테스트에 포함돼 있다. `[실측]` `tests/integration/controller/test_controller_integration.py:297-304`

## 같은 action 요청이 두 번 온 경우

Team이 실행할 때마다 임의의 proposal 키를 새로 만들어도 Controller는 같은 Case와 action 종류에 대해 동일한 서버 키를 만든다. `[실측]` `tests/integration/controller/test_controller_integration.py:64-74`, `application/controller.py:244-252`

승인 요청을 만들고 Case를 다시 실행해 같은 action을 제안한 통합 테스트에서는 `action_requests` 행 수가 1로 유지됐다. 저장된 키도 서버가 계산한 예상 키와 같았다. `[실측]` `tests/integration/controller/test_controller_integration.py:270-294`

중복 action request를 실제로 억제하는 repository SQL, DB 제약 조건 또는 충돌 처리 방식은 지정된 읽기 범위에 없다. 결과가 1행이라는 테스트는 확인했지만 내부 억제 방식은 `[미확보]`다.

서로 다른 두 action이 우연히 같은 `action_type`과 같은 Case를 공유하지만 arguments만 다른 경우에도 현재 키 입력은 같다. arguments는 키에 포함되지 않는다. 이때 저장 계층이 두 요청을 어떻게 구분하는지는 지정된 읽기 범위에서 확인하지 못했다. `[실측]` `application/controller.py:247-252` `[미확보]`

## resume 요청의 별도 멱등성

resume은 action 키와 별도 규칙을 사용한다. 같은 token과 같은 `event_id`를 다시 보내면 재실행하지 않고 현재 상태와 version을 `idempotent: true`로 반환한다. `[실측]` `application/controller.py:259-266`, `tests/integration/controller/test_controller_integration.py:253-264`

같은 token을 다른 `event_id`로 다시 사용하면 멱등 재전송으로 보지 않고 거부한다. `[실측]` `tests/integration/controller/test_controller_integration.py:261-267`

초기 Case 생성 API를 포함한 모든 외부 요청에 이 action 키 또는 resume 규칙이 공통 적용되는지는 지정된 읽기 범위에서 확인하지 못했다. `[미확보]`

## outbox와의 구분

outbox는 action 키와 별도로 `(tenant_id, topic, dedupe_key)` 조합을 사용한다. 같은 조합의 재삽입은 `ON CONFLICT ... DO NOTHING`으로 무시된다. `[실측]` `core/transition.py:81-90`

## 관계

- [shared-state.md](shared-state.md)
- [conflict-retry.md](conflict-retry.md)
- [case-lifecycle.md](case-lifecycle.md)
