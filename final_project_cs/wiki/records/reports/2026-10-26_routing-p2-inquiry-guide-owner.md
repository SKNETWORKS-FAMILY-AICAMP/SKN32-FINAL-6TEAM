---
type: report
title: 라우팅 감사 P2 — 채팅 미해결 답 문의함 안내(D-024) · 활동 팀 기본 배정 제거 · booking_handoff 팀 id (독립 후보)
status: verified
domain: travel
---

# 라우팅 감사 P2 독립 후보 — 2026-10-26 02:10 KST

- 작업자: Hermes subagent(Opus 5.5, 개발 도구). 제품 E4B·실모델 호출 0, DB 쓰기 0, live API(8042)·프런트 조작 0, push 0, 원본 코드 수정 0(이 보고서만 추가).
- 기준: live v7a source(`action-v7a-allpast-20261025-233317-fac130f7/source-v7a`) 복사본, 팀 develop `d2ab93a65`(git archive 사본).
- 후보 폴더: `cache/scratch/routing-p2-20261026-011814-21438/` (source · baseline · develop · patches · evidence · harness · db).
- 근거 감사: [고객응대 라우팅 감사](2026-10-26_customer-response-routing-audit.md) P2 3·4번, P3 8번.

## 결론

세 건 모두 독립 후보에서 고쳤고 격리 단위 시험으로 확인했습니다. 운영(live v7a) 반영·push는 하지 않았습니다.

| 항목 | 결과 |
|---|---|
| ① D-024 채팅 미해결 답 문의함 안내 | 계약 문서 작성 후 구현. 공개 처리기 한 곳에서 붙인다 |
| ② 대상 미확인 시 `activity` 기본 배정 | **되묻기로 바꿈**(분류 실패 아님). live 오배정 **0/7 = 0%** |
| ③ 규칙 경로 `booking` → `booking_handoff` | 팀 id 기록 + 옛 값 읽기 호환. 데이터 이관 없음 |
| 새 시험 | RED 36/37 실패(1건은 회귀 가드) → GREEN **39/39 = 100%** |
| 라우팅 547 묶음 | 기준 479/547 = 87.57% → 후보 479/547 = 87.57%, 상태 변화 0 |
| 확대 합집합(1,056 node) | 기준 809/1,017 → 후보 848/1,056, 기존 node 상태 변화 **0/1,017** |

## ① 계약 — 채팅 미해결 답의 문의함 안내

정본 결정은 D-024와 D-CS-014입니다. 후보의 계약 문서는 `final_project_cs/wiki/external/chat-inquiry-guide.md`이고, D-024 사본에 링크를 달았습니다.

- **언제**: 채팅 결과가 Case `escalated`·`failed`로 끝났고 `status`가 `answered`가 아닐 때 붙입니다.
  - 포함: 해석 실패, 분류 실패, 문장 읽기 실패, 규정 검색 불가, 팀 처리 불가, `unhandled_*`, 그 Case의 `duplicate` 재전송.
  - 제외: 처리 완료, 되묻기, 사실 답, 처리 중, 부분 답.
- **문구**: 「채팅으로 해결하지 못한 일은 메뉴 › 「문의함」 › 「문의 작성」에서 남겨 주세요. 운영팀이 문의함으로 답변드려요(일정·예약은 대신 고치지 않아요).」
  - `answer`와 `answer_web` 끝에 줄을 바꿔 한 번 붙입니다. 이미 붙어 있으면 다시 붙이지 않습니다.
- **링크**: `inquiry_path: "/support/new"`. 사용자 웹 `routes.supportNew`와 같은 값입니다. 화면 단추는 아직 없습니다.
- **하지 않는 것**: 상담원 연결, 사람 대기, 문의 대신 작성, 운영자·외부 알림, 대신 수정. 실패 원문은 계속 비공개입니다.
- **구현**: `trip_replies.with_inquiry_guide` + 공개 `handle_trip_message`(본체는 `_handle_trip_message`로 이름만 바꿈).
  - 웹 JSON·SSE, 에이전트 API, 재시도·재개·중복이 모두 이 한 곳을 지납니다.
  - 대화 기록에도 고객이 본 문장이 그대로 남습니다.

## ② 판단 — 대상이 없으면 활동 팀이 아니라 되묻기

판단: **분류 실패가 아니라 되묻기가 맞습니다.**
- 요청 종류(intent)는 분류됐고, 비어 있는 것은 대상 축입니다. 이 경우 되묻는 것이 기존 계약(trip-chat-context의 「대상 근거 없음 → clarify」)과 같습니다.
- 활동 팀 기본값은 D-CS-014(「모르는 것을 아무 팀에나 보내지 않는다」)와 D-017에 어긋나는 무음 폴백이었습니다.
- 실제 결함도 있었습니다. 활동 팀이 받으면 후보로 활동 일정만 보였고, 식당 답을 받으면 팀 실행이 `target_kind_mismatch`로 처리 불가가 될 수 있었습니다.

새 담당 순서(`trip_messages._dispatch_decision`):
1. 대상 일정 종류.
2. 일정을 가리키는 첫 되묻기 후보의 종류(전에는 첫 후보만 봤습니다).
3. 판 되돌리기·다시 적용은 돌아갈 판과 지금 일정에서 바뀌는 일정(이동 제외)이 한 종류일 때 그 종류.
4. 대상 없는 바꾸기는 모든 종류의 후보로 되묻기로 바꾼 뒤 2번을 적용합니다.
5. 그래도 근거가 없으면 어느 팀에도 보내지 않습니다.
   - 고객 답: `status: clarify`.
   - Case 기록: `trip_desk`로 `ROUTED`(`owner_basis: "unresolved"`) → `COMPLETED`.
   - 재시도 실행 계획(`conversation_dispatch`)은 저장하지 않습니다.

