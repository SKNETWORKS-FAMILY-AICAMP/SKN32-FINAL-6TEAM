---
type: report
title: 접수 SSE beat · 슬롯 수명 — 최신 role-manager efc6fca47 누적 검증 · 실제 브라우저 확인 · 상대 날짜 누락 1파일
description: SSE 후보(35e1b0259 + 20a9a2bdf)는 role-manager 에 이미 들어 있다(op_stream 바이트 동일). efc6fca47 위 빠른 관문 10,725/0 · 격리 PG 158/159 → 날짜 누락 고친 뒤 1/1 · 실제 Chrome 에서 웹 watchIntake 기준 lost → 후보 끊김 0
status: draft
domain: travel
impl_scope: cs — tests/e2e/test_intake_prefill_scope.py (시험만, 제품 코드 0)
---

# 접수 SSE 최신 role-manager 누적 검증 — 2026-10-28

## 결론

- 팀 `role-manager` 최신은 `efc6fca47`(10-28 09:13, team fetch 로 확인). SSE beat 분리 · 슬롯 수명 후보는 **이미 들어 있다** — `3e7e4aabb` · `cf7e66164` · `724bbbb0d` · `f8e4aae0d`(이식 보고서 `2026-10-28_접수SSE_beat_role-manager_이식.md`).
  - `op_stream.py` 는 원 후보 `20a9a2bdf` 와 blob 이 같다(`35366c7f`). 새 시험 2파일도 같다. `trip_api.py` 는 이후 커밋(거절 문장 `bdb48ffc9`)과 이식 보강만 다르다.
- `efc6fca47` 위에서 SSE 와 무관한 **통합 누락 1건**을 찾았다: `tests/e2e/test_intake_prefill_scope.py` 가 날짜 `2026-10-15` 를 박아 두었다. 이 파일은 상대 날짜 전환(`4fee819ca`)의 기준(`8a1feae8f`)에 없던 갈래(`74b5eb479`)로 들어와 전환에서 빠졌다. 오늘(10-28) 실행하면 전부-과거 가드가 접수를 `fatal` 로 끝내 실패한다.
  - 수정: 같은 helper(`reldate.day`)로 옮겼다. 시험만 바뀌고 제품 코드는 그대로다. 격리 PG RED 1 → GREEN 1, 이웃 `test_intake_prefill.py` 4/4.
- push · 배포는 하지 않았다.

## 검증(격리 worktree, efc6fca47 + 이 커밋)

| 묶음 | 결과 |
|---|---|
| 빠른 관문 architecture · contract · unit · security · eval/tests, `not live and not db and not slow` (socket · psycopg 차단, MinGit PATH) | **10,725 passed · 0 failed** (skip 173) |
| SSE 단위 4파일(beat gap · slot lifetime · slot ownership · op_stream 비DB) | 39/39 |
| 격리 PG 12파일(이전 db10 + slot ownership + prefill_scope) | 158/159 — 실패 1 = 위 날짜 누락. 고친 뒤 prefill_scope 1/1 + test_intake_prefill 4/4 |
| `slow and not live and not db` | 135 passed · 4 failed(격리 runner 가 loopback bind 를 막은 test_llm_failover HTTP 4건 — 환경) |
| 위 4건 포함 test_llm_failover · local_queue 를 loopback 만 허용하는 guard(바깥 · 5433 차단 자체 시험)로 | **87/87** |
| ruff(바뀐 파일) · `git diff --check` | 통과 |

이전 보고의 환경 실패(guard bind 4 · sparse 로 빠진 `program/` 2 · python→git WinError 5 3)는 이번에 각각 loopback guard · 전체 checkout · MinGit PATH 로 다시 돌려 실패 0 이 됐다.

## 실제 브라우저 확인

준비: 실제 uvicorn 서버와 격리 PG 를 썼다. 접수를 읽는 중 상태로 두고, 브라우저가 붙은 뒤 8초에 `trip_intakes` 를 `ACCESS EXCLUSIVE` 로 20초 잠가 상태 조회를 멈췄다. 브라우저는 headless Chrome 145 이다. 서버 코드만 기준과 후보로 바꿨다. 기준은 `8a1feae8f`(SSE 수정 전 role-manager), 후보는 `efc6fca47` 이다.

| 소비자 | 기준 8a1feae8f | 후보 efc6fca47 |
|---|---|---|
| 브라우저 fetch 스트림(이벤트 시각을 브라우저가 잼) | 최대 간격 **23.3초**(beat 6.1초 → 29.4초) | 최대 간격 **3.09초**. 잠금 동안 `pending: "read"` beat 가 3초마다 왔다 |
| **웹의 실제 `watchIntake`**(`src/lib/live/stream.ts`, 7초 감시) | 13.9초에 **`lost`** — 화면의 「서버와 연결이 끊겼어요」 조건 | 45초 동안 beat 15개. 끝은 탐침이 끊은 `closed`, `lost` 0 |

- `watchIntake` 는 실제 소스를 rolldown 으로 묶었다. 세션(`./client`)과 react 대기(`./waiting`)만 scratch stub 으로 바꿨다(같은 출처 · `X-User-Key`). 두 서버에 같은 묶음을 썼다.
- 하지 않은 것: Next 화면 전체 렌더링, EKS · x600 확인, 실제 모델 읽기의 처리 시간.

## 한계

- 멈춘 DB 조회 자체의 수명은 그대로다. 조회는 상한 안에 묶일 뿐이다(슬롯 수명 후속 보고서와 같다).
- 위 표의 격리 PG 묶음은 SSE 주변 12파일이다. DB 전체 e2e 는 돌리지 않았다. `CI (main)` 전체는 부모 몫이다.
