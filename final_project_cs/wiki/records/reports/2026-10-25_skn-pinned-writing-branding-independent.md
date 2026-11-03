---
type: report
title: SKN develop pin 기준 기존 라이팅·GuguRoute 이름 독립 readonly 비교
status: documented
domain: travel
---

# 결론

**팀 최신 구현을 기반으로 로컬 응대 메타데이터만 선별 이식해야 합니다.** 문의·계획 읽기·감시·브랜딩은 이미 후속 구현이 있습니다. 로컬의 기존 시험 통과는 아래 pin에 통합됐다는 증거가 아닙니다. 이 보고서는 코드·계약·호출 경로의 정적 비교이며 시험/실DB/실모델/HTTP/서비스/배포 수락은 수행하지 않았습니다.

## 1. 정확한 기준선과 범위

- 원본: `C:/_proj/final_workspace`, HEAD `efeb873a8d065fbd28fe8e92dcc42e5cfb3de3e3`.
- 팀: `team = https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM.git`.
- 비교 대상은 부모가 이미 확보한 **develop pin `325ba25d88c91ce97da61f2bda635e5888fe3b40`**. 이 child는 fetch를 반복하지 않았습니다.
- pin 최신 커밋: 2026-10-23 16:56:27 +0900, PR #90 `role-eval-ui` 병합. 그 직전 `d8861a6c7`은 콘솔 오류 시험의 위험 확인 fixture 보정입니다. 최신 commit 자체가 응대 기능 전체 수락을 뜻하지 않습니다.
- `merge-base(local,pin) = efeb873…`, `rev-list --left-right --count local...pin = 0 899`. 즉 **로컬 HEAD만의 커밋 0, pin에서만 도달 가능한 커밋 899**이며 local HEAD는 pin의 조상입니다. 899는 merge된 가지 이력을 포함한 커밋 수입니다. 파일 수·결함 수·기능 수·미반영 patch 수·완료율이 아닙니다. 같은 구간 `--first-parent --count = 113`입니다. “대략 900개 기능”으로 바꾸어 말하면 틀립니다.
- 로컬 dirty/untracked 응대 구현은 HEAD 커밋 이력 밖에 있습니다. `git diff pin`만으로 untracked 파일을 누락 판정하지 않았습니다. missing disk/skip-worktree 역시 pin의 기능 부재가 아닙니다.
- 원본/candidate 소스·설정·규칙 파일을 수정하지 않았습니다. 고유 cs 보고서와 evidence만 추가했습니다. 다른 child의 candidate는 열거나 수정하지 않았습니다.

증거: [Git 원출력](../evidence/2026-10-25_skn-pinned-readonly-independent/git-evidence.txt), [pin caller 발췌](../evidence/2026-10-25_skn-pinned-readonly-independent/pinned-caller-excerpts.txt). 아래 줄 번호는 별도 표기가 없으면 **pin 파일** 기준입니다. 경로는 `final_project_cs/` 아래입니다.

## 2. 핵심 정상 3경로 matrix

