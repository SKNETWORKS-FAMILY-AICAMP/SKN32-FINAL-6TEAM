---
type: report
title: 지난 일정은 삭제만 — 서버 「완료」 · 웹 수정 화면 · 채팅 고치기
status: draft
domain: travel
---

# 2026-10-26 지난 일정은 삭제만(수정 불가)

작업 위치: 격리 worktree `scratch/past-edit-delete-only-20261026`, 브랜치 `feat/past-edit-delete-only-20261026`(부모 `337bcbd68`). 원본 `C:/_proj/final_workspace` · 동시 작업 worktree `mgr-merge-20261026-0045` 는 건드리지 않았다. `agent_read.py` · `dates` · 프롬프트 미변경. 커밋까지만(push · 배포 · 로컬 서빙 교체 없음). 실DB · 실모델 · 외부 호출 0.

## 결정(사용자 가설 → 확정 구현)

- 지난 일정(끝 ≤ 지금, 끝이 없으면 시작)은 기록이다 — 이름 · 장소 · 「장소 없음」 · 날짜 · 시각 · 고정 · 순서 **무엇도 고치지 않고 뺄 수만 있다**. 다시 하려면 새 일정으로 추가한다. [2026-10-26 기록](2026-10-26_past-date-guard-extension.md)의 「지난 일정 이름 수정 허용」을 대체한다.
- 그대로 둔 것: 새로 넣거나 옮기는 날짜 · 시각은 지금(분 단위) 이후만, 진행 중(시작 ≤ 지금 < 끝) 일정은 지금 이후 규칙 안에서 고칠 수 있다, 진행 중이거나 앞으로 올 일정이 있었으면 하나는 남긴다(`no_upcoming_items` — 이미 끝난 여행은 해당 없음).

## Codex 검토(`codex exec -s read-only`, codex-cli 0.163.0, 로그인됨)

- 1차(정책, `codex_review.log`): Codex 의 셸(PowerShell)이 읽기 전용 정책에 막혀 **코드를 읽지 못하고 정책 설명만으로** 「부분 타당」. 지적과 반영:
  1. 끝난 여행에 `no_upcoming_items` 를 일률 적용하면 기록 삭제가 막힌다 → 현재 코드는 원래 판에 진행/미래 일정이 있을 때만 검사(`_upcoming(base) and not _upcoming(new)`)라 이미 면제. 시험 추가로 확인.
  2. 진행 중 일정은 현재 일정으로 취급 → 그대로(이름 수정 허용 시험 추가).
  3. 저장 시점에 다시 판정, 편집 중 끝난 일정의 이름 · 장소 · 고정 변경도 거절 → **반영**(`plan_edit`, 기준은 서버 원본).
  4. 숙박은 실제 체크아웃 일시로 판정 → 서버는 `end_date` 로 이미 맞음(시험 추가). 웹은 2차 지적으로 반영.
  5. 고정(이미 지난) 일정은 접수에 없어 「삭제만」의 삭제 경로가 없다 — 최소 구현은 명시적 삭제 id 목록 → **미반영(남은 일)**. 이번에는 채팅이 그 사실을 정직하게 답하게만 했다.
  6. 되돌리기 · 대안 선택이 지난 일정 값을 바꿀 수 있다 → **미반영(범위 밖, 남은 일)**.
  7. 감시 · 실행 정보는 고객 일정 값과 구분 → 이번 변경은 수정 접수 「완료」 · 채팅 고치기만 막아 감시 쓰기 경로와 충돌 없음(코드 미변경).
  8. 서버 시각 기준 판정 · 화면은 안내용 → 그대로(웹은 사전 안내, 최종 판정은 서버).
- 2차(구현 diff 전문을 프롬프트에 실어 검토, `codex_review_v2.log`) 「반영 권고」:
  1. 웹 `pastEdit` 가 숙박 체크아웃 날(`endDate`)을 몰라 이틀 걸친 진행 중 숙박의 이름 수정을 막는다 → **반영**(`PastDraft.endDate`, `StopEditor` 가 원래 일정의 `endDate` 를 넘김, RED→GREEN).
  2. 시작 비교가 분 단위 내림(`_minute`)이라 12:00:30 에 12:00 시작을 허용 → **미반영**: 접수 시각이 HH:MM 이라 「지금 바로」를 허용한 앞 커밋의 의도된 규칙.
  3. 정책 잠금(숙박 · 항공) 잠금만 바꾼 경우 · 끝 없음 · 끝 = 지금 시험 부족 → **반영**(시험 추가, 기존 동작이 맞아 RED 없음). 순서만 바꾸기는 시각 변경으로만 표현돼 같은 검사를 탄다. 채팅 「뒤 일정 밀기(shift)」는 지난 기준 일정 뒤의 앞으로 일정만 옮기므로 지난 일정 수정이 아니다(허용 유지).

