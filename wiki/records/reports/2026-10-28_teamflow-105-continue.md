---
type: report
title: TeamFlow 미완료 105건 이어서 처리 — 다시 조회 · 실제 반영 확인 · 격리 후보
description: 117건 점검 뒤 남은 105건을 다시 받아 EKS 릴리스(PR #107) 이후 원격과 대조, 실제 반영된 ST4F-710 하나만 완료로 바꾸고, 521 · 724 · 502 · 531 · 574 · 714 격리 후보 4커밋(push 0)을 검증해 이슈에 증거를 덧붙였다
status: done
domain: travel
impl_scope: cs
---

# TeamFlow 미완료 105건 이어서 처리 (2026-10-28 밤)

앞 보고서: [117건 전수 점검](2026-10-28_teamflow-open-117-sweep.md).

## 1. 다시 조회 (1회차)

- 같은 읽기 도구(상태 4 × 유형 4 = 16묶음, 묶음당 최대 248 < 500)로 다시 받음: 688건 = done 583 · review 51 · todo 39 · inprogress 15. **미완료 105/688 = 15.3%**. 앞 보고서 갱신 뒤와 비교해 상태 · 본문 · 제목이 바뀐 이슈 0건.
- 원격(`git ls-remote` team): role-manager `c52fb5c69` · develop `3463b30c6` · main `20c296e77`(PR #107 EKS 릴리스). 앞 보고서 기준(`efc6fca47` · `36ba4c2fc` · `e88e01925`)에서 모두 움직였다.
- 새로 들어간 이슈 커밋: ST4F-710 `e6e02f4c7`(격리 후보 `e6e754f27` 의 cherry-pick) — role-manager · develop · main 셋 다 조상. ST4F-631 `6833b1153` 도 이제 셋 다. 574 · 714 후보 `010f9deeb` 은 아직 어디에도 없다.
- main `20c296e77` 검사: CI (main) 40696089641 success · CI (web) 40696089661 success · CD (AWS) 40699378486 success(앞선 40697290826 실패 뒤 재실행). develop `3463b30c6` CI (develop) 40694024694 success.

## 1-b. 다시 조회 반복 (4회)

| 회차 | 시점 | done | review | todo | inprogress | 미완료 |
|---|---|---|---|---|---|---|
| 1 | 시작 | 583 | 51 | 39 | 15 | 105/688 = 15.3% |
| 2 | 710 갱신 직전 | 583 | 51 | 39 | 15 | 105 — 1회차와 바뀐 이슈 0 |
| 3 | 증거 갱신 직전 | 584 | 51 | 38 | 15 | 104 — 바뀐 것은 710 하나 |
| 4 | 끝 | 584 | 51 | 38 | 15 | **104/688 = 15.1%** |

- 4회차에서 1회차와 달라진 이슈는 8건이다(710 상태 · 7건 본문 덧붙임). 8건 모두 원래 본문 앞부분이 그대로다.
- role-manager push 보류는 [라우팅 인계](../../handoff/2026-10-28_routing-open-audit-recount.md)에 적혀 있다. 라우팅 세션의 `fix/routing-open-audit-20261028` 가 `c52fb5c69` 위에서 반영을 기다린다. 겹치지 않도록 이번 작업은 **push 0** 이다. 운영 데이터 쓰기도 0이다.

## 2. 상태를 바꾼 것 — 1건

| 키 | 전 → 후 | 증거 |
|---|---|---|
| ST4F-710 | todo → **done** | 고침이 세 가지 모두에 있다. main CI · CD success. main 트리에서 `test_intake_stays` + `test_intake_trip_title_memo` 22/22 통과(격리 Py 3.12, 소켓 · DB 차단) |

한계: x600(523) · EKS 실서버에서 직접 넣어 보지는 않았다. 운영 데이터를 써야 하기 때문이다.

## 3. 격리 후보 4커밋 — push 0, 상태 유지 · 증거 덧붙임

- 위치: 격리 clone `allpast-hotfix-20261025-2005/repo` 의 가지 `tf105/candidates`. worktree 는 scratch `teamflow-105-20261028b/wt_rm` 이다.
- 기준: 팀 role-manager `c52fb5c69`.
- patch: `ev/patches/0001~0004`.

| 커밋 | 이슈 | 내용 · 검증 |
|---|---|---|
| `7af3c9b66` | 574 · 714 | `010f9deeb` 을 c52fb5c69 위로 옮겼다(patch-id 같음). 새 시험 12/12 통과 |
| `76053f529` | 521 | 시험만 고쳤다. 원인은 제한시간 0.5초 + 벽시계 3초 상한이다. CPU 40개 부하에서 기준이 4.49초로 실패했다(1/6, 다른 6회 묶음은 0/6). 후보는 제한시간 20초 · 상한 10초 · 사유 connect 를 본다. 같은 부하에서 6/6 통과(최대 3.62초), 파일 63/63 |
| `ef4a3c54b` | 724 | zod 4.6.5 → 4.6.7 로 올리고 관리 콘솔 단일 HTML 을 다시 만들었다. `npm ci` → `audit --omit=dev` 3/3 앱 0건. `npm run check` 3/3 통과(web 1,219 · admin 46 · dev-console 55 + lint · typecheck · build) |
| `a0ba3e50f` | 502 · 531 | admin `check:html` 을 더했다. export 와 같은 함수를 쓰고, 옛 출력과 바이트가 같다(cmp). web `check:stale` 을 더했다(node:test 3/3). 문구를 바꾸면 RED 2곳이 나오고, 되돌리면 0곳이다. AGENTS · CLAUDE 에 같은 문장을 넣었다 |

- **넓은 묶음 회귀**: core · activity · infrastructure · architecture · contract 묶음을 같은 runner 로 돌렸다.
  - 기준 2,196(통과 2,101 · 실패 95), 후보 2,198(통과 2,103 · 실패 95).
  - 상태가 바뀐 시험은 0이다. 늘어난 2건은 새 시험이고 둘 다 통과했다.
  - 실패 95건은 양쪽이 같다. DB · git 자식 프로세스 차단 때문이다.
- **check:html 이 실제로 잡은 것**: zod 를 올리면 admin 단일 HTML 이 바뀐다. 다시 만들지 않으면 CI (admin) 의 재생성 대조가 깨진다.
- **독립 검토**:
  - Codex CLI 는 read-only 샌드박스가 파일 읽기까지 막아 검토하지 못했다.
  - Claude CLI(opus)에는 diff 를 넣어 검토받았다. 결과는 **APPROVE**, 차단 0/4, NIT 3건이다.
  - NIT 중 check:html CRLF 경고는 반영했다. 나머지 2건(시험 docstring · lint)은 확인만 했다. 새 scripts 의 eslint 결과는 0이다.

## 4. 손대지 않은 것과 이유

- **504**: 실제 PostgreSQL 이 필요하다. 코드를 읽고 controller `_resume` 의 경합이라는 가설만 세웠다. 재현 증거가 없어 이슈에 적지 않았다.
- **547**: 전체 묶음을 오래 돌려야 해서 범위 밖으로 뒀다.
- **review 51**: 실서버 · 실기기 · 사람 확인이 남았다. 운영 데이터를 쓰지 않고 닫을 근거가 없다.
- **나머지**: 앞 보고서의 분류 그대로다.

## 남은 일

1. 부모 또는 라우팅 세션이 `tf105/candidates` 4커밋을 role-manager 에 반영한다. 반영하면 574 · 714 · 521 · 502 · 531 · 724 의 상태를 다시 판정한다. 724 는 develop · main CI 까지 확인해야 한다.
2. 504 는 scratch PG 클러스터에서 재현한다.
3. 631 은 실서버에서 test20 제목을 확인한다.

증거(저장소 밖, Hermes scratch `teamflow-105-20261028b/ev/`):

- 조회: `tf_all.json` · `pull2~4/`
- 갱신 입력 · 결과: `updates_710*.json` · `updates_evidence*.json`
- 710 · 631 시험: `main_710_631.{log,xml}`
- 후보 검증: `521_*` · `724_*` · `502_*` · `531_red_green.log` · `broad_{base,rm}.{log,xml}`
- 독립 검토: `claude_review.log` · `codex_review.log`
- patch: `patches/`
