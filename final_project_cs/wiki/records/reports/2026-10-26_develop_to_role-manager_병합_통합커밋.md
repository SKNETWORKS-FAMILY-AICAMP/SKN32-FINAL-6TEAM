---
type: report
title: develop → role-manager 병합 통합 커밋 (로컬, push 전)
date: 2026-10-26
domain: travel
status: draft
---

# develop(30e9f0a08) → role-manager(fb291b339) 병합 통합 커밋

**결론:** 로컬 merge 커밋 `4a67c6c733130fbb38ac892bacdbe484ca64547b`(부모 `fb291b339` role-manager · `30e9f0a08` develop, rebase 없음)을 만들었다. 충돌 22파일을 양쪽 의도를 보존해 풀었고, 빠른 관문 9709 통과 / 173 skip / 실패 0(9882건, 실패 0/9882 = 0%), 웹 tsc 0 · vitest 1197/1197 = 100%, 충돌 관련 DB e2e 202/209 = 96.7% 통과(실패 0, skip 7 = 실행기 연결 차단), ruff F/E9 통과. 마이그레이션 추가 0. push 하지 않았다(부모 몫).

- 위치: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/integ-merge-dev-20261026-0717/rm2` (가지 `integ/merge-dev-fb29`)
- 처음에는 role-manager `af6085887` 위에 병합(`381c1b53d`, 같은 해결)했다. 그 사이 role-manager 가 `fb291b339`(분류 계획 도구·예산 팀 선언·plan_stream: `execution_plan.py` · `feedback.py` · `trip_watch_batch.py` · `guardrails.yaml` · wiki)로 움직여 그 위에 다시 병합했다. `fb291b339` 의 10경로는 충돌 22파일과 겹치지 않아 충돌 파일은 `381c1b53d` blob 을 그대로 썼다. 검산: `381c1b53d`→`4a67c6c7` 경로 차이 = `af6085887`→`fb291b339` 경로 10개와 같음, 9개는 blob 동일, `test_classification_execution_plan.py` 1개는 develop 변경(`_operator_switch` 등)과 `fb291b339` 변경의 자동 병합이며 그 hunk 는 `af6085887..fb291b339` hunk 와 같다.

## 1. 충돌 파일별 선택

| 파일 | 택한 쪽 | 이유 |
|---|---|---|
| `conversation/edit_intent.py` (2 hunk) | role-manager | `place_setting` 칸 설명·「action과 무관하게 채운다」 지시(`1e4e3b246`). develop 쪽은 그 전 판(cherry-pick 원본) |
| `conversation/trip_messages.py` (3) | role-manager | `_setting_swap_choices` · `setting_guard` 안내(`c34bd376f`·`1e4e3b246`)가 develop `30e9f0a08`/`e1d1e0fc3`/`5f1627b5b`(role-manager 에 `da4ccd97`·`53c3c273`·`2ce73990` 로 이미 들어옴)의 후속 판 |
| `intake/review.py` (4) | 결합 | role-manager `wholly_past` · `ALL_PAST_MESSAGE`(`pipeline.process` fatal 문장 공용) + develop `_store_read`(읽기 저장 경쟁 보호) · `dining_review.refresh/prepare` · `dining_questions` 답 유지 · `risks.decorate(on_event)`(ST4F-732) |
| web `intake-review.tsx` | 합집합 | role-manager `entryReturnOf`(전부 과거 → 계획 담기로) + develop Dining 질문·상태 import |
| web `plan-check/model.ts` · `parts.tsx` · `lib/live/intake-review.ts` | 합집합 | `date` 줄(전부 과거) + develop `dining_check` · `dietary` · `kids` · `payment` · `business` |
| web `plan-check/stop-questions.ts` | 합집합 | `checkLineText`(role-manager) + `IntakeEdit` · `MODE_WORDS` · `MoveOptionMode`(develop ST4F-733) |
| `tests/unit/travel/test_all_past_confirm_api.py` · `test_all_past_dates.py` | develop | 병합 뒤 `review.py` 가 `dining_review` 를 부르므로 develop 의 `dining_review` 대역이 필요 |
| `tests/unit/travel/test_chat_place_setting.py` · `test_chat_setting_clarify_candidates.py` | role-manager | 새 `setting_guard` 계약(이미 그 조건이면 되묻기 · 남는 자리 활동으로 채움) 기대 |
| `wiki/external/trip-chat-context.md` | role-manager(develop 쪽 빈칸) | 실내·야외 되묻기 · 절대 시각·날짜 옮기기 절 |
| `wiki/external/web-screen-api.md` | develop | ST4F-739 줄의 PR #98·#99 병합·CD 결과가 더 최신 |
| `final_project_cs/wiki/index.md` | 양쪽 | develop 의 allpast 줄 + 웹 고침(ST4F-735~738) · ST4F-731/732 줄 + role-manager 실내·야외 4줄 |
| `final_project_cs/wiki/log.md` | develop(상위집합) | role-manager 쪽 한 줄이 develop 쪽에 그대로 포함 |
| `records/reports/2026-10-25_all-past-calendar-hotfix.md` · `..._allpast-normal-confirm-proof.md` | role-manager(develop 쪽 빈칸) | role-manager 이식 절 |
| `records/reports/2026-10-25_계획담기_보조칸_운영스위치_ST4F-739.md` (2) | develop | 5절 병합·배포 기록이 최신 |
| `wiki/handoff/2026-10-25_all-past-calendar-hotfix.md` · `..._allpast-normal-confirm-proof.md` | role-manager(develop 쪽 빈칸) | role-manager 후속 절 |
| 루트 `wiki/index.md` | role-manager | 같은 handoff 링크, role-manager 계열 설명 |

설계 판단은 Codex CLI(`codex exec -s read-only`, 본문 stdin, 텍스트만)와 논의했다. Codex 결론: 확정 병합 결함 없음, trip_messages/edit_intent 선택은 develop 변경을 계승한 후속 판 유지. 추가 확인 제안 — `_store_read` 실패 시 바로 반환해 `dining_review.prepare` 를 건너뛰는 길(develop 원래 동작, 병합이 바꾸지 않음), Dining 대역 없는 전부 과거 + Dining 결합 시험은 없음. 근거 `ev/codex_q.txt` · `ev/codex_a.txt`.

## 2. 검증

| 항목 | 병합(`4a67c6c7`) | role-manager 부모 `fb291b339` | develop 부모 `30e9f0a08` |
|---|---|---|---|
| 빠른 관문(`tests/architecture tests/contract tests/unit tests/security -m 'not live and not db and not slow'`, `-p pytest_asyncio.plugin`, venv `date_risk_env_312`, 근 변수 `IMD_SOURCE_ROOT`) | 9709 통과 · 173 skip · 실패 0 (9882) | 9582 · 173 · 0 (9755) | 9447 · 173 · 0 (9620) |
| ruff `--select F,E9` | 통과 | — | — |
| 웹 tsc `--noEmit` | 0 | — | — |
| 웹 vitest | 1197/1197, 376 묶음 실패 0 | — | — |
| DB e2e(비교 DB `gugu_replay_improved_20261025`, `run_aig_imd.py`) | 202 통과 · 7 skip · 실패 0 (209) | 미실행 | 미실행 |

- 관문 nodeid 대조: 병합에 없는 부모 nodeid는 develop 이 매개변수 이름을 바꾼 3건(`test_registered_moves …[title]` → `[legacy_title]`, `test_social_dining_constraints …[None]`/`[given1]` → `[…-True/False]`)과 role-manager 가 바꾼 `test_quoted_setting_survives_decision_as_a_plain_change` 매개변수 3건뿐. 병합에만 있는 nodeid 0.
- DB e2e 파일(18): 병합으로 바뀐 e2e/통합 11개(`test_intake_interpretations_api` · `keep_times` · `kept_end` · `move_mode` · `picked_title` · `progress_events` · `push_later` · `read_lock` · `test_trip_reopen` · `test_openapi_surface` · `test_dining_agent_tools`) + `test_intake_review` · `test_intake_dining_judge` · `test_intake_all_past_gate_db` · `test_trip_intake_api` · `test_chat_flight_change_web` · `test_chat_lodging_change_web` · `test_chat_edit_web` · `test_chat_context` · `test_conversation_resume`. skip 7건은 모두 「DB 에 붙지 못했다: aig isolated runner: network/database denied」이며 7건 모두 `tests/integration/dining/test_dining_agent_tools.py` 다(develop 에서 바뀐 Dining 도구 시험). 실행기가 5433 비교 DB 외 연결을 막아서 이 파일의 DB 연결이 거절됐다 — 통과로 세지 않고, 이 7건은 미검증으로 남긴다.
- DB e2e 는 `af6085887` 위 첫 병합(`381c1b53d`) 트리에서 돌렸다. `4a67c6c7` 과의 차이는 `fb291b339` 의 watch·분류 계획 10경로뿐이고 이 18파일의 대상(접수·채팅)과 겹치지 않는다. 웹 시험도 같은 트리에서 했고 두 트리의 `frontend/` 는 동일하다.
- DB 전후: 내 시험 tenant(`imdd_…`) 잔여 0. 같은 시각 `trip_api_0c17a5535fd7` tenant 1개(행 tenants 1 · customers 1 · outbox 6 · trips 1 · places 106)가 사라졌다 — `tests/e2e/test_trip_api.py` 의 tenant 이름이고 이 파일은 내 선택에 없으므로 동시에 돌던 다른 작업자의 시험으로 본다(근거 `ev/db-rm-merge/cmp.txt`).

## 3. x600 자동배포 영향(role-manager push 시)

- **마이그레이션 추가 0** (`*.sql` · requirements · Dockerfile · compose · yaml 변경 없음. `fb291b339` 의 `guardrails.yaml` 은 이미 role-manager 에 있음).
- 서버 변경(develop 에서 들어옴): Dining 판정 대기·질문(`intake/dining_review.py` · `dining_questions.py` 신규, `pipeline.py` · `prepared.py` · `registration.py` · `trip_api.py` · `instances/dining/*`), 계획 확인 진행 알림 ③(ST4F-732), 후보 대기 읽기 잠금 해제(ST4F-731), 도착 질문 뒤 일정 함께 미루기(ST4F-733/734), 장소 바뀐 일정 이름(ST4F-737), `deploy/worker.sh` 종료 코드 파일(bash `wait` 255 대응).
- 웹 화면 변화(46파일): 계획 확인 진행 표시 서버 단계 칸 막대 · 단계 알림, 식사 질문 칸(`dining-questions.tsx`)과 식당 확인 줄(식당 확인 · 식사 조건 · 아이 동반 · 결제 · 운영 상태), 도착 질문 「뒤 일정까지 함께 미루기」, 「예시 불러오기」 1일차 오늘 · 2일차 내일 + 첫 여행 첫 안내 덮개(`example-guide.tsx`), 지도 오른쪽 아래 흰 바탕 제거 · 계획 입력 고정 줄 · 보내는 중 회색 · 시트 손잡이, 스트림 재접속 세션 고정(`session_changed`), 지도 툴팁(OSM).
- 관리앱: `copy.ts` · `session-cleanup.ts` 신규, `AdminApp.tsx` · overview/workflows 화면(F-03·F-04).
- 위험: Dining 판정이 켜진 환경(`dining_agent_judge` 설정 · `dining_ledger.agent_judge_runner()`)에서는 식사 일정이 든 계획 확인에서 Dining 대기가 새로 생긴다. 이번 병합 검증은 Dining 을 대역으로 바꾼 전부 과거 시험과 e2e 뿐이고 실 E4B · x600 화면 확인은 하지 않았다.

## 4. 남은 일

- 부모: 원격 `role-manager` 가 `fb291b339` 그대로인지 확인 뒤 빨리감기 push, x600 배포 확인.
- 이 병합을 develop 으로 되돌려 반영(최종 목표).
- `test_dining_agent_tools.py` 7건 DB 연결 경로를 비교 DB 로 돌려 재실행.
- Codex 제안 시험(Dining 대역 없는 전부 과거 + Dining, 동시 읽기·답 저장 경쟁) 미작성.

증거: scratch `integ-merge-dev-20261026-0717/ev/` — `gate-merge2.xml` · `gate-rmbase2.xml` · `gate-merge.xml` · `gate-rmbase.xml` · `gate-dev.xml` · `vitest-rm-all/vitest.json` · `web-tsc-rm.rc` · `db-rm-merge/r.xml` · `ruff_merge2.txt` · `MERGE_MSG.txt` · `codex_a.txt`.
