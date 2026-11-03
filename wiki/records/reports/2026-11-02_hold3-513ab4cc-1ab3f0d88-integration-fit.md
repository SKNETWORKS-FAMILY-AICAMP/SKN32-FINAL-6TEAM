---
type: report
title: HOLD 3 — 513ab4cc · 1ab3f0d88 후보의 최신 role-manager·main 통합 적합성 (2026-11-02)
description: 보존 bundle 두 개로 격리 사본을 만들고 두 후보를 팀 role-manager(fab3da50a) 위에 cherry-pick, main(57f3d2f) 위 충돌을 모의했다. 빠른 관문을 오늘 날짜와 +37일로 두 번, 필수 관문(architecture·계약·보안·DoD26)과 mobility_full 층을 격리 PG16.15에서 돌렸다. 513ab4cc는 통합 적합, 1ab3f0d88은 수정 필요로 판정했다
status: done
domain: travel
impl_scope: 검증 기록. 원격 커밋·푸시·병합·배포·운영 DB·서비스 변경 0. 원본 저장소는 읽기만 했고, 격리 사본(.tmp/clones/hold3-integ-1102) 안에서만 로컬 커밋했다
---

# HOLD 3 — 513ab4cc · 1ab3f0d88 통합 적합성

- 수행: 라우팅 담당 36cd5c의 하위 세션(총괄 5fbd35ab 배정). 2026-11-02 23:05 ~ 11-03 00:30 KST.
- 이번 판정 범위는 **격리 사본에서 기술적으로 통합할 수 있는지**다. 푸시, PR110 HOLD 해제, 운영 reader fatal 해소, Mobility 담당의 정책 수락은 포함하지 않는다.

## 결론

| 후보 | 판정 | 핵심 근거 |
|---|---|---|
| **513ab4cc** (golden2, 57f3d2f 위 로컬 커밋 6개) | **통합 적합** | 제품 코드 변경 0. role-manager 위 code·tests 충돌 0, patch-id가 원본과 같다. 빠른 관문 결과는 두 날짜 모두 기준과 시험별로 같다(바뀐 시험 0). 필수 관문 4종도 기준과 같다. mobility_full 179/216 → 218/223 |
| **1ab3f0d88** (513ab4cc + 4개 = 로컬 커밋 10개) | **수정 필요** | 커밋 자체는 충돌 0, 회귀 0이다. 새 시험 23/23이 통과했고 mobility_full은 223/223이다. 다만 ① 앞선 독립 검토가 지적한 정책판(P2) 미갱신이 남아 있다. 그 후속 미커밋 패치는 깨끗이 적용되지만, 기존 빠른 시험 `test_plan_v1::test_fare_rules_have_basis`를 두 날짜 모두 깨뜨린다. ② 새 시험 파일이 `tests/test-suites.json`에 분류되지 않았다. ③ Mobility 담당 결정(혼합 자전거를 후보에서 빼는 정책)과 성능 비용 수락이 미결이다 |

- **두 후보의 관계:** 1ab3f0d88은 513ab4cc를 조상으로 포함하는 상위 집합이다. 같은 것을 고치는 대안도 아니고, 서로 충돌하지도 않는다.
  - 513ab4cc: golden2 시험·기대 파일과 정밀/잔여18 시험 기대값 정정
  - 1ab3f0d88이 더한 것: 혼합 자전거 판정(58), 혼합 판정 순서, 버스 첫차 승차 하한 — 제품 동작 4개 파일
  - 1ab3f0d88을 통합하면 513ab4cc를 따로 넣을 필요가 없다.
- Codex CLI와 1회 논의했다. 같은 판정이 나왔고, 추가 위험(P2 분리, suite 분류, 성능 수치가 오늘 측정이 아님)도 같았다.
  - 원문: `backups/hold3-integ-1102/evidence/codex-answer.txt`

## 기준과 출처

