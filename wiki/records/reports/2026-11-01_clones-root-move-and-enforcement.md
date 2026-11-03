---
type: report
title: 작업 사본 위치 이전(C:/_proj/_clones → final_workspace/.tmp/clones)과 「C:/_proj 바로 아래 새 폴더 금지」 강제 가능성 조사 (2026-11-01)
description: disk_guard 장부·관리 위치를 Git 무시 위치로 옮기고 check·inventory·reserve·abandon·바깥 거부를 새 경로로 확인한 뒤 옛 _clones를 지웠다. 새 폴더 금지는 지금 어떤 훅에도 연결돼 있지 않아 말뿐인 지침이며, 연결 방법과 NTFS ACL 안의 효과·위험을 적었다
status: done
domain: ops
---

# 작업 사본 위치 이전과 강제 가능성 조사 (2026-11-01)

담당: 라우팅 세션 `20261024_213155_36cd5c`(사용자 지시, 구구루트 Telegram 총괄 `20261027_205452_5fbd35ab` 하위 `6bebe8` 경유). 커밋·push·서비스 중지 0.

## 1. 이전 결과

| 단계 | 결과 |
|---|---|
| 새 위치 | `C:/_proj/final_workspace/.tmp/clones` — `C:/_proj` 루트 밖, 저장소 안 |
| Git 무시 확인 | 실제 파일을 두고 `python tools/safe_git.py check-ignore -v` → `.gitignore:12:.tmp/` 3/3 (탐침 파일은 지움) |
| 백업 | `.backup/2026-11-01_clones-root-move/` 3개 + `MANIFEST.json`(이전·이후 sha256) |
| 바꾼 줄 | `tools/disk_guard.json` 8–9행(`ledger_path`·`managed_roots`), `AGENTS.md` 15행, `CLAUDE.md` 19행. 백업과 diff 해서 이 줄만 바뀐 것을 확인했고, CRLF 그대로, 두 지시 파일의 해당 줄이 같다 |
| 하드코딩 | `disk_guard.py`·`guarded_clone.sh`에 `_clones` 문자열 0 — 경로는 설정에서만 읽는다(`disk_guard.py:75`, `:176`) |
| 실행 확인 | `check` rc=0(allowed) · `inventory` rc=0(entries 0) · `reserve` rc=0 → `abandon` rc=0, 장부 `{"entries": []}` · 옛 위치로 `reserve` 시 rc=3 `outside configured managed_roots` |
| 옛 폴더 | `C:/_proj/_clones`(장부 20 B 하나)를 `backups/proj-folder-retire-20261031/_clones/`에 sha256 일치로 보관한 뒤 지웠다. 경로가 없음을 확인 |

옛 경로가 남은 곳: guguroute cron·skill 0건. 현재 문서가 아닌 dated 기록 — `wiki/handoff/2026-10-29_eks-reader-fatal-telemetry-blocker.md`, `wiki/handoff/2026-10-29_explain-writer-serving-resume.md`, `wiki/records/` 아래 보고·증거 10개. 기록이라 고치지 않았다.

주의: 이 PC의 Python이 찾는 `git`은 WindowsApps 안 Hermes 동봉본이라 `subprocess`가 WinError 5로 실패한다. `safe_git.py`를 돌릴 때는 MinGit `cmd`(예: `cache/scratch/date_risk_independent_review_01/mingit/cmd`)를 PATH 앞에 둔다.

## 2. 「C:/_proj 바로 아래 새 폴더를 만들지 않는다」 — 강제되는가

| 수단 | 지금 | 근거 | 강제하려면 |
|---|---|---|---|
| (a) `disk_guard`·`guarded_clone` | **도구 안에서만 강제** | 관리 위치 밖 `reserve`가 rc=3로 거부(위 실행). 맨 `git clone`·`mkdir`은 이 도구를 거치지 않는다 | 도구를 쓰도록 하는 다른 수단(b·c)이 필요 |
| (b) Codex hooks · Claude PreToolUse | **연결 안 됨(말뿐)** | `tools/local_data_guard.py`는 삭제·원본 동기화만 막고 만들기 패턴이 없다. 로컬 `.claude/settings.local.json`·`~/.codex/config.toml`·role-manager `fab3da50` 어디에도 이 파일을 부르는 hooks 설정(`.claude/settings.json`·`.codex/hooks.json`)이 없다 | `.claude/settings.json`의 `hooks.PreToolUse`(Bash 매처)와 Codex hooks에 검사 스크립트 등록. 이때 AGENTS의 「Claude 실행 전 훅은 … 차단한다」 문장도 사실과 맞춰야 한다 |
| (c) Hermes | **연결 안 됨(쓸 수 있음)** | 프로필 `config.yaml`에 `hooks:` 블록 없음, `hooks/` 빈 폴더, `approvals.mode: smart`(위험 명령 승인만). 공식 문서: 셸 `pre_tool_call` 훅이 차단·fail-closed 가능 | 프로필 `config.yaml`에 `hooks:` 셸 `pre_tool_call` 등록(이 프로필만). 다른 프로필은 각자 |
| (d) NTFS ACL | **제안만** | 아래 | 사용자 결정 |

격리 시험(정식 반영 아님): `profiles/guguroute/workspace/disk-audit/proj_root_guard_candidate.py` — 만들기 동사(mkdir·New-Item·git clone/worktree add·cp/mv·os.makedirs 등)와 `C:/_proj/<기존에 없는 이름>`이 함께 있으면 거부. 거부 6/6, 허용 4/4(저장소 안 `.tmp/clones`, `guarded_clone`, 읽기 명령). 못 막는 것: 변수로 경로를 만드는 명령, 파일로 쓴 뒤 실행하는 스크립트, Explorer·다른 프로그램. 그래서 b·c는 **에이전트 실수 방지**이지 완전한 차단이 아니다.

(d) ACL 안: `icacls C:\_proj /deny <사용자>:(AD)` — 상속 표시 없이 `C:\_proj` 자체에만 「하위 폴더 만들기」 거부. 기존 하위 폴더와 그 안 작업은 그대로.
- 효과: 에이전트·스크립트·Explorer 모두 `C:/_proj` 바로 아래 새 폴더·폴더 이동을 못 한다. 훅이 못 막는 우회도 막는다.
- 위험: 사용자 본인도 막힌다(Explorer 「새 폴더」, 설치 프로그램, 압축 풀기). 거부 항목은 허용보다 우선이라 관리자 권한 실행도 막힌다. 소유자는 ACL을 다시 바꿀 수 있어서 의도적 우회는 못 막는다. 되돌리기는 `icacls C:\_proj /remove:d <사용자>`.
- 적용하지 않았다.

## 3. 파일

- 바꿈: `tools/disk_guard.json`, `AGENTS.md`, `CLAUDE.md`
- 새로 만듦: 이 보고서, `.backup/2026-11-01_clones-root-move/`, `.tmp/clones/.disk_guard_ledger.json`(도구가 생성)
- 결과 JSON: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/_routing_session_result.json` 의 `clones_migration_1101`
