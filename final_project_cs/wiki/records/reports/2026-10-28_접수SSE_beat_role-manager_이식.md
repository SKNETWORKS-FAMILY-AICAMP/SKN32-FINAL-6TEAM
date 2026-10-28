---
type: report
title: 접수 SSE beat 후보(35e1b0259 + 20a9a2bdf) role-manager 이식 · 관문 · 슬롯 반환 보강
description: role-manager 8a1feae8f 위 cherry-pick -x 2 + 보강 2 커밋(push 0). 빠른 관문 10,575/0 · 격리 PG 158/158 · 실제 uvicorn 잠금 탐침 최대 간격 10.42 → 3.02초
status: draft
domain: travel
impl_scope: cs — app/domains/travel_ops/modules/live_progress/op_stream.py · app/domains/travel_ops/entry/trip_api.py
---

# 접수 SSE beat 후보 role-manager 이식 — 2026-10-28

## 결론

- role-manager `8a1feae8f` 위 후보 tip 은 아래 표의 4 커밋이다(**push 0**). worktree `cache/scratch/sse-rm-20261028-0336/rm`.
- 빠른 관문 **10,575/10,575 통과**(skip 173, 실패 0). 기준 tip 의 XML 과 대조하면 빠진 nodeid 는 0개이고, 새 시험 26개만 늘었다.
- 격리 PostgreSQL 관련 묶음 **158/158**(11 파일). 첫 실행에서 1건이 시간 경쟁으로 실패했고, 시험을 고친 뒤 같은 nodeid 를 6/6 다시 통과했다(아래 3절).
- 실제 uvicorn 과 격리 PG 에서 상태 조회를 9초 잠갔을 때 SSE 이벤트의 최대 간격:
  - 기준 tip: **10.42초**. 웹 감시(beat 2번, 약 6~7초)가 거짓 「연결이 끊겼어요」를 띄우는 조건이다.
  - 후보: **3.0초 · 3.02초**(2회). 잠금 동안에도 beat 가 3초마다 왔다.
- 실제 웹 화면 브라우저 확인은 하지 않았다. 위 탐침은 httpx SSE 소비자를 썼다. EKS 와 x600 은 확인하지 않았다.

| 커밋 | 내용 |
|---|---|
| `f00806dcc` | cherry-pick -x `35e1b0259` — `op_stream.watch` beat 를 조회 · 내용 계산과 분리 |
| `4ae7f4d83` | cherry-pick -x `20a9a2bdf` — 끊김 뒤 도는 조회의 슬롯 · anyio 토큰 수명(`settle`) |
| `8af4a4435` | Codex 검토 후속 — 슬롯을 잡은 뒤 본문이 돌기 전에 실패하거나 떠나도 슬롯을 정확히 한 번 돌려준다(`give_back` · `_SlotStream`) |
| (4번째) | `tests/e2e/test_op_stream.py` 의 beat `pending` 시간 경쟁 정정, 시험 머리말 정정, 이 보고서 |

## 1. 이식 · 충돌

- 코드 충돌 0. `wiki/external/rest-endpoints/web-intakes.md` 한 단락이 두 번 충돌했다(두 커밋 모두).
- 해결: role-manager 의 「화면의 예상 시간 안내」 단락은 그대로 두고, 「접수 읽기 진행」 줄은 후보 쪽을 택했다. 충돌 표식 0을 확인했다.
- 모든 git 명령에 `-c core.autocrlf=false` 를 붙였고, 바뀐 파일의 CR 은 0이다.

## 2. 남아 있던 「환경 실패」 분류(앞 작업자 sse-slot-fix 9건) — 코드 결함 0

| nodeid 묶음 | 원인 | 이 tip 결과 |
|---|---|---|
| `test_llm_failover::test_http_*` 4 | 앞 runner 가 loopback bind 를 막았다. 이 파일은 root conftest 가 slow 로 표시해 빠른 관문에서 빠진다 | 격리 가드(p1_guard, loopback 허용 · 외부 차단 · 차단 0건)에서 통과 |
| `test_human_review_adapters` 2 | 앞 tree 가 sparse 라 `program/` 이 없었다 | 전체 worktree 에서 통과 |
| `test_api_key_file` 2 · `test_no_infra_in_tracked_files` 1 | python→git WinError 5 | MinGit PATH 로 84/84 통과 · 빠른 관문에서도 통과 |

## 3. 고친 것

