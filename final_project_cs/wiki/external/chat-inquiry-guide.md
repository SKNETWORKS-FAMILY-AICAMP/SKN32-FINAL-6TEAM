---
type: contract
title: 채팅 미해결 답의 문의함 안내 · 담당 근거 없는 업무 · 팀 id 기록
description: D-024 를 채팅 답에 적용하는 조건·문구·링크, 대상 축이 빈 채팅 업무의 처리, 규칙 경로의 팀 id
status: draft
domain: travel
---

# 채팅 미해결 답의 문의함 안내 — D-024 적용 계약

`[2026-10-26 라우팅 감사 P2 후보 · 운영 반영 전]` 정본 결정은 [D-024](../../../wiki/decisions/D-024-inquiry-reply-path.md)
(「일반 대화에서 해결 못 한 일은 고객에게 이유를 알리고 이 문의 경로를 안내하는 데서 끝난다」)와
[D-CS-014](../decisions/D-CS-014-routing-reroute.md)(내부 `escalated` 를 상담원 대기로 번역하지 않는다)다.
이 문서는 그 결정을 채팅 입구(`POST /v1/web/trips/{id}/messages` · `POST /v1/trips/{id}/messages`)에 적용하는 방법만 정한다.

## 1. 언제 안내하나

채팅 한 통의 결과(`trip_messages.handle_trip_message` 의 반환 — 웹 JSON · SSE `result` · 에이전트 API 가 같은 것을 받는다)가
아래 둘을 **모두** 만족할 때만 안내한다.

| 조건 | 값 |
|---|---|
| Case 가 해결되지 못하고 끝났다 | `case_status` ∈ {`escalated`, `failed`} |
| 고객에게 답을 준 결과가 아니다 | `status` ≠ `answered` |

- 포함: 해석 실패(`decision_failed`) · 분류 실패(`classification_failed`) · 문장 읽기 실패(`no_extractor` · `extractor_failed` · `not_understood`) ·
  규정 검색 불가(`question_needs_policy_answer`) · 팀 업무 처리 불가(`case_dispatch` 의 `escalated`/`failed`) · 처리 못 한 종류(`unhandled_*`) ·
  위 Case 의 같은 요청 재전송(`duplicate`).
- 제외: 처리 완료(`resolved`) · 되묻기(`waiting_input`, `clarify`) · 사실 답(`answered` — 기록용 분류가 뒤에서 실패해도 고객은 답을 받았다) ·
  처리 중(`routing` · `running`) · 부분 답(`response_status: partial` 은 Case 가 `resolved` 다 — 아래 「남은 것」).
- HTTP 오류(503 `team_unavailable` · 409 · 422)는 결과 본문이 아니므로 이 계약 밖이다.

## 2. 무엇을 싣나

- 문장(`trip_replies.INQUIRY_GUIDE`): 「채팅으로 해결하지 못한 일은 메뉴 › 「문의함」 › 「문의 작성」에서 남겨 주세요. 운영팀이 문의함으로 답변드려요(일정·예약은 대신 고치지 않아요).」
- 위치: 기존 답(`answer`, 웹 전용 판 `answer_web` 이 있으면 그것도) **끝에 줄을 바꿔 한 번** 붙인다. 이미 붙어 있으면 다시 붙이지 않는다.
- 링크: 결과에 `inquiry_path: "/support/new"`(사용자 웹 `routes.supportNew` 와 같은 값)를 함께 싣는다. 화면이 단추로 그릴 수 있게 한 값이며,
  지금 화면은 문장만 보여 준다(화면 연결은 ui 몫 · 미구현).
- 대화 기록(`chat_log`)에는 고객이 본 문장 그대로 남는다(입구가 결과의 `answer` 를 기록한다).

## 3. 하지 않는 것

- 상담원 연결 · 사람 대기 · 「넘겼어요」 약속을 쓰지 않는다. 문의를 대신 만들지 않는다(고객이 직접 쓴다).
- 운영자 알림 · 외부 알림을 보내지 않는다. 운영자가 일정을 대신 고치는 길을 만들지 않는다(D-024).
- 실패 원문(예외 이름 · 모델 오류)은 여전히 공개 답에 싣지 않는다.

## 4. 담당 근거가 없는 채팅 업무 — 활동 팀 기본 배정 금지

두 축 라우팅(`case_type` + `intent`)에서 채팅 결정 경로는 API 가 담당 팀을 정한다([web-intakes 채팅 해석과 팀 업무](rest-endpoints/web-intakes.md)).
담당은 **근거로만** 정한다. 순서:

1. 해석된 대상 일정의 종류(종전 그대로). 늦음 신고 · 지금 식사의 휴무 신고는 식당 팀(종전 그대로).
2. 되묻기 후보 중 **일정을 가리키는 첫 후보**의 일정 종류(전에는 첫 후보만 보고, 일정이 없으면 활동 팀이었다).
3. 판 되돌리기 · 다시 적용(`rollback` · `redo`)에 대상 일정이 없으면, 지금 일정과 돌아갈 판의 일정을 비교해 **바뀌는 일정(이동 제외)이 한 종류일 때** 그 종류.
4. 대상 없는 바꾸기(`apply_change` · `propose_alternatives`)는 모든 종류의 후보로 **되묻기**로 바꾼 뒤 2를 적용한다.

