---
type: report
title: 고객 응대 라이팅(writer) 설계 대비 구현·연결·검증 감사 (로컬 live v7a, 읽기 전용)
status: verified
domain: travel
---

# 고객 응대 라이팅(writer) — 설계 대비 감사

- 작성: 2026-10-26 01:25 KST · 감사자: Hermes subagent(Opus) · 범위: **라이팅 = 답변 작성·저장·전달·상태**. 라우팅 판정(어느 경로·팀으로 보내나)은 [라우팅 감사](2026-10-26_customer-response-routing-audit.md)가 맡았으므로 다시 판정하지 않았습니다.
- 대상: live API 8042(PID 10756, `action-v7a-allpast-20261025-233317-fac130f7/runtime-v7a-serving/launch-serving.py`), 웹 3100(PID 26720, `web-v5-release-20261025-170512-b1431a/localhost`), source `source-v7a/final_project_cs`.
- 지킨 것: 코드 수정 0 · 서버 kill/재시작 0 · DB 쓰기 0(`SET TRANSACTION READ ONLY` 후 rollback, 집계·키 이름만 출력) · **제품 E4B 호출 0**(lease 안 받음, counters admitted 5 = completed 5 그대로) · 유료·알림·push 0 · 비밀·고객 원문 출력 0. live GET은 부작용 없는 `/openapi.json` 1회뿐입니다(`/v1/web/support/notices`는 GET 안에서 `sync_board` 쓰기를 해서 부르지 않았습니다).

## 결론

**아니요. 설계한 「진짜 여행 비서」 응대는 아직 다 구현·동작하지 않습니다.** 공통 writer(질문별 종결·완료/부분 구분·공개 enum allowlist)와 계획서 등록 응대는 코드·live 연결·단위 시험이 맞습니다. 그런데 비서가 **먼저 알려 주는 쪽**이 live에서 멈춰 있습니다.

- 최근 7일 `trip.notice` 6건이 모두 pending이고, 마지막 배달은 2026-09-30입니다.
- 정기 안내(②③)는 2026-10-07 이후 생성 0건입니다.
- writer 메타를 단 알림은 전체 0/182입니다.

채팅의 **변경 실행 결과**와 **해결 못 한 일에 대한 문의 경로 안내**도 writer에 연결되지 않았습니다.

설계 항목 판정: **완료 5/18 = 27.8%**, 부분 12/18 = 66.7%, 설계와 다름 1/18 = 5.6%.

## 정본(읽은 문서)

- 루트 `AGENTS.md` 27~33행(바뀐 값: D-018·D-020), 44행(언어), 53~56행(알림 세 시점·접점), 62행(Composer 소재)
- `wiki/delivery/travel-response-current.md` 78~102행(결론·경로별 상태)
- `wiki/records/reports/2026-10-24_travel-writing-review.md` 14행(Composer≠writer), 39~43행(개선안), 53~58행(수용 기준 6)
- `final_project_cs/wiki/external/travel-response.md` 14~49행, `travel-monitoring-response.md` 12~31행, `plan-response.md` 10~22행, `web-response-status.md` 14~25행, `trip-chat-context.md` 22~27·46~60행, `plan-reading-restoration.md` 20~44행
- `wiki/decisions/D-020` 12~23행, D-024(v7a source `wiki/decisions/D-024-inquiry-reply-path.md` 16~20행), D-025(같은 위치, 76~90·104~106행)
- `wiki/architecture/notifications.md` 27~32·36~44·54~65·114~151·192~216행
- 인계: `wiki/handoff/2026-10-24_travel-writing-implementation.md`, `2026-10-25_v7-api-parent-live.md`, `2026-10-25_final-serving-i06-8b1e6c3b.md`

## 항목별 판정표

