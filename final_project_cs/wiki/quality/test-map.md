---
type: guide
title: 테스트 지도
description: 어떤 검사가 어디 있는가. 폴더 최상위만 보면 있는 테스트도 못 찾는다
status: draft
tags: [testing]
owners: [human:미배정]
domain: neutral
domain_note: 시험 지도라 여행 도메인 시험(감시 · 제안 · MCP · 실시간 진행)의 이름과 설명이 표에 나온다 — 시험 이름은 도메인을 말할 수밖에 없다
---

# 테스트 지도

**이 문서가 필요한 이유가 있다.**

`[실측]` 불변식 카탈로그 초판에서 "Runtime 불변식은 테스트로 강제되지 않는다"고 적었는데 **틀렸다.** 테스트는 `tests/integration/db/`, `tests/unit/core/`, `tests/contract/`에 흩어져 있었다. `tests/integration/` 최상위에 `__init__.py`만 있는 걸 보고 비어 있다고 판단한 실수였다.

**지도가 없으면 있는 것도 못 찾는다.**

## 전체 구조

`[실측]` 2026-09-01 기준 70개 파일

```text
tests/
├─ architecture/   2   계층 경계
├─ contract/       7   계약·상태표·격리·idempotency
├─ security/       4   인증·스코프·PII
├─ unit/          28   core/ 하위에 상태 기계와 예산
├─ integration/   22   a2a api controller db graph llm messaging rag
├─ e2e/            4   Composer·introspection·UI
└─ live/           3   실 LLM 호출
```

**`integration/`과 `unit/`은 하위 폴더가 있다.** 최상위만 보면 안 된다.

## 무엇을 어디서 검사하는가

