---
type: contract
title: 웹 API와 남용 방어
description: 호출 주체와 책임별 REST 요청·응답 계약
status: draft
domain: travel
---

# 웹 API와 남용 방어

## 웹(고객 브라우저) — `/v1/web/*` `[2026-09-24]`

`[실측]` `app/domains/travel_ops/entry/trip_api.py` · 키 `app/domains/travel_ops/modules/web_account/web_session.py` · 저장 `web_user_keys`(마이그레이션 025).
★서버용 scope 키(테넌트 전체)를 브라우저에 넣지 않는다. 웹은 **사용자 식별 키** 하나로 **그 사용자 본인의 여행만** 연다.

| 경로 | 인증 | 뜻 |
|---|---|---|
| `POST /v1/web/session` | 없음 | 첫 방문 — 사용자와 키를 만든다. 응답 `user_key` 는 **이번에만** 나온다 |
| `POST /v1/web/session/rotate` | 키 | 새 키. **옛 키는 바로 무효** |
| `GET /v1/web/trips` | 키 | 내 여행 목록 |
| `POST /v1/web/trips` | 키 | 등록 — `/v1/trips` 와 같은 몸통에서 **`customer_id` 를 빼고** 보낸다(보내면 `422 customer_id_not_allowed`, 키가 정한다) |
| `GET /v1/web/trips/{trip_id}` | 키 | 여행 조회 |
| `GET /v1/web/trips/{trip_id}/proposals` · `POST …/{proposal_id}/choose` | 키 | 위 보류 제안과 같은 규칙 |
| `POST /v1/web/trips/{trip_id}/messages` | 키 | 자유 문장 접수·추가 답변. 에이전트 입구 `/v1/trips/{trip_id}/messages`와 같은 대화 처리기를 쓰며, 변경·후보 요청·되돌리기·지연·휴무·되묻기 업무는 **Controller → 등록된 담당 Team → 공통 적용 경로**로 진행한다. 추가 답변은 같은 Case를 재개한다. 사실·규정 답변은 별도 읽기 경로이며 일정 변경을 적용하지 않는다. 아래 「채팅 업무와 답변 재개」 참조 |
| `POST /v1/web/trips/{trip_id}/progress` | 키 | ★`[2026-10-22 ST4F-716]` 여행 화면 「끝났어요」 — 진행 중 일정을 끝내고 다음 일정을 지금 출발로 앞당기거나(`advance_trip`) 끝난 시각만 기록(`complete_item`). 채팅 진행 보고와 **같은 저장 경로**, 모델을 안 거친다. 요청 `{request_id, base_version, item_id, action}` · 다음 일정 운영시간 확인 · 오류는 [실제 여행 진행 계약](../../actions/journey-progress.md) 「웹 진행 단추」 |
| `POST /v1/web/trips/{trip_id}/reports` · `POST …/items/{item_id}/alternate` | 키 | ★`[2026-10-02]` 에이전트 입구(`/v1/trips/{id}/reports` · `…/alternate`)와 **같은 처리**(신고 지연·휴무·품절 · 다른 안으로 — 요청 몸통도 같다), **그 사용자 본인의 여행만**(남의 것 404). 모델을 안 거치는 구조화 입구다 — 개인 AI(MCP)가 쓴다([MCP 도구](../mcp-tools.md)). 남용 방어는 채팅과 같은 `message` 로 센다 |
| `POST /v1/web/warmup` | 키 | ★`[2026-09-29]` **모델 예열** — 화면이 여행·채팅 칸을 열 때 부른다(식은 모델의 첫 채팅이 34초 걸렸다). 몸통 없음. 응답 `{status: "warm" \| "warming" \| "unavailable", model, last_attempt: null \| {ok, seconds, at, reason?}, deduped?}` — 이미 올라가 있으면 `warm`(아무것도 안 함), 1분(`web_guard.warmup.dedupe_seconds`) 안 되풀이는 `warming` + `deduped: true`(다시 안 부름), 그 밖엔 응답 뒤 한 토큰 생성으로 깨우고 `warming`. **`last_attempt.ok=false` 면 모델 서버가 못 올린 것**(`reason` 에 서버가 준 이유 — 예: GPU 메모리 부족). 실제로 부를 때만 남용 방어 `warmup` 으로 센다(한도가 켜져 있으면 429/503) |
| `GET /v1/web/trips/{trip_id}/notices` | 키 | 나간 알림 전부. `type` = `guidance`(하루 시작·다음 일정·이동) · `proposal_request` · `safety_alert` · `change_notice`. ★`[2026-10-06]` `guardian` 칸(늘 있고 없으면 null) — `{changed: true}`(항로 지킴이를 켜 둔 사용자에게 **자동으로 바꿨다**는 표시) · `{offer: {label, via, path, url}}`(꺼 둔 사용자에게 가는 「다른 안」 알림의 **「항로 지킴이 켜기」**) — 아래 「항로 지킴이」. ★`[2026-10-23 사용자 지시 — ST4F-723]` `changed` 칸(늘 있고 없으면 null) — 그 알림이 바꾼 일정 「무엇 → 무엇」 — 아래 「알림 목록의 `changed`」 |
| `POST /v1/web/trips/{trip_id}/reopen` | 키 | ★`[2026-10-13]` 「일정 수정」 — 등록한 여행을 확인 화면 접수로 다시 연다 `{version}` → 접수 조회 모양 + `reopen`. 고치기는 기존 `/v1/web/trip-intakes/*`, 「완료」(`/confirm`)는 같은 여행의 새 판, 「취소」는 `/v1/web/trip-intakes/{intake_id}/cancel` — [등록한 여행 고치기](web-intakes.md#등록한-여행-고치기수정-모드--post-v1webtripstrip_idreopen--수정-접수의-confirm-2026-10-13-사용자-결정) |
| `POST /v1/web/trips/{trip_id}/guardian` | **쿠키 세션만** | ★`[2026-10-06]` 항로 지킴이 켜기 · 끄기 `{enabled, via}` → `{enabled, since, via}`. 여행 조회(`GET …/{trip_id}`)의 `guardian` 도 같은 모양 — 아래 「항로 지킴이」 |

- `[실측 2026-09-29 · 2026-10-05 확인]` `GET /v1/web/trips` 의 응답은 `{trips: [{trip_id, title, version, created_at}]}` 이며 여행 날짜 · 진행 상태 · 미확인 제안 수는 이 응답에 없다(`trip_api.py` 의 `web_list`). 직접 등록 `POST /v1/web/trips` 가 있는 것과 화면이 쓰는 것(접수 → 확인 → 생성)은 다르다.
- ★`[2026-10-04]` **브라우저는 키 대신 쿠키 세션을 쓴다** — 아래 「브라우저 세션 쿠키」. 이 절의 `키` 칸은 **쿠키 세션 또는 키**로 읽는다(둘이 같이 오면 `400 ambiguous_credentials`). `X-User-Key` 는 에이전트(MCP)와 옮겨 가는 동안의 옛 호출자용이다.
- 키는 헤더 **`X-User-Key`** 로 보낸다. 형식 `acop_u_…`. 없거나 틀리거나 거둔 키는 모두 `401`(어느 쪽인지 말하지 않는다).
- **남의 여행은 `404`** — 있는지도 말하지 않는다. 서버용 scope 키로는 웹 경로가 열리지 않는다(`401`).
- 서버는 키 원문을 저장하지 않는다(SHA-256 만). 웹은 키를 브라우저 저장소에 두고, 사용자에게 **따로 보관하라고 한 번 보여 준다.**
  브라우저 저장소는 그 페이지의 모든 스크립트가 읽을 수 있으므로 **새는 것을 전제로** 두고, 새면 `rotate` 로 끊는다.
- 브라우저 출처는 설정 `ACOP_WEB_ALLOWED_ORIGINS`(쉼표로 여럿, 기본 `http://127.0.0.1:3100,http://localhost:3100`)만 받는다.
- 키 없이 열린 `POST /v1/web/session` 은 **주소마다 한 시간에 20개**까지(`security.web_session_issue_per_hour`,
  운영 API 로 바꿀 수 있다 — 아래). 넘으면 `429 too_many_sessions` + `Retry-After`(다음 정시까지 초). 이미 가진 키로 하는 일은 막지 않는다.
  ★`[2026-09-28]` **DB 에서 센다**(`web_usage`, 마이그레이션 031) — 재시작·여러 프로세스에도 이어진다. 주소는 원문이 아니라
  `HMAC(서버 비밀키, 날짜|주소)` 로만 남고 48시간 뒤 지운다. 역방향 프록시 뒤라면 설정 `ACOP_TRUSTED_PROXIES`(쉼표)에 적힌
  주소에서 온 요청만 `X-Forwarded-For` 의 원 주소를 믿는다(비어 있으면 연결 주소).

### 알림 목록의 `changed` — 바뀐 일정(전 → 후) `[2026-10-23 사용자 지시 — ST4F-723]`

`GET /v1/web/trips/{trip_id}/notices` 의 알림마다 `changed` 칸이 있다(늘 있고, 없으면 `null`). 그 알림이 일정을 「무엇 → 무엇」으로 바꿨을 때만 **목록**이다 — 감시 묶음 알림은 한 통에 여러 일정을 바꾸므로 한 건짜리 알림도 같은 목록 모양(한 줄)으로 낸다.

| 칸 | 형식 | 뜻 |
|---|---|---|
| `item_id` | UUID 문자열 · null | 바뀌기 **전** 일정 id. 감시 묶음 알림(항목마다)과 고른 제안의 변경 알림에 있다. 그 밖의 한 건짜리 변경 알림에는 적혀 있지 않아 `null` |
| `new_item_id` | UUID 문자열 · null | 바뀐 **뒤** 일정 id. 고른 제안(`…/proposals/{id}/choose`)의 변경 알림에만 있다 — 고르면 그 일정이 새 id 로 들어가므로(`Item.replaced_by`) 같은 알림의 `proposal_id` 로 닫힌 제안과 지금 일정을 잇는다 |
| `from` · `to` | 문자열 · null | 바뀌기 전 · 뒤 이름 — 장소(활동 · 식당 · 숙소 · 항공 후보)면 그 이름, 이동 수단 변경이면 수단 이름 |
| `at` | ISO 시각(서울 `+09:00`) · null | 바뀐 일정의 시작 시각. 이동 수단 변경 알림에는 없다(`null`). 여행 조회의 `starts_at` 처럼 서울 시각으로 바꿔 낸다(같은 순간) — ISO 시각으로 읽을 수 없는 값은 적힌 그대로 |

- 서버가 알림을 만들 때 적어 둔 값(알림 payload 의 `changed{from, to, at}` · 감시 묶음의 `changes[]{item_id, changed}`)만 옮긴다 — 적혀 있지 않은 칸을 채우지 않는다.
- `null` 인 알림: 등록 · 안내(하루 시작 · 다음 일정 · 이동) · 선택 요청 · 안전 알림 · 서비스 공지, 그리고 「무엇 → 무엇」이 아닌 변경(되돌리기 `rollback_to` · 진행 「끝났어요」 `progress` · 이름만 받은 목적지 `requested_place` · 일정 수정 「완료」 `edit`).
- 이 변경 전에 나간 고른 제안 알림에는 `item_id` · `new_item_id` 가 적혀 있지 않다(`null`). 그 판의 일정(`chosen_version`)에서 `replaces_item_id` 가 제안의 `item_id` 인 일정이 바뀐 뒤 일정이지만, 이 칸을 위해 거슬러 찾지는 않는다.
- 구현 `app/domains/travel_ops/entry/trip_api.py` `_notice_changed` · 고른 제안의 두 id `components/planning/pending.py` `choose` · 시험 `tests/unit/travel/test_notice_center_server_text.py`.

**알림 문장 고침** `[2026-10-23 사용자 지시 — ST4F-723]` — 웹 알림 센터가 서버 문장을 그대로 보이는 자리의 결함:
- 자동 변경(활동 대체) 「{날} {오전·오후} {장소}{은·는} {이유}, {새 장소}{으로·로} 변경됩니다.」 — **{날}** 은 그 일정의 서울 날짜를 알림을 만든 때와 견줘 `오늘` · `내일` · 그 밖은 `10월 25일(일)`(채팅 답의 날짜 표기 `trip_facts._day_label` 과 같다). 전에는 늘 「오늘」이었다. **조사**는 앞 낱말의 마지막 글자 받침으로 고른다(ㄹ 받침은 「로」 · 한글이 아닌 글자로 끝나면 받침 없음으로 본다 — `components/intake/review.eun` · `ro`, 진행 「끝났어요」 문장과 같은 도우미). 전에는 「는」 · 「으로」 고정이었다.
- 고객 문장에 마크다운 별표(`**`)를 넣지 않는다 — 감시의 「일정은 그대로 두었어요」 세 문장(`trip_watch_batch._line`)과 조건을 푼 안을 묻는 문장(`watch_relaxed.relaxed_text`)에 남아 있어 웹이 별표를 그대로 보였다.
- 제안 안의 경고 해요체 · 안 고르기 거절 문장 — [보류 제안](trips.md#보류-제안--v1tripstrip_idproposals-2026-09-24).

### 채팅 업무와 답변 재개 `[2026-10-11 코드 확인]`

서비스 기능·사용법 질문은 일정 질문과 분리한 읽기 행동 `answer_service`로 운영 지식을 검색한다. 대상·출처·실패 처리와 별도 지식 적재는 [고객 채팅 기능 안내](../service-chat-help.md)를 따른다.

웹 JSON·웹 SSE·에이전트 메시지 입구는 `trip_messages.handle_trip_message`를 함께 쓴다. 해석 결과를 만드는 것과 업무를 실행하는 것은 다르다. 변경 업무는 `case_dispatch`가 담당 Team의 가용성과 capability를 확인한 뒤 `Controller.run_case`로 전달한다. 로컬 실행기는 `Team.execute`를 호출하며, Team은 계산·제안만 하고 공통 적용기가 일정·알림을 적용한다. Team이 꺼졌거나 적재되지 않았으면 `503 team_unavailable`이며 기존 직접 계산 경로로 대신 실행하지 않는다. 저장된 여행을 읽는 독립 조회는 계속 사용할 수 있다. [플러그인 가용성 계약](../../teams/team-contract/plugin-availability.md).

**요청 본문** — 두 메시지 입구가 같은 `MessageIn`을 받는다. 웹은 쿠키 세션 또는 사용자 키, 에이전트 입구는 `trip:write` scope를 사용한다.

| 칸 | 형식 | 규칙 |
|---|---|---|
| `request_id` | 빈 문자열이 아닌 문자열 | 요청 한 번의 멱등 식별자. 추가 답변에는 새 값을 보내고 같은 답변의 재시도에는 같은 값을 보낸다 |
| `message` | 빈 문자열이 아닌 문자열 | 새 요청 또는 추가 답변 원문. 답변은 Controller를 거쳐 담당 Team의 입력에 전달된다 |
| `at` · `item_id` · `location` | 선택 | 처리 시각 · 선택한 일정 UUID · 현재 위치. 위치의 형식·보유 경계는 [현재 위치 계약](web-intakes.md) 참조 |
| `case_id` | 선택 UUID | 답변할 업무. 생략하면 같은 여행·고객의 저장된 질문 형식에 명확히 맞는 답변만 자동 연결한다. 여러 업무에 동시에 맞으면 `409 state_conflict`. 새 문의·새 변경 요청은 이전 대기를 소비하지 않는다 |
| `resume_token` | 선택, 빈 문자열이 아닌 문자열 | 대기 응답에서 받은 재개 토큰. 없으면 인증된 여행 소유 고객의 입력 대기를 재개한다 |
| `expected_version` | 선택, 0 이상 정수 | **Case 버전**의 동시성 확인값. 여행 일정 버전이 아니다 |

모르는 칸은 `422`다. 다른 고객·여행의 `case_id`는 `404 not_found`, 잘못된 재개 토큰은 `401 invalid_resume_token`, 상태·버전 충돌은 `409 state_conflict`, 답변 값 오류는 `422 invalid_customer_input`이다. 같은 최초 `request_id`에 다른 메시지를 보내는 것도 `409`다.

**응답** — `answer`는 고객에게 보일 문장이다. Team 업무의 정상 응답에는 `{case_id, case_status, version, classification, status, reason, outcome, answer}`가 있다. `version`은 Case 버전이고, 일정이 실제 적용됐을 때의 `outcome.version`은 여행 일정 버전이다. 사실 답변·해석 실패·중복 응답은 이 Team 응답과 칸이 같지 않으며 `version`·`outcome`을 항상 반환한다고 가정하지 않는다. `report`도 공통 필수 칸이 아니다(현재 품절 상품 추천 응답의 별도 칸은 유지한다).

| 확인할 칸 | 뜻 |
|---|---|
| `case_status: "waiting_input"` | 업무가 끝나지 않고 고객 답변을 기다린다. `required_input_schema`가 추가되며, 발급된 경우 `resume_token`, 선택지가 있으면 `choices`도 온다 |
| `status: "clarify"` · `"ask_rollback"` · `"asked"` | 화면에 보여 줄 되묻기·되돌리기 확인·선택 안내. 이 값만 보고 업무 완료로 판단하지 않고 **`case_status`를 함께 읽는다** |
| `status: "adjusted"` · `"rolled_back"` | 공통 적용 결과로 일정이 변경됐거나 되돌아갔다 |
| `status: "duplicate"` | 같은 요청의 재시도이며 재실행하지 않았다. 최초 접수의 중복 응답은 저장된 답과 `case_id`·`case_status`만 돌려줄 수 있다 |

예: 첫 요청이 「늦어요」여서 `case_status: waiting_input`·`status: clarify`·`required_input_schema.required: ["minutes"]`를 받았다면, 새 `request_id`와 같은 `case_id`로 `message: "30분이요"`를 보낸다. 답변 본문과 이력이 같은 Case에 저장돼 담당 Team이 이어서 처리하며, 입력이 여전히 부족하면 다시 `waiting_input`이다. `case_id` 없이도 「30분이요」처럼 저장된 질문에 명확히 맞는 답은 자동 연결한다. 「식당 주소 알려줘」 같은 새 문의는 별도 Case로 처리한다. 자유 답변을 이전 업무에 연결하려면 `case_id`를 명시한다.

명시한 업무·토큰의 만료는 기존 `401 invalid_resume_token`을 유지한다. 명시 연결이 없는 자동 답변이 만료됐다면 이전 업무에는 `WAIT_EXPIRED`를 기록하고 그 메시지는 새 요청으로 해석한다. 꺼진 담당의 사전 거절은 이전 업무와 토큰을 보존하며, 관계없는 새 문의까지 막지 않는다. 보완의 검증 범위는 [대기 업무 분리 계획](../../records/plans/2026-10-11_2325_conversation_isolation.md)에 기록한다.

**최초 접수의 실패·동시 재시도** — 새 업무의 해석 결과와 실행 계획은 담당 가용성 검사 전에 저장한다. 담당 부재로 `503`을 받았다면 같은 `request_id`와 같은 메시지를 재전송할 수 있다. 담당이 다시 준비됐고 진행 중인 실행이 없으면 같은 Case와 저장한 계획으로 재시도한다. 진행 중인 업무에 이미 추가 답변 이력이 있거나 일정 기준 버전이 달라졌거나 실행 중이면 `409`이며 이전 계획을 새 일정에 임의 적용하지 않는다. 대기·종료된 업무의 재전송은 기존 결과를 반환한다. 실행 계획이 없는 옛 미완료 업무를 자동으로 추정해 실행하지 않는다.

동시에 최초 접수돼도 같은 고객·여행·`request_id`의 Case 생성과 적용은 하나다. 기존 `action_requests`의 멱등 기록과 짧은 생성 트랜잭션을 사용한다. 생성에서 늦은 요청은 `409`를 받고 같은 요청 번호로 기존 업무를 다시 확인한다. 해석은 생성 전에 수행하므로 동시에 들어온 최초 요청은 모델을 두 번 호출할 수 있다. 모델 호출까지 한 번이라는 보장은 아니다. 새 업무는 메시지 원문의 SHA-256을 비교해 개인정보 가림 결과가 같은 서로 다른 원문도 충돌로 거절한다. 이 해시가 없는 기존 업무의 재전송은 종전의 가린 메시지 비교를 유지한다. 같은 메시지의 `at`·`item_id`·`location` 변경을 요청 충돌로 판정하지는 않으며 처음 저장한 계획을 유지한다. 시각·대상·위치를 바꾸려는 새 요청에는 새 `request_id`를 보낸다.

웹의 `Accept: text/event-stream` 응답은 `result` 이벤트에 같은 최종 JSON을 싣는다. 스트림이 열린 뒤의 실패는 `error` 이벤트로 받으므로 HTTP 상태만 검사하지 않는다. `basis`·`basis_sources`·`decision`은 웹의 `web.dev_mode=on`일 때만 공개한다. 해석 설정과 대화 기록은 [채팅 해석과 팀 업무](web-intakes.md) 참조.

구현 확인: `app/domains/travel_ops/entry/trip_api.py`의 `MessageIn`·`message`·`web_message`·`_web_message_result`, `components/conversation/case_dispatch.py`의 `execute`·`resume_pending`·`response`. 이 절은 공유 코드 계약이다. 이번 운영 적용 대상과 확인 범위는 [최종 운영 기록](../../records/reports/2026-10-12_0236_team_plugin_operating_release.md)의 고정 manifest를 따른다. 별도 기능 개편까지 모두 배포됐다는 뜻은 아니다.

### 남용 방어 — 횟수 제한 · 사람 확인 `[2026-09-28]`

`[실측]` `app/domains/travel_ops/modules/web_account/web_guard.py` · `web_limits_api.py` · `app/infrastructure/turnstile.py` · 저장 `web_usage` ·
`runtime_limits` · `runtime_limit_events`(마이그레이션 031). 계획 `records/plans/2026-09-28_2130_웹_남용방어_실행계획.md`.

**비싼 작업 횟수 제한.** 대상 — `POST /v1/web/trip-intakes`(`intake`) · `…/{id}/plan`(`plan`) · `…/{id}/confirm`(`confirm`) ·
`POST /v1/web/trips`(`trip_create`) · `POST /v1/web/trips/{id}/messages`(`message`). 키(사용자)당 · 주소당 · 서비스 전체의 **하루**(KST) 횟수.
- ★**기본 꺼짐**(`web_guard.limits_enabled: false` — 개발 단계, 사용자 결정 2026-09-28). 꺼져 있어도 **세기는 한다**(운영 API 의 오늘 사용량).
- 켜지면 입력 검사를 통과한 뒤 · 일을 시작하기 전에 한 칸을 확보한다. 일이 실패해도 한 번으로 센다.
- 키·주소 한도 → `429 usage_limit` + `Retry-After`(다음 KST 자정까지 초), 본문 `{limit: per_key|per_ip, action, used, cap, retry_after_seconds}`.
- 서비스 전체 한도 → `503 service_daily_cap` + `Retry-After`. 사용자 잘못이 아니라 가른다.
- 제안 기본값과 산정 근거는 `config/guardrails.yaml` `web_guard.limits` 주석(전부 `[추정]`).

**서비스 모드 — 회원 · 게스트 한 시간 한도 `[2026-10-22 사용자 지시]`.** 결정 [D-CS-020](../../decisions/D-CS-020-service-mode-hourly-limits.md).
- 운영 설정 `service.mode_enabled`(기본 **꺼짐** — 지금은 시험 단계). 켜면 ①위 하루 한도가 함께 켜진다(`web.limits_enabled` 를 따로 켜지 않아도) ②**사람(키) 한 명의 한 시간** 횟수 한도가 더해진다.
- 등급: **회원**(소셜 로그인이 붙은 계정 — 지금 유료 등급은 없다) · **게스트**(로그인 안 함, `guest_policy.is_guest`). 이름 `service.<member|guest>.<작업>.per_hour`(작업 = 위 하루 한도와 같은 10개). 기본값은 가드레일 `web_guard.service_mode.per_hour`(우리가 고른 값 — 게스트가 늘 더 적다), 범위 1~100000.
- QA 예외 계정(`usage_exempt`)은 등급 한도를 받지 않는다. 꺼져 있으면 한 시간 칸은 세지도 않는다(DB 를 더 부르지 않는다).
- 넘으면 → `429 hourly_limit` + `Retry-After`(다음 정시까지 초), 본문 `{limit: member_hour|guest_hour, action, used, cap, retry_after_seconds}`. 막힌 요청은 하루 칸도 올리지 않는다(한 트랜잭션).
- 화면 문구: 웹 `error-text.ts` `hourly_limit` — 게스트면 「로그인하면 더 쓸 수 있어요」를 붙인다. 관리 콘솔 「운영 설정」의 「서비스 모드」 칸(스위치 + 작업 × 등급 표)에서 바꾼다.
- 시험 `tests/e2e/test_web_guard_service_mode.py`.
- `[2026-10-23]` 확인 화면 경로 후보 「더 보기」(`GET …/trip-intakes/{id}/moves/{pair}/routes`)와 경로 고르기(`POST …/route`)는 **`move_judge`** 칸으로 센다 — 카카오 · 유료 소스를 부르지 않고 시간표 계산기만 쓴다([web-intakes 「경로 후보 더 보기 · 고르기」](web-intakes.md)). 수단 고르기(`…/options` · `…/mode`)는 종전대로 `place_search` 다.

**사람 확인(Cloudflare Turnstile).** `POST /v1/web/session`(헤더 `X-Turnstile-Token` 또는 JSON `{"turnstile_token"}`) ·
`POST /v1/web/trip-intakes`(폼 칸 `turnstile_token`). 서버가 `siteverify` 에 비밀키·토큰·원 주소를 보내 확인한다.
- 설정 `ACOP_TURNSTILE_SECRET` 이 있으면 **늘 확인한다.** 토큰이 없거나 실패 → `403 human_check_failed`(`reasons` = Cloudflare `error-codes`).
  Cloudflare 에 닿지 못하면 → `503 human_check_unavailable`(통과시키지 않는다). `ACOP_TURNSTILE_HOSTNAMES`(쉼표)를 두면 `hostname` 도 본다.
- 비밀키가 없으면: `ACOP_TURNSTILE_REQUIRED=true` 또는 `ACOP_ENV=prod` 면 **서버가 뜨지 않는다**. 아니면(개발) 확인을 건너뛰고
  응답에 `human_check: "skipped"` 를 싣는다. 확인했으면 `human_check: "passed"`.
- 개발 시험 키(Cloudflare 공개, `[확인 2026-09-28]` developers.cloudflare.com/turnstile/troubleshooting/testing): 비밀키
  `1x0000000000000000000000000000000AA` 항상 통과 · `2x0000000000000000000000000000000AA` 항상 실패 ·
  `3x0000000000000000000000000000000AA` 「이미 쓴 토큰」. 시험 사이트키는 토큰 `XXXX.DUMMY.TOKEN.XXXX` 를 낸다.
  토큰은 5분 유효 · 한 번만 확인된다 · 최대 2,048자.

**빈 키 정리 — `[2026-10-04]` 걷었다.** 옛 규칙(여행 0건인 키만 · 기본 꺼짐 — 2026-09-29 「키는 그 사용자를 알아보는 유일한 수단이라 지우지 않는다」)을 **게스트 정리**가 대신한다 — 아래 「게스트 · 여행 삭제 · 게스트 정리」. 같은 되잡기 단계가 48시간 지난 주소 줄과 35일 지난 사용량 줄도 지운다.

**운영 API — 제한값 보기·바꾸기.** ★`[2026-09-29]` **운영 앱**(127.0.0.1:8070, [D-CS-008](../../decisions/D-CS-008-ops-console-separate-app.md))에 있다 — 고객 API 앱(8042)에는 없다(404). 바꾼 값은 DB 라 고객 앱이 30초 안에 읽는다. scope `limits:read`(보기) · `limits:write`(바꾸기). ★scope 키를 브라우저에 두지 않는다 —
운영자 로그인을 확인한 **콘솔 서버**가 부르고 `actor`(운영자 id)를 싣는다. API 는 그 값을 믿는다(한계 — 감사 줄에 키 id 도 남긴다).

```
GET   /admin/limits                      scope limits:read
  200 {"revision": 3, "applies_within_seconds": 30,
       "limits": [{"name": "web.intake.per_key_day", "label": "…", "unit": "회", "type": "int",
                   "value": 4, "default": 4, "min": 1, "max": 100000,
                   "source": "default"|"override", "updated_at": null|"…", "updated_by": null|"…"}, …],
       "usage_today": {"day": "2026-09-28", "all": {"intake": 3, "plan": 1, …}}}   // 키·주소별은 싣지 않는다

PATCH /admin/limits                      scope limits:write
  요청 {"expected_revision": 3, "actor": "운영자 id", "reason": "…(필수)",
        "changes": {"web.limits_enabled": true, "web.plan.per_key_day": null}}      // null = 기본값으로
  200 GET 과 같은 모양(revision + 1)
  409 stale_revision {current_revision} · 422 unknown_limit | out_of_range | wrong_type | reason_required | actor_required
  401/403 scope

GET   /admin/limits/events?limit=50      scope limits:read
  200 {"events": [{"at", "revision", "actor", "key_id", "name", "old", "new", "reason"}, …]}   // 새것부터
```
- 이름: `web.limits_enabled` · `web.<intake|plan|confirm|trip_create|message|warmup>.<per_key_day|per_ip_day|service_day>` ·
  `web.session.per_ip_hour` · `web.guest_idle_hours` · `web.member_idle_hours` · `web.session_max_hours` · `web.guest_cleanup_enabled`(★`[2026-10-04]` 옛 `web.idle_key_*` 를 대신한다) ·
  ★`[2026-10-22]` `service.mode_enabled` · `service.<member|guest>.<작업>.per_hour`(위 「서비스 모드」). 기본값·범위는 가드레일, 바꾼 값은 `runtime_limits`.
- 바꾼 값은 각 프로세스가 최대 30초 캐시해 늦게 반영된다(`applies_within_seconds`). 감사 줄(`runtime_limit_events`)은 고치지도 지우지도 못한다(트리거).
- 시험 `tests/e2e/test_web_api.py` 10건.


## 관계

- [REST 안내](index.md) — 계약 지도


최종 대기·재개·초기 접수 경합의 실행 근거와 운영 반영 상태는 [최종 운영·검증 보고서](../../records/reports/2026-10-12_0236_team_plugin_operating_release.md)에 기록합니다. 격리 후보 통과를 운영 반영으로 해석하지 않습니다.


### 숫자 답변의 최근 대화 연결 — 2026-10-12 후속 보완 계약

업무 ID·토큰을 명시하지 않고 숫자만 답한 경우에는 질문 형식뿐 아니라 최근 안내의 업무도 확인합니다. 최근 assistant 기록의 업무 ID가 있는 경우 해당 업무의 대기만 자동 연결합니다. 새 사실 안내 뒤의 “1번”을 예전 선택 질문의 답으로 소비하지 않습니다. 명시한 업무 ID·토큰과 이미 연결된 같은 재개 요청의 재전송은 기존 소유권·버전·토큰 검증을 유지합니다. 최근 assistant 기록이나 업무 ID가 없는 옛 대화는 기존 질문 형식 판정과 다중 후보 거절을 유지합니다. 자유 문장과 단위가 명확한 답변의 범위를 이 규칙으로 넓히지 않습니다.

수정·실행 검증과 운영 반영은 분리합니다. [재현·보완 범위](../../records/reports/2026-10-12_0159_plugin_read_recovery_followup.md). 최신 운영 적용과 읽기 확인 범위는 [최종 기록](../../records/reports/2026-10-12_0236_team_plugin_operating_release.md)을 따릅니다.


### 중단된 사실 조회의 동일 요청 복구 — 2026-10-12

위치에 의존하지 않는 `answer_fact`의 중단은 저장한 읽기 해석·시각·대상·일정판과 문맥 ID를 검증해 같은 Case에서 이어간다. 같은 `request_id`의 재전송은 원문 해시 또는 종전 가린 문장 확인을 먼저 통과해야 한다. 재전송의 새 시각·대상으로 원래 해석을 바꾸지 않고 모델·Team을 다시 호출하지 않는다. 새 복구 정보에는 원문·GPS를 저장하지 않는다.

처리 중인 같은 Case는 NOWAIT 잠금 경합으로 409다. 최초 입력의 일정판뿐 아니라 문맥 조회와 실제 답변 조회의 두 판도 처음 저장한 판과 일치해야 한다. 변경됐다면 409이고 업무를 재해석하거나 이전 대상과 새 일정을 섞지 않는다. 부가 장소 조회의 rollback은 별도 조회 연결에 한정하여 Case 잠금·전이를 보존한다.

위치 의존 질문·저장 근거가 없는 옛 미완료 조회는 자동 복구하지 않는다. 원래 읽기 답이 안전하게 저장된 경우에는 그 답을 그대로 반환한다. 옛 off/defer의 classifying 답은 저장된 문자열과 결정적 사실 질문, 변경 업무·추가 답변 이력 부재가 확인된 좁은 경우만 반환하며 새 계산은 하지 않는다. 실제 변경 업무의 실행 계획·진행 실행·추가 답변 검증은 기존 계약을 유지한다.

공개 충돌 응답은 기존 `409 state_conflict`와 고정 문구 「업무 상태가 바뀌었거나 답변할 업무를 지정해야 합니다」다. 내부 예외의 세부 안내가 그대로 노출된다고 가정하지 않는다. 충돌 뒤 시각·대상·현재 일정에 맞게 다시 물을 때에는 새 `request_id`를 보낸다.

실행 근거: [최종 모델 검토·두 경계 재현](../../records/reports/2026-10-12_0233_v11_v12_read_recovery_cli_review.md), [고정 후보·운영 확인](../../records/reports/2026-10-12_0236_team_plugin_operating_release.md).
