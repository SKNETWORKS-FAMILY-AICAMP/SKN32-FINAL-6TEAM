---
type: report
title: 로컬 live v9(git 밖) vs role-manager c286b906 — 로컬 전용 코드 기능 단위 감사
status: verified
domain: travel
---
# 로컬 live v9 vs role-manager — 로컬 전용 코드 감사 (읽기 전용)

- 작성: 2026-10-26 07:15 KST · Hermes subagent(Opus) · Codex CLI 의견 1회(텍스트 전용, 도구 미사용).
- 대상: 로컬 live 8042(PID 5088, `integ-v9-20261026-025943/runtime-v9-serving/launch-serving.py`)의 source `integ-v9-20261026-025943/source`.
- 비교: role-manager `c286b9060bcf`(ls-remote 확인) · develop `30e9f0a08fdb` · v9 계보 pin `6c34589b4e34`(develop 병합 커밋, writer2 보고서 기준) · merge-base(pin, role-manager) `6410f754b3fe` · 기존 이식 후보 `port/writer-on-develop` `52032f1dd`.
- 지킨 것: 코드 수정 0 · push 0 · live/DB 접근 0 · 제품 E4B 호출 0. 원본 작업트리는 건드리지 않았고 worktree 4개는 scratch 에만 만들었다.
- 증거: `cache/scratch/local-only-audit-20261026-0645/` — `inventory.json`(기능 묶음과 파일), `fourway_pin.json`(파일별 4자 분류), `rm_commit_presence.json`, `codex-bundle.md`, `codex-answer.md`.

## 결론

1. **로컬 v9 의 로컬 전용 기능은 role-manager 에 거의 없다.** 범위(app·config·tests·wiki) 안에서 pin 대비 로컬이 바꾼 파일은 114개다. 그중 로컬에만 있는 파일이 88개, 양쪽이 다르게 바꾼 파일이 20개, role-manager 쪽이 더 새 판인 파일이 6개다. 라우팅 에이전트에 직접 필요한 것은 **Routing P2**(문의 경로 안내·근거 기반 담당·`booking_handoff`)다. 이것은 role-manager 에 아예 없다.
2. **절반은 이미 이식 후보가 있다.** v7a 분은 `port/writer-on-develop`(develop d2ab93a65 + 15 커밋, push 안 함)에 있다. 로컬 전용 88파일 중 49/88 = 56%가 그 후보 tip 과 같은 바이트다. 빠진 것은 v7a→v9 추가분 17개 app 파일이다: Comment9, I06, F02, temporal, C02, T09/T10, Dining seeded, Routing P2.
3. **role-manager 가 develop 28 커밋을 갖고 있지 않다.** 로컬은 이 커밋들의 내용을 갖고 있고 role-manager 는 없는 파일이 47개다. 예: Dining PR #84 `dining-answers` 경로, ST4F-731~734 계획 확인. 이 부분은 이식할 일이 아니라 **develop→role-manager 병합**으로 들어와야 한다. 로컬과 role-manager 의 공개 route 차이도 `POST /v1/web/trip-intakes/{intake_id}/dining-answers` 하나뿐이고, 이 경로는 develop 에 있다.
4. **오늘 role-manager 커밋 중 v9 에 없는 것**(추가 줄 포함률 v9 / 준비된 v10):
   - v10 에 들어간 것: da4ccd97 3%/90%, c023140b 3%/100%, 231e303a 0%/100%, d3d0a063 5%/94%, eebd9691 2%/99%, c34bd376 5%/100%, 418cc190(T16) 0%/100%.
   - **v10 에도 없는 것**: 1e4e3b24 0%/1%, 3c1af5b7 0%/0%, 53dea261 1%/1%, 539cef63 0%/0%, 8fae4901 0%/0%, c286b906 3%/4%.
   - 포함률은 줄 단위 존재 비율이다. 동작 보존률이 아니다.
5. **로컬 교체 전략: B(role-manager tip 기반 재구축)를 택한다.** Codex 의견도 같다. v9 계보에 rm 커밋을 계속 3-way 로 얹는 A 는 다음 문제가 쌓인다.
   - 다르게 구현된 6개 영역(아래 (c))을 매번 손으로 맞춰야 한다.
   - push 대상 트리와 live 트리가 계속 갈라진다. 이번 감사에서 갈라진 범위는 role-manager 기준 114 + 47 + 43 파일이었다.
   - v10 같은 중간 판은 A 방식이 계속 필요하므로, 비교·회귀용으로만 쓴다.
