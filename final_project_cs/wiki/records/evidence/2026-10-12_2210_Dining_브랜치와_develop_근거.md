---
type: evidence
title: Dining 브랜치와 develop 조사 근거
description: 원격 커밋 비교와 GitHub PR 및 CI 조회 결과를 기록한다
status: draft
tags: [release, testing]
domain: travel
---

# Dining 브랜치와 develop 조사 근거

[실측 2026-10-12 KST] 저장소 `SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM`. `git fetch origin` 후 고정 SHA를 사용했고, 조사 중 `git ls-remote`로 같은 두 SHA를 재확인했다. 현재 작업 체크아웃은 role-eval-ui이므로 실행 코드는 작업 파일 대신 `git show <SHA>:<path>`와 `git grep <SHA>`로 읽었다.

## Git 비교

```text
git ls-remote origin refs/heads/develop refs/heads/role-dining
c612c994f8d3a668175cd742e8d8c6778cb38476 refs/heads/develop
93dd3efb8fbbe12591577894c3d984edc66d956b refs/heads/role-dining

git rev-list --left-right --count c612c994...93dd3efb
0 7

git diff --shortstat c612c994 93dd3efb
18 files changed, 2695 insertions(+), 32 deletions(-)
```

role-dining에만 있는 커밋(최신순): `93dd3efb`, `b7bfca44`, `566a8409`, `5541fd09`, `ba33e179`, `22216d85`, `fc591f6f`.

실행 코드 diff는 `final_project_cs/app/domains/travel_ops/instances/dining/ledger.py`의 `AREA_TAIL = re.compile(r"(동|구|역|로|길)$")`와 3글자 앞부분 검색에서 해당 끝말을 제외하는 조건이다. 마이그레이션 231도 변경됐으며 그 외는 scripts/tests/eval/wiki다.

## GitHub PR 조회

`get_pr_info`의 응답 필드 요약이다. PR #42를 생성하거나 수정하지 않았다.

| 번호 | state | merged | head SHA | merged_at UTC |
|---|---|---|---|---|
| 37 | closed | true | `2caa12ca4fb7b5c8d9b423b02055e9fbb1e8c8d6` | 2026-10-12T01:23:53Z |
| 39 | closed | true | `526b88e85e712c9aff5b0c04c672413948236cc6` | 2026-10-12T02:06:41Z |
| 40 | closed | false | `b7bfca443ea90c8b95933f06291ae1d8d8eb7c7a` | null |
| 42 | open | false | `93dd3efb8fbbe12591577894c3d984edc66d956b` | null |

PR #42: `base_sha=c612c994f8d3a668175cd742e8d8c6778cb38476`, `mergeable=true`, `draft=false`, `commits=7`, `changed_files=18`, `additions=2695`, `deletions=32`. 생성 시각 `2026-10-12T12:46:20Z`.

## CI 조회

GitHub REST Checks/Actions 읽기 응답에서 확인했다. 두 SHA별 체크는 각각 5/5 = 100% completed/success였다. 작업 수이며 테스트 케이스 수가 아니다.

| SHA | 실행 | 완료 KST | 결과 |
|---|---|---|---|
| c612c994 | [CI develop 38247475103](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/38247475103) | 21:13:39 | success |
| c612c994 | [CI main 38247474659](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/38247474659) | 21:21:32 | success |
| 93dd3efb | [CI develop 38251138833](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/38251138833) | 21:48:36 | success |
| 93dd3efb | [CI main 38251138848](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/38251138848) | 21:56:14 | success |

PR #42의 레거시 commit-status API는 total_count=0, pending을 반환하지만 등록된 레거시 status가 없는 결과다. 실제 Checks/Actions는 위와 같이 성공이다. GitHub Deployments API는 HTTP 200, `[]`였다. 서버 별도 폴링 배포이므로 이것을 미배포 증거로 해석하지 않는다.

## 코드와 과거 배포 증거

`git show c612c994:<path>`로 다음 경로를 대조했다. 파일 경로 접두는 `final_project_cs/`다.

- 요청: `app/domains/travel_ops/entry/trip_api.py:1026,1936`, `components/conversation/trip_messages.py:262,347,619,675`, `components/conversation/case_dispatch.py:74`.
- 판정: `instances/dining/team.py:154,190,248`, `instances/dining/ledger.py:188`, `components/planning/replan.py:127,415`.
- 일정 적용: `instances/_shared/itinerary_team.py:304`, `components/actions/itinerary_actions.py:125,171,177`, `components/itinerary/itinerary.py:477`.
- 자동 점검: `deploy/worker.sh:18`, `scripts/run_sweepers.py:245,342,367`, `components/watch/dawn_check.py:101,136,168,175`, `components/planning/pending.py:493`.
- 미연결 부품: `instances/dining/sweep.py:sweep_day`, `instances/dining/tick.py:tick_once,outbox_notice`, `instances/dining/survey.py:conds_from_survey`에 대해 app/scripts 호출을 검색. 정의와 설명을 제외한 서비스 호출 없음.
- 별도 연결된 설문: `components/planning/survey.py:135`, `components/planning/planner.py:1385,1387`.

위 components/instances 상대 경로는 `app/domains/travel_ops/` 아래다. 조회 결과의 기능 해석은 [보고서](../reports/2026-10-12_2210_Dining_브랜치와_develop_실행흐름.md)에만 둔다.

배포 기록 `wiki/records/evidence/2026-10-12_manager_recovery/deployment-final-summary.json`과 후속 보고는 실행 SHA `439487e5`의 16:46~16:48 KST 상태를 담는다. `git rev-parse <SHA>:<path>`로 develop과 해당 커밋의 dining/planning/conversation/watch 트리 객체가 모두 같은 것을 확인했다. 현재 서버에 직접 접속한 결과가 아니다.

## 변경 범위

프로그램 코드·DB·배포·원격 브랜치를 수정하지 않았다. 로컬 보고서와 이 근거 파일을 추가하고 Dining wiki에 링크 한 줄을 넣었다. 커밋·푸시는 하지 않았다. 일반 샌드박스 프로세스 시작이 `0x80070020`으로 실패해, 승인된 읽기 전용 셸로 Git과 공개 GitHub 조회를 수행했다.