| 경로 | pin의 실제 정상 caller → 업무/저장 → 고객 소비 | 반드시 upstream 보존 | 로컬에서 추가할 수 있는 것 / 충돌 가능 |
|---|---|---|---|
| 계획서 접수·검토·등록 | `entry/trip_api.py:web_intake` → `intake.pipeline.open_intake/process/read_source/view`; `web_intake_confirm`(1990) → scoped `draft` → unchecked review 거절 → `registration.require_review/confirmed_trip_id`(2051~2060) → `_create_trip/mark_confirmed`; 수정 접수는 `_confirm_reopened`(2065) → 공통 `intake.reopen_commit.commit`(2083). 웹은 `intake.ts:getIntake/confirmIntake` → `intake-review.tsx` mutation(142~145) → prefetch 후 `registered` 이동(135~140) | D-025 전체 읽기, 인용 검증, 모델측/내용측 실패 분리, survey·prefill·interpretations, saved-only edits 뒤 재검사 요구, prepared alternates, 등록 lock/중복 방지, 수정 시 같은 trip 새 판·변경 없음 판 유지 | 로컬 optional `response`/저장 재조회 검증은 pin에서 확인 안 됨. **기존 confirm handler 통째로 교체 금지**: 로컬 초안은 최신 `registration` lock·`reopen_commit`·`check:false/recheck_needed`·대안 보존을 놓칠 수 있음. confirmed 기록과 commit 이후 검증된 registered 문구를 구별해 최신 handler마다 연결해야 함 |
| 고객 문의·후속·변경 | agent `messages`(1154) 및 웹 JSON/SSE 공용 `_web_message_result`(2497) → `handle_trip_message` → `_run_decision` → `read_requests.reply`(893), 변경은 `case_dispatch`/`TripDesk`/공통 commit. 답 `outcome_reply` → Case `state_patch.answer/trip_outcome/chat_reply`(1062~1088), `_log_turn`; 웹은 `answer_web` 치환 후 `_web_view`, `gateway.sendMessage` → 탭 저장·서버 chat 재조회 | 시간 anchor, 별도 새 요청/대기 재개, focus/판/TTL, 선택 장소 정체성, weather/outdoor, 목적지 직접 고르기 pick, 변경/도착/진행 경로, summary_day, 업무 dispatch·승인 상태. duplicate는 기존 choices/more/answer_web/pick 허용 목록(365~370) | `components/response` 순수 작성기, 질문별 종결·optional 공개 enum 및 duplicate/저장 reply 연결은 pin에서 확인 안 됨. 최신 `read_requests`가 바꾼 request/fact와 **원래 질문 사본**을 구별해 adapter를 끼워야 함. `basis.response` 추가만으로 웹/reload가 소비한다고 주장 금지 |
| 감시 → 일정 변경/대기 → 알림 → 고객 후속 | `scripts/run_sweepers.py:_run_trip_watch_cases`(564) → `TripWatchCaseOpener`(592) → `tick` → Controller `run_case`; 실제 적용은 `actions/itinerary_actions` append_version + `_version_notice`/질문 outbox. 실패는 `_after_run`(381) → `_defer_notice`/`_unhandled_notice`/`unresolved_notice`; 별도 `TripWatcher`도 존재. 웹 `getNotices`·proposal choose·chat/rollback으로 이어짐 | 재난 정지 선행, team availability, 실패 지연/통지·dedupe, batch, 대안 완화 질문, guardian on/off/ask-first, 거래·고정 항목 경계, 저장/notice 동일 트랜잭션, 정기 reminder 문구틀 | applied/awaiting_choice/failed/unknown의 로컬 응대 adapter와 공개 enum은 추가 후보. **resolved를 applied로 승격 금지**. 최신 성공 outbox 한 건에 부착하고 별도 두 번째 통지를 만들지 말 것. 최신 `_after_run`은 escalated만 후처리(384)하므로 로컬 성공 응대 수집을 그대로 복사하면 다른 실행 summary/트랜잭션 의미와 어긋날 수 있음 |

### 계획 생성은 정상 등록과 별도 계약입니다

- `trip_api.py:web_intake_plan`의 `plan_and_register`(2153)는 이미 JSON/SSE 공용이고, `request.review_only`이면 **`social_dining_plan.stage_generated`로 검토 접수만 반환**합니다(2182~2193). 그 밖에만 `_create_trip/mark_confirmed`로 갑니다(2194~2200).
- 로컬 `registered_plan_payload`를 모든 plan 성공에 달면 **review_only를 등록 완료로 오표시**할 위험이 있습니다. 기존 response body/상태와 review-only 갈래를 보존하고, 등록 경로에만 재조회 기반 registered를 붙여야 합니다.
- `frontend/lib/live/intake.ts:planIntake`(270)는 일반 계획 짜기 정상 경로를 confirmed trip으로 타입화하고, `intake-plan.ts:planFromIntake`(69)는 trip id를 소비합니다. 모든 서버 plan 호출이 이 한 타입과 같다고 일반화하면 안 됩니다.

## 3. 이미 upstream에 있는 읽기·날씨와 남은 차이

### 이미 구현: 다시 “새 복구”로 가져오지 말 것

