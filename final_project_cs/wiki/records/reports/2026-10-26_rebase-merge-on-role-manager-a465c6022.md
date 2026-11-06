---
type: report
title: 원격 role-manager(a465c6022) 위 재병합 · 충돌 해결 · 전체 시험
status: draft
domain: travel
---

# 2026-10-26 원격 role-manager 위 재병합 · 전체 시험

> `[2026-11-06 후속]` 이 문서의 push 보류 · 서빙 롤백 경로는 낡았다 — 원격 `1cf4542a1` 위 재병합(`43a3ced29`)과 push · 정리는 [2026-11-06 마무리](2026-11-06_pastguard-remerge-push-cleanup.md). 여기 적힌 scratch 경로(`fullrun-20261026` · `integ-mgr-a465c6022-20261026` 등)는 이미 없다.

작업 위치: 격리 worktree `scratch/integ-mgr-a465c6022-20261026`(`core.autocrlf=false`로 꺼냄), 브랜치 `integ/rebase-on-manager-a465c6022-20261026`. 원본 `C:/_proj/final_workspace`는 건드리지 않았다. push는 하지 않았다. 증거는 `cache/scratch/fullrun-20261026/integ-877e6723b*`, `integ-92541686d/`, `cache/scratch/integ-mgr-a465c6022-20261026-tools/`에 있다.

## 결론

- 원격이 또 앞섰다. 지시 시점의 `1e4e3b246` 뒤로 13커밋이 더 있다(최신 `a465c6022`, 08:00). push할 수 있는 후보가 되려면 최신 끝에 올려야 한다. 그래서 `a465c6022`에서 브랜치를 땄다. `1e4e3b246`도 그 조상이다.
- 우리 가지 `07dcebe35`를 병합했다(rebase 아님). 이어서 Codex 검토에서 나온 결함 1건을 고쳤다.
  - 최종 코드 커밋은 `92541686d`이고, 이 문서 커밋이 그 위에 있다. 원격 대비 ahead 10 / behind 0(문서 커밋 포함)이다.
  - fast-forward로 push할 수 있다. 다만 push는 하지 않았다.
- 시험(DB 없음, 실DB/네트워크 차단): 요구 범위의 실패는 0이다.

## 원격 커밋 (08b995976 이후 first-parent)

`1e4e3b246`까지 12커밋이다. 작성자는 roroblack이고 ST4F-739 한 건만 Choi-Sangwook이다.

- all-past 4건:
  - `c023140b5`: 전부 과거인 계획은 접수 첫 검사 뒤 `fatal all_dates_in_past`로 처리한다(`pipeline._wholly_past`, `review.wholly_past`, `ALL_PAST_MESSAGE`).
  - `fdbe5b4ef`: 웹에서 전부 과거인 접수는 계획 담기로 돌려보내고 글은 보존한다(`entryReturnOf`).
  - `fb6a6cba1`: 웹이 거절 문구를 번역하고, `date` 검사 줄에 「날짜」 라벨을 붙인다.
  - `376f2a672`: 고정 날짜 fixture의 시계를 고정한다.
- 채팅 실내·야외 바꾸기 5건: `2ce73990c`, `53c3c273f`, `da4ccd974`, `c34bd376f`, `1e4e3b246`.
- 그 밖에 3건: 채팅 결정 스트림(`eebd96919`), 예약 취소·환불 미지원 답(`231e303a5`), 계획 담기 보조 칸 운영 스위치(`d3d0a0637`, ST4F-739).
- 웹 5파일에 닿은 변경은 `fdbe5b4ef`와 `fb6a6cba1`뿐이다. 둘 다 all-past 관련이다.

그 뒤 13커밋은 다음과 같다.

- 잠금·예약 일정 채팅 교체 거절
- 시작 알림 문구(D-020)
- Ollama 예열과 `num_ctx` 12288
- 읽기 예외 비노출
- 절대 시각·날짜 옮기기
- Activity 공개 웹 보조조회와 ddgs
- 감시 분류 계획과 sweeper
- develop 병합(`4a67c6c73`)
- 공개 응답의 해석 실패 사유 제거
- Routing P2(D-024)
- reader 정책(`a465c6022`, L03)

## 충돌과 해결

- 코드는 모두 자동 병합됐다. `1e4e3b246` 기준에서 충돌하던 웹 5파일도 이번에는 충돌하지 않았다.
  - 이유: 원격의 develop 병합 `4a67c6c73`이 우리 통합 병합(`446bbb170`, `0239cef98`)과 같은 develop·role-eval-ui 입력을 이미 품고 있다.
  - 5파일 중 4개는 원격 내용 그대로다. 우리 기능 커밋은 이 4개를 건드리지 않았다.
  - `plan-check/model.ts`에는 원격의 `date` CheckKind와 우리 `pastEdit`·`draftProblem`이 함께 들어 있다.
- 보존 검산은 프로그램으로 했다.
  - 우리 기능 diff(`0239cef98..07dcebe35`)의 추가 줄은 2606/2606이 병합 트리에 있다.
  - 원격 diff(`08b995976..a465c6022`)의 추가 줄은 docx를 빼면 1줄만 빠졌다. `plan-check.tsx`의 import 줄이고, 우리 쪽이 `type SeoulClock`을 더한 상위집합이라 내용은 빠지지 않았다.
