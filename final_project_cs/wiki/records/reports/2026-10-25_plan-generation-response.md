---
type: report
title: 별도 plan 생성·등록 정상입구 응대 연결 검증
status: verified-local
domain: travel
---

# 별도 plan 생성·등록 응대 — 2026-10-25 00:07 KST

## 결론

`/v1/trips/plan`과 `/v1/web/trip-intakes/{intake_id}/plan` 정상 handler에 선택 `response`를 연결했습니다. 생성 초안은 `plan_generated`/`needs_input`/`partial`, 실제 저장과 소유권·판 재조회 확인 뒤에만 `registered`/`answered`/`complete`입니다. 접수가 없는 입구에 가짜 intake를 만들지 않습니다.

| 검증 | 결과 |
|---|---:|
| 직전 318건 manifest 회귀 | 318/318 = 100% |
| 신규 생성·등록 경계 시험 | 42/42 = 100% |
| 결합 트리 단일 실행(고유 nodeid) | 360/360 = 100% |
| 수정 전 handler와 기존 payload 비교(초안·API 등록/재생·웹 등록/재생 묶음) | 3/3 = 100% |
| 실행 중 대상 source/test 해시 변화 | 0건 |

이 비율은 격리 unit 시험의 통과율이며 제품 전체·실모델·운영 완료율이 아닙니다.

## 변경

- 먼저 [plan-response 계약](../../external/plan-response.md)에 별도 생성·등록 입구와 읽기 검증 경계를 추가했습니다.
- `trip_api.py`는 시작 백업 AST와 비교하여 `plan_draft`, `web_intake_plan` 두 함수만 달라졌습니다. 기존 `/api` 접수·confirm·`_web_view`·message·notices 및 `_create_trip`은 건드리지 않았습니다.
- `response/plan.py`에 `plan_generated` 문구, `generated_payload`, `registered_plan_payload`, `verify_plan_registration`을 최소 추가했습니다. 검증 함수는 실제 handler에서 호출되며 I/O·모델·저장·재시도를 수행하지 않습니다. 기존 공통 `writing.py`·`public.py`는 수정하지 않았습니다.
- API 등록은 실제 `_create_trip` 후 별도 connection으로 소유권과 여행을 재조회합니다. 원래 생성 결과와 재조회 결과의 고객·여행 id·양의 정수 판이 일치해야 성공 문구를 작성합니다. 원래 결과의 bool 판도 거절합니다.
- 웹 plan은 여행 생성 후 재조회, 접수 mark 후 scoped 링크와 여행 재조회를 따로 검증합니다. 기존 고정 일정 병합·설문·원래 `planner`와 trip 필드를 유지합니다. 중복 요청도 scoped 재조회한 결과만 재사용합니다.
- 신규 시험: `tests/unit/travel/test_plan_generation_response.py`. 정상 중첩 endpoint와 실제 `_create_trip`/`mark_confirmed`를 실행하고 저장소·모델 경계만 메모리 대역으로 사용했습니다.

## 확인한 경계

- 초안 생성은 저장·등록 완료가 아님; 접수 없는 API는 intake SQL 0회.
- 정상 등록·중복 재생에서 모델/생성 1회, 웹 mark 1회. 작성 실패 후 재생도 업무 횟수가 늘지 않음.
- 저장 실패·생성 후 조회 실패·mark 실패·연결 후 여행 조회 실패·링크 없음/상태/판/id 불일치에서 완료 응답 없음.
- 남의 여행을 가리키는 중복 결과는 404; 남의 접수는 생성 전 404; API `trip:write` dependency는 read-only scope에 403.
- 생성 결과 또는 재조회 결과의 고객/id/판 불일치·잘못된 판 타입 차단.
- 고정 일정 detail과 설문 ask_first/relaxed 보존. 새 response는 answer/completion/question_status/execution_status만 허용.
- 실제 `op_stream.run`과 `StreamingResponse.body_iterator`를 소비한 JSON/SSE result 비교(최초·중복) 통과. 앱이나 HTTP 서버를 기동하지 않았습니다.

## TDD·실행 증거

[증거 폴더](../evidence/2026-10-24_plan-generation-response/)의 최종 정본:

- [combined-final.log](../evidence/2026-10-24_plan-generation-response/combined-final.log): **360 passed in 8.35s**, exit 0.
- [verification-final.json](../evidence/2026-10-24_plan-generation-response/verification-final.json): 정확한 명령·파일 manifest·고유 nodeid·기존/신규 분모·전후 해시·변경 함수 목록.
- [compatibility.log](../evidence/2026-10-24_plan-generation-response/compatibility.log): 수정 전 API 백업과 같은 입력 비교, `response`만 제외한 모든 기존 payload 동일.
- red1b → green1(초안), red2 → green2(API 등록), red3 → green3(웹 등록), red4 → green4(작성 경계), red5/red6 → 최종 결합 실행(생성 결과 고객/판 불일치). 초기 red1은 dining planner factory 시험 대역 누락이며 기능 RED로 세지 않았습니다. 이후 fixture를 수정하고 red1b의 `response` 누락을 실제 RED로 확인했습니다.
- boundaries/boundaries2는 추가 경계 특성화 실행입니다. 초기 356건 결합 실행은 combined.log/verification.json에 별도 보존했으며 최종 360건으로 덮지 않았습니다.

실행기는 기존 `travel-writing-s1-venv/Scripts/python.exe`(Python 3.12.15), runner는 활성 프로필 scratch `plan-generation-response/run.py`입니다. pytest는 `--confcutdir=tests/unit/travel -o addopts= -p no:cacheprovider -v`로 루트 DB fixture를 제외했습니다. socket connect/connect_ex/create_connection/bind·psycopg 연결을 차단했습니다. Windows asyncio의 정확한 stdlib `_fallback_socketpair` code object에서 호출하는 loopback self-pipe만 허용하고, 애플리케이션 loopback connect/bind 차단과 실제 socketpair 생성을 실행 전에 검증했습니다. `standalone_services()`만 사용하고 앱 조립·기동은 하지 않았습니다.

수정 전 원본 백업: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/plan-generation-response/{trip_api.py,plan.py,plan-response.md}`. 재현 runner·검증 스크립트·비교 스크립트 사본도 증거 폴더에 보존했습니다(비교 스크립트는 이 원본 백업이 필요합니다).

## 남은 한계

실DB 트랜잭션·실모델·외부 HTTP·실인증 HTTP·브라우저 UI·운영 서비스·배포는 검증하지 않았습니다. 커밋·푸시·DB 변경·앱/서비스 기동을 하지 않았습니다. 저장 성공 뒤 mark 자체가 실패한 orphan의 자동 복구는 구현하지 않았으며 중복 재생도 링크 검증 없이 완료하지 않습니다. 이 경우 새 업무를 재실행하거나 실패를 성공으로 감추지 않습니다. 정확한 판 일치 정책상 조회 사이 새 판이 생기면 완료를 보류합니다. 동시 요청 DB 직렬화는 기존 `_create_trip` 계약을 유지했으며 실제 DB 경쟁 시험은 하지 않았습니다.

root wiki/index/handoff와 전체 병렬 작업 결합 최종 수락은 부모 담당입니다. 이 절 범위의 추가 사용자 결정은 없습니다.