| 검사 대상 | 위치 | 대표 파일 |
|---|---|---|
| Core 도메인 격리 | `architecture/` | `test_basement_is_domain_free.py` |
| 다른 도메인 서빙 가능성 | `architecture/` | `test_engine_serves_another_domain.py` |
| Case 상태 기계 | `contract/` | `test_case_state_table.py` |
| 상태 축약(reducer) | `unit/core/` | `test_case_reducer.py` |
| **동시 쓰기 충돌 (CAS)** | `integration/db/` | `test_stale_write_conflict.py` |
| 실행 유일성 | `integration/controller/` | `test_active_run_uniqueness.py` |
| Context 예산 | `unit/core/` | `test_context_budget.py` |
| idempotency | `contract/` | `test_consumer_idempotency_contract.py` |
| Team 계약 | `contract/` | `test_team_contract.py` |
| Core가 modules를 import 안 함 | `contract/` | `test_core_isolation.py` |
| 인증·스코프 | `security/` | `test_auth_and_scope_guards.py` |
| PII 마스킹 | `security/` | `test_pii_redaction_runtime.py` |
| tenant·customer 격리 | `security/` | `test_query_scope.py` |
| 옛 MCP 도구 수 고정(쇼핑몰 Case 도구 3개 — 연결 안 됨) | `security/` | `test_scope_contract.py` |
| **MCP 실제 접속**(initialize → 도구 호출) · 키 401 · 남의 여행 404 · 쓰기 스위치 `[2026-10-02]` | `e2e/` | `test_mcp_server.py` (15건) |
| **웹 실시간 진행(SSE)** — 단계 · 생존 신호 · 시간 초과 · 끊김 · 접수 읽기 멈춤 `[2026-10-02]` | `e2e/` | `test_op_stream.py` (21건) |
| **검사 진행 알림** — 일정마다 item·check(이동 전에) · 이동 구간마다 move · 「n/m」 progress · 보관소 · Feed 비우기·퇴보 방지 `[2026-10-03 ui 요청서 2번]` | `unit/travel/` · `e2e/` | `test_intake_progress.py` (7건) · `test_intake_progress_events.py` (5건) |
| **전체 자동 추천 미리 보기(`dry_run`)** — 저장 안 함 · 실제 적용과 같은 검사 `[2026-10-03 ui 요청서 3번]` | `e2e/` | `test_intake_autofix_dry_run.py` (5건) |
| **이름 없는 줄(종류 + 지역만)** — 줄을 조각으로 읽기(평가 줄 40개 · 새 말은 표에 한 줄 · 지명 사전 우선순위) · `needs_choice`/`needs_name` · 같은 종류만 후보 · 지역 중심 · 예약한 일정 보호(`kept: booked`) · `booking` 줄 · `category` · 고른 곳 문장 `[2026-10-03 ui 요청서 1번]` | `unit/travel/` · `e2e/` | `test_line_parts.py` (53건) · `test_intake_nameless_read.py` (7건) · `test_intake_nameless_lines.py` (7건) |
| **웹 소셜 로그인(구글)** — 시작 → 콜백 → 표 교환 한 바퀴 · 연결 · 해제 · 로그인 CSRF 막기 · 일회용 표 · state 한 번 · 이름 · 이메일 저장 없음 · 사람 확인 · 한도 · ID 토큰 서명 · nonce · 대상 확인 `[2026-10-03 ui 요청서]` | `e2e/` · `unit/travel/` | `test_web_social_login.py` (17건) · `test_oauth_providers.py` (15건) |
| **감시의 비슷한 안 묻기** — 대안 0곳 · 재판정 전부 걸림에도 조건을 풀어 묻기 · 자동 적용 안 함 · 같은 원인 재점검 · 일정 전체 재판정 · 밀도 · 날씨는 실내만 · 제안 하나 · 스위치 · 묶음 `[2026-10-03 사용자 지적]` | `e2e/` | `test_watch_relaxed.py` (11건) |
| **감시 반복의 끝맺음** — Case 예외 격리 · 끝난/낡은 제안 닫기 · 바꿀 곳 없음 알림 · 일시 실패 재시도 `[2026-10-03]` | `e2e/` | `test_watch_failures.py` (10건) |
| 활동 대체 후보가 예산보다 많아도 예외 없이 `[2026-10-03]` | `unit/travel/activity/` | `test_activity_trigger_budget.py` (3건) |
| **여행 감시 3분 주기 문**(일꾼은 1분) `[2026-10-03]` | `integration/` | `test_watch_cadence.py` (8건) |
| **고정한 일정도 감시 — 바꾸지 않고 알림** `[2026-10-03]` | `scenario/` | `test_pinned_items_are_watched.py` (3건) |
| **자동 변경 전 일정 전체 재판정** `[2026-10-03]` | `scenario/` | `test_apply_recheck.py` (3건) · 감시 알림 `test_watch_failures.py` |
| **시나리오 감시 · 새벽 확인의 일정 전체 재판정** `[2026-10-03]` | `scenario/` | `test_apply_or_ask_recheck.py` (5건 — 안 맞으면 쓰지 않고 알림 · 같은 사건 한 번만 · 맞는 변경은 그대로 · 1순위가 걸리면 2순위 · 감시기가 `rechecked` 로 셈) |
| **일정 판정기의 서울 시각 읽기 · 지연 뒤 일정 연쇄 · 하루 마감 · 식당 라스트오더** `[2026-10-03 체크리스트 H3·L2·T13·O4]` | `unit/travel/` | `test_itinerary_checks_seoul_time.py` (7건) · `test_delay_knock_on.py` (16건) · `test_itinerary_quality_day_end_last_order.py` (9건) |
| **체크리스트 반영 적대 검토 보완** `[2026-10-03]` — 비뚤어진 break 값 · 점검별 예외 격리 · 시간대 섞임 · 자정 넘김 · 식당 판정 서울 시각 · 라스트오더 잡음 · 끼니 틈 · 하루 마감 대상 · 동선 비용 | `unit/travel/` · `scenario/` | `test_checklist_review_fixes.py` (34건) · `scenario/test_desk_report_recheck.py` (4건 — 채팅 신고 경로 재판정) · `scenario/test_dawn_check.py` (새벽 확인 재판정 막힘 세기) |
| **시(hour) · 날짜를 직접 읽는 곳의 서울 시각** `[2026-10-03 ui 검증 세션 지적]` — 화면 끼니 이름표 · 되돌리기 자리 이름 · 채팅 끼니 말 찾기 · 알림 문구 시각 | `unit/travel/` | `test_seoul_hour_readers.py` (12건) |
| **일정 품질 경고 — 같은 곳 두 번 · 끼니 · 왔다 갔다** `[2026-10-03]` | `unit/travel/` · `e2e/` | `test_itinerary_quality.py` (17건 — 잡는 것 · 잡음 방지 · 거절 아님) · `e2e/test_trip_api.py::test_quality_warnings_ride_along_with_an_accepted_registration` |
| **바깥 소스 호출 줄이기 — ITS 서울 한 번 조회 · 프로세스를 건너 나누는 응답 캐시** `[2026-10-03]` | `unit/travel/` | `test_shared_source_cache.py` (8건 — 장소 20곳이 ITS 요청 1건 · 서울 밖은 전처럼 · 다른 프로세스가 바깥에 안 나감 · 만료 · 허용 소스만 · 서비스 키 미저장 · DB 가 안 되면 메모리) |
| **여행 분류 평가 자료 · 재생 도구** `[2026-10-03]` | `unit/eval/` | `test_travel_classification_eval.py` (7건 — 자료가 서버 어휘 · 여행 문장인지 · 검사기가 쇼핑몰 낱말·모르는 라벨·`other` 어긋남·겹침을 잡는지 · 실패를 분모에 넣는지 · 엉뚱한 팀과 escalate 를 가르는지) |
| **같은 여행 문제 묶음** `[2026-10-03]` | `scenario/` · `unit/travel/activity/` · `e2e/` | `test_watch_batch.py` (8건 — Case 1·판 1·알림 1 · 못 푼 것 · 전부 보호 · 중복 알림 방지 · 안전 줄 먼저) · `test_watch_batch_unit.py` (15건 — 초안 기준 · 항목별 예산 · 마지막 재판정 · 표지 · 예외 · 시간 한도 · 알림 키 · 항목별 시간·호출 기록) · `test_watch_failures.py` 묶음 구간 (3건 — 재시도 · 한 통 알림) |
| **다음 순위 안 시험 · 밀도 판단** `[2026-10-03]` | `unit/travel/` | `activity/test_activity_fit.py` (6건) · `test_density_gate.py` (12건) · 감시 알림 `test_watch_failures.py::test_every_ranked_option_blocked_by_the_recheck_is_announced_the_same_way` |
| outbox 해소 | `integration/api/` | `test_outbox_resolution.py` |
| outbox tenant 격리 | `integration/messaging/` | `test_outbox_tenant_guard.py` |
| 제공자 timeout | `integration/controller/` | `test_provider_timeout_unknown.py` |
| 실행 직전 재확인 | `integration/api/` | `test_recheck_before_execution.py` |
| 제안 차단 | `integration/controller/` | `test_proposal_guard_blocks.py` |
| A2A 왕복 | `integration/a2a/` | **`test_travel_remote_round_trip.py`** (테스트 7건) `[정정 2026-09-10]` 옛 `test_remote_round_trip.py` 는 **작업 트리에서 삭제됐고 git 에는 남아 있다** — 커머스 원격의 것이었다 |
| SQL Graph Adapter | `integration/graph/` | `test_sql_graph_adapter.py` |
| RAG | `integration/rag/` | `test_rag_integration.py` |
| LLM 호출 감사 | `integration/llm/` | `test_llm_call_audit_wiring.py` |
| Composer 쓰기채널 | `e2e/` | `test_composer_write_channel.py` |