6. **기록 손실 위험**: 계보 사본에만 있는 보고서·handoff 29건이 정본 wiki 에 없다. 예: writer2 통합 마감, source-v3/v4, v5 binding, final-serving-i06, survey 수정 2건, Dining clarifications, f02-origin, team12. 목록은 `inventory.json` 의 `lineage_only_wiki_records` 에 있다. 재구축 전에 이 기록을 정본으로 옮겨야 한다(옮길지는 부모가 정한다).

## 1. 파일 단위 분류 (범위: app·config·tests·wiki, 로컬 v9 vs pin/merge-base/role-manager/develop)

| 분류 | 파일 수 | 뜻 |
|---|---:|---|
| (a) 로컬 전용 | 88 | pin 대비 로컬만 바꾸고 role-manager 는 안 바꾼 파일 |
| (c) 양쪽 변경 | 20 | 로컬과 role-manager 19 커밋이 같은 파일을 다르게 바꿈 |
| (c) role-manager 상위판 | 6 | 로컬 추가 줄의 91~100% 가 rm 에 있음(rm 쪽이 최신) |
| 같음(rm 이식본) | 9 | 로컬 = rm (08b99597·2ce73990·53c3c273 이식) |
| (b) role-manager 전용 | 43 | rm 19 커밋이 바꾸고 로컬은 pin 그대로 |
| (e) develop 내용, rm 에 없음 | 47 | pin 이 가진 develop 커밋 내용(로컬 = pin, rm 은 그 전) |
| (f) pin 뒤 develop | 14 | develop 34 커밋 중 로컬·rm 모두 없음(ST4F-737 등) |
| 계보 전용 기록 | 29 | 서빙 사본 wiki 에만 있는 보고서·handoff |
| 사본 누락(copy gap) | 4,654 | v9 사본이 wiki/records 를 다 복사하지 않음. 삭제가 아니다 |

## 2. 기능 단위 표

우선순위 기준: P0 = 라우팅 에이전트 완성 또는 x600 개인정보 경계, P1 = 채팅·접수 정확도, P2 = 후속 개선, hold = UI·운영 협의 필요.

