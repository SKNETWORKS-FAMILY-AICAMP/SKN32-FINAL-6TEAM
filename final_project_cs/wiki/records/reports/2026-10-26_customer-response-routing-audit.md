---
type: report
title: 고객응대 라우팅 에이전트 설계 대비 구현·연결·live 감사 (로컬 v7a)
status: verified
domain: travel
---

# 고객응대 라우팅 에이전트 — 설계 대비 감사 (로컬 live v7a, 읽기 전용)

- 작성: 2026-10-26 01:10 KST · 감사자: Hermes subagent(Opus) · 범위 정정: 사용자 지시로 「고객응대 라우팅」(계획서 접수·문의·등록 후 채팅·감시 전달 → 처리 경로 선택) 기준. Case/TeamRegistry 라우팅은 연결 범위만.
- 대상: live API 8042(PID 10756, `runtime-v7a-serving/launch-serving.py`), source `action-v7a-allpast-20261025-233317-fac130f7/source-v7a/final_project_cs`.
- 금지 준수: 코드 수정 0, 서버 kill/재시작 0, DB 쓰기 0(모든 조회 `SET TRANSACTION READ ONLY` + rollback), 제품 E4B 추론 0, push 0, 비밀·고객 원문 출력 0(집계·enum만).

## 결론

**아니요 — 설계대로 「다 구현·동작」 상태가 아닙니다.** 채팅 해석(decision_unit)→처리 경로 분기, 분류 실패 처리, Registry/Controller 관문은 코드·시험·live 기록이 맞습니다. 그러나 ① 로컬 live에는 API 하나만 떠 있어 감시 루프·알림 배달·멈춘 Case 되잡기가 동작하지 않고, ② 계획서 접수 읽기가 최근 7일 5/20 = 25% fatal(그중 DB 905 미준비 2건)이며, ③ D-024 「미해결 시 문의 경로 안내」와 D-017 「질의에 대한 다중 팀 계획」이 채팅 경로에 없습니다.

설계 항목 판정 **완료 6/17 = 35.3%**, 부분 8/17, 설계와 다름 2/17, 증거 없음 1/17.

## 정본(읽은 문서)

- 루트 `AGENTS.md` 47~50행(분류 라벨·라우팅 두 축·DoD-23), 27~33행(바뀐 값: D-018·D-020)
- `wiki/delivery/travel-response-current.md`(경로별 상태 95~100행)
- `final_project_cs/wiki/external/travel-response.md`(ResponseInput/Result 14~31행), `external/trip-chat-context.md`(22~27·46~60행), `external/rest-endpoints/web-intakes.md` 209·213행(채팅 해석 → case_dispatch → Controller.run_case, `answer_fact`·`ask_policy`·`other` 별도 경로, 503 team_unavailable)
- D-024(문의함 경로, develop latest `wiki/decisions/D-024-inquiry-reply-path.md` 16~19행), D-025(계획 읽기, 42~70·120~132행), D-020(현재 변경 규칙 표 12~21행), D-017(18·25~27·44행), D-CS-014(56~62·80~92행), `teams/team-registry.md`(17~32행), `runtime/agentic-controller.md`, `teams/team-plugin-lifecycle.md` 227행, v11 §5-A/§5-B(456~575행)·§12 DoD-23(1608행) — v11은 당시 기록으로 후속 wiki 결정 우선.

## 항목별 판정표