- `7d503bfb6` D-025 새 계획 읽기, `502da503c` 한 계획 한 모델·stream/멈춤 감시·명시적 읽기 실패가 pin에 있습니다.
- `intake/agent_read.py:read`(392)는 `structured_stream`/first_wait/stall/max_seconds, api_only 전환을 이미 사용합니다. `pipeline.read_source`(1391~1405)는 모델측 실패 시 `IntakeRejected(reading_model_failed)`, 답 내용측 실패만 다음 줄 읽기 경로로 나눕니다. 오래된 규칙 읽기 구조로 되돌리는 큰 이식은 D-025 위반 위험입니다.
- `011f4e7e3 → af4a9723c` 시간 질문 서버 계산 및 `27ea017c6` 채팅 v165 날씨·수정 뒤 focus 보강도 pin에 있습니다.
- **날씨는 upstream 실제 router까지 연결돼 있습니다.** `_desk`(896~905)가 `weather=lambda **query: source.forecast(...)`를 주입하고, `TripDesk.weather` → `_run_decision`(899) → `read_requests.reply(weather_lookup=...)` → `weather_read.reply`(147)로 갑니다. upstream을 “helper만 있고 생산 caller 미연결”이라고 보고하면 틀립니다.
- 최신 read는 weather/outdoor의 previous·now·anchor 충돌, 최신 장소 재이름 안내, forecast 목록·출처/확인시각·대상별 근거를 보존합니다(`read_requests.py:90~172`). 로컬 weather 작업의 기능명·파일명이 같다는 이유로 전부 추가/전부 폐기할 수 없습니다. 추가 검증·안전성 hunk만 최신과 재대조해야 합니다.

### 추가 후보: 기존 기능과 구별할 것

- pin의 `app`, 사용자 웹 `src`, `wiki/external`을 대상으로 `response_status|question_status|ResponseInput|registered_plan_payload|stale_registration_session`를 조회했으며 일치하지 않았습니다. **이 명명과 계약의 로컬 응대 메타데이터는 해당 검사 범위에서 신규**입니다. 모든 동등 기능의 부재를 증명한 것은 아닙니다.
- `conversation/change_read.py`는 pin 파일 목록에서 확인되지 않았습니다. 그러나 `decision_unit.changes_of`(264), 변경 이력 prompt(343~364), trip_messages rollback/redo·오변경 의심(974~1010)은 이미 존재합니다. 따라서 **변경 이력/되돌리기 전체 부재가 아니라**, 로컬 “왜 바뀌었는가” 순수 읽기 종결·명시적 설명 계약을 기존 이력과 연결할 필요가 있는지 별도로 정해야 합니다. 해석 action을 새로 늘리거나 rollback과 혼동하지 않아야 합니다.
- 기존 `response_review`를 이 기능의 완성품으로 취급하면 안 됩니다. `config/project.yaml:110~112`는 **enabled:false**입니다. `Controller._maybe_review`(530~552)는 켜면 reviewer의 **TeamResult 전체를 반환**하므로 승인·제안·next_action을 그대로 보존하는 순수 문장 adapter와 다릅니다. `composition.py`는 enabled일 때 runnable 팀을 요구합니다. 이번 readonly 비교에서는 이를 활성화하지 않았습니다.

## 4. 고객 웹 상태 소비·세션 경계 matrix