| # | 항목 | 정본 줄 | 코드(v7a) | live 반영 | 후보에만 | 실모델 검증 | 판정 |
|---|---|---|---|---|---|---|---|
| W1 | 공통 응대 입력·결과(질문별 종결, all answered일 때만 complete) | travel-response 18~33 | `response/writing.py:9-74` | 예. `read_requests.py:8,80,300` | — | v6 full49 P01/P02 pass. v10 동일 반례 2/2 | **완료** |
| W2 | 질문 완결: 누락·중복 거부, unresolved인데 answered 금지 | review 53, travel-response 23·43 | `writing.py:51-59`, `read_requests.py:89-93` | 예 | — | v6 P03 fail(grounding). C01/C02/C04/C05/C07 not_run | 부분 |
| W3 | 조회 책임: 출처·확인시각, 다른 장소로 답하지 않음 | review 54, trip-chat-context 25·48 | `read_requests.py`, `fact_context.py` | 예. 단 F02 수정은 없음(`origin_quote` 0회) | f02-origin(`read_requests.reply`), chat-subject(`fact_context`/`read_requests`) | v6 F02 fail. f02 후보 실E4B 2/2(후보 소스 기준) | 부분 |
| W4 | 실행 확인: 계획 등록은 저장 재조회 후에만 registered | plan-response 13·20~21, review 55 | `response/plan.py:66-101`. `trip_api.py:1094,2028,2263` | 예 | — | v6 I02~I05·I08 pass(GET 재조회·미등록 안내) | 부분(`test_plan_generation_response` 39/42가 고정 날짜 2026-10-25 fixture 때문에 all-past 422로 실패해 지금 재현 불가) |
| W5 | 채팅 변경 실행 결과 응대(전후·판·이유·되돌리기 + 상태) | travel-response 16·25, review 55 | `case_dispatch.py:24-57`(applied_actions 재조회), `trip_replies.outcome_reply`. **writer 미연결**(`trip_messages.py:1073-1077`은 basis.response가 있을 때만 status를 냄) | 예. live DB: v7a 교체 뒤 change_time 1건, chat_reply는 있으나 response_status 없음 | chat-outdoor(조건 전달) | 없음 | 부분 |
| W6 | 감시 결과 응대 applied/awaiting_choice/failed/unknown | travel-monitoring-response 13~27 | `response/monitoring.py:11-125`. 호출 `itinerary_actions.py:338,358,515`, `pending.py:203`, `watch_relaxed.py:192`, `trip_watch_cases.py:438` | 코드만. 로컬에 sweeper/outbox worker 없음 | — | 없음 | 부분 |
| W7 | 상태 불변: workflow·resume_token 보존, 작성 실패해도 업무 재실행 없음 | review 56, travel-monitoring 26 | `writing.py:69-74` deepcopy, `monitoring.py:75-77` writing_status=failed | 예 | — | 해당 없음(결정론) | **완료**(단위) |
| W8 | 고객 공개 투영 allowlist(enum만, scope/request/token 제외) | travel-response 37~41, plan-response 15, web-response-status 14~16 | `response/public.py`, `chat_log.py:33-39`, `trip_api.py:2646,2962`, `plan.py:31-35` | 예. 웹 3100 번들에 `question_status`·`stale_registration_session` 있음. DB 10-25 chat_reply status 1건 | — | v6 P01/P02 pass | **완료** |
| W9 | ① 변경 통지(생성 포함) + 링크 + writer 메타 | notifications 27·31·44, travel-monitoring 25 | Case `_version_notice`(`itinerary_actions.py:344-366`)만 writer 연결. 생성 `trip_api.py:1075`, `trip_desk.py:538`, `journey_progress.py:330`, `requested_destination.py:47`, `reopen_commit.py:180`은 meta 없음 | 생성 알림은 쌓임. 최근 7일 6/6 pending(키는 생성형 `text/causes/changed/other_options/replay`), writer 메타 0/182, 마지막 delivered 09-30 | — | 없음 | 부분 |
| W10 | ②③ 정기 안내: 문구틀+원값, 언어마다 LLM 1회, 대기 항목에는 출발 안내 안 함 | notifications 29·32·54~65·192~199, review 57 | `trip_reminders.py:161-278,451-505`, `notify/phrase.py`, `notify/translate.py` | 코드만. guidance 전체 8건(전부 skipped, 마지막 10-07) | — | 없음 | 부분 |
| W11 | ③ 출발 시각에 경로 조회, 실패하면 미발송 | notifications 30·135~151 | `build_departure`(`trip_reminders.py:508-`) fatal/held/unchecked | 코드만 | — | 없음 | 부분 |
| W12 | D-020: 켜짐=적용 후 통지, 꺼짐·미응답=먼저 묻기, 지킴이 켜기 제안 | D-020 14~23 | `planning/guardian.py:31-133`, `action_notice(status="awaiting_choice")` | 코드만. 감시 미기동. **하루 시작 문구가 상태와 상관없이 「먼저 조정하고 알려드릴게요」**(`trip_reminders.py:176`) | — | 없음 | 부분(모순 1) |
| W13 | 후속 연결: 「왜 바꿨어?」 → 저장된 변경 설명 | review 58, travel-monitoring 31 | `decision_unit.py:47,191,733,770,1096`, `change_read.py`, `read_requests.py:89-93` | 예 | — | 없음 | 부분 |
| W14 | D-024 문의함: 웹 저장 → 관리자 답변 → 웹 「운영팀 답변」 | D-024 16~20 | `admin_customer_api.py:27-101`, 조립 `composition.py:1039,1110`, 답변 `admin_service.py:224` | 고객 API 마운트 확인(live openapi에 `/v1/web/support/inquiries`). 관리자 앱 미기동. DB 문의 0건 | — | 해당 없음 | 부분 |
| W15 | D-024: 채팅이 해결 못 하면 이유 + 문의 경로 안내 | D-024 18 | `trip_replies.py:143-150`, `case_dispatch.py:53-55`에 문의 안내 없음. 문의 접수 응답(`admin_customer_api.py:100`)은 다시 「여행 화면에서 다시 요청」을 안내 → 순환 | 예(현행 문구) | — | — | **설계와 다름** |
| W16 | Composer는 고객 writer가 아님, 옛 response_review 비활성 | review 14·30 | `config/project.yaml:110-112` enabled=false. response 모듈에 Composer import 0 | 예 | — | — | **완료**(문서 모순 1) |
| W17 | 고객 언어: 알림은 보낼 때 고객 언어로, 값은 원값 그대로 | AGENTS 44, notifications 192~216 | `translate.py`(숫자·통화 검사), `phrase.py`. 채팅·응대 writer에는 locale 처리 없음 | 알림 locale zh-TW 58/182 쌓임, 배달 멈춤 | — | 없음 | 부분 |
| W18 | 계획서 접수 상태 응대 reading/review_required/confirmation_recorded/registered/failed | plan-response 12~15 | `plan.py:46-56`, `pipeline.py:615`, `trip_api.py:2249` | 예 | i06(locked 판정, 읽기 쪽) | v6 I02~I05·I08 pass. I06/I07 fail(읽기 의미 문제, writer 아님) | **완료** |

