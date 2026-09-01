---
type: contract
title: 불변식 카탈로그
description: 깨면 안 되는 규칙 전체 목록. 대부분 테스트가 자동 판정한다
status: draft
tags: [testing, architecture]
owners: [human:미배정]
size_exempt: true
size_exempt_reason: 불변식 카탈로그. 전체를 훑어야 의미가 있다
---

# 불변식 카탈로그

**코드를 고치기 전에 여기를 본다.**

이 목록의 대부분은 **테스트가 자동으로 판정한다.** 어기면 CI가 실패한다. 문서가 "지켜주세요"라고 부탁하는 게 아니라 실행이 막는다.

## ID 문법

```text
INV-<REPO>-<영역>-<번호>
```

`REPO`는 `CS`, `SAMPLE`, `HUB`, `DOJO`, `DATA`. 번호는 재사용하지 않는다.

## 판정 종류

| 판정 | 의미 |
|---|---|
| `automated` | CI나 테스트가 통과·실패를 판정한다 |
| `manual` | 재현 가능한 절차로 사람이 판정한다 |
| `review` | 정책·의미 판단이 필요하다 |

---

## 아키텍처 — `INV-CS-ARCH-*`

Core가 도메인을 모른다는 것을 지킨다. **Pack 교체 가능성의 근거다.**

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ARCH-001` | Core 계층은 도메인 어휘에 의존하지 않는다 | automated | `tests/architecture/test_basement_is_domain_free.py::test_basement_layers_do_not_know_the_business_domain` |
| `INV-CS-ARCH-002` | Core 파일은 도메인 모듈을 import하지 않는다 | automated | `tests/architecture/test_basement_is_domain_free.py::test_no_basement_file_imports_a_domain_module` |
| `INV-CS-ARCH-003` | Core는 `app/modules`를 import하지 않는다 | automated | `tests/contract/test_core_isolation.py::test_core_does_not_import_modules` |
| `INV-CS-ARCH-004` | 도메인 어휘 예외 목록은 작게 유지된다 | automated | `tests/architecture/test_basement_is_domain_free.py::test_allow_list_stays_small` |
| `INV-CS-ARCH-005` | 엔진 소스에 도메인 어휘가 없다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_engine_source_has_no_domain_vocabulary` |
| `INV-CS-ARCH-006` | 도메인 모듈은 자기 도메인을 알아도 된다 | automated | `tests/architecture/test_basement_is_domain_free.py::test_domain_modules_are_allowed_to_know_their_domain` |

**`INV-CS-ARCH-004`가 특이하다.** 예외 목록의 **크기 자체**를 검사한다. 예외가 늘어나면 그게 설계가 무너지고 있다는 신호다.

현재 예외는 `app/core/redaction.py` 하나다. PII 마스킹은 결제 식별자 **모양**을 알아야 가릴 수 있는데, 이건 도메인 로직이 아니라 보안 규칙이다.

금지 어휘.

```python
DOMAIN_WORDS = (
    "payment", "subscription", "entitlement", "refund", "invoice",
    "order_id", "line_item", "shipment", "sku", "cart",
)
```

---

## Team 계약 — `INV-CS-TEAM-*`

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-TEAM-001` | Team manifest는 프로토콜을 구현한다 | automated | `tests/contract/test_team_contract.py::test_team_manifests_implement_protocol` |
| `INV-CS-TEAM-002` | manifest의 scope는 정확히 선언된다 | automated | `tests/contract/test_team_contract.py::test_manifest_scopes_are_exact` |
| `INV-CS-TEAM-003` | Team은 side effect를 실행하지 않는다 | review | [../teams/team-boundary.md](../teams/team-boundary.md) |
| `INV-CS-TEAM-004` | Team은 read 도구를 직접 호출하지 않는다 | review | 동 |
| `INV-CS-TEAM-005` | Team은 다른 Team을 직접 호출하지 않는다 | review | 동 |

**003~005가 `review`인 게 약점이다.** 설계의 핵심 규칙인데 자동 판정이 없다. 사람이 리뷰에서 잡아야 한다.

`[미확보]` 자동화 방법을 찾아야 한다. `allowed_tools` 선언과 실제 호출을 대조하는 테스트가 가능해 보인다.

---

## Action — `INV-CS-ACT-*`

**side effect가 한 번만 일어나는 것**을 지킨다.

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-ACT-001` | 동일 dedupe key는 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_duplicate_dedupe_key_has_one_side_effect` |
| `INV-CS-ACT-002` | 동시 claim도 side effect가 1회다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_concurrent_claims_have_one_side_effect` |
| `INV-CS-ACT-003` | timeout은 unknown이며 자동 재시도하지 않는다 | automated | `tests/contract/test_consumer_idempotency_contract.py::test_timeout_is_unknown_and_not_automatically_retried` |