| # | 항목 | 정본 | 코드(v7a) | 실제 연결 | 시험(직접 실행) | live 증거(acop_cs 집계) | 판정 |
|---|---|---|---|---|---|---|---|
| 1 | 계획서 접수 분기: 빠른 거름 → 이해 에이전트 1회 → 사실검사 → 빈칸 담당 연결표 | D-025 §1~4, 53행 | `intake/pipeline.py:108-118`(screen), `agent_read.py`, `fact_check.py`, `gaps.py`(ROUTES), `prefill.py` | `trip_api.py:1414` open_intake/process; live guardrail `intake_reader.mode:"on"`(local-guardrails 332~337) | agent_read 12/12 통과(union), `test_intake_screen` 4 ERROR(DB 차단) | intakes 83건, 7일: confirmed 5·review 9·fatal 5·closed 1 → **fatal 5/20 = 25%**(schema_not_ready 2·model_failed 2·reading_failed 1). screened 기록 0/83 | 부분 |
| 2 | 문의함 접수·운영자 답변 경로 | D-024 16~20행 | `web_account/admin_customer_api.py:28` `/v1/web/support` | 코드상 router 존재; live 마운트는 미확인(라우트 목록 조회 승인 미응답으로 중단) | 이번에 미실행 | 문의 전용 표 이름 미발견(public 표 21개 중) — 저장 위치 미확인 | 증거 없음 |
| 3 | 채팅에서 해결 못 한 일 → 이유 + 문의 경로 안내, 상담원 연결 없음 | D-024 18행, D-CS-014 62행 | 상담원 대기 없음 ✓(`_shared/_base.py:138`, `trip_messages.py:10`). 안내 문구에 문의 경로 없음: `trip_replies.py:28-29,143-150`, `trip_messages.py:780`, `case_dispatch.py:53-55` | 모든 escalated 답이 이 문구 | — | 10-20 이후 채팅 6건 중 해석 실패 2건이 이 문구로 종료 | 설계와 다름 |
| 4 | 등록 후 채팅 해석 입구(decision_unit, 실패 시 규칙 경로로 안 넘김) | web-intakes 209·213, trip-chat-context | `trip_messages.py:394-418`, `decision_unit.py:26-32`, 실패 `trip_messages.py:774-781` | `chat.decision_mode` 기본 `travel.decision_unit.mode:"on"`(local 361행) | decision_* 단위 다수 통과(target_guard 23·unsupported 25·failure_privacy 3) | ROUTED `routed_by=decision_unit` 59건; 10-20 이후 6건: resolved 4(answer_fact 2·change_time 2), 해석 실패 2 | 완료 |
| 5 | 사실 질문 → read_requests/fact_context → 공통 writer | travel-response.md 14~31행 | `trip_messages.py:877-937`, `read_requests.py:301`(`source="inquiry"`), `response/writing.py` | `_run_decision` → `read_requests.reply` | slice1 8·consumer 26·fact_context 통과, **`test_read_requests::test_general_request_answer_is_preserved_beside_a_travel_read` 실패**(v7a schema가 `anyOf` 분기로 바뀌어 시험의 `schema["required"]` 가정과 불일치) | answer_fact 누적 27건, v7a 교체 뒤 1건 resolved | 부분 |
| 6 | 일정 수정 → case_dispatch → Controller.run_case → 담당 팀(503 team_unavailable) | web-intakes 209행, lifecycle 227행 | `trip_messages.py:851-857,1122-1195`, `case_dispatch.py:83-105`; 담당 = 항목 종류, **대상 없으면 `activity` 기본**(`trip_messages.py:1174-1181`) | API가 ROUTED(owner 직접) 후 run_case | edit_intent 51·owner_team_routing 통과, `test_conversation_resume` 19 ERROR(DB 차단) | apply_change 21·rollback 10·propose 4·change_time 2(누적) | 부분 |
| 7 | 되묻기·거절(대상 근거 없음 → clarify, 미지원 → 안내, 일정 불변) | trip-chat-context 25·56행, D-CS-014 58행 | `guard_target`, `_clarify_with_choices`(`trip_messages.py:1227`), unsupported actions | `_run_decision` | target_guard 23·unsupported 25 통과 | clarify 2건(누적) | 완료 |
| 8 | 새 요청/대기 분리·재개 소유권 | trip-chat-context, travel-response 62행, lifecycle 185행 | `case_dispatch.resume_pending`(166~), `trip_messages.py:373-388` | 채팅 입구 | conversation_work 통과, conversation_resume 19 ERROR(DB) | waiting_input 2건 잔류 | 부분 |
| 9 | Controller 두 축(case_type+intent)·Registry resolve/require_runnable·team_unavailable | 루트 AGENTS 48행, v11 §5-B, team-registry 17~32 | `controller.py:367-416`, `routing.py:18-48`, `registry.py:113-177`, `core_hooks/routing.py`, `composition.py:403-406` | `/v1/cases`·감시·규칙 경로. **채팅 결정 경로는 resolve를 쓰지 않고 API가 owner를 정함**(설계 web-intakes 209와는 일치) | plugin_availability·registry_capability·case_subject_routing·case_state_table 통과(asyncio 플러그인 명시 시) | ROUTED actor: controller 258·api 71·decision_unit 59 | 완료 |
| 10 | 라우팅 실패 시 한 번 재배분(D-CS-014) | D-CS-014 80~92행 | `controller.py:148-183,389-409`, `core_hooks/reroute.py`, `composition.py:612-621`, `reroute_enabled: true` | Controller가 ROUTING 상태 Case에만 적용 → 채팅 결정 경로(이미 ROUTED)는 해당 없음 | `test_routing_reroute` 통과, `test_unknown_route_availability` 5 ERROR(DB) | **rerouted 0건(누적)**, routing_failed(no_team) 92건(누적, 대부분 9월) | 부분 |
| 11 | 분류 실패 `classification_failed` 명시·escalate | cs AGENTS, INV-CS-RT-017/020 | `classification.py:41-103`, `events.py:57` | 채팅 해석 실패도 이 경로(`trip_messages.py:776-779`) | classification_step·sweeper·case_state_table 통과 | 166건 누적, 10-25 2건 | 완료 |
| 12 | 감시 전달 → Case → 분류 에이전트 계획(classify_plan/validate_plan) → 팀, D-020 묻기/자동, 고객별 알림 | D-017 18·26행, D-020 12~21행 | `trip_watch_cases.py:836-873`, `trip_watch_batch.py:225-271`, `execution_plan.py:61-121`, `planning/guardian.py`, `notice_routing.py` | `scripts/run_sweepers.py:531-573`, `run_outbox_worker.py:55` — **local live에서 미기동**(프로세스 조사: API PID 10756만) | classification_execution_plan 7·guardian_switch·notice routing·monitoring_response_adapter 통과 | trip.notice 7일 pending 6·delivered 0; `notice_per_customer_enabled:false` | 부분 |
| 13 | 멈춘 Case 되잡기(classification/routing sweeper) | routing_sweeper 문서, D-CS-014 115행 | `routing_sweeper.py:30-89`, `classification_sweeper.py` | `run_sweepers.py:218,232` — local 미기동 | 두 sweeper 단위 통과 | **routing 잔류 9건(agent_runs 없음, 09-14~10-11)**, running 잔류 7건 | 부분 |
| 14 | 공통 ResponseInput/Result를 계획·감시 결과에도 연결 | travel-response 16행, travel-response-current 95~100행 | `response/plan.py`, `response/monitoring.py`; 호출 `intake/pipeline.py`, `trip_watch_cases.py _record_response`, `watch_relaxed.py`, `planning/pending.py` | 코드 연결 있음(감시는 위 12번 미기동) | monitoring adapter·plan_response_adapter 통과, **`test_plan_generation_response` 39/42 실패**(전부 `all_dates_in_past` 422 — 고정 날짜 fixture가 v7a all-past 가드에 오늘부터 걸림; 10-25 union에선 통과) | 증거 없음 | 부분 |
| 15 | allowed_tools·도구 예산·팀별 범위 | cs AGENTS, D-017 26·44행 | `controller.py:278`, watch 계획 도구 범위, `policy.py:31-43`(Dining 도구 스키마 고정) | 실행 경로 | each_teams_own_scope 통과 | 증거 없음(이번 집계 대상 아님) | 완료 |
| 16 | DoD-23 라우팅 도달성 | v11 §12 1608행 | `scripts/verify_dod_v11.py:229` | 관문 스크립트 | feedback_case_type_alignment·intent_vocabulary·basement 129/129 통과 | 해당 없음 | 완료 |
| 17 | 질의에 대해 분류 에이전트가 담당·순서·우선순위 결정(다중 팀) | D-017 18·44행 | 채팅은 단일 action + 항목 종류로 담당 1개 | — | — | — | 설계와 다름 |