집계: 완료 5/18 = 27.8%(W1·W7·W8·W16·W18), 부분 12/18 = 66.7%, 설계와 다름 1/18 = 5.6%(W15).

## 시험(직접 실행, 네트워크·DB 차단)

- 하네스는 `run_isolated_writer.py`입니다. allpast `run_isolated.py` 방식에서 환경변수 이름만 `WRAUDIT_SOURCE_ROOT`로 바꿨습니다. venv `date_risk_env_312`, `-p pytest_asyncio.plugin`을 썼습니다. 출력 root는 `...\action-v7a-allpast-20261025-233317-fac130f7\source-v7a\final_project_cs`(로그 첫 줄)입니다.
- 결과: 16파일 **245/295 = 83.05%**, 실패 40, ERROR 10, skip 0.
  - 실패 39건은 `test_plan_generation_response`의 고정 날짜(2026-10-25) fixture가 v7a all-past 가드에 걸린 것입니다. 시험 자료가 만료된 경우이고 writer 결함은 아닙니다. 다만 W4 단위 증거를 지금은 다시 얻을 수 없습니다.
  - 실패 1건 `test_admin_json_gateway::test_customer_support_router_has_no_operator_credentials`와 ERROR 10건 `scenario/test_trip_reminders`는 DB 차단 때문입니다.
  - DB 필요분 11건을 빼면 245/284 = 86.27%입니다. 날짜 fixture 39건까지 빼면 245/245입니다. 그래도 전체 GREEN이라고 쓰지 않습니다.
- 파일별 통과: monitoring_adapter 33, consumer 26, slice1 8, plan_response_adapter 9, change_explanation 34, phrase_cache 15, translation 29, guardian_switch 19, trial_live 15, departure 계열 29, deploy_customer_notice 12.
- 증거: `writer-tests.{log,xml}`.

