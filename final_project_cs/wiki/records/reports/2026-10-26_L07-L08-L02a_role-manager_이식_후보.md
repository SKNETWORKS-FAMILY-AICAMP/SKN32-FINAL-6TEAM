---
type: report
title: L07 I06 명시 고정 · L08 Comment9 · L02a 공통 writer 내부 — role-manager a465c602 이식 후보(push 안 함)
status: candidate
domain: travel
---
# L07 · L08 · L02a role-manager 이식 후보

- 작성: 2026-10-26 08:55 KST · Hermes subagent(Opus) · Codex CLI 의견 1회(텍스트 전용).
- 기준: role-manager `a465c6022b9b` (ls-remote 확인). worktree `cache/scratch/port-l07-l02a-20261026-080756/rm`, tip `65b6bc99a`.
- 지킨 것: push 0 · 원본 코드 수정 0 · 유료 호출 0 · 공개 API/웹 계약 변경 0.
- 근거 감사: `2026-10-26_로컬전용코드_vs_role-manager_감사.md`.

## 결론

1. 커밋 8개를 만들었다. L07 1개, L08 1개, L02a 6개다. 빠른 관문은 실패 0이다: 9,996 통과, 173 skip, 전체 10,169건이다(`ev/gate.xml`). DB 시험은 140/140 = 100% 통과했다.
2. L02a 는 **내부만** 이식했다. 공개 `response_status`·`question_status` 투영은 모두 뺐다(L02b 보류). 다음 세 경로가 대상이다.
   - 문의 답(`read_requests`)
   - 채팅 변경 답(새 `response/change.py`)
   - 감시 안내(`response/monitoring.py`)

   세 경로 모두 결과를 `basis.response` 또는 outbox·Case 의 내부 `response` 에만 남긴다. 고객 문장은 바뀌지 않는다.
3. 계획 writer(`response/plan.py`)와 `change_read` 는 보류했다. 이유는 다음과 같다.
   - 계획 writer 는 공개 `response` 키를 더하고, 등록 후 재조회가 실패하면 오류를 낸다. 둘 다 관찰 가능한 계약 변경이다.
   - `change_read` 는 `decision_unit` 의 `change_explanation` fact 가 있어야 동작한다. 그 fact 는 L05 소유다.
   - 시험이 모두 공개 상태 필드를 단언한다.
   - Codex 의견도 같았다. 원문은 scratch `held-l02b/` 에 보존했다.
4. 실 E4B(L07 계획 읽기, 정상 속도 35/s) 결과는 다음과 같다.
   - 명시 고정: 1/1 = 100%. `items[0].locked=true`, 인용은 「이 일정은 고정해 주세요.」.
   - 예약만 있음: 2/2 = 100%. locked claim 없이 `booked`·`booking_no` 만 나왔다.
   - 「고정하지 마세요」: locked=false claim 0/1. 모델이 null 을 냈고, 고정되지 않는다는 결과는 같다.
   - **예산 초과**: 실제 E4B 호출은 7회다(한도 4). 원인과 영향은 아래 「한계」에 적었다.

## 커밋

| # | SHA | 묶음 | 파일 | 계약 |
|---|---|---|---|---|
| 1 | `563c9dfee` | L07 | `intake/agent_read.py`, `intake/pipeline.py::_agent_rows`, 시험 3, `wiki/external/intake-explicit-lock.md` | 공개 변경 없음. SYSTEM/`PROMPT_VERSION=intake.agent_read.v3-booked-not-locked` 변경(계획 읽기 프롬프트) |
| 2 | `70842e814` | L08 | `intake/hours.py`, `team_hooks/activity_ledger.py`, `instances/activity/closure_rules.py`, 시험 2 | 공개 변경 없음 |
| 3 | `f6171925c` | L02a | `response/writing.py`, `response/public.py` (cherry-pick -x 7edaa6930) | 새 모듈 |
| 4 | `f84392235` | L02a | `read_requests.py`, `trip_messages.py`(response_scope), `trip_api._web_view`(developer_basis만), 시험 2 | 공개 상태 투영 제외. 5e86f683a 기반 |
| 5 | `9699ad92e` | L02a | 새 `response/change.py`, `trip_messages._run_decision`(EDIT_ACTIONS), 시험 | 채팅 변경 답 → writer. 문장 불변·내부만 |
| 6 | `5c1987a5b` | L02a | `response/monitoring.py`, `planning/pending.py`, `itinerary_actions.py`, watch 4파일, 시험 | notices GET 투영 제외(be5262d86 기반) |
| 7 | `2e5414727` | L02a | `response/change.py` | Codex 검토 반영: 작성 성공·실패 기록이 함께 남지 않음 |
| 8 | `65b6bc99a` | L02a | 시험 import 정리 | ruff F401 |