| 항목 | 값 |
|---|---|
| 팀 role-manager | `fab3da50ab970a7d8c79ed65c1df2e666abc1cd0` (fetch·ls-remote 일치) |
| 팀 main | `57f3d2f004d0600f781599a6a92e8691b49bef82` (= 두 후보의 base) |
| role-manager ↔ main | merge-base는 c52fb5c69다. role-manager에만 있는 커밋 17개, main에만 있는 커밋 38개. mobility 엔진 4개 파일(candidates·plan·verify_time·rules_v0.3.json)의 blob은 양쪽이 같다 |
| 513ab4cc | 보존 `wsl-claude-fix-all.bundle` (sha256 `4d3073d5…84ee`, `KEY-ARTIFACTS.sha256` 18/18 재대조 OK). 57f3d2f..513ab4cc = 3e5a60af6·acf0fadcd·346a57d4d·7484a180e·ee8ca8807·513ab4cc0 |
| 1ab3f0d88 | 보존 `candidate-1ab3f0d88-local-chain.bundle` (sha256 `d5cec928…f0bd`). 57f3d2f..1ab3f0d88은 위 6개에 52f933e82·56fc3ce15·47549aa4e·1ab3f0d88을 더한 것이다 |
| 기포함 여부 | 후보 커밋 10개의 patch-id를 role-manager·develop(3463b30c6)과 비교했다. 일치 0/10이다(이미 반영된 것 아님) |
| 참고 | `eksfix3_1029` candidate.patch(38,745 B, `c1cd7925…7cc8`)는 1ab3f0d88 마지막 커밋과 같은 5개 파일을 바꾼다 |

## 충돌

| 대상 | 513ab4cc | 1ab3f0d88 |
|---|---|---|
| role-manager, 체인 cherry-pick | acf0fadcd와 ee8ca8807에서 문서 색인 3개가 충돌했다: `final_project_cs/wiki/index.md`, `wiki/handoff/index.md`, `wiki/index.md`. 양쪽 줄을 모두 남겨 해결했다(스크립트 `resolve_union.py`, 허용 경로 3개). code·tests 충돌은 0 | 513ab4cc 위에 4개를 더할 때 충돌 0 |
| role-manager, 단일 커밋 merge-tree | 0 | 0 |
| main | fast-forward(base 동일), 충돌 0. 단일 커밋 merge-tree도 0 | 같음 |
| patch-id (`final_project_cs/app`·`tests`) | 원본 = 격리 결과 (`b2be27b6…`) | 원본 = 격리 결과 (app `2eb17f34…`, tests `74ceaed5…`) |
| `git diff --check` (code·tests) | 깨끗 | 깨끗 |

- 공백 경고 85줄은 후보가 이미 가지고 있던 wiki evidence 원본(XML·source.patch)에서 나온다. 통합 과정에서 생긴 것이 아니다.

## 관문 결과 (같은 사본, 같은 환경)

환경은 다음과 같다.
- Python: NuGet python 3.12.10 AMD64(`0eb85c2d…`)로 만든 scratch venv에 `requirements.txt`를 설치했다.
- Git: Hermes 번들 git 사본을 scratch에 두었다.
- 빠른 관문: 네트워크와 DB를 차단한 `run_isolated.py`로 돌렸다.
- 필수 관문: 보존 `ekscheckingcontinue1029/pgdata.tar.gz`(Windows PG16.15)를 scratch에 풀어 127.0.0.1:56311로 띄웠다. 트리마다 새 DB를 만들고 CI main 순서(TZ→migrate→register_prompts→seed_travel)를 거친 뒤 시험했다. 끝난 뒤 `pg_ctl stop -m fast`로 멈췄다.

### 날짜 빠른 관문 2개 (오늘, `RELDATE_SHIFT_DAYS=37`)

- 지정된 `integ-rm13-20261027-2006/gate.sh`는 scratch 정리로 이미 없었다.
- 같은 계보인 `schedule-explain-impl-20261029/{gate.sh,run_isolated.py,reldate_shift.py}`를 복사했다. 경로만 바꾸고 이동 일수를 인자로 받게 했다. 5 shard, `-m 'not live and not db and not slow'`이다.

| 트리 | 오늘 | +37일 | 기준 대비 |
|---|---|---|---|
| role-manager 기준 | 10,767/10,768 = 99.99% (skip 173) | 같음 | — |
| +513ab4cc | 10,767/10,768 = 99.99% (skip 173) | 같음 | 공통 10,941개 중 바뀐 시험 0, 사라진 시험 0 |
| +1ab3f0d88 | 10,790/10,791 = 99.99% (skip 173) | 같음 | 바뀐 시험 0, 사라진 시험 0, 새 시험 23/23 = 100% |

- 남은 1건은 모든 트리에서 같다: `tests/security/test_no_infra_in_tracked_files.py`.
  - role-manager tip fab3da50a가 추가한 `wiki/records/evidence/2026-10-29_st4f728-guest-logout/security-ready.xml`에 시험용 IP 8.8.8.8, 8.8.4.4와 가짜 discord 웹훅이 들어 있다.
  - **기준선 결함이다. 후보와 무관하다.**
- 처음 돌렸을 때 6건이 더 실패했다(`test_context_budget` 3, `test_case_subject_routing` 3). 새 venv에 tiktoken 인코딩 캐시가 없어 네트워크 차단에 걸린 것이다.
  - 캐시를 scratch에 미리 받아 다시 돌렸다. 3트리 × 2날짜 모두 12/12 통과했다. 위 표는 이 재실행 결과를 반영한 수다.

