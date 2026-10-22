---
type: contract
title: 불변식 카탈로그
description: 깨면 안 되는 규칙 전체 목록. 대부분 테스트가 자동 판정한다
status: draft
tags: [testing, architecture]
owners: [human:미배정]
size_exempt: true
size_exempt_reason: 불변식 카탈로그. 전체를 훑어야 의미가 있다
domain: neutral
domain_note: 불변식 목록이다. 과거 어휘는 재유입 방지 금지 목록에만 사용하며 동작 사례는 여행 자료로 검증한다
---

# 불변식 카탈로그

> `[실측 2026-09-01]` **`app/core/case_runtime/`·`access_action/` 은 `__init__.py` 만 남은 빈 패키지다.**
> 2026-08-13 에 중첩 구조로 갔다가 **평면 구조로 되돌아왔다.** 정본은 `app/core/*.py` 다.
> 구조가 또 바뀔 수 있으므로 **작업 전에 실제 경로를 확인한다.**

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
| `INV-CS-ARCH-003` | Core는 `app/domains`를 import하지 않는다 | automated | `tests/contract/test_core_isolation.py::test_core_does_not_import_modules` |
| `INV-CS-ARCH-004` | 도메인 어휘 예외 목록은 작게 유지된다 | automated | `tests/architecture/test_basement_is_domain_free.py::test_allow_list_stays_small` |
| `INV-CS-ARCH-005` | 엔진 소스에 도메인 어휘가 없다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_engine_source_has_no_domain_vocabulary` |
| `INV-CS-ARCH-006` | 도메인 모듈은 자기 도메인을 알아도 된다 | automated | `tests/architecture/test_basement_is_domain_free.py::test_domain_modules_are_allowed_to_know_their_domain` |
| `INV-CS-ARCH-007` | 상태 전이도는 코드의 상태·전이와 일치한다 | automated | `tests/architecture/test_state_diagram_matches_code.py::test_state_diagram_is_regenerated_from_the_code` |

**`INV-CS-ARCH-004`가 특이하다.** 예외 목록의 **크기 자체**를 검사한다. 예외가 늘어나면 그게 설계가 무너지고 있다는 신호다.

현재 예외는 `app/core/redaction.py` 하나다. PII 마스킹은 결제 식별자 **모양**을 알아야 가릴 수 있는데, 이건 도메인 로직이 아니라 보안 규칙이다.

금지 어휘.

```python
DOMAIN_WORDS = (
    # 구독·결제 (sample 도메인)
    "payment", "subscription", "entitlement", "refund", "invoice",
    # 커머스 (v9 까지 이 저장소의 도메인. 2026-09-10 에 코드에서 나갔다)
    "order_id", "line_item", "shipment", "sku", "cart",
    # ★여행 (v10~ 현재 도메인). 2026-09-10 추가
    "booking", "itinerary", "lodging", "supplier_booking", "traveller",
)
```

★**도메인이 바뀌면 새 어휘를 여기 넣는 것까지가 교체다.** `[실측 2026-09-10]` 2026-09-08 에 도메인을 갈면서 `app/domains/travel_ops/` 만 만들고 이 목록은 안 늘렸다 — 그래서 **`booking_id` 가 코어로 새도 검사가 울지 않는 상태**였다.

★**옛 어휘를 지우지 않는다.** 커머스 코드가 저장소에서 나갔어도 커머스 낱말이 코어에 들어오면 안 되는 것은 그대로다. **목록은 도메인마다 누적된다.**

---

## Team 계약 — `INV-CS-TEAM-*`

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-TEAM-001` | Team manifest는 프로토콜을 구현한다 | automated | `tests/contract/test_team_contract.py::test_team_manifests_implement_protocol` |
| `INV-CS-TEAM-002` | manifest의 scope는 정확히 선언된다 | automated | `tests/contract/test_team_contract.py::test_manifest_scopes_are_exact` |
| `INV-CS-TEAM-003` | Team은 side effect를 실행하지 않는다 | review | [../teams/team-boundary.md](../teams/team-boundary.md) |
| `INV-CS-TEAM-004` | Team은 허용된 자료 조회 Port·ReadToolbox로만 읽고 고객 권한·허용 목록·예산·근거 경계를 지킨다 (2026-10-12 확정) | review | 동 |
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
| `INV-CS-ACT-004` | **자동 변경은 쓰기 전에 일정 전체를 다시 판정하고, 바꾼 뒤 새로 생긴 위반이 있으면 적용하지 않는다**(D-017 전체 일정 재검증 — 등록 때와 같은 판정기 `check_itinerary`). ★최고 안이 걸리면 담당이 뽑아 둔 **다음 순위 안**을 차례로 시험한다 | automated | `tests/scenario/test_apply_recheck.py::test_an_automatic_change_that_breaks_the_whole_itinerary_is_not_applied` · `tests/unit/travel/activity/test_activity_fit.py` |
| `INV-CS-ACT-005` | **자동 변경이 하루 밀도를 나쁘게 만들면(목표 밖으로 새로 밀기 · 이미 밖인 날을 허용 오차보다 더 밀기 · 잴 수 있던 날을 못 재게 하기) 순위에서 뒤로 밀리고, 더 나은 안이 없을 때만 감수하며 알림에 적는다.** 구조 위반은 밀도와 상관없이 늘 막는다(D-019 개정) | automated | `tests/unit/travel/test_density_gate.py` |
| `INV-CS-ACT-006` | **같은 여행의 새 문제가 한 회차에 둘 이상이면 Case 1 · 새 판 1 · 알림 1** — 뒤 항목은 앞에서 고친 초안 기준이고, 하나를 못 풀어도 나머지는 진행하며, 묻는 것은 새 판 기준 · 못 푼 것은 같은 알림에 한 줄 · 같은 사건은 다시 열지도 알리지도 않는다(D-017 여행별 묶음) | automated | `tests/scenario/test_watch_batch.py` · `tests/unit/travel/activity/test_watch_batch_unit.py` · `tests/e2e/test_watch_failures.py`(묶음 구간) |
| `INV-CS-ACT-007` | **시나리오 감시 · 새벽 확인(`pending.apply_or_ask`)도 자동 변경 전에 일정 전체를 다시 판정한다** — Case 적용기와 같은 문(`itinerary_fit.fit_change`: 순위 순 재판정 + 밀도 게이트). 다 걸리면 **쓰지 않고** 「일정은 그대로 두었어요」(`recheck_failed`)를 같은 사건·같은 판에 **한 번만** 알리고 `rechecked` 로 센다. 묻는 쪽(변경 안 할 일정 등)은 지나지 않는다. ★`[2026-10-03 적대 검토]` **채팅 신고 경로**(`TripDesk._outcome(gate=True)` — 「늦어요」 · 「문 닫았대요」로 자동 고른 대체)도 같은 문을 지나고, 다 걸리면 쓰지 않고 `rechecked` 답 문장을 돌려준다. 고객이 직접 고른 길(다른 안으로 바꿔 줘 · 되돌려 줘)은 지나지 않는다(D-017 · 체크리스트 v2 T5) | automated | `tests/scenario/test_apply_or_ask_recheck.py` · `tests/scenario/test_desk_report_recheck.py` · `tests/scenario/test_dawn_check.py` |
| `INV-CS-ACT-009` | **일정 판정기(`check_itinerary`)는 시각을 서울 시각으로 읽는다** — 같은 순간을 세계 표준시로 보내든 서울로 보내든 영업 전 · 마감 뒤 · 쉬는 날 · 브레이크 · 입장 마감 판정과 안내 문장의 시각이 같다. 시간대 없는 시각은 서울로 본다(이 PC 시간대가 아니다). 자동 변경 전 일정 전체 재판정이 DB 에서 읽은 시각으로 이 판정기를 돌리므로 DB 세션이 UTC 여도 같은 결과다(체크리스트 H3). ★`[2026-10-03 적대 검토]` 시간대 있는 시각과 없는 시각이 한 일정에 섞여도 죽지 않고, **자정을 넘기는 일정**이 마감 · 브레이크 검사를 빠져나가지 않는다(자정 마감으로 읽힌 곳은 진짜 닫는 시각을 모르니 안 센다). 식당 판정(`replan.dining_fits` · `dining_warnings`)도 서울 시각이다. ★`[2026-10-03 ui 검증 세션 지적]` 시(hour) · 날짜를 직접 읽는 곳도 같다 — 화면의 끼니 이름표(`trip_api._meal_label`) · 되돌리기 안내의 자리 이름표 · 채팅의 「점심 식당」 찾기 · 변경 알림 문구의 시각 서식(`replan._hm` · `_part_of_day` · 고객 요청 변경 알림) · 변경 링크 화면의 시각 · 일정 응답의 `starts_at`/`ends_at`(서울 +09:00 — 지도의 날짜 묶음) · 날씨 소스의 예보 칸(DB 세션이 UTC 여도 서울 12:00 점심이 「점심」) | automated | `tests/unit/travel/test_itinerary_checks_seoul_time.py` · `tests/unit/travel/test_checklist_review_fixes.py` · `tests/unit/travel/test_seoul_hour_readers.py` |
| `INV-CS-ACT-010` | **앞 일정이 늦어지면(「N분 늦어요」) 그 식사만 보지 않고 뒤 일정이 밀려도 성립하는지 본다** — 겹치는 뒤 항목만 차례로 밀어 영업 · 휴무 · 브레이크 · 입장 마감(같은 `check_itinerary` 판정)에 걸리거나 예약 · 고정 일정이면 알리고, **일정은 바꾸지 않는다**(체크리스트 L2). ★`[2026-10-03 적대 검토]` 끝 시각을 모르는 항목은 끝을 지어내지 않고 · 예약 · 고정 일정은 밀리지 않고 제자리에서 **늦는 것**으로 세어 뒤로는 원래 끝에서 이어지며 · 안내 문장은 서비스가 실제로 해 주는 일(「○○ 바꿔줘」 대체 찾기)만 말한다 | automated | `tests/unit/travel/test_delay_knock_on.py` |
| `INV-CS-ACT-011` | **일정 품질 경고 계산은 장소 값이 비뚤어져도 여행 화면을 죽이지 않는다** — 읽을 수 없는 `break` 값(`"15:00~17:00"` · `[null,null]` …)은 모름으로 보고, 점검 하나가 예외를 내도 나머지 경고는 나가며 죽은 점검은 로그와 `quality_check_skipped` 경고로 **센다**(조용히 빼지 않는다). 동선 점검은 8곳이어도 값싸다(동적 계획법) | automated | `tests/unit/travel/test_checklist_review_fixes.py` |
| `INV-CS-ACT-012` | **감시가 대안을 못 찾거나(`no_alternate`) 찾은 안이 일정 전체 재판정에 다 걸려도(`recheck_failed`) 곧바로 「일정은 그대로 두었어요」로 끝내지 않고 조건을 풀어 비슷한 안을 묻는다** — 시각 늦추기 · 다음 일정 근처 · 반경 넓히기 셋까지, **자동 적용하지 않고** 보류 제안(이유 `relaxed`)으로. 묻는 안은 **고르면 그대로 적용될 안만**(같은 원인 재점검 통과 · 일정 전체 재판정 · 밀도 판단) 싣고, 날씨 원인이면 활동은 실내만. 한 곳도 없을 때만 옛 알림이고, 같은 항목 · 같은 판에는 제안 하나(`travel.watch.relaxed_enabled`) | automated | `tests/e2e/test_watch_relaxed.py` |
| `INV-CS-ACT-008` | **일정 품질 경고(같은 곳 두 번 · 끼니 빠짐 · 왔다 갔다 · 하루 마감 · 식당 라스트오더)는 거절이 아니라 `warnings` 로만 알린다** — 위반(`check_itinerary`)이 없는 일정은 경고가 몇 개든 등록된다(201). 경고는 밀도 경고와 같은 목록 · 같은 모양(`code`·`date`·`reason`·`remedy` + `items`)이다(체크리스트 v2 T7·T8·T9) | automated | `tests/unit/travel/test_itinerary_quality.py::test_a_day_with_every_warning_is_still_accepted_by_the_registration_judge` · `tests/e2e/test_trip_api.py::test_quality_warnings_ride_along_with_an_accepted_registration` |

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
| `INV-CS-SEC-007` | scope 목록은 공통 guardrail 설정이 소유한다 | automated | `tests/security/test_scope_contract.py::test_scopes_are_guardrail_owned` |
| `INV-CS-SEC-009` | **MCP 호출자는 사용자 키가 정한다** — 키가 없거나 틀리면 연결 단계에서 401, `mcp` 모듈 토글을 끄면 404. 도구 인자에 `customer_id` 가 없어 본인 여행만 열린다(남의 여행은 404) | automated | `tests/e2e/test_mcp_server.py::test_without_a_key_or_with_a_wrong_key_the_connection_is_401_and_a_disabled_module_is_404` |
| `INV-CS-SEC-010` | **MCP 쓰기 도구는 `travel.mcp.write_enabled` 가 켜졌을 때만 등록된다**(기본 꺼짐 — 「MCP 는 read-only」). 읽기 도구만 있을 땐 전부 `readOnlyHint` | automated | `tests/e2e/test_mcp_server.py::test_by_default_only_read_tools_exist_and_all_say_they_are_read_only` |
| `INV-CS-SEC-011` | **바깥 소스 응답 공유 캐시는 허용된 공개 소스만 DB 에 두고, 요청 인자의 서비스 키 원문을 두지 않는다**(열쇠는 해시). 고객 검색어가 담기는 소스(카카오 · 구글 장소)는 메모리에만 — DB 가 안 되면 메모리로 계속한다 | automated | `tests/unit/travel/test_shared_source_cache.py::test_only_allowed_sources_reach_the_db_and_the_service_key_is_not_stored` |
| `INV-CS-SEC-012` | **서버용 OpenAI 키를 읽는 제품 코드는 모델 서버 장애 넘김 한 곳뿐이다** — 개발 중 호출 · 시험 · 측정으로 새면 요금과 노출 위험이 생긴다(사용자 지시 2026-10-07, [D-CS-016](../decisions/D-CS-016-llm-failover-server-key.md)) | automated | `tests/architecture/test_server_key_readers.py::test_only_the_settings_declaration_and_the_failover_read_the_server_key` |
| `INV-CS-SEC-013` | **모델 서버 넘김 장치가 모든 경로에 실패해도 오류 · 로그에 키 값을 싣지 않는다**(상태 코드와 이유 이름만) | automated | `tests/unit/infrastructure/test_llm_failover.py::test_when_every_path_fails_the_error_names_the_reasons_and_never_the_key` |
| `INV-CS-SEC-014` | **사진 · 스캔 이미지는 `llm_failover_vision` 을 따로 켜지 않으면 API 로 넘어가지 않는다** — 이미지의 이름 · 예약번호는 가릴 수 없다 | automated | `tests/unit/infrastructure/test_llm_failover.py::test_images_do_not_go_to_the_api_unless_vision_is_switched_on` |
| `INV-CS-SEC-015` | **서버용 키가 비어 있으면 스위치가 켜져 있어도, 개인 키가 있어도 OpenAI 로 넘어가지 않는다**(Ollama 만 쓴다) | automated | `tests/unit/infrastructure/test_llm_failover.py::test_personal_key_does_not_enable_failover_without_a_server_key` |