patch SHA256 은 `patches/SHA256.txt` 에 있다. 전체 diff `all.patch` 의 SHA256 은 `75423f8d…a497c` 이다.

## 시험

- 각 묶음의 RED→GREEN 로그는 `ev/` 에 있다.
  - L07: 17 실패 → 33/33.
  - L08: 18 실패 → 38/38. 관련 31파일은 596/596.
  - 채팅 변경 writer: 4 실패 → 15/15.
  - monitoring: 33/33.
- 빠른 관문: `tests/architecture tests/contract tests/unit tests/security eval/tests -m 'not live and not db and not slow'` → 실패 0, 오류 0. 새 시험 nodeid 가 XML 에 모두 있다.
- ruff `F,E9`: 변경 파일 모두 통과.
- DB: `gugu_replay_improved_20261025`(run_aig 계열 runner, 고유 tenant)에서 9파일을 돌렸다 → 140/140.
  - 파일: `test_intake_review`·`intake_read_lock`·`chat_edit_web`·`chat_read_requests`·`consents`·`forecast_advisory`·`watch_relaxed`·`watch_failures`·`test_activity_ledger_db`.
  - 내 tenant 잔여 행 0. 표 변화는 동시에 돈 다른 작업자 tenant(`bulk_shift_*`)의 것이다.
- contract_correction 2건(단언 약화 없음):
  - `test_intake_agent_locked`: anyOf variant(L05) 유무와 상관없이 모든 항목 갈래를 검사한다.
  - `test_comment9_review_boundaries`: `_customer_inputs`(L10)가 없는 트리에서는 대역을 `raising=False` 로 둔다.
- 보류 시험:
  - `test_response_consumer_contract` 의 공개 상태 단언 6건(JSON/SSE·duplicate).
  - `test_plan_response_adapter`.
  - `test_skn_change_explanation`.
  - 원문은 `held-l02b/` 에 있다.
  - 대신 넣은 시험: 「보류 중 duplicate 가 상태 enum 을 싣지 않음」 1건, 실제 messages JSON/SSE 에 상태 필드가 없음.

## 겹침 (L05 동시 작업자)

- 같은 파일은 `read_requests.py` 하나다. L05 tip `601bb08a` 와 `git merge-tree` 로 합치면 충돌이 0이다.
- 이 이식은 `agent_read.py` 의 날짜/시각 anyOf 생성 variant 를 뺐다. 그 부분은 L05 temporal 소유다. L05 가 넣으면 `test_intake_agent_locked` 가 anyOf 갈래도 검사한다.
- `trip_messages.py` hunk 는 2개다: response_scope 1줄과 EDIT_ACTIONS writer 7줄.

## 한계

- **E4B 예산 초과(4 → 7)**:
  - 처음에는 probe 가 rm 설정 `ollama_num_ctx=12288` 을 보냈다. 로컬 live runner 는 8192 였다. 그래서 runner 가 다시 올라가며 첫 조각 시간 초과가 2회 났다.
  - 이 실행을 멈추려고 백그라운드 프로세스를 죽였지만, bash 자식 루프는 계속 돌았다. 그 결과 12288 호출이 2회 더 나갔다.
  - 이후 load-only `/api/generate` 로 8192 를 복원하고 8192 로 3회를 다시 돌렸다.
  - 중간에 본 `/api/ps` 는 12288 이었다. 그때 lease 는 다른 작업자(`v10c`)가 쥐고 있었다. 작업을 끝낼 때 다시 확인했더니 lease 는 비어 있었고 ctx 는 8192 였다. 그래서 다시 올리지 않았다.
- 실 E4B 는 이 트리에서 `read_source` 를 직접 불러 확인했다. 서빙 overlay 는 쓰지 않았다. 계획 읽기 전체 흐름(검토·GET)은 확인하지 않았다.
- 빠른 관문의 skip 173 은 a465c602 기준 XML 과 nodeid 단위로 대조하지 않았다.
- `change_read`·계획 writer 는 미이식이다. 감사의 L02a 완료율은 이식한 영역 기준 3/5 = 60% 다(공통·문의·감시 + 채팅 변경 연결).