1. **슬롯 반환 사각지대**(Codex 차단 항목, role-manager 기준 tip 에도 있던 결함)
   - 증상: `op_stream.acquire` 뒤 응답을 만들다 예외가 나거나, 본문 첫 순회 전에 브라우저가 떠나면(spec 2.0 에서 task group 이 `stream_response` 를 취소) 슬롯이 프로세스가 끝날 때까지 남았다. 3개가 쌓이면 그 사용자는 429 를 받는다.
   - 고친 뒤: `give_back` 이 정확히 한 번 반환한다. `flow` 가 돌았으면 `settle` 이 반환하고, 돌지 않았으면 `_SlotStream.__call__` 의 finally 가 반환한다. 응답을 만들다 난 예외는 바깥 except 가 반환한다.
   - 시험 `tests/unit/travel/test_intake_events_slot_ownership.py`: RED 2/4(슬롯 1이 남음) → 4/4 × 3회.
   - spec 2.4 send 실패와 429 거절은 고치기 전에도 통과했다. 회귀 감시용으로 둔다.
2. **`test_intake_events_end_at_once_…` 시간 경쟁**(후보의 contract_correction)
   - 증상: 내용 계산이 막 끝나고 `result` 가 큐에 들어가는 사이에 나간 beat 는 `pending: null` 이다. 소비 쪽이 `is_disconnected` 를 기다리는 동안 생긴다.
   - 판단: 이 beat 의 내용은 사실과 맞다. 제품 결함이 아니라 시험이 너무 좁았다. 다시 읽기(`read`)가 없다는 단언과 `reads == 1` 단언은 그대로 둔다.
   - 결과: db11 에서 1회 실패한 뒤 정정했고, 같은 nodeid 6/6, 파일 묶음 25/25 로 통과했다.

## 4. 검토

Codex CLI(`gpt-6.1-sol`)에 두 번 물었다. 둘 다 본문만 주고 도구는 쓰지 않게 했다.
- 1회차: session `01a17ea9-886d-7633-86fa-9a1b24740858`, 21,333 tokens. 2절의 차단 항목 (a) acquire 뒤 예외, (b) 본문이 돌기 전 떠남을 지적했다.
- 2회차: session `01a17eb5-70e2-7860-8798-afbbbcecaf1d`, 6,849 tokens. 보강 diff 를 보고 「(a)(b) 닫힘 · 추가 차단 없음 · YES」라고 답했다. 비차단으로 지적한 머리말 문구는 고쳤다.

## 5. 검증 수치

| 묶음 | 결과 | 증거(`cache/scratch/sse-rm-20261028-0336/ev/`) |
|---|---|---|
| 빠른 관문(architecture · contract · unit · security · eval/tests, `not live and not db and not slow`) | 10,575 통과 / 0 실패 / 173 skip(기준과 같은 skip) | `gate-fast2.xml` · 기준 `integ-c12-wait-ev/ev/gate-fast.xml` |
| 격리 PG 11 파일 | 157/158 → 정정 뒤 해당 파일 25/25 + nodeid 6/6 | `db11.xml` · `db11b.xml` · `opstream_rep*.xml` |
| ruff check .(CI 와 같은 0.16.8) | 통과 | `ruff_all.log` |
| 실제 uvicorn 잠금 탐침 | 기준 10.42초 / 후보 3.0 · 3.02초 | `probe_base.json` · `probe_cand.json` · `probe_cand3.json` |
| 웹 바뀜 | 없음 → vitest 대상 아님 | — |

- 격리 PG: `sse-slot-fix-20261028/pgdata` 의 사본을 `sse-rm-20261028-0336/pgdata` 에 두었다. 주소는 127.0.0.1:55513 이고, 이 tree 에서 migrate 했다. 끝나고 멈췄으며 폴더는 보존했다.
- 공유 DB · 운영 DB · 모델 호출은 0이다. live 8042 · 3100 은 건드리지 않았다.

## 6. 남은 일

1. 부모: role-manager push 여부를 결정한다(push 전 `ls-remote` 로 팁이 그대로인지 확인).
2. 실제 웹 화면에서 느린 읽기를 브라우저로 확인하고, EKS 에서 80.7초를 분할한다(AWS 자격이 필요하다).
3. 한계(앞 보고서와 같다): 멈춘 DB 조회 자체에는 시한이 없다(`statement_timeout`). 첫 조회(`accepted` 전)에는 beat 가 없다. 응답 객체가 ASGI 로 한 번도 호출되지 않는 경우(endpoint 뒤 미들웨어 실패)는 이번 보강 범위 밖이다.
