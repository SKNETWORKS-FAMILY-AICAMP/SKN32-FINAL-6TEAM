# 2026-10-26 옛 작업공간 `C:/_proj/파이널스페이스` 고유 자료 이관과 폴더 삭제

사용자 지시(2026-10-26): 「datasets 는 우리 final_project 폴더로 이관시키고 나머지 봐서 안쓰는 것들은 다 지우고 저 데이터셋 처럼 잘못 저장되어 있는것들은 final_project 폴더로 다 이관시켜야지」. 실행 2026-10-27 18:35–20:22.

## 결론

- 옛 사본에만 있던 파일 **38,114개(10.65GB)** 를 이 작업 폴더로 덮어쓰기 없이 옮겼다. 검증 결과 **38,114/38,114 = 100%** 가 크기와 sha256(원본·사본 양쪽 다시 읽음)이 일치했다. 삭제 뒤 표본 재해시는 300/300, 존재+크기 확인은 38,114/38,114였다.
- 옮기지 않은 것: 개별 파일 4,402개(1.43GB, 이유별 표 아래)와 통째로 제외한 폴더 `.tmp`·`scratch`·`.claude`·`.git`·캐시류.
- 옛 git에만 있던 커밋 11개는 `.backup/2026-10-26_finalspace_git.bundle`(78KB, sha256 `85d0dfc0…`)에 보존했다.
- `C:/_proj/파이널스페이스`는 **삭제 완료**했다(파일 1,124,307개, 디렉터리 137,211개, 64.49GiB). 삭제 직전 C: 여유 공간은 246.1GB, 직후는 436.6GB였다. 같은 시간대에 다른 세션도 정리를 해서, 늘어난 190GB 전부가 이번 삭제분은 아니다.
- 매니페스트(이관한 파일 전부, 버린 파일과 이유): [`../evidence/2026-10-26_finalspace-migration/manifest.json`](../evidence/2026-10-26_finalspace-migration/manifest.json)

## 사전 조치

- 남아 있던 프로세스 `ccapiserver.exe`(PID 13224, `scratch/admin-trip-dod-local-20261018/native-pg-runtime-r2`, 부모 프로세스 없음)를 강제 종료했다. DB 5433(`C:/_proj/postgresql`, PID 6536)은 건드리지 않았고, 종료 후에도 LISTEN 상태다.
- 옛 폴더 안에는 재분석 지점(reparse point)·정션이 0개였다. 삭제 직전에 파일 목록을 다시 떠서 비교했고, 새로 생기거나 바뀐 파일은 0개였다.

## 이관 묶음

| 묶음 | 파일 | 크기 | 위치 |
|---|---:|---:|---|
| datasets/core (answer_selection·chat_probe·field_test·intake_chunking_20261016·itinerary_crud·itinerary_generation·pointing·travel_tasks·사람검수_대기_모음) | 1,319 | 3.04GB | 같은 경로 |
| datasets/mobility (raw 등) | 1,311 | 2.73GB | 같은 경로 |
| datasets/travel (plan_samples·model_queue_handoff 등) | 205 | 1.56GB | 같은 경로 |
| datasets/_recovery 고유분(내용 해시 기준) | 32,760 | 1.55GB | 같은 경로 |
| datasets/_archive · _backup | 227 | 0.89GB | 같은 경로 |
| datasets 기타(dining·safety·ml·chat_probe 10-14/10-15·pointing/testset README·`자체_sLLM_모델_6팀.zip`) | 100 | 0.45GB | 같은 경로 |
| datasets 충돌 보관 | 65 | 0.03GB | `datasets/_archive/2026-10-26_finalspace_conflicts/` |
| program (산출물양식 w3/w5/w6, scripts, plan, briefing 등) | 751 | 0.19GB | 같은 경로 |
| wiki (handoff·records/reports·_backup 등) | 585 | 0.01GB | 같은 경로 |
| final_project_cs/wiki · var · _backup | 323 | 0.02GB | 같은 경로 |
| 코드·문서 충돌 보관(program 130 · cs 68 · wiki 5 · team_branch 1) | 204 | 0.02GB | `.backup/2026-10-26_finalspace_conflicts/` |
| final_project_cs 코드 트리 신규 57 + `.codex/hooks.json` | 58 | 0.002GB | `.backup/2026-10-26_finalspace_unmerged/`(실행 코드·훅에 섞이지 않게) |
| 루트 `_backup` → `.backup` | 107 | 0.005GB | `.backup/<같은 하위 경로>` |
| `tripilot-eks-build-context-v3.zip` · `tmp/pdfs`(53) · `_handoff_teamflow`(3) | 57 | 0.13GB | `.backup/2026-10-26_finalspace/` |
| output/pdf · team_branch · tools(`local_data_guard.py`·`safe_git.py`) | 42 | 0.03GB | 같은 경로 |

