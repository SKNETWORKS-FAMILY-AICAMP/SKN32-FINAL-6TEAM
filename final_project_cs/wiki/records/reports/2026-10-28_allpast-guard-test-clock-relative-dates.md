---
type: report
title: 전부-과거 가드 시험 시계 전역 고정 제거 — 고정 날짜 자료를 실행 날 기준 상대 날짜로 (role-manager 후보)
status: verified
domain: travel
---

# 시험 시계 전역 고정 → 상대 날짜 전환 (2026-10-28 KST)

10-27 할 일(★ `wiki/handoff/index.md`, 사용자 지시 「상대날짜 전환 다음날로 해놔」)의 role-manager 후보다. **push 0** · 제품 코드 변경 0 · live/x600/로컬 서빙 반영 0.

## 결론

- 상태: **안 돼 있었음 → 후보 만듦.** role-manager `8a1feae8f`(ls-remote 팀 동일)의 `tests/conftest.py` 에 `ALL_PAST_GUARD_TEST_TODAY=(2026,8,1)` · `_pin_all_past_guard_today` 가 그대로 있었고, `git log -S` 는 넣은 커밋(`376f2a67`·`f57be997`)만, 다른 세션의 전환 기록도 없었다.
- 후보 커밋: `254a0b1d46396144922800da1f1fd09bb67264e2`(부모 `8a1feae8f`, 별도 커밋 1개 — develop 에 따로 올릴 수 있다). 작업트리 `cache/scratch/reldate-rm-20261028-0337/rm`, patch `ev/patch/0001-test.patch`(sha256 `d0aa51f8…b6b5a`). 팀 develop `36ba4c2f` 에 `apply --check -3` 통과(develop 은 role-manager 의 조상이 아니므로 develop 관문은 따로 돌려야 한다).
- 바뀐 파일 39: conftest 1(고정 제거) · 새 helper 1 · 새 helper 시험 1 · 기존 시험 36.

| 관문 | 결과 |
|---|---|
| 빠른 관문(architecture·contract·unit·security·eval/tests, `not live and not db and not slow`) 실제 시계 | 10,572 passed · 0 failed · skip 173 |
| 같은 관문, 가드+helper 시계 **+37일** | 10,572 / 0 |
| 같은 관문, 시계 **2026-12-31 23:58**(자정 · 연말) | 10,572 / 0 |
| 비교 DB `gugu_replay_improved_20261025`, 97파일(이전 안전 목록 39 ∪ CI 실패 파일 ∪ 바뀐 파일, 전역 표 파일 제외) | 1,108건 중 실패 5 → 1건(`test_mcp_read_tools` 위험 보고)은 수정 후 파일 재실행 17/17, 4건 `test_llm_failover::test_http_*` 는 격리 runner 의 loopback bind 차단(기준 트리도 같은 4건) |
| 비교 DB, 가드+helper 시계 **+37일**, 핵심 10파일(trip_api · intake_review · trip_intake_api · trip_planner · notice_routing · ask_first · nambu_progress_web · forecast_advisory · mcp_read_tools · intake_stay_lines) | 227건 0 failed |
| scratch PG16(55531, 다른 작업자 pgdata 사본 + 이 트리 migrate) 전역 표 6파일(safety_pause · web_api · guest_and_trip_delete · watch_failures · watch_relaxed · trip_dining_ledger) | 129건 0 failed |
| 비교 DB 23표 행 수 · md5, 첫 실행 전 ↔ 마지막 실행 후 | 차이 0 |
| ruff 0.16.8 `ruff check .` | 0 |

- 기준(같은 tip, 고정만 제거 · 실제 시계) 39파일: 570건 중 168 실패(114 failure · 54 error). CI 의 고정 전 실패(run 40224187039)는 67파일 479건.

## 무엇을 바꿨나

- `tests/helpers/relative_dates.py`
  - `epoch_shift()` — 기준일 2026-08-01(예전 고정 값, 박힌 날짜 중 가장 이른 2026-08-17 보다 앞)을 **오늘+7일 이후 같은 요일**로 보내는 한 가지 폭(7의 배수). 한 프로세스에서 처음 부를 때 한 번 정한다(자정을 넘겨 도는 실행에서 import 한 자료끼리 어긋나지 않게).
  - `day()` · `moved()` · `shifted()`(값 전체가 ISO 날짜·시각인 문자열만, 판 이름 `2026-09-24.v1` 불변) · `shift_text()`(문장 속 ISO 날짜) · `clock_class()`(재생 시계 대역, `isinstance` 보존).