**`INV-CS-ACT-003`이 중요하다.** timeout을 실패로 간주해 자동 재시도하면 이중 실행이 된다. **모르는 건 모르는 채로 둔다.**

---

## 보안 — `INV-CS-SEC-*`

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-SEC-001` | 유효하지 않은 토큰은 인증되지 않는다 | automated | `tests/security/test_auth_and_scope_guards.py::test_any_seven_character_prefix_must_not_authenticate` |
| `INV-CS-SEC-002` | scope 없는 principal은 거부된다 | automated | `tests/security/test_auth_and_scope_guards.py::test_scope_guard_denies_a_principal_with_no_scopes` |
| `INV-CS-SEC-003` | 다른 scope를 가진 principal도 거부된다 | automated | `tests/security/test_auth_and_scope_guards.py::test_scope_guard_denies_a_principal_holding_another_scope` |
| `INV-CS-SEC-004` | PII는 DB·API·audit 전부에서 마스킹된다 | automated | `tests/security/test_pii_redaction_runtime.py::test_case_message_is_redacted_in_db_api_and_audit` |
| `INV-CS-SEC-005` | 같은 tenant 안에서도 customer 간 누출이 없다 | automated | `tests/security/test_query_scope.py::test_case_list_does_not_leak_across_customers_in_one_tenant` |
| `INV-CS-SEC-006` | customer 미지정 조회도 tenant를 벗어나지 않는다 | automated | `tests/security/test_query_scope.py::test_case_list_without_customer_stays_inside_the_tenant` |
| `INV-CS-SEC-007` | scope 10개는 guardrail이 소유한다 | automated | `tests/security/test_scope_contract.py::test_ten_scopes_are_guardrail_owned` |
| `INV-CS-SEC-008` | MCP는 정확히 3개의 read scope 도구를 갖는다 | automated | `tests/security/test_scope_contract.py::test_mcp_has_exactly_three_read_scoped_tools` |

**`INV-CS-SEC-004`가 셋을 한 번에 본다.** DB에만 마스킹하고 audit에 원본이 남는 실수를 막는다.

---

## 도메인 검증 — `INV-CS-VER-*`

Action을 실행하기 전 근거를 대조한다.

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-VER-001` | 존재하지 않는 주문은 거부된다 | automated | `tests/architecture/test_engine_serves_another_domain.py::test_unknown_order_is_rejected` |
| `INV-CS-VER-002` | 주문 총액을 넘는 환불은 거부된다 | automated | `::test_refund_over_the_order_total_is_rejected` |
| `INV-CS-VER-003` | 부분 환불은 통과한다 | automated | `::test_partial_refund_passes` |
| `INV-CS-VER-004` | 주문 수량을 넘는 반품은 거부된다 | automated | `::test_return_quantity_over_the_item_count_is_rejected` |
| `INV-CS-VER-005` | 주문 범위 내 반품은 통과한다 | automated | `::test_return_quantity_within_the_order_passes` |
| `INV-CS-VER-006` | 배송 소유권을 확인한다 | automated | `::test_shipment_ownership_is_checked` |
| `INV-CS-VER-007` | 이 도메인의 불투명 필드는 거부된다 | automated | `::test_this_domains_opaque_field_is_rejected` |

전부 `tests/architecture/test_engine_serves_another_domain.py`에 있다.

### ★ 이 불변식들이 못 잡는 것

**`INV-CS-VER-002`는 "환불 ≤ 주문 총액"만 본다.** 총액 자체가 잘못된 기준이면 통과한다.

```
30,000원 주문 · 5,000원 쿠폰 → 실결제 25,000원
2개 중 1개 반품 → 우리 계산 15,000원

15,000 ≤ 30,000  →  INV-CS-VER-002 통과 ✅
실제 환불액은 12,500원                    ❌
```

**불변식이 있다고 안전한 게 아니다.** 기준값이 틀리면 검증도 틀린다.

