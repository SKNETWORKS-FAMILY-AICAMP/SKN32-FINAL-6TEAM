---
type: report
title: develop ← role-eval-ui(= role-manager 9f20a7ff) 병합 — 충돌 9곳 · 기존 브라우저 실패 18건 고침 · 로컬 전체 시험
date: 2026-10-22
domain: travel
---

# develop ← role-eval-ui 병합 (2026-10-21 21:41 ~ 2026-10-22, ST4F-715)

**결론:** 충돌 9곳(서버 6 · 웹 2 · 문서 1)은 모두 양쪽이 같은 자리에 서로 다른 것을 더한 경우라 양쪽을 다 남겨 풀었다. 병합으로 새로 생긴 실패는 서버 · 웹 모두 0이다. 같은 가지에서 병합 전부터 있던 실패 21건(웹 브라우저 시험 18 · 서버 3)을 고쳤다 — 모두 시험 기대값 · 모방 서버만 고쳤고 앱 코드 변경은 0이다. 고친 뒤 브라우저 전체 915/916(남은 1 = 부하 흔들림, 혼자 3회 통과) · 고친 서버 시험 파일 통과. 실서버 · 실기기 확인은 하지 않았다.

## 범위

| 항목 | 값 |
|---|---|
| develop | `6016fcc21` (10-21 16:04, GitHub CI(develop) 빠른 검사 통과) |
| 우리 쪽 | `role-eval-ui` = `role-manager` `9f20a7ff2` (PR #64 병합, 10-21 21:39) |
| 공통 조상 | `4e2a685b4` (10-20 16:58) — 그 뒤 develop 118커밋 · 우리 69커밋, 양쪽이 고친 파일 26개 |
| 작업 위치 | 격리 사본 `Dev/SKN32-develop-merge-20261021` · 가지 `merge/develop-role-eval-ui-20261021` (원본 폴더는 fetch · 조회만) |

## 충돌 9곳 — 푼 방법

| 파일 | 양쪽이 더한 것 | 풀이 |
|---|---|---|
| `app/core/settings.py` | develop `dining_trial_live_view_enabled` ↔ 우리 `guardian_enabled`(ST4F-613) | 두 함수 모두 |
| `components/settings_hook.py` | 같은 짝(운영자 값 → 가드레일 기본) | 두 함수 모두 — 공통 끝줄 `return guardrail_default()` 을 함수마다 |
| `modules/web_account/web_guard.py` | 같은 짝(관리 콘솔 운영 설정 항목) | 두 항목 모두 |
| `components/intake/review.py` | develop `intake_state`(판 잠금) ↔ 우리 `_reopened_from`(ST4F-705) | 두 함수 모두 |
| `entry/trip_api.py` | develop `_intake_survey(…, base)` 4인자 ↔ 우리 `_party_from_survey`(ST4F-581) | 우리 함수 + develop 의 4인자 정의(자동 병합된 두 호출부가 4인자로 부른다). 우리 쪽은 정의 줄을 바꾸지 않았다(공통 조상 그대로) |
| `components/intake/candidates.py` | import 한 줄 — develop `MEAL_WORDS` · `SOURCE_DEFAULT` ↔ 우리 `_PerLeg` | 합집합 |
| `web/src/features/trip/trip-rows.tsx` | lucide import — develop `Users`(시험 값 줄) ↔ 우리 `MapPin`(ST4F-706) | 합집합(둘 다 쓰인다) |
| `web/src/features/trip/trip-screen.module.css` | develop 시험 값 줄 · `trialMark` ↔ 우리 `data-stop-place` | 모두 |
| `wiki/log.md` | 같은 자리에 날짜별 기록 | 10-21 우리 → 10-21 develop → 10-20 우리 → 10-20 develop 순. 두 판의 모든 줄이 남았는지 기계 대조(빠진 줄 0 · 더한 줄 0) |

자동 병합된 17파일 점검: 같은 범위의 함수 이름 겹침 — 병합으로 새로 생긴 것 0(양쪽이 고친 파이썬 13파일). `config/guardrails.yaml` 은 양쪽이 다른 키를 더했다(우리 `travel.guardian` · develop `social_dining` · 요식 키). ☆같은 파일의 `a2a_cancel_timeout_seconds` 중복 키(38 · 61줄)는 공통 조상 · 두 판 모두에 이미 있다 — 병합 탓이 아니라 고치지 않았다. 문서(`decisions/index.md` · `handoff/index.md` · 웹 `DEVELOPMENT.md`)는 번호 · 절이 겹치지 않는다.

## 기존 브라우저 실패 18건 — 고친 것

[10-21 원인 조사](2026-10-21_웹_화면시험_기존실패35_원인조사.md)의 35건 중 17건(선택 장소 이름 16 · 「알림 보기」 1)은 10-21 ST4F-706 · ST4F-703 이 이미 고쳤다. 남은 18건을 이 병합에서 고쳤다(사용자 지시 2026-10-22 「이번 병합에 같이 고쳐줘」). 모두 시험 기대값이 화면 동작을 못 따라갔거나 모방 서버 · 시계가 새 동작을 못 받친 것이다 — 앱 코드는 바꾸지 않았다.

| 시험 | 원인(조사 기록) | 고친 것 |
|---|---|---|
| `compact-edge-unlock-add-20261010:35` ×2 · `quiet-lock-map-width-20261010:51` ×2 | 결과 화면 위험 칸만큼 단추가 내려와 고정 250px 굴림으로 부족 | 단추 아래 끝이 목록 위로 넘어가게 굴린다 |
| `departure-alignment-20261009:58` | 첫 출발 표시가 812px 아래 | 끌기 전 `scrollIntoViewIfNeeded`(zweing `f486ff9f` 와 같은 방식) |
| `intro-registration-20261011:25` ×2 | 홈 `/` 은 동의를 다시 읽지 않는다 | 그 요청을 기다리던 동기화 줄 삭제 |
| `location-entry` 「버튼에서 동의하면 위치 점…」 | 선택 동의는 서버 기록이 있어야 진행 — 모방 서버 기본 `consents: "off"` | `openFinished(…, { consents: "on" })` |
| `trip-marker-no-toast-20261011:11` ×2 · `trip:135` | 모방 서버에 `/risks` 가 없어(404) 위험 칸이 status 한 줄 · 「살펴볼 점이 없어요.」 문장은 위험 칸으로 바뀜 | 모방 서버에 `risks: "clear"` 장면 추가(**기본은 그대로 404** — 다른 시험 영향 없음) · `trip:135` 기대 문구를 「현재 점검 대상 일정이 없어요」로 |
| `trip-center:73` | 만료된 제안을 거른다 — 시계 고정 없음 | `beforeTheTrip`(같은 파일 :52 와 같다) |
| `trip:230 · 240` | 채팅에도 같은 선택 단추 | 알림 센터 안에서 고른다(:202 와 같다) |
| `trip:301 · 451` | 채팅이 알림을 시각 순으로 섞어 `.last()` 가 알림 | `notices: "none"` |
| `trip:416` | 판이 다른 제안을 거른다 — 「제안」 신호만 보냄 | `ring(["itinerary", "proposal"])` |
| `trip:377` | `GET /v1/web/features` 404(ST4F-613, 우리 쪽 커밋 `aaf34996`) | 시나리오에 `features: "on"` |

## 시험 결과 (로컬 · 이 PC)

| 검사 | 결과 | 범위 · 한계 |
|---|---|---|
| ruff F·E9 · `ruff check .`(CI 명령 그대로) | 통과 | 저장소 전체 |
| 웹 `npm run check` | lint · typecheck · 단위 1029/1029 = 100% · build 통과 | 병합 직후(시험 수정 전). 시험 수정 뒤 `eslint tests/live` · `tsc --noEmit` 통과 |
| 서버 단위 · 구조 · 계약 · eval | 9,226 통과 · 실패 0 · 건너뜀 134 | CI 환경값(`ACOP_LLM_PROVIDER=mock` 등) · 갈래마다 새 DB(migrate → register_prompts → seed_travel) |
| 서버 통합 · 시나리오 · 보안 | 937/938 = 99.9% · 건너뜀 309 | 세 갈래 동시 첫 실행의 실패 2건은 DB 접속 `Address already in use (10048)`(로컬 포트 고갈) — 이 갈래만 다시 돌린 결과. 남은 1 = 아래 기존 실패 |
| 서버 e2e | 1,330/1,332 = 99.8% · 건너뜀 24 | 남은 2 = 아래 기존 실패 |
| 웹 브라우저(모방 서버) 6묶음 — 시험 수정 전 | 898 통과 · 실패 18 · 건너뜀 20 | 실패 18 = 위 표의 18건과 정확히 같다(병합으로 늘어난 실패 0) |
| 고친 8개 시험 파일 다시 돌리기 | 70/70 = 100% | 같은 빌드(앱 코드 그대로) |
| 웹 브라우저 6묶음 — 시험 수정 뒤 | 915/916 = 99.9% · 건너뜀 20 | 남은 1 = `sheet-motion.spec.ts:19`(400ms 안에 미끄러짐을 잡는 시각 시험, 첫 실행에서는 통과 · 고친 파일 아님) — 다른 시험 없이 혼자 3회 9/9 통과 → 6묶음 부하 흔들림 |
| 서버 기존 실패 3건 고친 뒤 — 두 시험 파일 | 9 통과 · 실패 0 · 건너뜀 1 | 새 DB · CI 환경값. 세 갈래 전체는 고치기 전 결과(위 행) — 고친 것은 이 두 파일뿐 |

**서버 기존 실패 3건 — 병합 탓이 아님을 확인한 뒤 고침(시험 기대값만):**

- `tests/e2e/test_intake_nameless_lines.py` 2건 — develop 판만 · 우리 판만 따로 돌려도 같은 2건이 실패한다(`git archive` 로 뽑은 두 트리에서 확인). 원인: `380e3909`(10-19, 공통 조상에 있음)이 **2026-10-18 사용자 확정 계약** [직접 장소 검색](../../external/explicit-place-search.md) — 고객이 직접 찾을 때는 활동 · 식사를 함께 보이고 실제 종류를 둔다 — 을 구현했는데 시험은 옛 「검색도 같은 종류만」이었다. 고친 것: 결과는 활동 · 식사만 · 각 곳의 실제 종류 유지 · 식당 이름을 직접 찾으면 그 식당(`no_same_kind` 없음). 자동 후보의 같은 종류 조건 단언(`candidates == []` · `booked_needs_name`)은 그대로. 내용과 맞지 않게 된 시험 이름 하나를 `test_direct_search_shows_activities_and_restaurants_together_with_their_real_kind` 로 바꿨다(참조하는 곳 0).
- `tests/integration/dining/test_dining_agent_judge.py::test_rule_rows_map_to_checks_and_days_without_meals_are_skipped` 1건 — develop 에만 있는 시험. develop 판에서도 같은 단언으로 실패한다(DB 없는 함수 시험). 원인: hwansj `82eecd6b2`(10-20, 자유문 고객 조건 검증)가 `NOTES_MAX = 2000` · `[:NOTES_MAX]` 를 뺐는데 시험은 그대로였다. 고친 것: 메모를 자르지 않고 그대로 넘긴다는 기대값. ★가정: 커밋 메시지에 이유가 없다 — 긴 계획서 뒤쪽 조건까지 읽게 일부러 뺀 것으로 봤다. 실수였다면 시험이 아니라 코드에 자르기를 되살려야 한다. develop 의 GitHub 빠른 검사는 통합 · e2e 시험을 돌리지 않아 두 묶음 모두 드러나지 않았다.

## 남은 것

- hwansj 확인: 요식 판정 메모 2000자 자르기를 뺀 것이 의도인가(위 가정).
- `config/guardrails.yaml` 의 `a2a_cancel_timeout_seconds` 중복 키(기존) — 보고만.
- 실서버 · 휴대폰 실기기 확인 안 함. 모방 서버 시험 통과를 실서버 동작 확인으로 보지 않는다.
- 커밋 · 푸시 · develop PR 은 사용자 승인 뒤.
