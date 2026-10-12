---
type: concept
title: 모델 입력용 ContextPack 조립
description: Controller와 Context Broker가 근거 맥락을 구성하고 예산 초과 시 제거하는 순서를 설명한다.
status: draft
tags: [architecture, contract, agent]
domain: neutral
---

Context Broker는 답변을 만들지 않고, 입력 재료를 12,000 token 예산 안의 `ContextPack`으로 조립한다. token은 문자 수로 추정하지 않고 `cl100k_base` tiktoken 인코더로 센다. `[실측]` `core/context.py:1-12`, `core/context.py:39-46`, `core/context.py:86-87`

## Controller가 넘기는 재료

`[2026-09-10]` **이 문서의 `controller.py:NNN` 줄 번호는 낡았다** — Controller 가 커밋을 셋으로 나눈 뒤 밀렸다. 함수 이름으로 찾는다(`acop_basement/application/controller.py`): `_task` :79 · `_transition_with_retry` :95 · `run_case` :130 · `_apply_result` :237 · `_reject_unverified` :243 · `_event_for_result` :297 · `resume` :330. `[실측 2026-09-10]`

Controller는 Team을 선택한 뒤 정책 검색과 현재 Case 상태를 모아 `ContextInputs`를 만든다. `[실측]` `application/controller.py:68-89`

현재 상태에는 다음 값이 들어간다. `[실측]` `application/controller.py:78-81`

- `case_id`
- `customer_id`
- `status`
- `version`
- `intent`
- `issue_code`
- `sentiment`
- `owner_team_id`
- 원 요청 ID 또는 Case ID fallback으로 정한 `request_id`

정책 검색은 Case의 `subject`를 query로 사용하고 Team manifest의 `knowledge_scope`를 scope로 사용한다. 검색 예외는 빈 결과와 `retrieval_failed=True`로 변환된다. `[실측]` `application/controller.py:68-84`

Controller가 현재 구성하는 입력에는 고정 system instruction, 현재 상태, 정책 청크가 들어간다. `history_entries`는 빈 목록으로 전달하며 tool facts와 similar cases는 기본 빈 목록을 사용한다. `[실측]` `application/controller.py:82-85`, `core/context.py:64-79`

## 팩 구성

`ContextInputs`가 받을 수 있는 전체 재료는 다음과 같다. `[실측]` `core/context.py:64-79`

- system instruction
- 현재 Case 상태
- tool facts
- 정책 RAG 청크
- 최신 우선 history 항목
- 유사 Case
- 검색 실패 신호

정책 청크는 `document_id`, `chunk_no`, 본문, similarity score, scope를 가진다. source ID는 `<document_id>#c<chunk_no>` 형식이다. `[실측]` `core/context.py:49-61`

유지된 정책 청크는 `source_type="policy"`인 `Evidence`로 변환된다. evidence ID는 `policy:<source_id>`이며 score는 `0.0`에서 `1.0` 사이 confidence로 제한된다. `[실측]` `core/context.py:219-233`

최종 `ContextPack`에는 식별자, tenant와 Team 범위, 현재 상태, evidence, history 요약, 유사 Case, token 수, degraded 신호와 omissions가 들어간다. `[실측]` `core/contracts.py:122-157`, `core/context.py:259-272`

system instruction은 token 계산에는 포함되지만 반환되는 `ContextPack` 필드는 아니다. Team 내부가 이 문자열을 실제 모델 system message에 어떻게 전달하는지는 지정된 읽기 범위에서 확인하지 못했다. `[실측]` `core/context.py:194-200`, `core/context.py:239-272` `[미확보]`

## 예산

전체 token 예산은 12,000이다. 이 값은 모델 context window의 크기가 아니라 건당 비용 통제, lost-in-the-middle 완화, 실험 재현성을 위한 제한으로 명시돼 있다. `[실측]` `core/contracts.py:122-142`, `core/context.py:1-10`

section별 예산은 runtime guardrail에서 읽는다. section 예산의 합이 전체 예산과 다르거나 필수 section이 없으면 Broker 생성 단계에서 `ContextBudgetError`가 발생한다. `[실측]` `core/context.py:89-106`

각 section의 실제 숫자는 지정된 읽기 범위에 나타나지 않는다. `[미확보]`

`ContextPack` 계약은 다음 상한도 검증한다. `[실측]` `core/contracts.py:132-144`

- evidence: 최대 40건
- history summary: 최대 10,000자
- similar cases: 최대 3건
- `estimated_input_tokens`: 12,000 이하