### 필수 관문 (현재 role-manager 정의 그대로)

| 관문 | 기준 | +513ab4cc | +1ab3f0d88 |
|---|---|---|---|
| architecture | 170/170 = 100% | 170/170 = 100% | 170/170 = 100% |
| 계약(tests/contract) | 367/367 = 100% | 367/367 = 100% | 367/367 = 100% |
| 보안(tests/security) | 124/125 = 99.2% | 124/125 = 99.2% | 124/125 = 99.2% |
| DoD26(`verify_dod_v11`) | 26/26 = 100% | 26/26 = 100% | 26/26 = 100% |

- 계약 시험 수는 role-manager 정의에서 367개다. 예전 보고서의 「계약368」은 main(57f3d2f) 기준이다.
- 보안 1건은 위와 같은 기준선 결함이다.

### mobility_full 층 (후보가 실제로 겨냥한 층)

- 로컬 원본 `datasets/mobility/processed`를 scratch로 복사해 `DATA_DIR`로 지정했다. 파일 115개, manifest sha256 `8c32e9c3…5054`. 실행 조건은 `MOBILITY_GH_URL=none`, 오늘 날짜다.

| 트리 | 결과 |
|---|---|
| 기준 | 179/216 = 82.87% |
| +513ab4cc | 218/223 = 97.76%. 남은 4건: earliest after_last_holiday, mixed stations_blocked, bike_not_called_by_default, station_fallback only_blocked. 나머지 1건은 환경 |
| +1ab3f0d88 | 222/223 = 99.55%. 환경 1건을 빼면 **223/223 = 100%** |

- 환경 1건은 `test_passenger_car_exception_policy_v1::test_public_graph...`다. 이 시험은 `DATA_DIR`을 무시하고 저장소 안 `datasets/` 경로를 직접 읽는다.
  - 자료를 그 경로에 잠시 두고 다시 돌리니 1 passed였다. 확인 뒤 그 복사본은 지웠다.
- 이 결과는 10-29 Linux 기록(기준 220/223 → 후보 223/223, 정밀 198/216)과 방향이 같다.

## 수정이 필요한 점 (1ab3f0d88)

1. **정책판(P2).** 보존 `candidate-uncommitted.patch`(7,239 B)와 `test_rules_policy_version_v1.py`를 격리 커밋 `e8093b2a0`에 넣었다. 패치는 rules_v0.3.json, history, wiki/teams/mobility.md를 바꾼다.
   - 적용은 깨끗하다.
   - mobility 빠른 시험은 오늘·+37일 모두 1,478 passed, 1 failed다. `test_plan_v1.py::test_fare_rules_have_basis`가 허용판 `("v0.9","v0.9.1","v0.9.2")`에 `v0.9.3`이 없어 실패한다. 같은 조건의 1ab3f0d88은 1,477/1,477이다.
   - main과 role-manager의 시험이 모두 같은 튜플을 갖고 있어서, 어느 base에서도 이 시험을 함께 고쳐야 한다.
2. **suite 분류.** `test_mix_settle_first_pass_v1.py`가 `tests/test-suites.json`에 없다. `run_test_suite.py --suite travel`은 분류되지 않은 파일이 기준선에서 16개였고, 후보를 넣으면 17개가 된다. 기준선이 이미 이 오류로 실패하므로 후보만의 차단 사유는 아니다. 다만 통합할 때 함께 등록해야 한다.
3. **담당 결정.** 52f933e82와 56fc3ce15는 「혼합 자전거는 판정하되 후보·more_options·earliest에 넣지 않는다」를 제품 코드로 정한다. golden 보고서는 이것을 Mobility 담당 결정 사항으로 남겼다. 성능 비용(10-29 10구간 24.099→26.576초)은 오늘 다시 재지 않았다.
4. 문서 색인 3개는 통합 담당이 양쪽 줄을 수동으로 정리해야 한다. 513ab4cc도 같다.

## 격리 커밋·패치·보관

격리 사본: `C:/_proj/final_workspace/.tmp/clones/hold3-integ-1102`. 로컬 브랜치만 만들었고 원격 반영은 0이다.