| 소비 지점 | pin에서 확인한 현재 계약 | 통합에 필요한 추가/보존 |
|---|---|---|
| JSON/SSE 답변 | 웹 `_web_message_result` 공용, answer_web 소비; stream `result`와 JSON body는 같은 업무 결과 | response_status/question_status는 별도 optional enum allowlist로. basis 내부 scope·request를 고객 공개 상태에 복사 금지. 기존 status와 응대 completion의 뜻을 섞지 않음 |
| duplicate·서버 chat reply | trip_messages duplicate 허용 목록에 choices/title/more/answer_web/pick; `_run_decision`의 chat_reply에도 구조화 focus/edit_goal 존재 | 두 공개 enum은 **저장·duplicate·chat 조회** 각각 추가 필요. 기존 focus/pick/edit_goal을 잃지 않아야 함 |
| 탭 보관·chat reload | `gateway.ts:ServerTurn`(199)·`recordedMessages`(214~235), case id/content 기반 병합·`sessionStorage`(264~276). 새 UI는 status/minutes/summaryDay/steps/secs/focusId도 유지 | 로컬 옛 gateway를 덮으면 ST4F-719 결과 카드·진행 과정이 사라짐. 응대 상태만 선택적으로 병합·재검증. 과거 상태 부재는 그대로 두기 |
| 알림 | `extras.ts:getNotices`(169)에서 text/type/kind/version/proposal/rollback/safety/**changed** 소비. 10-22~23 알림 센터 ST4F-723이 선택 결과·변경 전후를 사용 | 로컬 새 enum 투영을 추가하되 changed·chosenKey·알림 센터 분류·되돌림 계약 보존. 저장한 outbox와 조회 projection/UI까지 연결해야 함 |
| 접수 조회·수정·확정 | `IntakeView`는 reading/review/confirmed/fatal, prefill/handoff/interpretations·frozen 이유 등. confirm은 trip/changed/version. 신규 응대 response는 확인 안 됨 | 모든 mutation 결과·events 재조회가 새 response를 보존하는지 별도 수락. review_required와 registered를 별도 표시. `check:false` 미검사 상태를 complete로 바꾸면 안 됨 |
| 인증 조회 레이스 | `client.ts:probeSession`(237~262)은 beganWith snapshot identity로 늦은 **인증 조회**가 로그인/로그아웃 상태를 덮지 않게 이미 방어함 | 이 보호를 “등록 결과 세션 fence도 이미 완료”로 일반화 금지 |
| 실제 등록 dispatch/반환 | `api`(322~336)는 ensureSession 후 send/json 반환, csrf_failed는 강제 probe 후 한 번 retry. `sessionInit`(340)은 headers 반환만. `stream.attempt`(70)은 재접속마다 sessionInit, `streamApi`(152~153)는 done을 바로 반환 | **로컬 registration dispatch generation fence가 추가 후보**. 최초 게스트 생성 후 실제 dispatch snapshot을 잡고, retry/reconnect·늦은 body decoding·반환 경계까지 같은 세대인지 확인. 토큰 값 비교만으로 A→B→A·동일 토큰 replacement 방어 안 됨 |
| 성공 후 화면 이동 | `intake-review.tsx:registered`(135~140)는 비동기 trip prefetch 뒤 router.push. `intake-starting`도 plan 결과 trip으로 이동 | 로컬 API 성공 반환 전 fence를 가져와도 **반환 후 prefetch 대기 중 세션 교체→이동** 경계는 별도 시험 필요. pin 소스상 해당 함수에 세션 snapshot 재확인이 없음. 재현 시험을 돌리지 않았으므로 정적 위험으로 남김 |

추가로 pin `gateway.sendMessage`는 await 뒤 `pending.set`에서 **현재 csrf**를 사용합니다(458), 메시지 저장(479)도 dispatch 소유 세대 확인 없이 이어집니다. 이는 등록 전용 fence의 해결 범위 밖인 **문의 늦은 결과 귀속** 별도 후보입니다. 인증 조회 방어와 업무 응답 귀속 방어를 혼동하지 말아야 합니다.

## 5. 제품 이름 GuguRoute: 완료 scope와 남은 scope

- 사용자 현재 정확 표기는 **GuguRoute**입니다. 팀 이름은 **A-COPilot**입니다.
- `63adc5621`(ST4F-610/609/205): 사용자 웹·관리자·개발 콘솔 이름/아이콘/글자로고/약관판. `frontend/apps/web/src/components/ui/brand.tsx:26`은 한국어 구구루트 / 그 외 **GuguRoute**, pin README 첫 줄도 `구구루트 (GuguRoute)`입니다. 즉 **고객 표면 브랜딩이 미착수라는 주장은 틀림**.
- `88defd2b0`: 문서·문구·주석·systemd 설명의 광범위 이름 변경. pin 루트 AGENTS:1~5·cs AGENTS:1~3은 이미 새 이름이고 유지 예외 보고서를 연결합니다. 다만 이 규칙 문서는 소문자 **guguroute**를 씁니다. 정확 GuguRoute 대소문자 일괄 통일까지 끝났다고 말하지 않습니다.
- `1c54359fe` 병합 메시지는 이름 충돌을 구구루트·GuguRoute 결정으로 처리했다고 명시합니다. 이력의 소문자 rename과 현재 고객 브랜드 표시를 구별합니다.
- **의도적 유지**: ACOP_* 환경변수, acop_cs, tripilot-* 컨테이너/모델/systemd 파일, tripilot_* MCP 도구, 로그인 쿠키/브라우저 저장 키, ID 계산 문자열, 실제 파일 경로, 과거 기록. `wiki/records/reports/2026-10-18_guguroute-rename-exceptions.md`의 설명 범위입니다. 이것은 현재 브랜드 누락과 다르며 무차별 치환 금지입니다.
- **낡은 local 원본**: 읽은 로컬 root/cs AGENTS·CLAUDE·wiki index는 아직 triPilot입니다. upstream 브랜딩 완료를 원본 반영/실배포 완료로 주장하지 않고, **원본이 오래된 base라는 증거**로 분리합니다. 이 child는 이름을 수정하지 않았습니다.

## 6. 부모 다음 통합 소유 영역 제안

1. **기준선 담당**: 다른 child가 만드는 pin candidate를 정본으로 보존. 오래된 원본의 디렉터리/handler 통째 복사 금지. 이름 변경·D-025·chat_edit/reopen_commit·최신 프론트 UI를 선행 보존 목록으로 고정.
2. **공유 계약 담당 1명**: `components/response` 순수 모델·공개 enum allowlist 및 추가 실패 의미 확정. plan_generated와 review_only를 기존 로컬 enum/consumer가 지원하는지 먼저 조정. 새 공통 계약을 기존 TeamResult reviewer 대체로 구현하지 않기.
3. **문의 담당**: 최신 read_requests의 질문별 결과를 수집하는 작은 hunk, Case/chat_reply/duplicate/_web_view. weather·time·focus·새 요청 분리의 최신 로직 유지. 변경 설명은 이력 읽기 전용으로 분리.
4. **계획 담당**: 최신 registration/reopen_commit lock·revision·중복·review_only를 보존한 실제 confirm/plan별 adapter. 새 연결로 scoped 재조회한 경우에만 registered. 응대 실패가 등록 재실행을 유발하지 않게 하기.
5. **감시 담당**: itinerary_actions의 성공/질문 기존 outbox 한 건과 실패 알림/배치 결과에 부착. TripWatcher·dawn·Case 성공/실패·제안 선택의 입력 차이 비교. 저장 성공과 배달 성공 분리.
6. **웹/세션 담당**: 최신 gateway 카드/notice changed·intake schema를 보존한 allowlist 소비. client/stream의 **좁은 dispatch hook은 한 명이 소유**. 등록 API 반환 전 fence와 반환 뒤 navigation await 경계를 따로 검증. 문의 pending race는 별도 범위를 확정.
7. **수락 담당**: pin+선별 변경의 정확 파일/시험 hash를 동결한 단일 실행. 정상 3경로의 실제 caller·저장 readback·고객 projection·후속을 각각 수락하며, 로컬 원본의 798/798·959/964 같은 과거 결과를 새 candidate 통과로 재사용하지 않기. DB/모델/HTTP/서비스/배포는 별도 승인 전 실행하지 않기.

## 7. 수행·한계

이번 bounded 독립 검토에서 Git pin/이력·README/규칙·cs wiki·실제 caller 및 local draft 계약을 비교했습니다. 제품 수락 시험의 분모는 정의하지 않았으므로 완료율을 만들지 않습니다. 소스 정적 연결 확인과 동작 보증은 다릅니다. brand SVG의 실제 화면·실시간 DB commit/outbox 배달·모델 품질·운영 적용은 검증하지 않았습니다.

도구 이슈: Python subprocess에서 git 호출은 WinError 5로 실패해 shell git의 readonly 조회로 전환했습니다. 원본 `tools/safe_git.py`는 없습니다(pin의 후속 규칙에만 존재). 도구를 원본에 복사하지 않았습니다. 후반 조회는 `GIT_OPTIONAL_LOCKS=0`을 지정했습니다. 초기 status 조회의 선택적 색인 refresh 여부를 소급 보증하지 않습니다. evidence README에 이 한계를 남겼습니다.