조치는 [중앙 허브 D-001](../../../wiki/decisions/D-001-payment-ownership.md).

---

## Runtime — `INV-CS-RT-*`

**[2026-09-01 정정]** 이전 판에서 "테스트로 강제되지 않는다"고 적었으나 **틀렸다.** 테스트는 있었고 불변식 ID로 연결되지 않았을 뿐이다. 검증 과정에서 발견해 아래로 교체했다.

### 상태와 버전

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-001` | 이벤트 재생은 결정적이다 | automated | `tests/unit/core/test_case_reducer.py::test_replay_is_deterministic` |
| `INV-CS-RT-002` | version은 항상 이벤트 수와 같다 | automated | `tests/unit/core/test_case_reducer.py::test_version_always_equals_event_count` |
| `INV-CS-RT-003` | 상태 변경은 version을 증가시킨다 | automated | `tests/unit/core/test_case_reducer.py::test_created_moves_to_classifying_and_bumps_version` |
| `INV-CS-RT-004` | 부분 접기 결과가 단계별 결과와 같다 | automated | `tests/unit/core/test_case_reducer.py::test_fold_reproduces_step_by_step_result` |
| `INV-CS-RT-005` | 상태 패치는 병합되며 기존 값을 지우지 않는다 | automated | `tests/unit/core/test_case_reducer.py::test_state_patch_merges_and_does_not_wipe` |

### 동시성 (CAS)

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-006` | 현재보다 낮은 version 쓰기는 거부된다 | automated | `tests/integration/db/test_stale_write_conflict.py::test_writing_with_a_version_older_than_current_is_rejected` |
| `INV-CS-RT-007` | 앞선 version 쓰기도 거부된다 | automated | `::test_writing_with_a_version_ahead_of_current_is_rejected` |
| `INV-CS-RT-008` | **거부된 쓰기는 Case를 바꾸지 않는다** | automated | `::test_a_rejected_stale_write_does_not_change_the_case` |
| `INV-CS-RT-009` | 같은 version을 읽은 두 writer는 정확히 1건만 충돌한다 | automated | `::test_two_writers_that_read_the_same_version_produce_exactly_one_conflict` |
| `INV-CS-RT-010` | 진행된 Case의 stale 쓰기는 전이 오류가 아니라 충돌이다 | automated | `::test_stale_write_on_an_advanced_case_is_a_conflict_not_a_transition_error` |
| `INV-CS-RT-011` | 동시 최초 실행은 active run을 정확히 1개 남긴다 | automated | `tests/integration/controller/test_active_run_uniqueness.py::test_two_simultaneous_first_start_runs_leave_exactly_one_active_run` |

`INV-CS-RT-008`이 "실패한 갱신은 부분 변경을 남기지 않는다"의 실제 판정이다.

`INV-CS-RT-010`이 미묘하다. **충돌과 전이 오류를 구분한다.** 충돌은 재시도 대상이고 전이 오류는 버그다. 같은 예외로 뭉뚱그리면 Controller가 잘못 대응한다.

### 상태 기계

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-012` | 상태는 정확히 12개다 | automated | `tests/contract/test_case_state_table.py::test_all_twelve_statuses_exist` |
| `INV-CS-RT-013` | `cancelled`는 종단 상태다 | automated | `tests/contract/test_case_state_table.py::test_cancelled_is_terminal` |
| `INV-CS-RT-014` | 허용 전이 표가 기준과 일치한다 | automated | `tests/contract/test_case_state_table.py::test_allowed_next_statuses_match_v5` |
| `INV-CS-RT-015` | 불법 전이는 거부된다 | automated | `tests/unit/core/test_case_reducer.py::test_illegal_transition_is_rejected` |
| `INV-CS-RT-016` | 모든 이벤트가 전이 표에서 쓰인다 | automated | `tests/contract/test_case_state_table.py::test_every_event_is_used_in_transition_table` |

### ★ 조용히 넘어가지 않는다

이 넷이 **"실패를 성공으로 처리하지 않는다"**를 강제한다. 이 제품의 핵심 주장과 직결된다.

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-017` | **분류 실패는 조용히 진행하지 않고 escalate한다** | automated | `tests/contract/test_case_state_table.py::test_classification_failure_escalates_not_silently_continues` |
| `INV-CS-RT-018` | **대기 만료는 자동 resolve하지 않고 escalate한다** | automated | `tests/contract/test_case_state_table.py::test_wait_expiry_escalates_not_auto_resolves` |
| `INV-CS-RT-019` | 반려된 승인은 resume하지 않는다 | automated | `tests/contract/test_case_state_table.py::test_rejection_does_not_resume` |
| `INV-CS-RT-020` | 분류 실패 시 라벨을 비운다 | automated | `tests/unit/core/test_case_reducer.py::test_classification_failure_leaves_labels_empty` |