**`INV-CS-SEC-004`가 셋을 한 번에 본다.** DB에만 마스킹하고 audit에 원본이 남는 실수를 막는다.

---

## 도메인 검증 — `INV-CS-VER-*`

Action을 실행하기 전 근거를 대조한다.

### 여행 정책 주입 시험의 범위

합성 철도 패스·승차권 정책을 기존 예약 정책과 같은 엔진에 주입합니다. 참조·금액·인원 상한과 성공·실패를 검사합니다. **실제 패스 기능 출시나 모든 산업의 범용성을 증명하지 않습니다.** 이전 주문·반품 시험은 D-023에 따라 현재 관문에서 제외했습니다. ID는 검증 책임을 이어받되 데이터와 증명 범위를 명시적으로 개정했습니다.

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-VER-001` | 존재하지 않는 철도 패스는 거부한다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_unknown_pass_is_rejected` |
| `INV-CS-VER-002` | 패스 결제 금액보다 큰 환급을 거부한다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_refund_over_the_pass_payment_is_rejected` |
| `INV-CS-VER-003` | 결제 금액 이내의 부분 환급을 통과시킨다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_partial_refund_passes` |
| `INV-CS-VER-004` | 좌석 상한보다 많은 여행자를 거부한다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_travelers_over_the_seat_limit_are_rejected` |
| `INV-CS-VER-005` | 좌석 상한 이내의 여행자는 통과시킨다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_travelers_within_the_seat_limit_pass` |
| `INV-CS-VER-006` | 허용 사실에 포함된 승차권만 통과시킨다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_ticket_ownership_is_checked` |
| `INV-CS-VER-007` | 대조 수단이 없는 필드를 거부한다 | automated | `tests/architecture/test_engine_accepts_travel_policies.py::test_this_domains_opaque_field_is_rejected` |

제품의 여행 예약 정책은 `tests/unit/core/test_proposal_verification.py`가 예약 식별자·금액·정원·미선언 필드를 검사합니다. 필드가 여행과 관련돼도 선언되지 않은 `permit_id`는 거부합니다. 단순 금액 상한 검사는 업체의 실제 환급 규정 계산이 옳다는 보장이 아닙니다. 사실 집합의 범위와 원본 값의 정확성도 별도로 확인해야 합니다.

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

### 웹 실시간 진행(SSE) `[2026-10-02]`

서버·모델이 멈춰도 사용자가 자기 요청의 상태를 알게 하는 장치(`op_stream.py`)의 약속 둘.

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-021` | **일꾼이 막혀 있어도 생존 신호(`beat`)가 계속 나간다** — 이벤트 루프가 낸다. 모델·장소 조회를 기다리는 단계가 `slow_seconds` 를 넘으면 `slow=true` | automated | `tests/e2e/test_op_stream.py::test_beats_keep_coming_while_the_worker_is_blocked_and_flag_a_slow_model` |
| `INV-CS-RT-022` | **연결이 끊겨도 일은 끝까지 돌고 응답 뒤로 미룬 일은 정확히 한 번 돈다** — 처리 중인 요청을 버리지 않는다 | automated | `tests/e2e/test_op_stream.py::test_if_the_client_leaves_midway_the_work_and_its_deferred_part_still_finish_once` |