- 대본 `seoul_day_taiwan_friends.json`: `test_trip_api.SCENARIO` 를 통째로 옮긴다 → 이것을 import 하는 파일 다수가 함께 풀린다.
- 접수 · 계획 시험: 문자열 속 2026 날짜 → 모듈 상수 `D_2026_10_15 = reldate.day("2026-10-15")`(스크립트 변환, 문서 문자열 제외, 줄마다 검토).
- 재생 기록(`nambu_field_chat.json`): `turn['at']` 과 문장 속 날짜(`2026-10-17 20:20 …`)를 같은 폭으로.
- 날짜가 지나 있어야 의미가 있던 시험은 그 상태를 **오늘 기준으로 명시**:
  - `_new_guest_with_trip(ended_days_ago=30)` — 게스트 정리 · 백업 · 보관 시험의 「이미 끝난 여행」.
  - `test_mcp_read_tools` 위험 보고 1건 — 등록 뒤 그 여행만 쓰인 날로 되돌린다(멀리 남은 항목은 `too_early` 가 정상 동작, `risk_report.judge_item`).
- 재생 fixture 의 벽시계: `disruptions` 의 대기질 예보 범위(72시간) 판정이 `datetime.now(UTC)` 를 읽어 앞날 대본이 범위 밖이 됐다 → fixture 에서 그 모듈 시계를 재생 시계로(`pending.wall_clock` 을 재생 시계로 바꾸는 기존 선례와 같은 방식).
- 옮기지 않은 것: 가드 자체 시험(자기 시계 주입) · 공휴일표 범위 시험(`test_mobility_engine_flow`) · 순수 함수 시험(`test_mcp_server` 개요 · `test_chat_edit_web` — 변환했다가 실패/불필요로 되돌림) · 2030 이후 상수 대부분.

## Codex 검토 (gpt-6.1-sol, 1회, 텍스트 전용 · 도구 없음)

- 결론: 방향 찬성 · 별도 커밋 찬성. 반영한 지적: ① 「휴무·영업시간 불변」 주장을 요일 규칙으로 좁힘(n번째 요일 · 특정 월 · 공휴일은 못 지킨다고 문서화) ② 72시간 주석을 「재생 시각과 같은 시간축」 근거로 고침 ③ `clock_class.now()` 시간대 의미 명시 ④ 재생 문장 속 날짜 누락(실제로 `2026-10-17 20:20 …` 있음) → `shift_text` ⑤ 폭을 독립 상수로 재는 시험 추가(2026-10-28 → 98일).
- 남은 위험(수용, 되돌릴 수 있음): 7일 배수라 **n번째 요일 · 월별 휴무 · 공휴일**에 걸리는 날이 생기면 그 시험만 깨질 수 있다. 현재 두 시계(+0 · +37일 · 연말 자정) 전부 0 실패. 깨지면 그 시험만 국소 시계 고정으로 바꾼다. pytest 병렬(xdist) 실행에서 자정을 사이에 두면 worker 마다 폭이 7일 다를 수 있다(시험끼리 독립이라 현재 결함 아님).

## 한계

- DB 관문은 CI 전체가 아니라 「안전 목록 ∪ CI 실패 파일 ∪ 바뀐 파일」 103파일. DDL 파일(`test_watch_simulation` · `test_watch_monitoring`)과 나머지 DB 파일은 돌리지 않았다 → push 뒤 `CI (main)` 전체로 확인 필요.
- +37일 시계는 가드와 helper 시계만 옮긴다(DB `now()` · 다른 제품 벽시계는 실제 시각).
- `test_decision_unit_web::test_the_raw_coordinates_are_stored_and_logged_nowhere` 는 비교 DB 전 테넌트 표를 읽어 20분+ 걸려 제외(환경).
- 이 후보를 시험한 트리를 마지막 DB 실행 도중 1파일(`test_mcp_read_tools`) 고쳤다 — 그 파일만 고친 뒤 따로 재실행(17/17), 다른 파일은 그것을 import 하지 않는다.
- develop 포팅: patch 는 깔끔히 적용되지만 develop 은 dining 시험 주입점 등 다른 줄기라 develop 트리에서 빠른 관문 · DB 관문을 다시 돌려야 한다.