**`INV-CS-RT-018`이 특히 값지다.** 대기가 만료됐을 때 "그냥 완료 처리"하면 고객은 답을 못 받았는데 시스템은 해결됐다고 본다. 이걸 테스트가 막는다.

---

## Context 예산 — `INV-CS-CTX-*`

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-CTX-001` | 예산 초과 시 정해진 순서로 축출한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_eviction_is_budgeted_and_ordered` |
| `INV-CS-CTX-002` | 자를 수 없는 구간은 거부한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_rejects_untruncatable_sections` |

`INV-CS-CTX-002`가 중요하다. **잘라서 의미가 깨지는 자료는 조용히 자르지 않고 거부한다.**

---

## 코드 쪽 역방향 표식

문서에서 테스트를 가리키는 것만으로는 부족하다. **테스트도 자기가 어떤 불변식을 지키는지 밝힌다.**

```python
# invariant: INV-CS-ARCH-001
def test_basement_layers_do_not_know_the_business_domain():
    ...
```

`[미확보]` **아직 코드에 표식이 없다.** 넣어야 한다.

## CI가 검사할 것

```text
1. 문서의 automated 테스트 경로가 실재하는가
2. 그 테스트에 같은 invariant: 표식이 있는가
3. 코드의 ID가 이 카탈로그에 있는가
4. ID가 중복되지 않는가
```

`[미확보]` 아직 구현 안 됐다.

## 현황 요약

**[2026-09-01 정정]** Runtime을 실측으로 다시 세면서 33개 → 54개가 됐다. 불변식이 늘어난 게 아니라 **이미 있던 테스트를 찾아 연결한 것**이다.

| 영역 | 총 | automated | review (자동화 필요) |
|---|---|---|---|
| ARCH | 6 | 6 | 0 |
| TEAM | 5 | 2 | **3** |
| ACT | 3 | 3 | 0 |
| SEC | 8 | 8 | 0 |
| VER | 7 | 7 | 0 |
| RT | 20 | 20 | 0 |
| CTX | 2 | 2 | 0 |
| **합계** | **51** | **48** | **3** |

**남은 사람 판정은 Team 경계 3개뿐이다.**

| ID | 불변식 | 자동화 방법 `[추정]` |
|---|---|---|
| `INV-CS-TEAM-003` | side effect를 실행하지 않는다 | Team 모듈이 `access_action/`을 import하는지 검사 |
| `INV-CS-TEAM-004` | read 도구를 직접 호출하지 않는다 | Team 모듈이 `tools/`를 직접 import하는지 검사 |
| `INV-CS-TEAM-005` | 다른 Team을 직접 호출하지 않는다 | Team 모듈이 다른 Team을 import하는지 검사 |

`tests/architecture/test_basement_is_domain_free.py`가 이미 import 검사를 하므로 **같은 방식으로 셋 다 가능해 보인다.**

## 이 검증에서 배운 것

문서에 "테스트가 없다"고 적기 전에 **테스트를 실제로 찾아봐야 한다.**

이전 판은 `tests/integration`에 Runtime 테스트가 없다고 봤는데, 실제로는 `tests/integration/db/`, `tests/unit/core/`, `tests/contract/`에 흩어져 있었다. **폴더 최상위만 보고 판단한 실수다.**

이게 [test-map.md](test-map.md)가 필요한 이유다. 테스트가 어디 있는지 지도가 없으면 있는 것도 못 찾는다.

## 관계

- [test-map.md](test-map.md) — 무엇을 어디서 검사하는가
- [blind-spots.md](blind-spots.md) — 불변식을 어겼는데 테스트가 안 우는 지점
- [../teams/team-boundary.md](../teams/team-boundary.md) — TEAM 불변식의 설명
- [../../../program/wiki/delivery/dod.md](../../../wiki/delivery/dod.md) — DoD와의 연결