## live 집계(acop_cs, 읽기 전용)

- chat_reply: 10-25에 5 Case 중 reply 3, 그중 response_status 1(`complete`/`answered`). 10-26에는 1 Case(change_time resolved)의 reply에 status가 없습니다.
- `trip.notice`: 전체 182건, writer 메타(`response`/`response_status`/`writing_status`) 0건. 최근 7일 6건 모두 pending(attempts 0). 마지막 delivered 2026-09-30. guidance 8건 모두 skipped, 마지막 10-07. locale은 ko 124, zh-TW 58.
- 문의(admin_records kind=inquiry) 0건. 항로 지킴이(survey.on_disruption)는 replace(답함) 52, replace(미답) 11, ask_first 5, 없음 76.
- 스크립트: `db_writer_readonly{,2,3}.py`, 결과: `db-writer{,2,3}.json`.

## 후보 6개 — live 미반영 확인(`git apply --check`, 대표 토큰 grep)

| 후보 | writer와의 관계 | live v7a |
|---|---|---|
| f02-origin | W3: 원문 인용 장소 검증 후 다른 장소 답변 대신 확인 질문(needs_input/partial) | 미반영(`origin_quote` 0회) |
| chat-subject | W3: 고른 일정 대상 연결(`fact_context`/`read_requests`) | 미반영(정방향 check 통과, `source=selection` 없음) |
| chat-outdoor | W5: 조건(야외) 전달. 응대 결과 정확도 | 미반영 |
| comment9-v8 | 방문 제한시간 안내(hours/activity) — writer 밖 | 미반영 |
| i06-booked-only | W18 입력 정확도(예약≠고정) — 읽기 쪽 | 미반영(`locked_booking` 0회) |
| fix8 | i06 후보의 시험·자료만 고침(제품 0) | 해당 없음 |

## 문서 간 모순

1. **Composer 역할.** 루트 `AGENTS.md` 62행은 「Composer 소재: 승계. 소재를 한국어 통지 문구로 교체」, `travel-writing-review.md` 14행은 「Composer는 설정·모듈 조립 도구이며 고객 응대 작성기가 아닙니다」입니다. 코드는 뒤쪽(response_review off, writer는 travel_ops/response)입니다.
2. **하루 시작 안내 문구와 D-020.** `trip_reminders.py:176`은 늘 「먼저 조정하고 알려드릴게요」라고 보냅니다. D-020 14~18행에서는 꺼짐·미응답이면 먼저 묻습니다(live trip 5건이 ask_first). `notifications.md`에도 옛 「최고 안을 먼저 적용」 서술이 남아 있습니다(review 21행이 이미 지적).
3. **알림 번호.** `notifications.md` 29행은 「① 하루 시작 · ② 각 일정 시작 · ③ 이동」, 36~42행은 「① 변경 · ② 여행·하루 시작 · ③ 항목 출발」입니다. 코드 docstring(`trip_reminders.py:163` 「① 하루 시작」)은 29행 쪽을 씁니다.
4. **현재 상태 문서가 낡음.** `travel-response-current.md` 78~83행은 「최신 = V10, proc_194b6e03a438/PID27500」이라고 합니다. 실제 live는 v7a(PID 10756, 인계 `2026-10-25_v7-api-parent-live.md` 이후 v7a 교체)입니다.
5. **reader 설정.** `plan-reading-restoration.md` 21행은 「config에 `travel.intake_reader` 없음」입니다. D-025 132행과 live guardrail에는 `intake_reader.mode:on`이 있습니다(라우팅 감사 1번).
6. **D-024 순환.** D-024 18행은 「채팅에서 못 한 일 → 문의 경로 안내」입니다. 실제로는 채팅이 문의를 안내하지 않고, 문의 접수 응답(`admin_customer_api.py:100`)은 「여행 화면에서 다시 요청」으로 되돌려 보냅니다.
7. **알림 실패 정책.** 루트 `AGENTS.md` 53행 「대체까지 안 되면 서버를 끈다」와 D-018(27~29행 바뀐 값: 해당 작업만 보류)이 다릅니다. AGENTS가 스스로 「바뀐 값」 표로 정정했지만, 53행 본문은 그대로입니다.

