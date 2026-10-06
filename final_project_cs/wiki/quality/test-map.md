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
| **이름 없는 줄(종류 + 지역만)** — 줄을 조각으로 읽기(평가 줄 40개 · 새 말은 표에 한 줄 · 지명 사전 우선순위) · `needs_choice`/`needs_name` · 같은 종류만 후보 · 지역 중심 · 예약한 일정 보호(`kept: booked`) · `booking` 줄 · `category` · 고른 곳 문장 `[2026-10-03 ui 요청서 1번]` | `unit/travel/` · `e2e/` | `test_line_parts.py` (53건) · `test_intake_nameless_read.py` (7건) · `test_intake_nameless_lines.py` (8건) |
| **웹 소셜 로그인(구글)** — 시작 → 콜백 → 표 교환 한 바퀴 · 연결 · 해제 · 로그인 CSRF 막기 · 일회용 표 · state 한 번 · 이름 · 이메일 저장 없음 · 사람 확인 · 한도 · ID 토큰 서명 · nonce · 대상 확인 `[2026-10-03 ui 요청서]` | `e2e/` · `unit/travel/` | `test_web_social_login.py` (17건) · `test_oauth_providers.py` (15건) |
| **웹 브라우저 세션(HttpOnly 쿠키)** — 게스트 세션 발급(속성 · 해시만 저장) · 쿠키로 열기 · 쿠키+키 동시 400 · 모르는 쿠키 401 + 지우기 · CSRF(Origin · 토큰 · 읽기 면제 · 세션 묶임) · 유휴/절대 수명 · 운영자 설정 즉시 적용 · 로그아웃 · 옛 키 옮기기 · 소셜 교환 쿠키 모드 · 회원 수명 `[2026-10-04 D-CS-011]` | `e2e/` | `test_web_cookie_session.py` (27건) |
| **여행 삭제 · 게스트 제한 · 게스트 정리** — 즉시 완전 삭제(외래키 없는 표 · 전용 장소 · 바깥함) · 같은 404 · 열린 Case 정상 전이로 닫기 · 여행 번호 표 목록 빠짐없음 · 게스트 1개(동시 생성) · 기간 상한 · 에이전트 고객 제한 없음 · 감시 대상에서 게스트 제외 · 만료 게스트만 삭제 · 일정 남은 게스트 보존 · 상한은 마지막 사용 기준 · 기록이 가리키면 사용자 행만 남김 · 설정 끄기/보존 시간 · 계획서 내려받기 `[2026-10-04 D-CS-011]` | `e2e/` | `test_guest_and_trip_delete.py` (16건) |
| **디스코드로 연결** — 설정 없으면 `available:false` · `start` 404 · 한 바퀴(권한 `webhook.incoming` 하나 · 콜백 주소 · 가린 저장 · `untested`) · 같은 `state` 두 번 · 11분 · 모름 · 다른 흐름 → `expired`(디스코드에 안 묻는다) · 취소 `cancelled` · 토큰 교환 실패 9종 `failed`(기존 웹훅은 그대로) · 토큰 · 비밀값이 DB · 로그에 없음 · 다시 연결하면 교체 · 남의 `state` 는 그 사용자에게만 · 쿠키면 CSRF · 사용자당 한도 | `e2e/` | `test_discord_connect.py` (28건 · 디스코드는 mock 서버) |
| **텔레그램으로 알림 받기** — 설정 없으면 `available:false` · `start` 404 · 웹훅 늘 401 · 한 바퀴(링크 · `/start <코드>` → `connected` · `notice_channel=telegram` · 봇 인사 · 대화 번호는 어느 응답에도 없음) · 같은 코드 두 번 · 11분 · 모르는 코드 · 비밀 헤더 없음/틀림 401 · 같은 업데이트 재전송은 한 번만 · 다른 사용자에게 묶인 대화 · 아무 글이나 고정 문장(모델 0 · 글이 DB · 로그에 없음) · 그룹 무시 · 차단 `blocked` · 해제 `untested` · `DELETE` · `PUT notice_channel`(422) · 디스코드 연결하면 알림 받는 곳 이동 · 시험 발송 4갈래 · 한도 · 동의 게이트 · **알림 채널 동의 철회가 대화 번호도 지움** · 평문 비밀값 없음 `[2026-10-05]` | `e2e/` | `test_telegram_connect.py` (35건 · 텔레그램은 mock 서버) |
| **텔레그램 클라이언트(`sendMessage`)** — 2xx · 429(헤더/본문/없음/900초 초과·음수) → `RetryAfter` · 403 · 400 chat not found → `ChatUnavailable`, 그 밖 400 · 401 · 5xx 는 막힘이 아님 · 시간 초과 · 연결 오류 · 4096자 자르기 · 빈 본문 · 예외 · 로그에 토큰 · 대화 번호 · 본문 없음 · `httpx` 요청 주소 로그 필터 `[2026-10-05]` | `unit/travel/` | `test_telegram_client.py` (47건 · mock 서버) |
| **라우팅 재배분**(D-CS-014) — 지어낸 팀 거부 · 되묻기 **정확히 1회** · 「못 고르겠다」 존중 · 모르는 요청 종류는 버림 · 고를 것이 없으면 모델 호출 0 · **코어가 등록부에 다시 묻는지** · 꺼 둔 팀은 후보 제외 · 모델이 죽어도 Case 는 종전대로 · 재배분기를 안 꽂으면 아무것도 안 바뀜 `[2026-10-06]` | `unit/travel/` | `test_routing_reroute.py` (10건) |
| **고객별 알림 발송** — 스위치 꺼짐이면 옛 동작 · 켜짐+텔레그램/디스코드 한 곳에만 · 번역 · `[재생]` · 연결 없음 · 여행 지워짐 · 허용 안 된 테넌트 · 키 모양 이상 · 동의 게이트 · 저장값 못 풂 · 오염된 웹훅 주소는 호출 안 함 · 막힘 `blocked` · 거부 `invalid` · 429 · 5xx · 시간 초과 · 토큰 없음 · 한도 · 로그 · **실제 `OutboxWorker.process_once` 한 바퀴**(delivered · skipped · pending · unknown · dead_letter) `[2026-10-05]` | `e2e/` | `test_notice_routing.py` (48건 · 텔레그램 · 디스코드는 mock 서버) |
| **텔레그램 웹훅 등록 스크립트** — `setWebhook` 요청 모양 · https 아님 · 허용 밖 포트 · 비밀값 모양 · 설정 누락은 호출 전 중단 · 출력에 토큰 · 주소 · 비밀값 없음(텔레그램 설명에 섞여 와도) · `--info` · `--delete` · 연결 실패 `[2026-10-05]` | `unit/travel/` | `test_telegram_set_webhook.py` (37건 · mock 서버) |
| **소스별 호출 예산(DB)** — 안쪽 제한기 먼저 · 목록 밖 소스는 DB 안 부름 · 예산이 차면 `BudgetExhausted`(미스 이유 `budget_exhausted` · 호출 안 함) · DB 오류 `allow`/`refuse`(경과 시간 · 재시도) · 80% 경보 · 95% 위험(`essential_only`) · **실DB**: 한국 자정 경계(일 · 월 · 자정까지 초) · 새 프로세스가 이어서 셈 · 8스레드 상한 · 월 줄이 차면 하루 줄도 안 오름 · 실패 · 거절 칸 · 여유율 보고 · 일꾼 5번 새로 떠도 3번만 호출 · 조립이 ITS · UTIC 에 얹음 · `build_gate` · **제공처 한도 초과 신호(ITS 4001)가 월 줄을 멈추고 한도를 기록 · 그날 자정까지 정지 · 다음 날 한 번 시험 · 달이 바뀌면 풀림** | `unit/travel/` · `integration/db/` | `test_source_budget.py` (24건) · `test_source_budget_db.py` (12건) |
| **약관 동의 기록 · 게이트** — 게이트 꺼짐이 기본(아무것도 안 바뀜) · 켜면 필수 미동의 403 `consent_required`(면제 길 통과) · 선택 항목은 안 막음 · 버전이 오르면 다시 동의(옛 버전 `POST` 409) · 기록은 추가만(동의→철회→동의 3줄 · 해시 저장 · 주소 원문 없음 · DB 가 UPDATE/DELETE 거절) · 같은 동의 반복은 줄 안 늚 · 입력 검사 7종(하나라도 틀리면 전부 안 기록) · 철회 효과(웹훅 삭제 · 식사 답 삭제 · 실패하면 기록도 되돌림) · 옛 키 · 에이전트 키(키 주인 따름 · 기록은 못 함) · CSRF · 보관 기간 정리 | `e2e/` | `test_consents.py` (24건) |
| **재난 시 일정 정지 · 대피 안내 · 다시 시작** — 분류(지진 규모로 그날/전체 · 긴급재난+위험 재해 = 그날 · 위급재난 · 전쟁 낱말 · 화산 = 전체 · 모르는 구분(기타)도 낱말로 · 일상 문자 · 날씨 재해 · 훈련 · 해제 · 규모 모르는 지진은 정지 안 함 · 전체가 그날보다 앞섬 · 대피 장소 종류 · 끄면 정지 안 함) · 재난문자 판정(심각 낱말 포함 · 훈련 제외 · 실종 문자 무변화 · 해제 조회 · 샘플 기간 밖은 모름) · 적재 스크립트(열 이름 후보 · 필수 열 없으면 중단 · 좌표 나쁜 줄 건너뛰고 셈 · 지역 거르기 · CP949) · **DB**: 지진→그날 정지(자정에 풀림) · 감시 · 안내 반복(`due` · `active_trip_ids` · 감시 한 틱)이 정지한 여행을 건너뜀 · 안전 알림이 안전을 앞세우고 표에 있는 대피 장소만(가까운 순 · 반경 · 걷는 시간 추정 · 자료 출처 · 일정 장소 기준 명시) · 같은 사건 두 번 안 멈춤 · 어제 사건 무시 · 전쟁→여행 전체 + 민방위 대피소 · 큰 지진 · 그날 정지가 전체로 올라감 · 자료 없음/근처 없음/화재(목록 없음) 정직한 문구 · 조회 실패는 정지 안 함 · 일상 문자 정지 안 함 · 해제 알림 한 번(정지는 그대로 · 다른 사건의 해제는 무시) · 다시 시작(같은 사건으로 재정지 안 함 · 새 사건은 정지) · 여행 조회 `safety` · `items[].paused` · 다시 시작 입구(본인만 · 남의 것 404 · 일정 불변) · 웹 알림의 안전 칸 · 여행 삭제 CASCADE · **아직 시작하지 않은 여행**(심각한 사건이면 사용자가 풀 때까지 정지 · 대피 장소 없는 안내 글 · 그날 정지 단계는 안 멈춤 · 규모 6 지진은 멈춤 · 일상 문자/조회 실패는 안 멈춤 · 조회 `safety.phase`) `[2026-10-06 사용자 결정]` | `unit/travel/` · `e2e/` | `test_safety_classify.py` · `test_disaster_msg_safety.py` · `test_load_safety_shelters.py` · `test_safety_pause.py` (29건 · 로컬 개발 DB 실제 SQL, 점검은 흉내 — 실제 재난문자 · 지진 확인 아님) |
| **항로 지킴이 켜기 · 끄기** — 켜기 = `replace` · 끄기 = `ask_first` **명시** + 둘 다 `survey_answered`(직접 고른 것) · 안 답한 여행에 끄기(건너뛰기)가 처음 「직접 골랐다」로 기록(미응답은 휴무 · 통제를 자동 적용) · 같은 값 반복은 행 · `since` 불변 · **쿠키 세션만**(키 403 · 인증 없음 401 · CSRF 없음 403) · 남의 여행 = 없는 여행 404 · 몸통 5종 422(`enabled` 는 JSON 참 · 거짓만) · 옛 여행 불변(`null`) · 등록 때 고른 값은 `registration` · 고정한 일정은 켜져도 먼저 묻기 · 여행을 지우면 기록 CASCADE · 기록 고치기는 트리거가 거절 · **알림**: 자동 변경 + 켜짐일 때만 `{changed}`(고객이 고른 변경 · 켜 두지 않은 여행 · 끈 뒤에는 없음) · 꺼진 사용자의 「다른 안」 알림에만 `{offer}`(고정 · 안전 · 「바꿀까요?」 · 대안 없음 제외) · 웹 알림 목록의 `guardian` 칸 · Case 버전 길도 같은 규칙 · 디스코드 · 텔레그램 글에 계획서 링크 앞 줄(없으면 문구 불변) `[2026-10-06 사용자 결정]` | `e2e/` | `test_trip_guardian.py` (25건 · 로컬 개발 DB 실제 SQL — 실서버 확인 아님) |
| **MCP 읽기 도구 둘 — 일정 위험 점검 · 이동 판정** — 항목마다 `problem`/`clear`/`unknown`(**확인 불가를 문제 없음으로 말하지 않음** · 해당 없음은 확인 불가 아님 · 문제가 있으면 못 확인한 종류도 따로) · 캐시만 읽는 호출은 **새로 묻는 점검기를 안 부르고 횟수도 안 셈** · fresh 는 3항목까지·세고·제한이 켜지면 429 · 점검기 없는 서버 503 · 점검 대상 창(진행 중 포함·이동 제외·최대 개수·`item_id`) · 장소 모르면/점검이 죽으면 그 항목만 `unknown` · 남의 것=없는 것 404 · 키 없음 401 · 이동 판정(시간표 판정 · 출발 시각은 판정기 두 번 · 판정기 꺼짐은 직선 어림만 · 「갈 방법 없음」은 어림값 안 덧붙임 · 서울 밖 · 두 시각 동시 422 · 끼움 자리 `basis`) · `CacheOnlyLimiter`(바깥으로 안 나감 · 경고 아님 · 처음 받아 온 시각 유지) · **낮은 우선순위 몫**(`CallBudget.share` — 일 · 월 줄을 같은 SQL 안에서 몫까지만 · 동시 8 스레드도 몫을 못 넘음 · 줄의 상한 칸은 진짜 값 · 몫 거절은 rejected 에 안 셈 · DB 를 못 읽으면 안 부름) · 캐시 읽기도 `risk_read` 로 셈 · 점검 응답에서 빠진 종류 · 일부만 답한 소스(`partial`) · 먼 일정의 지금-상태 종류(`too_early`)는 확인 불가 · 진행 중 항목은 지금 기준으로 점검 · 점검기의 사유 문구가 안 샘 · 가장 낡은 확인 시각은 시각 순 · 캐시만 읽는 묶음으로 6종 점검을 실제 어댑터로 돌려도 바깥 호출 0 · 동시 처리 상한(503 `busy`) · 터무니없는 시각 422 · fresh 점검기 없으면 503 · 버스는 어림 등급 · 못 판정(`undetermined`) · 판정기 내부 주소 가림 · 출발 폴백 표시 · 이동 등급은 고른 경로 기준(도보 · 택시는 어림) · 판정기 예외는 `unavailable` · 출발 시각은 도착 목표를 넓혀 찾음 · MCP 로 실제 접속(읽기 도구 7개 · 쓰기 스위치와 무관 · 웹과 같은 결과 · 남의 여행은 도구 오류 · 키 안 샘) `[2026-10-06 사용자 요청]` | `e2e/` · `unit/travel/` | `test_mcp_read_tools.py`(17건) · `test_risk_report.py` · `test_move_judge.py` · `test_cache_only_sources.py`(37건) · `test_source_budget_db.py` 몫 6건 — 로컬 개발 DB · 점검 · 판정기는 흉내(실제 소스 · 실제 시간표 확인 아님) |
| **로딩 중 질문** — 접수 조회의 `questions[]`(쓰는 문항만 · 같은 순서 · 답한 문항도 `answer` 로 남음 · `on_disruption` · `pace` · 식사 제한 · 접근성은 목록에 없음) · 한 문항씩 저장 · **같은 문항은 덮어씀** · 멱등 · 틀린 답 6종은 하나라도 틀리면 **아무것도 저장 안 함**(422 `invalid_answers`) · 빈 몸통 · 모르는 칸 422 · `updated_at` 불변(읽기 멈춤 판정 기준) · 남의 접수 = 없는 접수 404 · 인증 없음 401 · **등록 때 설문에 합침**(요청이 직접 준 값이 이김 · `priority_details` 영역별 합침 · 안 답한 `on_disruption` 은 채우지 않음 · 답 없으면 옛 동작) · 등록된 접수 409 · 선택지가 엔진이 아는 코드인지(`SURVEY_MODES` · `ORDER`) · **질문 묶음 버전**(접수 조회 · 저장 응답에 `questions_version` · 웹은 슬롯 · 값을 모름) · **문항 번호와 슬롯 분리**(다른 번호의 묶음으로도 설문에 올바르게 들어감) · **답 이력**(그때의 문구 · 라벨 · 슬롯 · 값 · 묶음 버전 · 재전송은 줄 안 늚 · 추가만 · 접수와 함께 지워짐) · **옛 답은 저장 때 뜻으로 등록**(묶음이 바뀌어도) `[2026-10-06 사용자 지시 · uiux 요청]` | `e2e/` | `test_intake_survey_questions.py` (24건 · 로컬 개발 DB 실제 SQL — 실서버 확인 아님) |
| **에이전트 키** — 회원만 쿠키로 만들기(게스트 `member_only` · 에이전트/옛 키 `cookie_required` · CSRF) · 원문 한 번만(목록 · DB 에 없음) · Bearer/X-User-Key · `read` 는 GET 만 · 계정 관리 경로 `agent_forbidden` · 쿠키+키 동시 400 · 서버 scope 키 거부 · 만료/폐기/모름 같은 401 · 개별 폐기(남의 것 404) · 활성 상한 409 · 만료 상한 422 · 마지막 연결 해제 시 전부 거둠 `[2026-10-04 D-CS-012]` | `e2e/` | `test_web_agent_keys.py` (12건) |
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