### 감시 반복의 끝맺음 `[2026-10-03 결함 인계]`

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-RT-023` | **감시 반복은 Case 하나의 실행 실패로 끊기지 않는다** — 터진 Case 는 `escalated`(`team_error`)로 닫혀 운영자가 오류로 보고, 그 회차의 나머지 Case 는 계속 돈다 | automated | `tests/e2e/test_watch_failures.py::test_one_case_blowing_up_does_not_stop_the_rest_of_the_tick_and_is_closed_as_team_error` |
| `INV-CS-RT-024` | **못 고르게 된 제안(끝난 일정 · 낡은 기준 버전)은 열린 채 두지 않고 그 자리에서 닫는다** — 닫은 기록은 커밋되고 부르는 쪽은 409 를 받는다 | automated | `tests/e2e/test_watch_failures.py::test_choosing_a_proposal_whose_item_has_ended_is_refused_and_the_closing_is_kept` |
| `INV-CS-RT-025` | **여행 감시는 주기 문(3분)을 지난 회차에서만 돌고 일꾼이 몇이 떠도 한 번 돈다** — 일꾼은 1분마다 돌아도 외부 소스를 3배로 부르지 않는다(D-017) | automated | `tests/integration/test_watch_cadence.py::test_two_workers_at_the_same_moment_only_one_wins` |
| `INV-CS-RT-026` | **고객이 「바꾸지 말 것」으로 고정한 일정도 감시한다 — 일정은 바꾸지 않고 알린다**(바꾸지 않는 것과 알림을 끄는 것은 별개, D-020) | automated | `tests/scenario/test_pinned_items_are_watched.py::test_a_pinned_activity_is_checked_and_the_customer_is_told_but_the_itinerary_is_not_changed` |
| `INV-CS-RT-027` | **채팅 결정에서 모델이 바꾸는 할 일(바꾸기 · 대안 · 되돌리기 · 다시 · 닫힘 알림)의 대상을 근거 없이 골랐으면 일정을 바꾸지 않고 되묻는다**(`guard_target` — 실제 모델 재생 172문장에서 엉뚱한 대상 변경 1건 → 0건, 2026-10-07) | automated | `tests/unit/travel/test_decision_target_guard.py::test_the_recorded_failure_a_dinner_on_another_day_is_asked_about_not_changed` |
| `INV-CS-RT-028` | **사진 · 스캔 받아쓰기가 같은 줄을 두 번 다르게 읽었으면 그 줄의 제목 · 예약번호는 값을 고치지 않고 「확인 필요」로 두며, 고객이 고르기 전에는 그 일정을 확정(등록)하지 않는다** — 고르면 표시가 사라진다 | automated | `tests/e2e/test_intake_transcription_differs_db.py::test_the_review_marks_the_item_for_review_and_gives_the_two_readings_to_draw_buttons` |

---

## Context 예산 — `INV-CS-CTX-*`

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-CTX-001` | 예산 초과 시 정해진 순서로 축출한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_eviction_is_budgeted_and_ordered` |
| `INV-CS-CTX-002` | 자를 수 없는 구간은 거부한다 | automated | `tests/unit/core/test_context_budget.py::test_context_broker_rejects_untruncatable_sections` |

`INV-CS-CTX-002`가 중요하다. **잘라서 의미가 깨지는 자료는 조용히 자르지 않고 거부한다.**

---

## 평가 — `INV-CS-EVAL-*`

| ID | 불변식 | 판정 | 실행 위치 |
|---|---|---|---|
| `INV-CS-EVAL-002` | 여행 분류 자료는 현재 intent·issue_code 어휘를 사용하고 과거 도메인 재유입을 검사하며 실패도 재생 시험의 분모에 넣는다 | automated | `tests/unit/eval/test_travel_classification_eval.py` |

사용 종료된 `INV-CS-SEC-008`(옛 MCP 도구 수)·`INV-CS-EVAL-001`(옛 평가 러너)은 현재 정의 표에서 제외합니다. 번호는 재사용하지 않으며 과거 정의·증거는 아래 보존 기록에 있습니다. 현재 MCP는 SEC-009·010과 여행 프로토콜 시험으로 확인합니다.

---

## 코드 표식과 현재 집계

정의 표의 고유 ID·판정 종류는 [자동 집계](invariant-summary.generated.md)에서 확인합니다. `python program/scripts/build_wiki_catalogs.py`로 갱신하고 `--check`로 정합성을 확인합니다. 등록 수·코드 표식 수·시험 연결 수·실행 통과 수는 각각 다른 분모입니다.

`INV-CS-ARCH-007`은 이미 존재하는 전이도 재생성 시험을 카탈로그에 연결한 것입니다. 새 제품 동작이나 새 제약을 추가하지 않았습니다.

TEAM-004의 허용된 자료 조회 계약은 2026-10-12에 확정했습니다. 모든 실제 호출 경로가 권한·예산·근거 경계를 지키는지는 별도 구현 검증 대상입니다. VER 자료를 교체했다는 이유로 다른 계약 검토까지 완료로 올리지 않습니다. 과거 48·52·56·61개 집계와 당시 진단은 수정 전 보존본에 있습니다.

## 관계

- [자동 집계](invariant-summary.generated.md) — 정의 표만 세는 생성물
- [시험 지도](test-map.md) — 실행 위치

## 이 검증에서 배운 것

문서에 "테스트가 없다"고 적기 전에 **테스트를 실제로 찾아봐야 한다.**

이전 판은 `tests/integration`에 Runtime 테스트가 없다고 봤는데, 실제로는 `tests/integration/db/`, `tests/unit/core/`, `tests/contract/`에 흩어져 있었다. **폴더 최상위만 보고 판단한 실수다.**

이게 [test-map.md](test-map.md)가 필요한 이유다. 테스트가 어디 있는지 지도가 없으면 있는 것도 못 찾는다.

## 관계

- [test-map.md](test-map.md) — 무엇을 어디서 검사하는가
- [blind-spots.md](blind-spots.md) — 불변식을 어겼는데 테스트가 안 우는 지점
- [../teams/team-boundary.md](../teams/team-boundary.md) — TEAM 불변식의 설명
- [../../../wiki/delivery/dod.md](../../../wiki/delivery/dod.md) — DoD와의 연결

## 개정 전 카탈로그

[과거 정의](../records/commerce_2026-10-11/wiki--quality--invariants.md) — 폐기 ID와 이전 시험 재료의 이력을 보존합니다.
