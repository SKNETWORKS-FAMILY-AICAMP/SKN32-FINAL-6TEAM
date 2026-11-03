---
type: report
title: P0 이식 후보 — L06 공개 실패 privacy · L01 Routing P2 (role-manager fb291b33 위, 로컬 커밋 2개)
status: verified
domain: travel
---

# P0 이식 후보 L06 · L01 — 2026-10-26 07:55 KST

- 작업자: Hermes subagent(Opus 5.5, 개발 도구). 제품 E4B·실모델·유료 호출 0, push 0, 원본 코드 수정 0(이 보고서만 추가), live·x600 변경 0.
- 근거: [로컬 전용 코드 vs role-manager 감사](2026-10-26_로컬전용코드_vs_role-manager_감사.md) L01 · L06, [Routing P2 독립 후보](2026-10-26_routing-p2-inquiry-guide-owner.md).
- 작업 폴더: `cache/scratch/port-p0-20261026-071725/` (최종 worktree `rm2`, 첫 기준 worktree `rm`, 증거 `ev/`, patch `patches2/`).

## 결론

| 커밋(로컬, fb291b33 위) | 묶음 | 파일 | patch sha256 |
|---|---|---|---|
| `10a6449d8c8451e0c0f1a21505b18b2c0fa29952` | L06 공개 실패 privacy | 4 (+130/−3) | `64feccd543a1b51dfff2e65e8a6946576c80c435cf2f0dda66f6537b73cf3d09` |
| `34fd04252c6408c3a678bfa0c685ca1c860e33b8` | L01 Routing P2 | 10 (+651/−20) | `e75c17b28cee9e36c7fbd6fce881b1eb52b0993f82b27dbfb372561a523ccde3` |

- 로컬 가지: `port/p0-l06-l01-on-fb291b33`(최종), `port/p0-l06-l01-on-af608588`(첫 기준 `b8e778633`·`90949d2e9`). 두 기준의 묶음 diff 는 `index` 줄을 빼면 바이트가 같다(sha256 `54a963d8…2cecc`).
- 빠른 관문(fb291b33 + 2 커밋): **9,627/9,627 = 100%** 통과(실패 0 · 오류 0, skip 173, 전체 9,800 node). L06 커밋만: 9,585/9,585 = 100%(9,758 node).
- 순서는 **L06 → L01** 이다. L01 시험 `test_web_entrypoint_shows_and_logs_the_guide_for_a_decision_failure` 의 마지막 단언이 공개 `decision_failed` 에 `failure` 원문이 없어야 통과하기 때문이다(Codex 동의).
- author = roroblack(L06 은 원 커밋 638d9a66b 작성자 그대로).

## L06 — 공개 실패 내용 비노출(접수 · 채팅 한 계약)

- 출처: 이식 후보 `port/writer-on-develop` 묶음 11 = `638d9a66b`. cherry-pick -x 한 뒤 `presentation/errors.py` 의 CORS `Access-Control-Allow-Credentials` hunk 는 뺐다(L06b 보류).
- 코드: `trip_messages._run_decision` 의 `view(...)` 에서 `"failure"` 키를 뺐다(1줄).
- 계약: `wiki/external/rest-endpoints/web-intakes.md` 에 「공개 실패 내용 비노출(접수 · 채팅 한 계약)」을 두었다. role-manager 8fae4901 의 `fatal.detail` 문단이 이 계약을 가리킨다.
  - 접수: `fatal_code` + 고객 문장.
  - 채팅: `status` · `reason` · `case_status` · `answer` 만 싣는다. `failure` 는 없다. JSON · SSE · `chat_log.record` 가 같은 값이다.
  - 내부 기록은 그대로 둔다.
- 시험:
  - RED: `test_public_decision_failure_privacy` 3/3 실패. 실패한 단언은 `'failure' not in plain` 이다.
  - GREEN: 3/3 통과. rm `test_intake_reading_failed_privacy` 3/3 도 통과했다.

## L01 — Routing P2

- 출처: `routing-p2-20261026-011814-21438/patches/develop-d2ab93a65-routing-p2.patch`(sha256 `33a3f5b8…5ad5`). role-manager 에 `apply --3way` 로 8/8 충돌 없이 들어갔다.
- 이식하면서 role-manager 와 맞춘 것 2건(Codex `codex exec` 텍스트 검토, `codex-answer.md`):
  1. **c286b906 「되돌릴 변경이 없어요」 회귀를 고쳤다.**
     - 증상: 대상 없는 되돌리기인데 처음 판 그대로면 `to_version` 이 없다. L01 은 이것을 담당 근거 없음으로 보고 「한 종류로 정하지 못해」 되묻기로 바꿨다.
     - 고친 것: `_unresolved_question` 이 `nothing_to_undo` 이면 `_undo_outcome` 을 먼저 쓴다. 결과는 `answered` · `nothing_to_undo` 이고 팀 실행은 없다. Case 는 `trip_desk` · `owner_basis: unresolved` → `COMPLETED`.
     - 새 시험 1건: RED(`'clarify' == 'answered'`) → GREEN.
  2. **1e4e3b24 시험 `test_swap_without_a_target_and_without_a_setting_is_unchanged` 을 contract_correction 했다.**
     - 그대로 둔 단언: 조건 경로가 요청을 건드리지 않는다(`decision.action == apply_change` · `setting` 없음).
     - 새 계약으로 바꾼 단언: 결과가 `clarify` + `pending_action: apply_change` 이고, 조건 머리말이 없고, 후보에 식사와 활동이 함께 있다.
     - 옛 기대는 docstring 에 남겼다. Codex 판정: 「새 계약 반영 — 모든 종류 후보 단언이 있으면 약화 아님」.