Broker가 사용하는 runtime `max_evidence`, `max_similar`, `max_history_chars`의 실제 설정값은 지정된 읽기 범위에서 확인하지 못했다. `[미확보]`

## 버리지 않는 항목

system instruction과 Case 상태는 절삭 대상이 아니다. 각각의 section 예산을 넘으면 일부를 자르지 않고 `ContextBudgetError`를 발생시킨다. `[실측]` `core/context.py:191-206`

테스트에서도 지나치게 큰 system instruction과 Case 상태가 모두 예외로 거부됐다. `[실측]` `tests/unit/core/test_context_budget.py:39-45`

## 제거 순서

코드가 기록하는 전체 제거 순서는 다음과 같다. `[실측]` `core/context.py:208-217`

1. similar cases
2. history detail
3. similarity가 낮은 정책 청크
4. 오래된 tool facts

예산 테스트는 첫 omission이 `similar_cases`이고, 낮은 점수의 정책 청크가 제거되며, Case 상태 omission은 없음을 확인한다. `[실측]` `tests/unit/core/test_context_budget.py:21-36`

구현은 하나의 공유 잔여 예산에서 section을 차례로 빼는 방식이 아니다. 각 절삭 가능한 section을 그 section의 한도에 독립적으로 맞춘 뒤, omission 기록을 위 전역 순서로 합친다. `[실측]` `core/context.py:208-217`

## section 내부 규칙

### Tool facts

fact는 `observed_at` 최신순으로 정렬한다. 같은 `(source_id, claim)`은 한 건만 남기고 중복 evidence ID를 omissions에 기록한다. `[실측]` `core/context.py:110-124`

그 뒤 최대 evidence 수와 tool-facts section 예산 안에서 최신 fact부터 유지한다. 한도를 넘는 항목은 각각 `max_items` 또는 `budget` omission으로 기록한다. `[실측]` `core/context.py:126-138`

### 정책

정책 청크는 similarity score가 높은 순으로 검사한다. section 예산에 들어가지 않는 청크는 `policy_rag:low_score:<source_id>`로 기록하므로 낮은 점수의 청크가 먼저 제외되는 결과가 된다. `[실측]` `core/context.py:140-154`

`[정정 2026-09-10]` **「낮은 점수 청크가 먼저 빠진다」는 보장이 아니다.** `_fit_policy()` 는 넘치는 청크를 건너뛰고(`continue`) 다음 청크를 계속 본다 — 그래서 **큰 고득점 청크가 빠지고 그보다 작은 저득점 청크가 남을 수 있다**(`acop_basement/core/context.py` `_fit_policy`).

### History

history 입력은 최신 항목 우선이라는 계약을 전제로 순서대로 유지한다. 예산에 들어가지 않는 항목은 index와 함께 `history_summary:detail` omission으로 기록한다. `[실측]` `core/context.py:64-77`, `core/context.py:156-170`

유지된 항목은 줄바꿈으로 합치고 runtime 최대 문자 수로 자른 뒤 token을 다시 센다. 문자 수 절삭으로 잘린 세부 범위는 별도 omission으로 추가되지 않는다. `[실측]` `core/context.py:167-170`

### 유사 Case

유사 Case는 runtime 최대 건수까지만 검사하고, section 예산을 넘는 Case와 최대 건수를 넘긴 Case를 omissions에 기록한다. `[실측]` `core/context.py:172-187`

## degraded와 omissions

검색 자체가 실패하거나, 정책 검색 결과가 없거나, 받은 정책 청크가 모두 제거되면 팩은 `degraded=True`가 된다. `[실측]` `core/context.py:248-257`

검색 실패는 `policy_rag:retrieval_failed`, 검색 결과 없음은 `policy_rag:no_results`로 기록한다. `[실측]` `core/context.py:252-257`

계약은 `degraded=True`인데 omissions가 비어 있는 팩을 거부한다. 또한 계산된 token 수가 12,000을 넘는 팩도 거부한다. `[실측]` `core/contracts.py:146-157`

Controller는 자신이 만든 degraded context에서 action proposal이 나오면 자동 실행 경로로 보내지 않고 guardrail 에스컬레이션 이벤트로 바꾼다. `[실측]` `application/controller.py:180-188`

## 관계

- [case-lifecycle.md](case-lifecycle.md)
- [shared-state.md](shared-state.md)
- [idempotency.md](idempotency.md)
