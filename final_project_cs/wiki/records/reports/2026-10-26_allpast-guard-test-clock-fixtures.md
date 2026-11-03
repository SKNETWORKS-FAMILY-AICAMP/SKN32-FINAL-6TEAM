---
type: report
title: 전부-과거 날짜 가드에 걸린 시험 fixture 정리·schema 시험 정정·DB 필요 28건 실행·팀 브랜치 영향
status: verified
domain: travel
---

# 전부-과거 날짜 가드 시험 fixture 정리 (2026-10-26 02:47 KST)

- 작업 폴더: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/fixture-clock-fix-20261026-0118-19126/`
- 기준 source: live v7a `action-v7a-allpast-20261025-233317-fac130f7/source-v7a`의 사본(`source/`)에서만 수정했습니다. 원본 코드·live API·프런트는 건드리지 않았고 push도 하지 않았습니다.
- 팀 기준: develop `d2ab93a65`, role-manager `08b995976`. 둘 다 `allpast-hotfix-20261025-2005/latest`에서 `git archive`로 꺼냈고, 원 저장소는 읽기만 했습니다.
- 제품 코드 변경은 0건입니다. 시험 파일만 바꿨으며 skip·xfail·assert 약화는 없습니다.

## 결론

1. 라우팅 감사 547건을 재실행하니 **549/549 = 100%**가 나왔습니다. 547건 + 새 paired 가드 시험 2건이고, DB가 필요한 28건도 비교 DB `gugu_replay_improved_20261025`에서 실제로 돌렸습니다.
2. **팀 브랜치도 영향을 받습니다.** 우리 가드 핫픽스 때문에 생긴 문제입니다.
   - develop: 빠른 관문(`ci-develop`, DB 없음)에서 `test_intake_dining_completion` 6건이 **2026-10-27 00:00 KST부터** 실패합니다. 10-26 시계에서는 통과, 10-27 시계에서는 실패로 재현했습니다.
   - develop·role-manager 공통: DB 관문(`ci-main`, main push·PR에서 실행)은 **이미 지금 깨져 있습니다.** 실행한 DB 시험 중 develop 163건(이 파일들은 532건), role-manager 165건(530건)이 `all_dates_in_past` 422로 실패합니다. 대본 날짜(2026-09-23 등)가 이미 지났기 때문입니다.
   - role-manager 빠른 관문에서는 날짜에 민감한 시험이 0건이었습니다.
3. patch는 3개이고, 모두 적용·해시 roundtrip을 확인했습니다. patch 적용 후 develop·role-manager 빠른 관문의 날짜 민감 시험은 0건, 위 DB 파일들의 가드 실패도 0건입니다.

## 건별 원인과 수정

| # | 대상 | 원인 분류 | 수정 |
|---|---|---|---|
| ① | v7a `test_plan_generation_response` 39건 | 시험이 새 계약을 모름. fixture가 2026-10-25로 고정돼 있어 전부-과거 가드가 실제 시계로 422를 냄 | `itinerary_checks.datetime`을 fixture 날짜 하루 전으로 고정했습니다. 이 방식은 기존 `test_all_past_confirm_api`의 시계 주입과 같습니다. 가드가 약해지지 않았는지 보는 paired 시험 2건(하루 뒤 시계면 422·생성 0)을 추가했고, 가드를 끄면 실패하는 것도 확인했습니다 |
| ② | v7a `test_read_requests::test_general_request_answer_is_preserved_beside_a_travel_read` | 시험이 새 계약을 모름. v7a `_schema(message=…)`는 맨 위가 `{"anyOf": [...]}`이고 permissive root가 없습니다. 이 형태는 `test_generation_is_action_first_without_permissive_root_object`가 계약으로 고정합니다 | 제품은 맞습니다. 시험만 "root `required` 없음 + 모든 분기에 `general_requests` 필수"를 확인하도록 고쳤습니다. develop·role-manager에는 이 schema 분기가 없어 해당 없습니다 |
| ③ | DB 필요 28건(conversation_resume 19·unknown_route 5·intake_screen 4) | DB 차단 하네스 때문에 setup ERROR | 하네스가 비교 DB만 가리키도록 바꿔 실제로 실행했습니다. **28/28 = 100%**. 23개 표의 내용 md5와 행 수가 실행 전후 같았습니다(당시 다른 접속 0) |
| ④ | develop·v7a `test_intake_dining_completion` 6건(감사 547 밖) | 고정 날짜 2026-10-26·27. 2026-10-27부터 실패 | 제품의 기존 주입점 `_review_of(..., now=NOW)`(→ `ensure(now=)` → `admission_dates(now=)`)을 썼습니다 |
| ⑤ | v7a `test_intake_survey_consumption::test_normal_ensure_cached_review_refreshes_survey_before_candidates`(v7a 전용) | 고정 날짜 2026-11-02. 2026-11-03부터 실패 | `current_review`에 `now`가 없어 `itinerary_checks.datetime`을 fixture 하루 전으로 고정했습니다 |
| ⑥ | 팀 DB 관문 e2e·통합(develop 163·role-manager 165, 지금 실패) 등 | 대본·접수 fixture 날짜가 고정돼 있음 | `tests/conftest.py`에 autouse `_pin_all_past_guard_today`를 넣었습니다. 가드의 오늘만 모든 고정 날짜(가장 이른 날 2026-08-17)보다 앞선 2026-08-01로 고정합니다. 가드 시험은 자기 시계를 다시 주입하므로 그대로 동작합니다 |

## patch (SHA256)

| 파일 | 대상 | 내용 |
|---|---|---|
| `patches/v7a-test-clock-fixtures.patch` `f53d0e548993b85daa85f1f4407496089bd87e147b415647364bf1bf98d422cc` | live v7a source | conftest pin, ①②④⑤. 5파일 +85/−11 |
| `patches/develop-allpast-guard-test-clock.patch` `1b95e7d43a4c50741752cb9f7c64e9e85eae8b636832511948713b16dd2cb9fb` | develop d2ab93a65 | conftest pin, ④. 2파일 +28/−3 |
| `patches/rm-allpast-guard-test-clock.patch` `ac8cf5ec0f84dfdbaeecb80767235d96fdb3739676821f6ac409bc7524c0844d` | role-manager 08b995976 | conftest pin. 1파일 +25 |

- 적용은 `git -c core.autocrlf=false apply`로 했고, 원 blob(LF)에 적용한 결과 해시가 시험한 파일과 같습니다.
- 결과 파일 해시: conftest `91594cc014a4…`, dining `1c7f26e58b8b…`, plan_generation `196859ef30bd…`, read_requests `5c903b400019…`, survey_consumption `10d5d43aea3b…`.

## 실행 결과

| 실행 | 결과 |
|---|---|
| RED: v7a 사본에서 547건(DB 차단) | 479 통과·40 실패·28 오류. 감사 결과와 같습니다 |
| GREEN: 수정 2파일만, 실제 시계·2030-01-01·2026-01-01 시계 | 각 73/73 |
| 최종: 547 manifest + paired 2건, 비교 DB | **549/549 = 100%**. 원래 547 nodeid 모두 포함, 추가분은 paired 2건 |
| develop 빠른 관문 patch 전, 실제 시계 vs 가드 시계 2027-12-31 | 같은 9,553건 중 날짜 때문에 바뀐 것 6건(dining). 10-26 통과, 10-27 실패 |
| develop 빠른 관문 patch 후, 두 시계 | 9370/9553. 날짜 때문에 바뀐 것 0건 |
| role-manager 빠른 관문 patch 전·후 | 9234/9417. 날짜 때문에 바뀐 것 0건 |
| v7a 빠른 관문 patch 후, 두 시계 | 9404/9628. 날짜 때문에 바뀐 것 0건(patch 전에는 survey 1건) |
| develop DB 관문 38파일, patch 전 → 후 | 346 → 506 통과, 23 skip. 가드 실패 163 → 0. 동시 실행 때 signup 3건 PK 충돌이 있었고 단독 재실행에서 11/11 통과 |
| role-manager DB 관문 37파일, patch 전 → 후 | 342 → 506 통과, 23 skip. 가드 실패 165 → 0. 부하 중 timing 시험 1건이 실패했고 단독 재실행에서 33/33 통과 |

- 빠른 관문의 9건(v7a는 36실패+9오류)은 날짜와 무관합니다. 두 시계에서 같은 시험이 실패했습니다.
  - archive에서 제외한 frontend·wiki evidence가 없어서 생긴 실패입니다.
  - .git이 없어서 생긴 실패입니다.
  - v7a 사본에는 eval·datasets·`.env.*.example`이 없습니다.
- v7a 전용으로 시계와 무관하게 실패한 6건(social_dining 3·service_help 1·meal_pick 2)은 이번 범위 밖이라 고치지 않았습니다.
- 가드 시계를 옮겨 보는 방식(freezegun 없음)
  - `FCLK_SHIFT_TO`는 `itinerary_checks.datetime`만 옮깁니다.
  - DB 관문은 `FCLK_RECORD` 기록 plugin으로 시험마다 가드 호출, 발동, 평가한 마지막 날짜를 남겼습니다.
  - 고정 날짜 fixture의 "미래 깨짐"은 마지막 날짜로 예측했습니다. develop `test_intake_stay_lines`는 2026-12-08에 1건, 2030-11-08/09에 7건이 깨질 예정이었고, patch 후에는 해당 없습니다.
  - 상대 날짜 fixture(`test_trip_reopen`, `test_trip_intake_api` 일부)는 실제 오늘을 따라가므로 깨짐 대상이 아닙니다.

## DB 쓰기 경계·남은 흔적

- 쓰기는 비교 DB `gugu_replay_improved_20261025` 하나에만 했습니다. 접속은 admin 계정으로 했습니다(app 계정에는 CONNECT 권한이 없음). 비밀은 출력하지 않았습니다.
  - 하네스는 그 DB의 127.0.0.1:5433만 허용했습니다.
  - xdist는 막았습니다. 사용하면 DB를 DROP/CREATE합니다.
  - 기본 tenant는 실행마다 새 `fclk_*`를 썼습니다.
- tenant별 행 수와 표 md5를 실행 전후로 비교했습니다. 다른 작업자(acceptance_matrix_*, attachv_*, c9reval_*)가 동시에 쓰고 있어 그 변화는 제외하고 판정했습니다.
- **예외 1:** 팀 DB 파일 `tests/integration/test_watch_simulation.py`가 fixture에서 migration 227을 실행했습니다. 그 결과 `ALTER TABLE pending_changes DROP/ADD CONSTRAINT pending_changes_scope_check`가 커밋됐습니다.
  - 정의는 baseline·acop_cs와 같습니다. pg_constraint xmin만 바뀌었습니다.
  - 그 시험의 tenant `simulation_test_eac9a348…`는 정리했습니다. 다만 tenants 1행과 `admin_audit` 1행이 남았습니다. admin_audit는 append-only라 우회하지 않았습니다.
  - 이후에는 DDL을 실행하는 파일 2개(watch_simulation·watch_monitoring)를 DB 실행에서 뺐습니다. watch_monitoring의 228 migration은 `IF NOT EXISTS`이고 기존 표 xmin이 그대로였습니다.
- **예외 2:** 첫 DB 일괄 실행을 중간에 끊었을 때 `trip_api_89a4c1c2260f`가 남았습니다. 이 tenant는 사전 snapshot에 없던 내 tenant로 확인한 뒤 삭제했습니다.
- 알림: outbox에 시험 tenant 행이 생겼다가 각 fixture나 정리 과정에서 지워졌습니다. 비교 DB에 붙은 outbox 일꾼은 없었습니다.

## 한계·되돌릴 수 있는 기본값

- conftest의 전역 고정(2026-08-01)은 시험 쪽 결정입니다. "실제 시계로 가드가 발동하길 기대하는 시험"이 생기면 그 시험이 자기 시계를 다시 넣어야 합니다. 현재는 그런 시험이 0건입니다(검색 결과 `all_dates_in_past` 단언은 시계 주입 unit 2파일뿐). 파일별 주입으로 되돌릴 수 있습니다.
- DB 관문은 CI 전체가 아니라 화면 검사 기준 38/37파일만 실행했습니다. 다음 파일은 비교 DB의 기존 행이나 전역 표를 건드릴 수 있어 실행하지 않았습니다(정적 검사만 함).
  - dining 원장 전역 표: `test_trip_dining_ledger`, `test_place_info`, `test_guest_and_trip_delete`
  - 전역 표 수정: `test_safety_pause`(safety_shelters), `test_web_api`(external_call_budget), `test_activity_catalog_pool`(place_catalog 미한정 UPDATE)
  - 운영 설정 표: `test_watch_failures`·`test_watch_relaxed`(guardrails), `test_simulation_guest_catalogue`(admin_records)
  - DDL 실행: `test_watch_simulation`·`test_watch_monitoring`

  이 파일들은 CI처럼 빈 DB에서 확인해야 합니다.
- 팀 CI 트리거: `ci-develop`은 develop push·PR, `ci-main`은 main push·PR에서 돕니다. role-manager push에는 이 workflow들이 돌지 않습니다.
- push·x600·로컬 서빙: 셋 다 반영하지 않았습니다(patch만 만듦).