**live 오배정 집계**(acop_cs, `SET TRANSACTION READ ONLY` + rollback, enum·건수만, 고객 원문 출력 0):
- 채팅 업무 `ROUTED`(subject_ref.request 있음) 7건: 전부 dining. apply_change 4건(대상 있음), rollback 2건(대상 있음), clarify 1건(첫 후보가 식당).
- 대상 없이 `activity`로 배정된 건: **0/7 = 0%**.
- `target_kind_mismatch`: 전체 0건.
- 비교 DB(gugu_replay_*)는 이 앱 계정에 CONNECT 권한이 없어 집계하지 못했습니다(자격 증명은 찾지 않았습니다).

## ③ 규칙 경로 팀 id

- `trip_messages.CASE_TYPE_TEAMS`를 추가했습니다. 종류 `booking`은 팀 id `booking_handoff`로 기록합니다. 표에 없는 종류는 `trip_desk`입니다.
- 이 표는 `_finish_fact_case`와 규칙 해석 경로 두 곳에서 씁니다. `REGISTERED_TEAMS` 하드코딩은 없앴습니다.
- 읽기 호환: `canonical_team_id()`가 `booking`을 `booking_handoff`로 읽습니다.
  - 채팅 재개 담당(`case_dispatch.resume_owner`)은 고른 일정이 없으면 이 값을 씁니다.
- live 현황: owner `booking` 16건(api: fact 11, question 1, rollback 4), `booking_handoff` 2건(controller). 이관하지 않았습니다.

## 시험(격리 runner — 네트워크·DB 차단, `RP2_SOURCE_ROOT`, 실행 root 출력 확인)

| 실행 | 결과 |
|---|---|
| RED(v7a 사본, 새 3파일) | 36 실패 / 1 통과. 통과 1건은 「대상 종류 담당 불변」 회귀 가드. 실패 원인은 기능 부재(AttributeError)와 `'activity' == 'dining'`·`'booking'` 단언이며 fixture 오류는 없습니다 |
| RED(재개 읽기 호환 추가분) | 2/2 실패 → 구현 후 통과 |
| GREEN 새 3파일 | **39/39 = 100%** |
| v7a 합집합 기준 → 후보 | 809/1,017(실패 41, DB 차단 오류 167) → 848/1,056(실패 41, 오류 167) |
| 기존 node 상태 변화 | **0/1,017** |
| 라우팅 547 | 479/547 → 479/547. DB 불필요분 479/519 = 92.29%로 같고 실패 증가 0 |
| develop RED(새 3파일) | 38/39 실패 |
| develop 합집합 기준 → 후보 | 694/862 → 732/901, 기존 node 상태 변화 0 |
| develop 새 시험 | 38/39 통과 |

- 남은 실패 41건은 기준에도 있습니다: `test_plan_generation_response` 39건(날짜 fixture), `test_read_requests` 1건(schema), `test_dining_needs_check` 1건(DB 차단).
- develop 실패 1건은 `test_web_entrypoint_shows_and_logs_the_guide_for_a_decision_failure`의 마지막 비공개 단언입니다.
  - develop `d2ab93a65`는 `decision_failed` 공개 결과에 `failure` 원문을 싣습니다. v7a에는 이미 고쳐진 별도 결함입니다.
  - D-024 단언(문구·링크·SSE 동일·기록)은 통과했습니다. develop에는 공개 실패 비공개 수정을 먼저 넣어야 합니다.

## 산출물

| 무엇 | 값 |
|---|---|
| v7a 후보 커밋(후보 폴더 로컬 git) | 기준 `50ef7f9ae9986995a29d402d224f2c8915c4bff2` → `cb3cecccbf2301204b2b33c5fa13ca3328f42bce` |
| v7a patch | `patches/v7a-routing-p2.patch`, sha256 `0f0fe546096415051b90a3ea9bbe6dcc5b7434788f5c52348944f1120431cda0`, 8파일 +539/−18 |
| v7a roundtrip | `git -c core.autocrlf=false apply` 8/8 해시 일치 |
| develop patch | `patches/develop-d2ab93a65-routing-p2.patch`, sha256 `33a3f5b8abaafde8ff629c395e476c3d62483752c6714d71363e71912f955ad5`, 커밋 `edcf4c7f` → `48613723` |
| develop 차이 | `_run_decision` 한 hunk만 문맥을 맞췄습니다. 시험·wiki는 v7a patch와 같습니다 |
| develop roundtrip | 8/8 |
| 증거 | `evidence/{red_new,green_new,red_resume_owner,baseline_union,candidate_union,develop_*}.{log,xml,exit}` |
| DB 집계 | `db/probe_activity_default2.py`, `db/ad2_acop_cs.json` |

## 남은 것(되돌릴 수 있는 기본값 포함)

- **규칙 해석 경로의 같은 패턴**: decision mode `off`에서 쓰는 `_report_dispatch_plan`에도 대상이 없으면 `activity`를 쓰는 기본값이 남아 있습니다. live는 `on`이라 이번 범위에서 뺐습니다.
- **판 되돌리기 동작 변경**: 바뀌는 일정이 여러 종류에 걸치면 이제 되묻습니다(전에는 활동 팀이 되돌렸습니다).
- **번호 판 질문의 이어받기**: 「되돌릴 판 번호를 묻는」 경우는 팀 대기가 없어졌습니다. 고객이 판 번호로 답하면 새 요청으로 해석됩니다.
- **부분 답**: `partial`에는 안내를 붙이지 않았습니다. Case가 `resolved`이기 때문입니다.
- **미구현**: 화면의 `inquiry_path` 단추, 감시·개인 AI 경로의 처리 불가 통지.
- **미실행**: DB가 필요한 167건, 실모델, 실화면.
