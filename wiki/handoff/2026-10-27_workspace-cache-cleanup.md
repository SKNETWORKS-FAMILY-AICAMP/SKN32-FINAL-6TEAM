# 작업 폴더 캐시·빌드 산출물 정리 — 인계

## 현재 결론

`C:/_proj/final_workspace`에서 재생성 가능한 캐시와 빌드 산출물만 지웠다. 파일 **13,909개, 1.88GB**이고 오류는 0건이다. 정리 뒤 작업 폴더는 약 51.80GB다. [보고서](../records/reports/2026-10-27_workspace-cache-cleanup.md)

## 한 일 목록

- 루트 `AGENTS.md`·`CLAUDE.md`, 하위 `AGENTS/RULE/CLAUDE`, wiki 인계 목차를 읽었다.
- 백그라운드로 폴더별 크기를 쟀다. 실행 중인 프로세스를 점검해 작업 폴더의 빌드 산출물을 쓰는 프로세스가 0개임을 확인했다.
- 허용 목록 32개 폴더(`frontend/apps/{admin,web}/.next*` 20개, `.pytest_cache` 10개, `.ruff_cache` 2개)와 `__pycache__` 764곳의 `*.pyc`를 지웠다. 삭제 전에 git 추적 0건, ignore 규칙, 최근 120분 쓰기 0건, 링크와 reparse point 0개를 확인했다.
- 프로세스 종료 0건, 서비스·DB 변경 0건, git 인덱스와 HEAD 변경 0건, 커밋과 push 0건이다.

## 다음(선택)

- 더 줄이려면 사용자 결정이 필요하다. `.tmp`(5.6GB)는 세션 작업물이고, `datasets`(34GB)는 데이터, `web/node_modules`(589MB)는 다시 설치할 수 있지만 런처가 쓴다.
- `.next*`는 다음 빌드나 `next dev` 실행 때 다시 생긴다. 웹 첫 실행이 느려질 수 있다.

## 2차: `.tmp` 전수 조사(2026-10-27)

- `.tmp`는 5.60GB(파일 189,274개)에서 **4.00GB(105,665개)**로 줄었다. 지운 것은 83,609개, 1,598,725,072바이트이고 오류는 0건이다. 대상은 `node_modules` 3곳(1.53GB), `.next` 1곳, `.py` 원본이 있는 `.pyc`, `.ruff_cache`다. 최상위 955개 항목을 전후로 대조한 결과 불일치는 0건이었다. [보고서 2차 절](../records/reports/2026-10-27_workspace-cache-cleanup.md#추가-정리-tmp-전수-조사2026-10-27-2차)
- 남긴 것: 안쪽 worktree와 저장소(병합하지 않은 코드일 수 있음), 증거 캡처·로그, PG 스냅샷, `.pytest_cache`, 원본 없는 `.pyc` 25개.
- 다음(선택): `manager_recovery_20261012`·`full-release-20261008`·`baseline-manager-20261012/team`·`wt_dev`·`mobility-develop-20261008` worktree를 현재 코드와 대조해 분류한다. 그 결과에 따라 보관하거나 삭제한다.

## 3차: `.tmp` 안쪽 worktree 대조(2026-10-27)

- `.tmp`는 **4.00GB에서 3.01GB**(파일 105,665개에서 89,574개)로 줄었다. 지운 것은 16,094개, 989,108,948바이트이고 보류·오류는 0건이다. [보고서 3차 절](../records/reports/2026-10-27_workspace-cache-cleanup.md#추가-정리-tmp-안쪽-worktree저장소-대조2026-10-27-3차)
- 지운 것은 공개 커밋과 같다는 것이 증명된 사본이다. `full-release-20261008/baseline`은 `38f9e08cb0`과 5,732/5,732, `mobility-develop-20261008`은 `d85cc7cf0c`와 3,118/3,118이 같았다. `manager-snapshot`은 `45ab1efa8e`의 archive로 manifest 3,682/3,682가 일치했다. 여기에 turbopack 캐시 3곳을 더했다. 지운 자리에 `_PRUNED_20261027.txt`(되살리는 법)를 남겼다.
- 통합 검토가 필요한 것: `recovery-candidate`의 공개되지 않은 커밋 `349ad1d`(native migration safety contract)는 루트에 없다. `wt_dev`에는 이력에 없는 파일 37개가 있다(develop 경로와 겹치는 것 35개).
- 보존: `baseline-manager/team`(private Playwright 설정 7개, `tsconfig.json`), `full-release/release`(증거 인용), `claude_followup/workspace`, `uiux-handoff-*/base`.
- 루트 git status 1,163행은 전후가 같다. 커밋·push·fetch·프로세스 종료는 0건이다.
