---
type: report
title: 활동 장소 별칭 — x600 서버 반영 확인과 병합 시도 기록 (2026-10-22)
status: record
domain: travel
---

# 활동 장소 별칭 — x600 서버 반영 확인과 병합 시도 (2026-10-22)

**결론 한 줄:** 활동 팀의 장소 별칭(시드 CSV 131행 + DB 표 `activity.ac_place_alias`, 마이그레이션 306)은 팀 role-manager `58f1d1b48` 에 들어 있고, x600 서버의 cs 프로젝트 서버에 `58f1d1b48b` 판으로 배포돼 있다(2026-10-22 11:12 반영 완료). 결정 [D-027](../../decisions/D-027-team-owned-place-aliases.md) 의 「팀 `aliases.yaml`」 방식은 그것과 다른 설계이고 여전히 코드로 반영되지 않았다.

## 구분

| 구분 | 내용 | 근거 |
|---|---|---|
| 로컬 구현 · 코드 | 활동 별칭 = `instances/activity/data_processing/place_aliases.csv`(131행, 시드) + `place_aliases.py` + 마이그레이션 `306_activity_place_alias.sql` + `scripts/activity/load_place_aliases.py`. 이름 찾기(`db_search/place_by_name.py:108`)가 시드를 **적재 없이** 먼저 읽고, DB 표는 운영 중에 더하는 추가 별칭용이다 | 팀 role-manager `58f1d1b48` 코드 읽기 |
| 시험(이 PC, 합친 격리 사본) | ruff F·E9 통과 · `tests/architecture` · `contract` · `unit` 9,296개 중 실제 실패 0건 · `tests/security` 98개 중 97 통과. **DB 가 필요한 시험(약 25건)은 이 PC 에 시험 DB 가 없어 접속 시간초과로 못 돌렸다**(실패가 아니라 못 돌린 것). 웹 화면 시험은 돌리지 않았다 | 격리 사본 실행(2026-10-22), 가짜 환경값은 CI 와 같음 |
| 배포(x600 서버) | 자동 배포 설정은 `DEPLOY_BRANCH=role-manager`, `DEPLOY_REPO` = 팀 SKN 저장소(개인 A-COP 아님). 배포 로그 「11:09:34 시작 58f1d1b48b → 11:12:37 반영 완료 (이전 2e6a61b020)」. api · worker 이미지 `tripilot-api:58f1d1b48b`. DB 에 `activity.ac_place_alias` 표 있음(새 표라 행 0), api 이미지 안에 `306_activity_place_alias.sql` 있음 | SSH work 세션의 읽기 조회(아무것도 바꾸지 않음) |
| 실제 고객 경로 확인 | **안 했음** — 「남산타워」가 든 계획이 N서울타워로 찾히는지 | — |
| 미확인 | 시드 CSV 가 api 이미지 안에 실제로 있는지(같은 `app/` 폴더라 있다고 보지만 직접 보지 않음) · DB 표 내용 | — |

## 경위와 정정

- 「팀이 `aliases.yaml` 로 관리 · 우리 6팀 datasets 구글 드라이브 폴더에 있다」는 말을 따라 찾았지만 **그 이름의 파일은 없었다**. Drive 6팀 폴더(activity · dining · mobility)의 첫 단계와 하위 폴더 `activity/{processed, raw, scripts}`, Drive 검색 `aliases` · `yaml`, 로컬·원격 모든 브랜치 이력(`git log --all -- '*aliases*.yaml'`)에서 못 찾았다. 확인하지 않은 곳: dining · mobility 의 하위 폴더 안쪽. 팀의 실제 별칭 자료는 활동 팀의 `place_aliases.csv` 이다.
- 처음에는 별칭 코드가 develop 에만 있고 role-manager 에는 없는 줄 알았다(2026-10-21 저녁 기준 맞았다). 로컬 격리 사본에서 develop(team/develop `6016fcc21`)을 role-manager(`597d3e32d`) 위에 합친 병합 커밋 `d69b28ecb` 를 만들었고(충돌 9곳을 양쪽 내용을 살려 풀었다), 그동안 UI 팀 PR #67 · #69 · #70 이 develop 을 팀 role-manager 에 먼저 합쳐 올려 `58f1d1b48` 이 되었다. `d69b28ecb` 의 모든 부모가 `58f1d1b48` 의 조상이고 별칭 관련 파일 차이가 0이라 **쓰지 않았다**. commit 세션이 개인 A-COP role-manager(`36871598f`)를 팀 머리로 **빨리감기** 푸시해(강제 없음) 팀 · 개인 모두 `58f1d1b48` 이다. develop 은 올리지 않았다.
- 격리 사본 두 폴더(클론 2.9GB · 작업 사본 1.6GB)는 사용자 승인(2026-10-22) 뒤 지웠다.
- 정정: commit 세션이 「별칭 표가 0행이니 적재가 남았다」고 했지만, 시드는 적재 없이 적용된다 — 적재(쓰기)는 필요 없다.

## 같은 날 오후 정정 — 배포됐지만 고객 경로에는 연결되지 않았다

`[2026-10-22 오후 · 「장소 이름 찾기 순서」 세션]` 이 기록의 「배포됨」은 고객 경로 연결을 뜻하지 않았다. 별칭을 읽는 곳은 두 곳뿐이었다.
하나는 활동 팀 이름 찾기(`read.place_lookup`)로, 고객 경로에서 부르는 곳이 없다. 다른 하나는 활동 팀의 같은 장소 판정이다.
확인 화면 장소 검색과 계획 읽기는 이 별칭을 읽지 않았다. 그래서 x600 서버에서 「mmca 서울」이 카카오 결과로만 나왔다.
모든 이름 찾기가 같은 순서로 이 별칭을 읽게 고쳤다. 결정은 [D-CS-021](../../../final_project_cs/wiki/decisions/D-CS-021-place-name-lookup-order.md), 기록은 [장소 이름 찾기 순서 통일](../../../final_project_cs/wiki/records/reports/2026-10-22_장소이름찾기_순서_통일.md)이다.
(이 기록의 위 본문은 당시 확인한 그대로 둔다.)

## 남은 일

1. 시드 CSV 가 api 이미지에 실렸는지 읽기 조회 한 줄(선택).
2. 「남산타워」 계획 줄로 실제 경로 확인(x600 서버에 시험 여행이 생기므로 「남길 시험 여행」 보관함 규칙대로).
3. D-027 의 `aliases.yaml` 설계를 이어갈지는 별도 결정 — 활동 팀 CSV 방식이 이미 배포돼 있어 두 방식의 관계를 정해야 한다.