판정 집계: 완료 6/17 = 35.3% · 부분 8/17 = 47.1% · 설계와 다름 2/17 = 11.8% · 증거 없음 1/17 = 5.9%.

## 시험 실행(직접)

- 하네스: `routing-audit-20261026/run_isolated_audit.py`(allpast `run_isolated.py` 복사, 환경변수 이름만 `RTAUDIT_SOURCE_ROOT`, 네트워크·DB 차단). 출력 root: `C:\Users\kcxsz\AppData\Local\hermes\profiles\guguroute\cache\scratch\action-v7a-allpast-20261025-233317-fac130f7\source-v7a\final_project_cs`. venv `date_risk_env_312`.
- 1차(플러그인 자동로드 꺼짐): 451/547 — asyncio 시험 28건이 하네스 탓으로 실패해 집계에서 제외.
- 2차(`-p pytest_asyncio.plugin`): **479/547 = 87.57%**, 실패 40(plan_generation 39 = 날짜 fixture, read_requests 1 = 시험·schema 불일치), ERROR 28(전부 DB 차단 — conversation_resume 19·unknown_route 5·intake_screen 4). DB 필요분 제외 시 479/519 = 92.29%. 로그 `routing-tests-v2.log`, JUnit `routing-tests-v2.xml`.
- DoD-23 묶음: 129/129 = 100%(`dod23-tests.xml`).
- DB가 필요한 28건은 격리 DB 승인이 없어 실행하지 않았습니다(실패로 숨기지 않음).

