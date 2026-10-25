---
type: report
title: 통합 HEAD 전체 시험 재실행 · push 보류 · 로컬 서빙 교체 보류 결정
status: draft
domain: travel
---

# 2026-10-26 통합 HEAD 전체 시험 · push · 로컬 서빙 결정

작업 위치: 격리 worktree `scratch/mgr-merge-20261026-0045`, 브랜치 `feat/past-date-guard-ext-20261026`, 시험 대상 HEAD `2cccbfaef`(= team/role-manager `08b995976` + team/develop + team/role-eval-ui 병합 + 과거 날짜 가드레일 3커밋). 원본 `C:/_proj/final_workspace` 는 건드리지 않았다. 증거: `cache/scratch/fullrun-20261026/`.

## 결론

- 전체 시험: 요구 범위는 모두 통과했다(실패 0). 비교 기준인 이전 가지 `08b995976`에서도 같은 runner로 실패가 0건이었다.
- push 안 함: 원격 role-manager가 그사이 `08b995976` → `1e4e3b246`으로 12커밋 앞섰다. 사용자 조건 (c)가 걸렸고, fast-forward도 아니다. PR도 만들지 않았다. Codex도 같은 판단이었다.
- 로컬 서빙 교체 안 함: 조건 (b) 「무영향」을 확인하지 못했다. 또 실제로 내보낼 후보(v9 + 이번 패치 = v10)가 아직 없다. Codex도 같은 판단이었다. 현재 v9 서빙은 그대로 둔다.

## 시험 (DB 없음 · 실DB/네트워크 차단)

- 실행 환경: Python 3.12 venv(`date_risk_env_312`), 격리 runner `past-guard-ext-20261026/run_isolated.py`, CI와 같은 가짜 설정.
- 차단: socket connect/bind/listen, `create_connection`, `psycopg.connect`를 막았다. stdlib `_fallback_socketpair`만 예외다.
- 선택: `-m "not live and not db"`. slow는 포함했다. DB 표시 시험은 실행하지 않았다.

| 묶음 | HEAD 2cccbfaef | 이전 가지 08b995976 |
|---|---|---|
| tests/unit/travel | 7382/7382 = 100% 통과(skip 128 별도) | 7200/7200 = 100%(skip 128) |
| architecture + contract + security | 607/607 = 100% | 606/606 = 100% |
| web tsc · eslint | 오류 0 · 0 | — |
| web vitest (node 24.22.1) | 1183/1183 = 100% (131 파일) | — |
| (추가) tests/unit 나머지 | 1577/1581 통과, 4 실패(skip 46) | 같은 4건 실패 |

- skip 128: 모두 git 밖 자료가 없어서 생긴 것이다(이동 시간표·도로 그래프·미쉐린 CSV). 통과로 세지 않았다.
- 추가 4건 실패(`tests/unit/infrastructure/test_llm_failover.py::test_http_*`)는 제품 실패가 아니다. 시험이 loopback `HTTPServer`를 bind하는데 격리 runner가 이를 막았다. 이전 가지에서도 같은 4건이 실패했다. 요구 범위(unit/travel) 밖이며 loopback 허용은 별도 승인 사항이라 풀지 않았다.
- 이전 실행(`past-guard-ext-20261026/gates.log`)의 13 실패·6 오류는 DB 표시 시험이 섞인 탓이었다. 이번에는 DB 표시 시험을 선택에서 빼고 다시 돌렸다(실패 0).

## push 판단

- 바로 전 fetch 결과: `team/role-manager` = `origin/role-manager` = `1e4e3b246`. 2026-10-26 05:32 roroblack 계정 커밋으로, `08b995976` 이후 12커밋이다.
- 겹치는 작업:
  - all-past: `c023140b5`, `fdbe5b4ef`, `fb6a6cba1`, `376f2a672`
  - 채팅 스트리밍: `eebd96919`
  - 실내/야외 되묻기: `2ce73990c` 외 3건
  - 계획 담기 보조 칸 스위치: `d3d0a0637`
- `git merge-tree` 결과: 웹 5파일이 내용 충돌한다(`intake-review.tsx`, `plan-check/model.ts`, `plan-check/parts.tsx`, `plan-check/stop-questions.ts`, `lib/live/intake-review.ts`). wiki index/log도 충돌한다.
- 결정: role-manager push 0, 강제 push 0, PR 0, 개인 저장소 push 0.
  - 이유 1: 조건 (c) 원격 전진, 그리고 fast-forward 불가.
  - 이유 2: role-manager는 5분 내 x600 자동 배포 대상이다.

## 로컬 서빙 판단