그래도 근거가 없으면 **어느 팀에도 보내지 않는다** — 일정은 바꾸지 않고 되묻는 답(`status: clarify`)으로 끝낸다. Case 는 기록 라벨
`trip_desk` 로 `ROUTED`(`owner_basis: "unresolved"`) → `COMPLETED` 이고, 재시도 실행 계획(`conversation_dispatch`)은 남기지 않는다. 고객의 다음 문장은 새 요청으로 해석된다.

- 예외 — 끝난 답은 그대로: 대상 없는 되돌리기인데 되돌릴 변경이 없으면(`request.nothing_to_undo`, role-manager c286b906) 되묻지 않고
  「되돌릴 변경이 없어요 …」 끝난 답(`status: answered` · `reason: nothing_to_undo`)으로 끝낸다(`trip_messages._unresolved_question` → `_undo_outcome`).
  Case 기록은 위와 같다(`trip_desk` · `owner_basis: "unresolved"` → `COMPLETED`, 팀 실행 없음). `[2026-10-26 role-manager 이식 중 발견]`
- 조건(실내·야외) 경로와의 관계: 조건이 있는 대상 없는 바꾸기는 role-manager 1e4e3b24 의 조건 선택지 되묻기(활동만)가 먼저이고, 그 첫 후보가 담당이다.
  조건이 없으면 위 4번(모든 종류 후보)이다 — 시험 `test_chat_setting_clarify_paths.test_swap_without_a_target_and_without_a_setting_is_unchanged`(contract_correction).

- 왜 분류 실패가 아니라 되묻기인가: 요청 종류(intent)는 분류됐고 비어 있는 것은 **대상 축**이다. 대상 근거가 없으면 되묻는다는 기존 계약
  ([trip-chat-context](trip-chat-context.md) 「대상 근거 없음 → clarify」)과 같다. 분류 실패로 닫으면 고객이 고칠 수 있는 입력을 막는다.
- 왜 활동 팀이 아닌가: 「모르는 것을 아무 팀에나 보내지 않는다」(D-CS-014) · 「Activity 에 다른 팀 조정을 맡기지 않는다」(D-017).
  활동 팀이 받은 식당 대상 답은 팀 실행에서 `target_kind_mismatch` 로 처리 불가가 되거나 활동 일정만 후보로 보였다.
- 규칙 경로(`travel.decision_unit.mode = off`)의 `_report_dispatch_plan` 기본 `activity` 는 이번 범위가 아니다(로컬 live 는 `on`) — 남은 것.

## 5. 규칙 경로의 담당 기록은 팀 id 다

분류 접두(`case_type`)와 팀 id 가 다른 팀이 있다 — 종류 `booking` 을 받는 팀은 `booking_handoff` 다(`config/project.yaml` · `BookingHandoffTeam.accepted_case_types`).
규칙 경로(사실 질문 기록 `_finish_fact_case` · 규칙 해석 모드)는 `trip_messages.CASE_TYPE_TEAMS` 로 **팀 id** 를 남긴다. 표에 없는 종류는 기록 라벨 `trip_desk`.

- 데이터 이관은 하지 않는다. 옛 기록의 `owner_team_id = booking` 은 그대로 두고, 팀 id 로 읽어야 하는 곳은 `trip_messages.canonical_team_id()` 로 읽는다
  (`booking` → `booking_handoff`). 채팅 재개의 담당 대체값이 이것을 쓴다.
- **롤백 안전** `[2026-10-26 Codex 지적]`: 이 묶음이 쓰는 담당 값은 등록 팀 id(`CASE_TYPE_TEAMS` 값)와 기존 기록 라벨 `trip_desk` 뿐이다.
  등록 팀 표는 `config/project.yaml` 로만 만들어지고 이 묶음은 그 파일을 바꾸지 않으므로, 이 묶음 **이전** 판의 Controller(`require_team(owner_team_id)`)
  · 재개 route(`_resume_route(...) or 저장 담당`)도 `booking_handoff` Case 를 그대로 읽고 실행한다(옛 값 `booking` 은 오히려 `not_installed` 였다).
  `trip_desk`(`owner_basis: "unresolved"`) Case 는 `COMPLETED` 로 끝나 재개 · 재시도를 타지 않고 실행 계획도 남기지 않는다.
  시험 `test_chat_booking_owner_id.test_an_older_reader_resumes_a_booking_handoff_case_with_the_registered_team`(이전 판 af608588 에서도 통과) ·
  `test_every_owner_this_bundle_records_is_runnable_in_the_real_registry_of_any_version`.

## 남은 것

- 부분 답(`response_status: partial` — 질문 일부 `failed`)에 안내를 붙일지: 이번에는 Case 가 `resolved` 라 붙이지 않는다(되돌릴 수 있는 기본값).
- 화면의 `inquiry_path` 단추, 감시 · 개인 AI 경로의 처리 불가 통지 문구(D-CS-014 승인 절)는 미구현.
- 실제 DB · 실모델 · 화면 확인은 하지 않았다(격리 단위 시험만).