## 변경

| 경로 | 변경 |
|---|---|
| 서버 `reopen.plan_edit` | 바뀐 일정의 원래 값이 끝났으면(끝 ≤ 지금) 무엇을 고쳤든 `past`(원래 이름으로). 삭제는 그대로 허용. `_moved_into_past` 는 진행/미래 일정의 시각 규칙만 |
| `reopen_commit` | 422 `item_in_past` 문구 「지난 일정은 고칠 수 없어요(뺄 수만 있어요) · 새로 넣거나 옮기는 날짜·시각은 지금 이후만 돼요: …」(코드 그대로) |
| 채팅 `chat_edit.ops_for` | 장소 바꾸기 · 고정/풀기 · 순서 바꾸기(두 일정 중 하나라도) · 시각 옮기기 대상이 지난 일정이면 `item_in_past` 「「X」은(는) 이미 지난 일정이라 고치지 않았어요. 지난 일정은 기록으로 두고 뺄 수만 있어요 — 다시 하려면 새 일정으로 추가해 주세요.」 빼기 · 그 뒤에 넣기는 그대로 |
| 채팅 고정 일정 | `frozen_refusal`: 지난 고정 일정 고치기는 위 문구, 빼기는 「지난 일정 빼기는 아직 채팅으로 하지 못해…」(경로 없음을 정직하게), 지나지 않은 고정(예약 등)은 기존 `frozen_item` |
| `edit_intent.time_ops` | 끝난 일정 시각 바꾸기 거절을 같은 문구로 |
| 웹 `model.pastEdit` · `StopEditor` · `error-text` | 지난 일정이면 이름 · 장소 · 「장소 없음」 변경도 「past」. 숙박 `endDate` 반영. 안내 「지난 일정은 고칠 수 없고 뺄 수만 있어요 — 다시 하려면 새 일정으로 추가해 주세요」, `item_in_past` 표 문구 갱신 |

하드코딩 점검: 추가한 비시험 줄의 문자열은 고객 안내 문구(표시 문구)뿐이고 고객 원문 낱말 매칭은 없다. 판정은 일정의 저장된 시각(`ends_at`/`starts_at`)과 서버 시계로만 한다.

## 검증(실행 결과, 증거 `scratch/past-edit-delete-only-20261026-evidence/`)

격리 runner `run_isolated.py`(socket · psycopg 차단, root 변수 `PEDO_SOURCE_ROOT`), Python 3.12 venv `scratch/date_risk_env_312`.

- RED: `red-python.log` 12 실패/16(새 시험 파일, 기능 RED — `frozen_refusal` 없음 · 거절 안 됨), `red-web.log` 2 실패/7, `red-web-stay.log` 1 실패/8.
- GREEN: 관련 Python 묶음 **320/320 = 100%**(`focused-final.xml` — 앞 커밋 303 + 새 17). `--confcutdir=tests/unit` 로 좁히면 `test_edit_intent.py::test_restaurants_and_relaxed_options_remain_near_requested_origin` 1건이 `composition_unbound`(runner 가 조립 fixture 를 뺀 탓 — 본 묶음은 `tests/conftest.py` 포함으로 통과).
- `tests/unit/travel` 전체(`-m "not db and not live"`): **7367 passed / 128 skipped / 503 deselected, 실패 0**(`unit-travel.xml`; 마지막 시험 1건 추가 · 웹 수정 전 시작한 실행).
- ruff F·E9(변경 Python 7파일) 통과, `git diff --check` 통과.
- 웹(`frontend/apps/web`, 이 worktree 에 `npm ci`): vitest 전체 **1183/1183**(131 파일), `tsc --noEmit` 0, 변경 파일 eslint 0.

## 남은 것 · 한계

- **이미 지난(고정) 일정의 삭제 경로가 없다.** 수정 접수가 지난 일정을 싣지 않아(`fixed_reason=past`) 웹 회색 줄 · 채팅 모두 뺄 수 없다. 이번 변경으로 서버가 막는 것은 「수정 화면을 연 뒤 끝난 일정」의 수정뿐이다. Codex 권고 최소안: 수정 접수에 「뺄 고정 일정 id」 목록(`reopen_frozen` 항목의 표시)과 웹 회색 줄 삭제 버튼 · 채팅 빼기를 같은 처리로 연결하고, `plan_edit` 가 그 id 를 재부착에서 빼고 `removed` 로 알린다. 공유 계약(`web-intakes.md`) 변경이라 별도 결정 필요.
- 되돌리기(`rollback`) · 대안 교체 · 제안 선택이 옛 판을 되살릴 때 지난 일정 값이 바뀌는지는 이번 범위 밖(미확인).
- 실DB e2e(`tests/e2e/test_trip_reopen.py`) · 실화면 · 웹 build · 실모델 미실행.