## 불변식과의 연결

`[실측 2026-10-03]` 불변식 **61개 중 58개**가 위 테스트에 연결돼 있다(2026-10-02 에는 56개 중 53개, 2026-09-10 에는 52개 중 49개).

연결 상태는 [invariants.md](invariants.md)에 있고, **검사기가 실제로 파일과 함수 존재를 확인한다.**

```bash
python program/scripts/check_wiki.py
```

이 명령이 검사하는 것.

```text
1. 불변식이 가리키는 테스트 파일이 실재하는가
2. 그 파일에 해당 test 함수가 실재하는가
3. 코드의 invariant 표식이 카탈로그에 있는가
4. 링크·front matter·문서 크기
```

## 코드 쪽 역방향 표식 — 완료

`[실측]` **2026-09-01 완료. 그때 48개, 2026-09-10 기준 49개.**

넣은 모양.

```python
# invariant: INV-CS-RT-009
def test_two_writers_that_read_the_same_version_produce_exactly_one_conflict():
    ...
```

**왜 필요한가.** 테스트를 지우거나 이름을 바꿀 때, 그게 어떤 불변식을 깨는지 **그 자리에서 보인다.** 문서를 열지 않아도 된다.

`[실측]` 대조 결과.

```
코드에만 있는 ID  0개
문서에만 있는 ID  3개  ← INV-CS-TEAM-003·004·005 (판정이 review 라 테스트 없음)
```

**양방향이 잠겼다.**

## 테스트가 없는 곳

| 대상 | 상태 |
|---|---|
| Team 경계 3개 (`INV-CS-TEAM-003~005`) | `review`. import 검사로 자동화 가능해 보임 |
| 그 외 | [blind-spots.md](blind-spots.md) |

## 관계

- [invariants.md](invariants.md) — 불변식 카탈로그
- [blind-spots.md](blind-spots.md) — 검사가 없는 지점
- [../../../acop_dojo/wiki/index.md](../../../acop_dojo/wiki/index.md) — 사각지대를 실행으로 찾는 프로그램