## live 집계(acop_cs, 읽기 전용)

- 전체 Case 662(09-02~10-26), escalated 403·resolved 239·routing 9·running 7·waiting 4. 옛 커머스 intent(shipping 170 등) 잔류 — 9월 기록.
- v7a 교체(10-25 23:40) 이후 Case 1건(resolved). 10-20 이후 6건: 정상 4, 해석 실패 2(`created > classification_failed`).
- 이벤트: classified 495·routed 394·classification_failed 166·guardrail_escalated 145(degraded_context 140)·routing_failed 92(no_team).
- 접수 83건(screened 기록 0), 7일 fatal 5/20. outbox trip.notice: delivered 101·skipped 75·pending 6(7일).
- 스크립트: `db_aggregates_readonly{,2,3,4}.py`, 결과 `db-aggregates*.json`.

## 설계와 다르게 동작하는 곳

### P1
1. **로컬 live에 감시 루프·바깥함 일꾼·스위퍼가 없습니다.** API(PID 10756)만 떠 있습니다. 감시 전달 입력 경로, 고객 알림 배달, 멈춘 Case 되잡기가 로컬에서 동작하지 않습니다. 근거: trip.notice 최근 7일 pending 6·delivered 0, routing 잔류 9건(실행 기록 없음)·running 잔류 7건이 10-11 이후 그대로입니다.
2. **계획서 접수 읽기가 최근 7일 5/20 = 25% fatal입니다.** `reading_schema_not_ready` 2건은 D-025의 DB 항목(905 `llm_agent` 제약)이 공유 DB에 준비되지 않았다는 뜻입니다. 나머지는 `reading_model_failed` 2건, `reading_failed` 1건입니다.

### P2
3. D-024: 채팅 미해결·해석 실패·escalated 답에 문의 경로 안내가 없습니다(`trip_replies.py:28-29,143-150`, `trip_messages.py:780`, `case_dispatch.py:53-55`).
4. 채팅 변경 요청에서 대상 항목을 못 찾으면 담당이 `activity`로 기본 지정됩니다(`trip_messages.py:1174-1181`). 「모르는 것을 아무 팀에나 보내지 않는다」(D-CS-014)와 「Activity에 다른 팀 조정을 맡기지 않는다」(D-017)에 어긋날 수 있습니다. 실제 오배정 건수는 측정하지 않았습니다.
5. D-CS-014 재배분은 live에서 한 번도 발생하지 않았습니다(rerouted 0). 채팅 결정 경로는 run_case 전에 ROUTED되므로 재배분 대상이 아닙니다.
6. D-017: 질의에 대한 다중 팀·순서·우선순위 계획은 감시 회차에만 있고 채팅에는 없습니다.
7. 시험 신뢰도: `test_plan_generation_response` 39/42가 날짜 fixture 만료로 실패하고, `test_read_requests` 1건이 v7a schema와 맞지 않습니다. 둘 다 v7a 시험 그대로이며, 실행하는 날짜에 따라 결과가 갈립니다.