| 브랜치 | 커밋 | tree |
|---|---|---|
| `h3/rm-513` (= role-manager + 513ab4cc 체인) | `2672f7cde9a8ff8f1661917bb6c72af2a6bcbe42` | `44b3cb17a345…` |
| `h3/rm-1ab3` (+ 1ab3f0d88 4개) | `1b0dbcb068b810017516c30515d35cc93cc0d5a1` | `352993b41080…` |
| `h3/rm-1ab3-p2` (+ P2, 판정 참고용) | `e8093b2a0a858aac1e2feac1a9f17c6a979c3749` | `5cef88fe7e58…` |

보관 위치는 guguroute `backups/hold3-integ-1102/`이다. `SHA256SUMS`는 213줄 모두 OK이고, 그 파일의 sha256은 `fdb27e62…0603`, 합계 20,632,319 B다.

| 파일 | 바이트 | sha256 |
|---|---|---|
| `patches/rm-fab3da50a__513ab4cc-chain.diff` | 2,413,126 | `be75e84d7eba70ac6b425cf0f7df5e35fbe86ea714b1ac81e8b44632ccb48a9c` |
| `patches/rm-fab3da50a__513ab4cc-code-tests-only.diff` | 66,326 | `a252a9995669149961af12ca1b7b6290233a7fe3e80a21a1b872aaa66ae9ec30` |
| `patches/rm513__1ab3f0d88-increment.diff` | 57,345 | `3d9d399d33fde03f9e2e9b7ec52108898f4432043e911bd468968e931ab43d3c` |
| `patches/rm-fab3da50a__1ab3f0d88-chain.diff` | 2,469,371 | `0350bcf609ad8955225b9712fe7cd0f3fe174ceb8517fb1095d931fe256aa286` |
| `patches/rm-fab3da50a__1ab3f0d88-code-tests-only.diff` | 122,571 | `e1948043480f617197d12df6f4fac367ca3d30aa93a134f213f008d71f498aec` |
| `patches/rm1ab3__p2-policy-version.diff` | 8,982 | `aeeafc9885919cd715465e510f5a1315b1f60d08a585a728c9fc8af7926f2fc7` |
| `hold3-local-branches.bundle` (전제 fab3da50a, head 3개) | 287,627 | `532d5366eaab5c689c76b766bf05181ea53d0aaf868ea551edbd19af1f404d0f` |

- 패치 4개(체인 2, 증분, P2)는 별도 색인에서 `read-tree base → apply --cached → write-tree`로 왕복했다. 결과가 각 브랜치 tree와 4/4 일치했다.
- `evidence/out/`에 빠른 관문 shard XML·로그, DB 관문 XML·DoD evidence, mobility_full XML, 비교 JSON이 있다. `scripts/`에는 gate·dbgate·runner·resolver가 있다.

## 사본·자원

| 대상 | 상태 | 크기 |
|---|---|---|
| `.tmp/clones/hold3-integ-1102` (guarded_clone, owner 36cd5c) | 만든 뒤 **release(idle)**. 삭제하지 않았다(대상별 삭제 승인 대기) | 7,219,351,447 B. 안에 worktree 3개 `.h3wt/{rmbase,rm513,rm1ab3}`(각 약 1.62 GB, `.git/info/exclude`에 등록)와 로컬 `h3/*` 브랜치가 있다. 예약값 4.0 GB를 넘었다 |
| scratch `hold3-integ-1102/` | 남겨 둠(24시간 미사용 시 자동 정리) | 약 1.55 GB: env312 646 MB, mingit 389 MB, mobdata 290 MB, pg 135 MB(정지), out 15 MB, tmp 18 MB 등 |
| 격리 PG 127.0.0.1:56311 | 정지함 | — |
| 지운 것 | worktree에 잠시 복사했던 `road_graph_v2`(25 MB, 시험 1건 확인용), 중단한 첫 관문 실행의 scratch 출력. 원본·보존물 삭제는 0 | — |

- 같은 시각 `hold3-eks-precision-r18` 예약(pending)은 다른 하위 세션 소관이라 건드리지 않았다.

## BLOCKED · 확인하지 못한 것

- BLOCKED 없음. 관문은 모두 실제로 실행했다.
- 환경 메모: 지정된 3.12 venv(`date_risk_env_312`)와 mingit(`date_risk_independent_review_01`)은 scratch 정리로 이미 사라져 있었다. 위 대체 환경을 새로 만들어 썼다.
- 보존 `eksprecision1029` pgdata는 Linux aarch64 클러스터라 Windows PG에서 띄울 수 없었다. 그래서 Windows 클러스터인 `ekscheckingcontinue1029`를 썼다.
- live·db·slow 전체 층, CI의 `-n auto` 전체 시험(약 13.5k), EKS AMD64 이미지, 운영 reader fatal, 성능 ABBA는 이번에 실행하지 않았다. 그래서 운영 전체 완료율은 분모를 모른다.