- 현재 구성(백업: `fullrun-20261026/serving/v9-identity/`):
  - API: PID 5088. 부모는 venv launcher 24140이고, 실행 파일은 `integ-v9-20261026-025943/runtime-v9-serving/launch-serving.py`(sha256 `c5aa961d…`)다.
  - 바인딩: 127.0.0.1:8042 + 192.168.0.15:8042.
  - 연결: Ollama `tripilot-pointer:e4b-ft`(127.0.0.1:11434), 로컬 PG 127.0.0.1:5433 `acop_cs`.
  - 설정: plan_test_mode true, `local-guardrails.yaml`(sha256 `33378294…`).
  - 웹: web-v5 release 127.0.0.1:3100(PID 26720)과 192.168.0.15:3100(PID 27028).
- 교체하지 않은 이유:
  1. v9 원천에는 HEAD에 없는 로컬 전용 모듈이 있다(`native_context_tokenizer`, `native_tool_renderer`, `context_instructions`, `change_read`, `components/response/` 등). 또 I06 `locked/locked_quote`를 넣은 agent_read 프롬프트도 있다. 따라서 HEAD를 그대로 띄우면 로컬 Ollama 경로와 기능이 빠진다.
  2. 올바른 후보는 v10 = v9 + 제품 패치(`pastguard-product.patch`, app+config)다. `git apply --check` 결과는 10파일 중 9파일 적용 가능, `agent_read.py` 1파일 실패였다. 양쪽이 모델 프롬프트·스키마를 고쳤기 때문이다. 합친 프롬프트는 E4B에서 측정한 적이 없다.
  3. 8042에 Hermes 데스크톱 앱 네트워크 프로세스(PID 20924)의 ESTABLISHED 연결 2개가 있었고, 최근 TIME_WAIT 약 10개가 있었다. 사용 중이라고 단정할 수는 없지만 「무영향」도 확인되지 않았다(Codex 지적 반영).
- v10 구성 순서(다음 담당):
  1. v9 원천 사본에서 `agent_read.py`를 손으로 3-way 병합한다.
  2. `local-guardrails.yaml`에 `travel.chat_edit.past_date_choices: 3`을 추가한다.
  3. 새 runtime-inputs/SERVING_FREEZE를 만든다.
  4. `--shadow --preflight`를 돌린다.
  5. E4B 날짜 81문장 + I06 locked 재측정을 공유 lease 아래에서 한다.
  6. idle gate(`runtime-v9/pre_swap_idle_check.py` 방식)를 통과시킨다.
  7. 교체한다.
  8. `/health`, LAN, test mode, Ollama, 과거 날짜 422/되묻기를 확인한다.
- 웹 delete-only UI를 반영하려면 별도로 웹을 다시 빌드해야 한다.
- 롤백: 교체하지 않았으므로 필요 없다. 교체할 때의 롤백은 v10 프로세스만 중지한 뒤 아래를 실행한다.
  - 실행: `api-runtime-20261025-014236/venv/Scripts/python.exe -B integ-v9-20261026-025943/runtime-v9-serving/launch-serving.py`(cwd 같은 폴더)
  - 검증: `runtime-v9/post_swap_verify.py`

## Codex 논의 (`fullrun-20261026/codex_review.log`, read-only, 1회)

- push: 「DO NOT」. 원격이 전진해 중단 조건이 충족됐다고 봤다. PR도 지금은 만들지 않는 것이 맞고, 활성 작업자와 조정이 먼저라고 했다. 새 기준에 다시 병합해도 push 승인이 자동으로 되살아나지 않는다는 점을 짚었다. → 그대로 반영했다.
- 서빙: 「DO NOT」. v10이 없고 결합 프롬프트를 E4B로 재측정해야 한다고 봤다. → 반영했다.
- 표현 정정: keep-alive·TIME_WAIT만으로는 「사용 중」이 아니라 「무영향 미확인」이라고 해야 한다고 지적했다. → 반영했다.
- 추가 권고: 롤백에 원천·환경·설정·웹 빌드 버전을 남길 것, 교체 후 LAN·test mode·Ollama·과거 날짜 동작을 확인할 것. → v9 식별 정보 백업과 위 v10 순서에 반영했다.

## 남은 것

- 새 원격 `1e4e3b246` 위로 다시 병합한다. 웹 5파일 충돌과 all-past 의미 충돌을 풀고 전체 시험을 다시 돌린다. push는 새로 합의한 뒤에 한다.
- DB 표시 시험(unit/travel 503 + gates 29 deselected)은 실행하지 않았다.
- v10 로컬 서빙 후보를 만들고 E4B 재측정을 한 뒤 교체한다. 웹은 다시 빌드해야 한다.
