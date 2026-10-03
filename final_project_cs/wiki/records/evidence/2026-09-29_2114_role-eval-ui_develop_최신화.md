---
type: evidence
title: role-eval-ui develop 동기화 검증 기록
description: Git 동일성 및 변경 보존, 린트와 Mobility 검증의 실행 출력을 기록한다
status: draft
domain: travel
---

# 실행 조건

2026-09-29 Windows PowerShell, SKN32-FINAL-6TEAM. Python 검증은 `final_project_cs/.venv/Scripts/python.exe` 3.12.10을 사용했다. 별도의 DB 생성·마이그레이션은 실행하지 않았다.

## Git

저장소 루트에서 실행했다. 출력은 필요한 부분만 발췌했다.

```text
git fetch origin develop role-eval-ui
From https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM
 * branch            develop    -> FETCH_HEAD
 * branch            role-eval-ui -> FETCH_HEAD

# 갱신 전
git rev-list --left-right --count develop...origin/develop
0  0
git rev-list --left-right --count role-eval-ui...origin/develop
0  9

git merge --ff-only --no-overwrite-ignore --quiet origin/develop
git reflog -1 --format='%h %gs'
38cd59d merge origin/develop: Fast-forward

git rev-parse HEAD
38cd59d4d51113c1eee4626aeb63c2393269bc1a
git rev-list --left-right --count HEAD...origin/develop
0  0
git diff --check
# 출력 없음, exit 0
```

기존 `final_project_cs/frontend/apps/web/.env.example`의 갱신 전후 SHA-256은 모두 `188F96456F2BAEF2268552AD3BD6FE7ADA2E4AE3D46E1DAA766A1B33C324F064`이다. 새로 들어올 경로와 로컬 파일의 중복은 0개였다.

## 사용자 후속 요청에 따른 push

push 직전 다시 fetch한 결과 원격 role-eval-ui 대비 로컬이 9개 앞서 있었고, 로컬과 원격 develop 차이는 0개였다. 다음 명령으로 기존 커밋만 반영했다. 미커밋 파일은 포함하지 않았다.

```text
git push origin refs/heads/role-eval-ui:refs/heads/role-eval-ui
To https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM.git
   07bfde4..38cd59d  role-eval-ui -> role-eval-ui

git ls-remote --heads origin develop role-eval-ui
38cd59d4d51113c1eee4626aeb63c2393269bc1a  refs/heads/develop
38cd59d4d51113c1eee4626aeb63c2393269bc1a  refs/heads/role-eval-ui
```

## Python 검증

아래는 `final_project_cs`에서 실행했다. 긴 traceback은 생략했고 결과 줄과 오류 원인만 발췌했다.

```text
.\.venv\Scripts\python.exe -m ruff check .
All checks passed!

.\.venv\Scripts\python.exe -m pytest tests/unit/travel/mobility -q --tb=short
6 failed, 187 passed, 173 deselected, 12 errors in 76.86s (0:01:16)
```

실패는 `test_plan_v1.py`의 `test_golden`, `test_0400_boundary`, `test_golden_all_modes`, `test_no_per_option_departure`, `test_replan_fare_known_locked`, `test_recheck_at_offsets`이다. 모두 기존 팀 문서 `docs/mobility/MERGE_CHECK_v1.md` §2-1에 기재돼 있다.

오류 12건의 공통 원인은 `PermissionError: [WinError 5]`로 공용 `pytest-of-sltko` 임시 폴더를 읽지 못하는 것이었다. 다음처럼 고유한 임시 경로를 만들도록 실행 옵션만 바꿔 관련 두 파일을 다시 확인했다.

```powershell
$env:PYTHONUTF8 = '1'
$syncTestTemp = Join-Path $env:TEMP ('codex-develop-sync-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $syncTestTemp) { throw 'Temporary path already exists' }
.\.venv\Scripts\python.exe -m pytest tests/unit/travel/mobility/test_review_fixes_runtime.py tests/unit/travel/mobility/test_review_fixes_wiring.py -q --tb=short --basetemp $syncTestTemp
```

```text
...................                                                      [100%]
19 passed in 3.04s
```

계약·보안 결합 명령 `.\.venv\Scripts\python.exe -m pytest tests/contract tests/security -q --tb=short`은 결과가 나오지 않아 Ctrl+C로 중단했다(exit 1). 테스트 통과율을 계산할 수 있는 결과가 없으며 분모 모름이다.

보안 개별 명령 `.\.venv\Scripts\python.exe -m pytest tests/security -q --tb=short`은 고유한 `--basetemp`를 `PYTEST_ADDOPTS`로 전달하고 60초 제한으로 실행했다. 제한 도달 시 이번 실행의 PID에만 `taskkill /PID <pid> /T /F`를 적용했다.

```text
security: TIMEOUT after 60 seconds; process tree stopped
..................
```

완료 요약이 없으므로 통과 판정은 하지 않는다.

규칙에 기재된 `.\.venv\Scripts\python.exe -m scripts.verify_dod`도 같은 방식으로 고유한 임시 경로와 60초 제한을 적용했다. 과거 evidence를 읽은 뒤 전체 pytest 결과를 기다리는 단계에서 제한에 도달했다. 출력 발췌:

```text
dod: TIMEOUT after 60 seconds; process tree stopped
triPilot DoD 검증  (v8 §27 · 29항목, 1~28은 v7 번호 보존)
15  A/B/Proposed·holdout 보존              있음       부분통과     INCOMPLETE
17  마일스톤 gate·기능 동결                      있음       부분통과     NOT PASS
28  파인튜닝 경로와 방어 지표                       있음       부분통과     NOT PASS
```

이 도구는 소스 머리말에 명시된 v8 과거 검증기다. 위 출력은 현재 v11 DoD 달성률이나 이번 코드의 전체 테스트 통과를 뜻하지 않는다. 전체 pytest 완료 요약은 확보하지 못했다.

## 관계

- [작업 리포트](../reports/2026-09-29_2114_role-eval-ui_develop_최신화.md)