### P3
8. 규칙 경로(decision mode off일 때)의 `REGISTERED_TEAMS`(`trip_messages.py:31`) 하드코딩이 팀 id(`booking_handoff`)가 아닌 `booking`을 owner로 기록합니다. DB에 owner `booking` 16건과 `booking_handoff` 2건이 섞여 있습니다. `trip_desk`는 등록 팀이 아닌 기록용 라벨입니다.
9. 옛 커머스 Case(intent shipping 170 등)가 공유 DB에 남아 집계를 흐립니다(D-023 범위 확인 필요).

## 팀 develop 최신(d2ab93a65)과 라우팅 코드 차이

- 바이트 동일: `controller.py`, `registry.py`, `routing.py`, `classification.py`, `core_hooks/{routing,reroute,feedback}.py`, `presentation/api/cases.py`, `case_dispatch.py`, `chat_edit.py`, `fact_context.py`, `notice_routing.py`, `execution_plan.py`, `intake/{screen,fact_check,gaps,prefill}.py`.
- v7a에만 있는 것: `components/response/{writing,plan,monitoring,public}.py`(develop에 폴더 없음)와 그 연결(`read_requests.py`, `trip_messages.py` +`change_read`/`response_status`, `trip_watch_cases.py` `_record_response`).
- 그 밖의 v7a 변경:
  - `decision_unit.py`(CR 무시 141줄): `change_explanation` 사실 종류 추가, action 우선 schema 분기.
  - `edit_intent.py`: 시각 pattern과 following 이동량 보존.
  - `agent_read.py`: `validate_reader` 추가.
  - `composition.py`: reader 예산 fail-closed, Ollama tool chat, Activity judge.
  - `trip_api.py`: 86줄 차이.
- develop을 그대로 올리면 위 writer·안전 보완이 빠집니다. v7a를 develop에 올릴 때는 이 묶음을 따로 통합해야 합니다.

## 다음 작업 제안

1. (승인 필요) 로컬에서 `run_sweepers`와 `run_outbox_worker`를 v7a와 같은 정책으로 띄우는지 결정합니다. 띄우기 전에 잔류 routing 9건과 pending 6건의 처리 방침(재실행, 닫기, 그대로 두기)을 먼저 정합니다.
2. (승인 필요) 공유 DB 905 적용 여부를 결정하고, 접수 fatal 3종(schema, model, reading)의 원인을 읽기 전용으로 분해합니다.
3. D-024 안내 문구와 대상 없는 변경의 `activity` 기본 지정은 계약을 먼저 정한 뒤 RED→GREEN으로 고칩니다.
4. 시험 fixture 날짜를 상대 날짜로 바꾸고, `test_read_requests`를 새 schema 분기에 맞춥니다.
5. (승인 필요) 격리 DB로 DB 필요 시험 28건(conversation_resume, unknown_route, intake_screen)을 실행합니다.
6. 재배분 실모델 종단 확인은 제품 E4B 추론이 필요합니다. 이번에는 호출하지 않았고, 필요하다는 점만 보고합니다.

## 한계

- live 앱의 실제 라우트 목록(`assembled.json`) 조회는 승인 대기 시간 초과로 막혀 재시도하지 않았습니다. 그래서 2번의 live 마운트 여부는 미확인입니다.
- 감시 Case 수는 표시 키 차이로 정확히 집계하지 못했습니다(`watch_cases` 0은 추정 키 기준입니다).
- 실제 고객 화면과 실모델 품질은 보지 않았습니다.

## 원본 증거 위치

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/routing-audit-20261026/` — REPORT_KO.md, routing-tests-v2.{log,xml}, dod23-tests.xml, db_aggregates_readonly{,2,3,4}.py, db-aggregates*.json, run_isolated_audit.py.