`tmp/pdfs`, `_handoff_teamflow`, 코드 트리, `.codex` 훅을 어디에 둘지는 Codex CLI와 함께 정했다. Codex는 `_recovery`도 `.backup`에 격리하자고 제안했지만, 사용자 지시가 「datasets는 final_project로」였고 고유분만 옮기는 조건이었으므로 `datasets/_recovery/`에 두었다.

## 옮기지 않은 것

| 묶음 | 파일 | 크기 | 이유 |
|---|---:|---:|---|
| datasets/_recovery 중복 | 2,285 | 1.35GB | datasets 안 다른 위치(또는 같이 이관한 파일)에 sha256이 같은 파일 있음 |
| final_project_cs/.tmp | 1,661 | 0.07GB | 임시 작업 사본(lodging-fix 등) |
| final_workspace git에 같은 blob 있음 | 420 | 0.006GB | 코드·문서 사본(git이 보존) |
| 크기 충돌, final_workspace 쪽이 더 최신 | 31 | 0.001GB | AGENTS.md·CLAUDE.md·.gitignore·bat 등 |
| 크기 충돌, 옛 쪽 내용이 이미 git에 있음 | 2 | 0.002GB | datasets/mobility |
| `final_project_cs/.env*` 3개 | 3 | — | 비밀 파일. 같은 종류가 이미 있어서 옮기지 않았고, 내용도 출력하지 않았다 |
| `.tmp` (277,764) · `scratch` (104,019) · `.claude` 옛 worktree (63,783) | — | 14.3·5.7·5.0GB | 임시 로그·실험 사본·로컬 런타임·옛 worktree |
| `.git` · `__pycache__`·`.pytest_cache`·`node_modules`·`.next`·venv 등 | — | — | 고유 커밋은 bundle로 보존. 나머지는 캐시·빌드 산출물 |

## 충돌 처리 규칙

같은 상대 경로에 크기가 다른 파일이 461개 있었다. 둘 중 하나라도 해당하면 버렸다(192개): final_workspace 쪽 파일이 더 최신이거나, 옛 쪽 내용이 final_workspace git에 이미 있는 경우. 옛 쪽만 더 최신이고 고유한 269개는 위 충돌 보관 폴더로 옮겼다. 덮어쓴 파일은 0개다(복사할 때 `open('xb')`로 기존 파일이 있으면 실패하게 했다).

## git

옛 `.git`의 `rev-list --all` 결과 2,863개 중 final_workspace에 없는 커밋은 11개였다(`backup/test-plan-presets-uncommitted-20261018{,b}`, `codex/customer-notice-fix`, `claude/plan-read-chunking-837f7a`, `integ/team-pull-20261014` 병합 6개, worktree HEAD `520d1b56e`). 원본 git은 `GIT_OPTIONAL_LOCKS=0` 상태에서 읽기만 했다. bundle은 scratch에 만든 임시 bare 저장소(alternates)로 만들었고 `git bundle verify`를 통과했다. 꺼내는 법: `git fetch .backup/2026-10-26_finalspace_git.bundle 'refs/finalspace/*:refs/finalspace/*'`

## 편집한 파일

`datasets/README.md`(끝에 이관 기록 한 단락)와 `wiki/handoff/index.md`(한 줄)를 고쳤다. 고치기 전 백업은 `.backup/2026-10-26_finalspace_migration_edits/`에 있다. 파이널스페이스 경로를 언급한 기존 문서 6개는 당시 기록이라 고치지 않았다.

## 참고

- 작업 지시에 있던 AGENTS.md 「로컬 원본·데이터셋 삭제 금지」 절과 `tools/local_data_guard.py` 훅은 현재 final_workspace에 없었다. 그래서 막힌 명령도 없었다. 옛 사본의 `tools/local_data_guard.py`·`safe_git.py`는 `tools/`로 옮겼지만 훅으로 연결하지는 않았다.
- 커밋·푸시는 하지 않았다.