- wiki 4파일은 손으로 풀었다. 양쪽 내용을 모두 남겼다.
  - `final_project_cs/wiki/external/trip-chat-context.md`: 원격의 새 절을 둔 뒤, 우리의 지난 날짜 bullet을 별도 2026-10-26 제목 아래에 붙였다.
  - `final_project_cs/wiki/index.md`: 우리 2026-10-26 항목을 넣었다. 이미 아래에 있는 2026-10-25 두 줄은 중복이라 뺐다.
  - `final_project_cs/wiki/log.md`: 양쪽 항목을 모두 남겼다.
  - `wiki/index.md`: 우리 2026-10-26 항목과, 원격이 고른 2026-10-25 두 줄을 남겼다.
- 충돌 표시는 0이다. 병합 트리를 `git grep -E '^(<<<<<<<|>>>>>>>)( |$)'`와 `'^=======\r?$'`로 검사했다. `a465c6022`와 `07dcebe35`도 0이다.
- all-past 두 구현은 코드상 겹치지 않는다.
  - 원격 관문은 저장된 첫 검사를 `all_dates_before_today`로 본다. 모르는 날짜는 과거로 치지 않는다.
  - 우리 쪽에서 연도 없는 날과 `year_unverified` 날은 다가오는 날로 채워져 과거가 되지 않는다.
  - 이 맞물림은 `test_all_past_gate_date_forms.py`로 고정했다.

## Codex 검토 (codex-cli 0.163.0, `codex exec -s read-only`)

1. 1회차(worktree 읽기 시도): 파일·git 읽기가 정책에 막혔다.
   - wiki 해결은 「OK」였다.
   - 지난 HEAD 기준의 「웹 5파일 충돌·push 보류」 항목에 당시 HEAD를 표시하라고 권했다. 반영했다(아래 index 항목).
2. 2회차(코드 stdin 제공): 「고칠 것 있음」.
   - 지적 내용: 에이전트가 달력에 없는 날(「2월 30일」, 「2025년 2월 29일」)을 버리면 `resolve_dates`가 다른 일정의 첫날로 채운다(`day_offset`). 그러면 적힌 지난 날짜와 함께 있을 때 전부 과거 관문이 열린다. 새 시험 설명의 「연도를 적은 지난 날만」 표현도 부정확하다(상대 날짜인 어제도 과거다).
   - 반영: 커밋 `92541686d`. `AgentItem.date_invalid`(날짜 인용)를 `_agent_rows`로 넘기고, `resolve_dates`가 그 일정을 `unknown`(메모 포함)으로 둔다.
   - RED는 `fullrun-20261026/integ-877e6723b/red-impossible-date.log`(2 failed)이고, GREEN은 7/7이다. 시험 설명 문구도 고쳤다.
3. 3회차(수정 diff를 stdin으로 제공): 「OK」, 추가 문제 없음.

- reader 정책(`a465c6022`)과 우리 `date_form`·`year_quote` 스키마는 함께 써도 된다.
  - `date_form`은 고정 enum이다. 원격이 피한 「원문 줄을 스키마 enum에 싣기」와 다르다(Codex 2회차 동의).
  - 다만 유료 wrapper 전체가 이를 지키는지는 제시 범위 밖이다.

## 시험 (DB 없음 · 실DB/네트워크 차단)

- 실행 환경: Python 3.12 venv와 `past-guard-ext-20261026/run_isolated.py`. socket과 `psycopg.connect`를 차단하고, stdlib socketpair만 예외로 뒀다.
- 선택: `-m "not live and not db"`.

| 묶음 | 877e6723b(병합) | 92541686d(최종) |
|---|---|---|
| tests/unit/travel | 7733/7733 = 100%(skip 128) | 7740/7740 = 100%(skip 128) |
| architecture + contract + security | 608/608 = 100% | 608/608 = 100% |
| tests/unit 나머지 | 1657/1661, 4 실패(skip 46) | 1657/1661, 같은 4 실패 |
| web tsc · eslint | 0 · 0 | 웹 변경 없음(재실행 안 함) |
| web vitest (node 26.7.0) | 1205/1205 = 100% (134 파일) | 웹 변경 없음 |

- all-past 관련(최종):
  - `test_all_past_dates` 5/5, `test_all_past_confirm_api` 8/8, `test_intake_all_past_gate` 12/12, `test_all_past_gate_date_forms` 7/7
  - `test_past_stop_delete_only` 17/17, `test_reopen_past_rules` 9/9, `test_llm_date_form` 14/14, `test_yearless_agent_dates` 6/6
- 4 실패(`test_llm_failover.py::test_http_*`)의 원인은 runner가 loopback `HTTPServer` bind를 막아서다. 전처럼 제품 실패가 아니다. 이전 HEAD `2cccbfaef`에서도 같았다.
- skip 128은 git 밖 자료가 없어서 생긴 것이다. 통과로 세지 않았다.
- 범위 실패가 0이라 원격 `a465c6022` 자체의 기준 실행은 따로 하지 않았다.
- `ddgs`·`primp`는 venv에 없다. 그래도 `test_activity_public_web_ddgs` 23/23은 대역으로 통과했다.
- DB 표시 시험(unit/travel 503건, gates 29건)은 실행하지 않았다.

증거(저장소 안): [codex 1~3회차 답 · remerge diff · wiki 해결 스크립트 · 시험 요약](../evidence/2026-10-26_rebase-merge-a465c6022/tests-summary.txt) — 같은 폴더의 `codex_review_round*.md` · `remerge.diff` · `resolve_wiki.py`.

## 남은 것

- push 여부는 새로 합의해야 한다. push 직전에 fetch해서 `team/role-manager == a465c6022`인지 다시 확인한다. role-manager는 x600에 자동 배포된다.
- DB 표시 시험과 실모델(E4B)에서 날짜 판정을 아직 측정하지 않았다.
- 로컬 서빙 v10은 이전 인계 그대로 남아 있다.