## 「진짜 여행 비서」 기준 빠진 기능·개선안(우선순위)

### P0 — 비서가 먼저 말하지 못함
1. **알림 배달·감시·정기 안내가 로컬 live에서 돌지 않습니다.** outbox worker와 sweepers가 없어서 ① 생성 알림 6건이 pending이고, ②③은 0건입니다. 기동 여부와 잔류 pending 처리 방침을 사용자 승인으로 정해야 합니다(라우팅 감사 P1-1과 같은 원인, writer 쪽에서 본 결과).
2. **W15 문의 경로 안내.** 해석 실패, escalated, 미지원 답에 「문의함에 남겨 주세요 + 경로」를 넣어야 합니다. 문의 접수 응답이 여행 화면으로 되돌려 보내는 순환도 고쳐야 합니다. 관리자 답변 앱(3300/8070)도 꺼져 있어서 「운영팀 답변」이 돌아오지 않습니다.

### P1 — 답의 정확도·일관성
3. f02-origin과 chat-subject 후보를 실E4B 재검증한 뒤 반영해야 합니다. 둘 다 W3 「다른 장소로 답함」, 「고른 일정을 되물음」에 직결됩니다.
4. **W5 채팅 변경 결과를 공통 writer로 보내야 합니다.** 저장 재조회 판, 전후, 이유, 되돌리기, 다음 행동을 한 답에 담고 response_status를 붙입니다. 지금은 template 문구이고 상태 enum이 없습니다.
5. **W12 문구를 항로 지킴이 상태별로 나눠야 합니다.** 켜짐이면 「먼저 조정 후 알림」, 꺼짐이면 「바꾸기 전에 먼저 여쭤볼게요」입니다.
6. **W9 writer 메타를 넓혀야 합니다.** 생성(①), trip_desk, journey_progress, requested_destination, reopen 알림에도 같은 메타를 달아 웹 알림 상태 표시를 일관되게 합니다.

### P2 — 비서다운 문장·범위
7. writer가 지금은 「질문별 문장 이어 붙이기」(결정론)입니다. LLM을 부르지 않고 template만으로 「확인한 것(출처·확인시각) / 바꾼 것 / 고객이 할 일 / 아직 모르는 것」 네 칸 구조를 만드는 것을 제안합니다. 확인시각은 basis에만 있고 고객 문장에 보이지 않습니다.
8. 채팅·응대 문구에는 다국어가 없습니다. zh-TW 여행이 있지만 알림만 번역됩니다.
9. 알림을 누른 뒤 채팅에서 「왜 바꿨어?」가 자동으로 그 변경을 가리키는지(W13)는 실모델·화면으로 확인하지 않았습니다.
10. 고객 선호 장부(D-025 §7)는 자리만 있습니다. 동의·삭제 계약을 먼저 정해야 합니다.

### 시험·증거
11. `test_plan_generation_response` fixture를 상대 날짜로 바꿔야 합니다. 그러면 W4 단위 증거가 다시 살아납니다. `scenario/test_trip_reminders` 10건은 격리 DB로 실행해야 합니다(승인 필요).
12. 실모델 ledger의 최신본은 v6 source 기준입니다(full49: pass 12, fail 9, not_run 26, mismatch 2). v7a 기준으로 not_run 26행 중 응대 행(C01/C02/C04/C05/C07, T01~T11)을 최소 배치로 다시 측정해야 합니다. 이번에는 E4B를 호출하지 않았습니다.

## 한계

- 실제 고객 화면, 실모델 응대 품질, 실제 알림 배달은 보지 않았습니다.
- 관리자 앱이 꺼져 있어 문의 답변의 실제 왕복을 확인하지 못했습니다.
- 「실모델 검증」 열은 과거 실측 ledger(v6 full49, v10 2/2, f02 후보)를 인용한 것입니다. live v7a에서 새로 측정한 값이 아닙니다. 과거 배치끼리는 합산하지 않았습니다.

## 원본 증거 위치

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/writer-audit-20261026-011526-23135/`: REPORT_KO.md, run_isolated_writer.py, writer-tests.{log,xml}, db_writer_readonly{,2,3}.py, db-writer{,2,3}.json, live-openapi.json.