| ID | 기능(공식 이름) | 분류 | 출처(보고서 / scratch) | 이식 묶음 | 이식 | 우선 | 웹 계약 | 예상 충돌 파일 |
|---|---|---|---|---|---|---|---|---|
| L01 | Routing P2: `trip_replies.with_inquiry_guide`, `_choice_owner`·`_version_owner`·`_unresolved_question`(owner_unresolved), `CASE_TYPE_TEAMS` booking→`booking_handoff`, `LEGACY_TEAM_IDS`, `case_dispatch.resume_owner` | (a) | `2026-10-26_routing-p2-inquiry-guide-owner`, D-024 / `routing-p2-20261026-011814-21438` | 새 묶음(후보에 없음) | 필요 | **P0** | 없음(답 문구 끝에만 안내, status 그대로) | `trip_messages.py`(rm da4ccd97·c34bd376·1e4e3b24·c286b906), `case_dispatch.py`(rm 8fae4901) |
| L03 | 계획 읽기 reader 안전: `validate_reader`·`ReaderPolicyError`, `reader_json(external_fallback_enabled=false)`, `register_reader_budget_provider`(fail-closed), `StreamLifetime` | (a)/(c) | `2026-10-24_reader-provider-safety`, `2026-10-25_reader-stream-policy-omission-tdd` | 후보 묶음 2·3 | 필요 | **P0** | 없음. x600 동작이 바뀐다: 접수 원문 유료 넘김이 기본 차단 | `llm_failover.py`(rm eebd9691·53dea261), `composition.py`(rm 53dea261·539cef63), `guardrails.yaml` |
| L06 | 공개 실패 privacy(`test_public_decision_failure_privacy`) | (c) | 후보 묶음 11 | rm 8fae4901 과 한 계약으로 합침 | 필요 | **P0** | 없음 | `pipeline.py`, `presentation/errors.py` |
| L06b | CORS `Access-Control-Allow-Credentials` | (a) | 후보 묶음 11 | 따로 커밋 | 보류 | hold | 웹 보안·배포 계약 | `presentation/errors.py` |
| L05 | 채팅 해석 문법·근거: temporal v7/v8, add 날짜 근거, F02 origin/subject, C02 `quoted_calendar_days`·read_requests anyOf, T09/T10 `generation_variants`, 증거 실패 코드 | (c) | `temporal-v7-20261025-192231-7982b9`, `f02-origin-20261025-201456-5daacb`, `c02-u01-fix-20261026-011759-27440`, `t09t10-temporal-20261026-012405-b39137b6`; 보고서 `acceptance-c02-u01-fix`, `t09-t10-temporal-boundary-candidate` | 후보 묶음 3·9 + v7a→v9 추가분 | 필요 | P1 | 없음 | `decision_unit.py`(rm 7 커밋), `edit_intent.py`(rm 2ce73990·1e4e3b24·c286b906), `read_requests.py`, `fact_context.py` |
| L07 | I06 명시 고정(`locked`/`locked_quote`, 예약만으로 고정 승격 금지) | (a) | `final-serving-i06-20261025-203428-8b1e6c3b`, `i06-booked-only-20261025-212313-e1309e55` | 새 묶음 | 필요 | P1 | 없음 | `agent_read.py`, `pipeline.py`(rm c023140b·8fae4901) |
| L02 | 공통 writer `response/writing.py`·`public.py`, 문의·계획·감시 writer(`plan.py`·`monitoring.py`·`pending._response_payload`·`action_notice`), `change_read` | (a) | `2026-10-24_travel-writing-slice1/slice2`, `travel-response-consumer`, `monitoring-fix-case-notices`, `change-explanation` / 후보 묶음 5~10 | 내부 writer(L02a)와 공개 필드(L02b)로 나눔 | L02a 필요 | P1 | **L02b: 있음** — `response_status`·`question_status` 를 chat JSON/SSE·duplicate·notices·plan 결과에 더함(가산형). 소비 코드는 로컬 frontend 에만 있고 final_project_ui 에는 없음 → hold | `trip_messages.py`, `read_requests.py`, `trip_api.py`(rm 08b99597), `pipeline.py`, `itinerary_actions.py`(rm 418cc190) |
| L04 | E4B 문맥 용량: `native_context_tokenizer`, `OllamaChat.context_capacity`·`_check_completion`, `prepare_decision_context`, `compact_instructions`, Dining native tool(`native_tool_renderer`·`EmptyToolTurn`) | (c) | `2026-10-26_채팅해석_문맥창초과_16항목_원인과_수정`, `2026-10-25_shared-original-safe-application` / `dining-tool-local-20261025`, `local-e4b-replay-20261025/context-v10-*` | 후보 묶음 4 | 일부 | P1~P2 | 없음 | `ollama_chat.py`(rm eebd9691·53dea261), `decision_unit.py`, `settings.py`(rm 539cef63·d3d0a063) |
| L08 | Comment9 방문 시간 제한(`hours._settle_stored_conditions`, `closure_rules._restriction_verdict`, `activity_ledger`) | (a) | `2026-10-25_comment9-visit-time-restriction`, `2026-10-26_comment9-revalidate-rehearsal` / `comment9-v8-20261025-194955-6b7597cf` | 새 묶음 | 필요 | P2 | 없음 | 없음 |
| L09 | Dining `_seed_required_lookups` | (a) | `2026-10-26_dining-seeded-lookups-comment8` / `dining-latency-20261026-012500-3532` | 새 묶음(develop #84 병합 뒤) | 필요 | P2 | 없음 | `instances/dining/agent.py`(develop #84), `llm/tool_chat.py` |
| L10 | 설문 답 소비, lodging `my_stay`, Activity `alternative_order`, `activity_duplicate_policy` | (a) | `2026-10-25_survey-consumption-fix`·`survey-agent-boundary-fix`(계보 전용) / `activity-duplicate-policy` | 후보 묶음 13 | 필요 | P2 | 없음 | `composition.py`, `candidates.py`, `prepared.py` |
| L11 | 첫 Dining 판정 순서, comment8(사진 1분 문구) | (a) | `2026-10-25_comment8_intake-performance`(계보 전용) | 후보 묶음 14 | 필요 | P3 | 문구만 | `prepared.py`(develop ST4F-731), `pipeline.py` |
| L12 | Activity 공개 웹 보조조회(`activity_public_web`·`public_web_transport`, 기본 꺼짐) | (a) | `2026-10-25_activity-public-web-independent`(계보 전용), `2026-10-26_activity-public-web-ddgs-candidate`(rm 53dea261 위 staged) / `activity-public-web-7f91`, `ddgs-check-20261026-043722` | 후보 묶음 1 | 나중에 | P3/hold | 없음 | `places.py`, `place_lookup.py`, `read_tools.py`, `guardrails.yaml` |
| L13 | `testing.plan_test_mode` | (a)/(d) | 후보 묶음 15, skill `local-plan-testmode-activation` | 후보 묶음 15 | 보류 | hold | `/features` 에 `plan_test_mode` 키를 더함(관리 화면) | `web_guard.py`·`features_api.py`(rm d3d0a063) |
| X01 | 야외/실내 QA·전부 과거 거절(로컬 = rm 08b99597·2ce73990·53c3c273 이식본) | (c) rm 상위판 | v9 build | — | 불필요 | — | — | — |

이식 묶음의 파일 목록은 `inventory.json` 의 `features[].files` 에 있다. 시험 목록은 `features[].tests` 에 있다.

### (c) 양쪽이 다르게 구현한 영역

1. **문맥 창.** 로컬은 tokenizer 계수와 용량 거절·지시 압축을 쓴다. rm 539cef63 은 `ollama_num_ctx` 12288 로 올리고, 같은 모델 호출자 모두에 같은 값을 보낸다. 정본 보고서는 12288 을 채택했다. 두 방식은 서로를 보완한다. 12288 은 유지하고, 로컬의 용량 판정은 manifest 가 있을 때만 켠다.
2. **접수 실패 공개 내용.** 로컬은 공개 실패 privacy 를 쓰고, rm 8fae4901 은 `fatal.detail` 을 숨긴다. 한 계약으로 합친다.
3. **스트림.** rm eebd9691 은 chat decision 스트림이고, 로컬 `StreamLifetime` 은 reader 스트림이다. 둘 다 `llm_failover.py` 와 `ollama_chat.py` 를 고친다.
4. **failover.** 로컬은 reader 예산을 fail-closed 로 막고 외부 대체를 차단한다. rm 53dea261 은 차가운 모델 예열과 keep_alive 를 맞춘다. 목적이 다르므로 둘 다 유지한다.
5. **스위치.** rm 은 `travel.plan_input.extras_enabled`, 로컬은 `testing.plan_test_mode` 이다. 같은 4개 파일을 쓴다.
6. **채팅 해석.** `decision_unit`·`edit_intent`·`trip_messages` 를 양쪽이 모두 크게 고쳤다. 이식할 때 SYSTEM·스키마 바이트를 다시 해시해야 한다.

### (d) 로컬 서빙 전용(제품 아님 — 이식하지 않는다)

- `runtime-v9-serving/{launch-serving.py, policy.py, local-guardrails.yaml, verify_target.py, SERVING_FREEZE.json, bind-manifest.json}`. `policy.py` 의 egress 허용목록이 로컬에서 Kakao 를 막는다.
- `integ-v9-*` 의 build·offline runner·`ext_guard.py`·`harness-datasets`·`external-dining`.
- acceptance49 runner(`run_full49_v8.py` + `deps/policy_v8.py`). 이 runner 는 `native_context_tokenizer` 가 있어야 돈다.
- tokenizer manifest 파일.
- 로컬 DB 운영값 `testing.plan_test_mode=true`.

## 3. 이식 순서 제안 (role-manager 기준 통합 가지 `integ/...`, 자동 배포 가지에 직접 push 하지 않음)

1. develop→role-manager 병합: (e) 47파일과 develop 28 커밋. 충돌 예상 파일은 `pipeline.py`·`review.py`·`trip_api.py`(rm all-past 계열)와 `web_guard.py`·`features_api.py` 이다. 시험은 fast gate 와 DB gate 를 돈다.
2. P0 묶음 3개를 차례로 얹는다.
   - L01 Routing P2.
   - L03 reader 안전: 후보 커밋 4f565ffe2 등을 cherry-pick 하고 rm 53dea261 과 맞춘다.
   - L06 privacy: rm 8fae4901 과 합친다.
   - 시험: L01 시험 3파일 + rm `test_chat_setting_clarify_*`·`test_resume_route_place_name` + `test_reader_provider_integration`·`test_intake_reading_stream`·`test_cold_model_warm_and_keep_alive`·`test_intake_reading_failed_privacy`.
3. P1 묶음을 얹는다.
   - L05+L07: 채팅·접수 문법.
   - L02a: 내부 writer.
   - L04: 용량 판정. 12288 은 유지한다.
   - 실 E4B 확인: acceptance49 를 rm 트리 + overlay 로 돈다. lease 를 받고 idle gate 를 지킨다.
4. P2 묶음 L08~L11 을 얹는다. L09 는 1번 병합 뒤에만 가능하다.
5. 보류: L02b `response_status`/`question_status` 공개 필드, L06b CORS, L12, L13. UI·운영 협의 뒤에 한다.
6. 전체 gate 를 돌리고 develop baseline nodeid 와 대조한다. 그 뒤 role-manager 에 push 하고(두 원격) develop 에 반영한다.

## 4. 로컬 교체 전략 (v10/v11)

| 선택 | 장점 | 기능 손실 위험 | 판정 |
|---|---|---|---|
| A: v9 계보 + rm 오늘 커밋 3-way | 로컬 기능 보존이 쉽다 | v10 도 rm 6 커밋(1e4e3b24·3c1af5b7·53dea261·539cef63·8fae4901·c286b906)이 빠졌다. (c) 6개 영역을 매번 손으로 맞춰야 한다. push 트리와 live 트리가 계속 갈라진다 | 급한 비교용으로만 |
| B: role-manager tip + develop 병합 + 3장 이식 묶음 | live = push 트리가 된다. x600 과 같은 코드 경로다 | v7a→v9 추가분, 웹 44파일, 계보 전용 기록 29건이 빠질 수 있다. `inventory.json` 의 기능 목록으로 확인 가능하다 | **채택** |

B 로 교체하기 전 조건:
- `inventory.json` 의 L01~L11 이 모두 들어갔는지 확인한다(hold 묶음은 OFF 상태를 확인한다).
- 로컬 serving 하네스(d)를 새 소스에 다시 맞춘다. policy·launcher·manifest 가 대상이다.
- acceptance49 결과가 v9 보다 나빠지지 않아야 한다.
- 웹 v9 frontend 의 응대 상태 소비분은 L02b 가 보류인 동안 서버가 새 필드를 보내지 않는다. 그러면 화면이 보이던 상태 표시가 사라진다. 이 화면 변화는 교체 승인 때 사용자에게 알려야 한다.

## 5. Codex 의견 (텍스트 전용, `codex-answer.md`)

- 전략은 B 다. role-manager 기준으로 develop 누락분부터 맞추고, 검증된 결과만 develop 에 반영한다. v9 는 비교·회귀 기준으로 보존한다.
- Codex 는 reader 안전·privacy·문맥 용량·I06·F02·temporal·Comment9·Routing P2 를 모두 P0 로 봤다. 이 보고서는 라우팅 완성과 x600 개인정보 경계만 P0 로 두었다(L01·L03·L06). 나머지는 P1/P2 로 낮췄다. 이유는 x600 을 바꾸는 범위를 묶음마다 실 E4B 로 확인해야 하기 때문이다. 이 차이는 되돌릴 수 있는 판단이다.
- `response_status`/`question_status` 와 CORS credentials 는 UI·보안 계약이므로 따로 보류한다(동의).
- 추가 위험:
  - x600 은 paid failover 가 켜져 있다. 공용 wrapper·재시도·stream fallback 이 reader 차단을 우회하지 않는지 확인해야 한다.
  - `booking_handoff` 로 저장한 case 를 롤백한 구버전이 읽을 수 있어야 한다. 읽기 호환만으로는 롤백 안전이 보장되지 않는다.
  - 로컬 `plan_test_mode=true` 와 Kakao 차단이 운영 설정으로 새면 안 된다.
  - 줄 포함률은 동작 보존률이 아니다.

## 한계

- 파일 분류는 blob 해시와 줄 단위 포함률로 했다. 기능 묶음 배정은 이름·함수·보고서를 보고 사람이 판단했다. 시험은 돌리지 않았다.
- 웹(final_project_cs/frontend, final_project_ui) 차이는 응대 상태 필드 소비 여부만 확인했다. 웹 44파일 미이식 상태는 이전 이식 보고서의 값이다.
- `1e4e3b24` 의 동작 검증은 이식 단계의 배포 조건으로 남긴다.