- 롤백 안전(Codex 지적):
  - 이 묶음이 기록하는 담당 값은 `CASE_TYPE_TEAMS` 의 등록 팀 id 와 기존 라벨 `trip_desk` 뿐이다.
  - 등록 팀 표는 `config/project.yaml` 에서 만들고, 이 묶음은 그 파일을 바꾸지 않는다.
  - 시험 2건을 더했다.
    - `test_an_older_reader_resumes_a_booking_handoff_case_with_the_registered_team`: 이전 판 af608588 코드로도 통과했다(`ev/l01-oldreader-base`).
    - `test_every_owner_this_bundle_records_is_runnable_in_the_real_registry_of_any_version`: 실제 `composition.build_registry` 로 확인한다. 옛 값 `booking` 은 `not_installed` 다.
  - Codex 는 구버전 Controller 의 재개 전 과정 시험을 더 요구했다. 이것은 하지 않았고, 남은 것으로 둔다.
- 계약 문서:
  - `wiki/external/chat-inquiry-guide.md`(신규): §4 에 nothing_to_undo 예외와 조건 경로 관계, §5 에 롤백 안전을 적었다.
  - `web-intakes.md` 「대상 없는 업무의 담당」: `activity` 자리 표시 → 근거 없으면 되묻기.
  - `wiki/decisions/D-024`: 링크를 더했다.
- 시험:
  - RED(af608588 코드 + 새 3파일): 39/41 실패. 통과한 2건은 회귀 가드와 이전 판 읽기 시험이고, 둘 다 기준에서 통과해야 정상이다.
  - GREEN: 41/41, nothing_to_undo 추가 뒤 42/42.
  - 관련 확대 12파일: 161/161.

## DB 시험(비교 DB `gugu_replay_improved_20261025`)

- `tests/e2e/test_trip_api.py`: af608588 위 23/23, fb291b33 위 23/23 통과.
- 실행 전후 비교: 내 시험 tenant 한 개마다 `tenants` 1행 · `customers` 2행이 남았다(`trip_api_e4b8c390e3ef`, `trip_api_ccf86a2260e6`).
  - 원인은 시험 fixture 정리 범위로 보이며, 이 묶음과 무관하다고 추정한다. 지우지 않았다.
  - 다른 tenant 의 변화는 동시 작업자 몫이다.

## 겹침

| 상대 | 겹침 | 판정 |
|---|---|---|
| U01 `231e303a5`(booking_transaction) | 의미: `answered` 라 문의함 안내가 붙지 않는다. 업체에 직접 문의하라는 안내와 충돌하지 않는다 | 충돌 없음 |
| `d3d0a063`(plan_input extras) | 파일 · 의미 겹침 없음 | 없음 |
| c34bd376 · 1e4e3b24 · da4ccd97 | 조건 있는 대상 없는 바꾸기는 조건 선택지가 먼저다(시험 통과). 조건 없는 경우는 위 contract_correction | 반영 |
| c286b906 | nothing_to_undo 회귀 | 고침 |
| 8fae4901 | `case_dispatch.resume_pending.route` 를 `resume_owner` 로 옮겼다. 장소 이름 재개 시험 통과 | 반영 |
| develop 병합 워커 `integ-merge-dev`(381c1b53d) | 같은 파일: `trip_messages` · `case_dispatch` · `web-intakes.md` · `test_chat_setting_clarify_*`. `git merge-tree` 충돌 0 | 문맥 충돌 없음, 병합 뒤 재시험 필요 |
| multi-change3(미커밋) | 이 묶음은 `handle_trip_message` 를 `_handle_trip_message` 로 이름을 바꿨다. 그쪽 hunk 는 이 함수 본문(427행)과 `_run_decision` 끝에 있다 | 병합 때 함수 이름 확인 |
| L03 reader(port-l03) | 파일 겹침 없음 | 없음 |

## 남은 것

- 구버전 Controller 의 재개 전 과정 호환 시험(Codex 3번 일부).
- 실 E4B acceptance49 의 라우팅 행 확인. 이 묶음은 x600 의 채팅 담당 · 답 문구를 바꾼다.
- 보류: L06b CORS credentials.
- L01 의 되돌릴 수 있는 기본값은 원 보고서와 같다: 판 질문의 팀 대기 없음, partial 은 안내 없음.
