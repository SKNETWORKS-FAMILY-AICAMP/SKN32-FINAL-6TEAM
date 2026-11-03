---
type: report
title: C:/_proj 지정 38개 폴더 — 담당 세션 직접 전달·인수 확인, 삭제 실측 25/38, 남은 13개의 정확한 차단 원인과 정식 승인 경로 (2026-11-01)
description: 라우팅 세션 36cd5c에 루트 폴더 금지 규칙과 _clones 설정 이전을 전달했고, 인수와 완료를 확인했다(_clones 삭제). Explorer 때문에 막힌 Codex 담당 3개에는 재시도를 전달했지만 모두 다시 BLOCKED였다. 남은 13개는 Codex 도구 정책 거부 11개와 Explorer 핸들 2개다. 우회는 하지 않았다
status: done
domain: ops
impl_scope: 운영 기록. 이 보고서의 작성자는 제품 코드나 설정을 바꾸지 않았다. 설정과 지시 파일 변경은 담당 세션 36cd5c가 했다(아래 표)
---

# C:/_proj 38개 폴더 — 담당 세션 직접 처리 감독 (2026-11-01 18:35–19:05 KST)

수행: 구구루트 Telegram 총괄 `20261027_205452_5fbd35ab`의 하위 세션 `20261101_183548_6bebe8`.
앞선 기록: [세션별 정리 지시 후속 감독](2026-10-31_session-cleanup-relay-supervision.md), guguroute `backups/proj-folder-audit-20261031/HANDOFF.md`.
담당 세션 보고서: [작업 사본 위치 이전과 강제 가능성 조사](2026-11-01_clones-root-move-and-enforcement.md).
단위: B. 원자료는 guguroute `cache/scratch/del38/`에 있다(`assignment_status.json`, `codex_out/*.r1101.log`). 이 폴더는 만료될 수 있는 scratch다.

## 결과

- **삭제 실측: 25/38** (19:00 실측. 18:35에는 24/38). 이번에 늘어난 1개는 `_clones`다.
- **남은 13개**: Codex 도구 정책 거부 11개, Explorer 디렉터리 핸들 2개. 우회, 강제 종료, 화면 조작은 0건이다.
- C: 여유 공간은 19:00에 253,885,165,568 B였다.

## 세션별 메시지와 수락

| 받는 쪽 | 전달 경로 | 보낸 시각 | 수락(실측) | 결과 |
|---|---|---|---|---|
| Hermes 라우팅 세션 `20261024_213155_36cd5c` | gateway `session.resume`→`prompt.submit`→`end_reason` 없는 detach. admission `60e5b1fd…` | 18:46:25 | 18:46:39 `ACK-ROOTRULE-1101 36cd5c`. 세션은 열린 상태이고 admission은 terminal/completed | `_clones` DONE (아래). 강제 가능성 조사 완료 |
| Codex `01a18393…` (busreview1029) | `codex exec resume`, 같은 스레드에서 1턴 | 18:46:59 | `ACK-1101 busreview1029` | BLOCKED: Explorer 핸들 |
| Codex `01a183a4…` (eksperf1029) | 〃 | 18:47:02 | `ACK-1101 eksperf1029` | BLOCKED: 핸들 검사는 통과했지만 삭제가 `blocked by policy`로 거부됨 |
| Codex `01a183de…` (eksscalar1029) | 〃 | 18:47:05 | `ACK-1101 eksscalar1029` | BLOCKED: Explorer 핸들 |

- 메시지 원문은 `del38/msg_root_rule_routing_1101.txt`와 `msg_codex_explorer_1101.txt`에 있다. 루트 금지 규칙, 지정 작업 폴더 사용, 완료 후 보존 검증과 자체 정리, 정책 거부 시 재시도와 다른 방식 금지, 프로세스 종료와 화면 조작 금지가 들어 있다.
- **정책 거부로 막힌 Codex 10개 스레드에는 다시 보내지 않았다.** 이유는 세 가지다.
  - 설정이 같아서 다시 거부될 가능성이 높다.
  - 한 턴에 0.6–0.9M 토큰이 든다. 실측치는 617,263, 896,995, 627,604다.
  - "명령 모양을 바꿔 다시 해 보라"는 지시는 우회가 된다.
- 이 10개 스레드는 한 번만 실행하고 끝나는 `codex exec` 스레드라서, 다시 실행하지 않는 한 새 폴더를 만들지 않는다. 앞으로 생기는 Codex에는 AGENTS.md의 규칙 문구가 적용된다. 다만 그 규칙이 실제로 강제되는 범위는 아래 「재발 방지」 표에 따른다.

## `_clones` 설정 이전 (36cd5c 수행, 이 세션이 다시 확인)

- `tools/disk_guard.json`의 `ledger_path`와 `managed_roots`를 `C:/_proj/final_workspace/.tmp/clones`로 바꿨다. 이 경로는 `.gitignore:12 .tmp/`에 걸린다.
- AGENTS.md 15행과 CLAUDE.md 19행의 사본 위치 문구를 같은 내용으로 고쳤다.
- 이 세션이 dated backup `.backup/2026-11-01_clones-root-move/`와 직접 diff해 봤다. 세 파일 모두 해당 줄만 바뀌었고, AGENTS.md와 CLAUDE.md는 CRLF를 유지했다.
- 36cd5c가 새 경로로 `check`, `inventory`, `reserve`, `abandon`을 실행했다. 모두 rc=0이었고 장부는 비어 있다. 옛 위치로 `reserve`를 시도하면 rc=3으로 거부된다.
- 옛 장부 20 B는 `backups/proj-folder-retire-20261031/_clones/.disk_guard_ledger.json`에 보관했다. 그 뒤 `C:/_proj/_clones`가 없는 것을 이 세션이 다시 확인했다.
- AGENTS.md와 CLAUDE.md의 변경은 미커밋이다. 이 두 파일은 HEAD 기준으로 이미 다른 미커밋 변경이 많이 있다.

## 남은 13개 — 담당자와 정확한 차단 원인

| 폴더 | 담당(만든 스레드) | 마지막 판정 | 정확한 원인 |
|---|---|---|---|
| busreview1029 (RETIRED.md 769 B만 남음) | Codex 01a18393 | BLOCKED | 네이티브 핸들 조회 결과, explorer.exe PID 11372가 루트 디렉터리 핸들 2개를 가지고 있음 |
| eksscalar1029 | Codex 01a183de | BLOCKED | 〃 |
| eksperf1029 | Codex 01a183a4 | BLOCKED | 핸들 검사는 통과. `Remove-Item`이 실행 전에 `rejected: blocked by policy`로 거부됨 |
| eksdeep1029, eksdawn_causality_1029, eksgolden_causality_1029, eks-independent-1029, eksmix_selection_1029, eksobserve1029, eksfatal1029, eksserve1029 | 각 생성 스레드(`del38/codex_assign.json`) | BLOCKED | 정확한 경로 삭제가 `rejected: blocked by policy`로 거부됨. 일부는 파일 단위 삭제도 거부됨. eksserve는 WSL 검사 시간 초과가 겹침 |
| ekscheckingcontinue1029 | Codex 01a18474 | BLOCKED | 삭제가 `blocked by policy`로 거부됨. 후속 턴에서 `.ps1` 실행이 PowerShell 실행 정책 `PSSecurityException`에 걸림 |
| eksprecision1029 | Codex 01a184c1 | BLOCKED | 첫 턴은 `blocked by policy`. 후속 턴은 스레드가 직접 만든 `.retire-tools`(7,623파일, 389,167,978 B, Git 도구 사본)가 manifest STOP 조건에 걸려 중단 |

### 정책 거부의 실제 출처 (eksdeep1029 rollout으로 확인)

- 스레드 설정은 `approval_policy=never`, `approvals_reviewer=user`, `sandbox=danger-full-access`다. `codex exec`의 기본값이고, `codex exec`에는 `-a` 옵션이 없다.
- 거부 문자열은 Codex 바이너리 안의 ``` `<cmd>` rejected: blocked by policy ```다. 프로세스가 만들어지기 전에 거부됐다.
- 그 rollout에는 guardian이나 auto-review 평가 이벤트가 0건이다. 그래서 Codex 응답에 적힌 "자동 승인 검토"는 실제로 리뷰어가 판단했다는 뜻이 아닐 수 있다. 승인을 물을 수 없는 `never` 모드에서 위험 명령을 실행 전에 막은 결과로 보인다. 이 해석은 rollout 1개만 확인한 것이다.
- 같은 설정에서도 7개 스레드의 `Remove-Item -Recurse`는 실행됐다. 판정 기준은 확인하지 못했다.

### 정식 승인 경로 (조사만 함, 실행하지 않음)

1. **사람이 승인하는 경로 (Codex 정식)**: 사용자가 자기 터미널에서 `codex resume <thread-uuid> -a on-request`를 실행한다. cwd는 `C:\_proj\final_workspace`다. 승인 요청이 사용자에게 가고(`approvals_reviewer=user`), 정확한 경로 삭제 명령에 사용자가 직접 승인한다. 화면 조작은 사용자 본인이 한다. 에이전트가 대신하지 않는다.
2. **Hermes 승인 경로**: 총괄 세션 5fbd35ab이 Hermes terminal 도구로 정확한 경로를 삭제한다. 위험 명령 승인 요청이 Telegram으로 사용자에게 간다. 실행 주체가 Codex 담당 스레드에서 그 스레드를 띄운 총괄 세션으로 바뀌므로, 사용자가 동의해야 한다.
3. `codex exec resume … --approve-for-me`: 승인을 사람 대신 자동 리뷰어에게 넘긴다. 사람이 승인하는 것이 아니므로 사용자가 결정해야 한다. `--dangerously-bypass-approvals-and-sandbox`는 우회이므로 쓰지 않는다.
- eksprecision1029는 위 경로와 별개로, 담당 스레드가 `.retire-tools`를 재생성 가능한 자기 산출물로 분류하고 STOP 해제 근거를 기록해야 한다.

### Explorer (2개)

- Shell.Application 창을 읽기 전용으로 열거했다. 열린 창은 `C:\Users\kcxsz`와 제어판 2개뿐이고, 대상 폴더를 보여 주는 창은 없다. 핸들은 PID 11372(10-21부터 실행 중인 셸)가 가지고 있지만 어느 창의 것인지 특정할 수 없다. 그래서 창을 특정해 닫는 안전한 경로가 없다.
- 해제 방법은 사용자가 원할 때 직접 해야 한다. 예를 들어 Explorer 탐색 창에서 `C:\_proj` 트리를 접거나, 로그오프하거나, 재부팅하는 것이다. 에이전트는 종료, 재시작, 화면 조작을 하지 않는다.
- **이 세션의 오류**: 18:44에 `FILE_READ_ATTRIBUTES`, share=0 조건으로 확인해 "핸들이 풀렸다"고 판정하고 Codex 3개에 그렇게 전달했다. 그런데 이 접근 권한은 공유 검사에 걸리지 않아서 핸들을 찾아내지 못한다. 실제로는 풀리지 않았다. 담당 스레드들이 네이티브 핸들 조회로 다시 확인해 BLOCKED로 바로잡았다. 삭제는 일어나지 않았다.

## 재발 방지 — 이행 상태 (코드인지 말뿐인지 구별)

| 수단 | 상태 | 근거 |
|---|---|---|
| disk_guard/guarded_clone의 managed root를 `.tmp/clones`로 이전 | **코드로 연결됨** (도구를 거칠 때만) | 옛 위치 `reserve`는 rc=3으로 거부됨. 맨 `git clone`이나 `mkdir`은 막지 못함 |
| `C:/_proj` 바로 아래 새 폴더 금지 (지시 문구, 하위 세션 goal 문구) | **말뿐인 지침** | 36cd5c가 규칙 문구를 skill `guguroute-claude-coding-workers/references/disk-hygiene.md`에 적음 |
| Claude PreToolUse와 Codex hooks | 연결 안 됨 | `.claude/settings.json`과 `.codex/hooks.json`에 등록된 것이 없음. 36cd5c 조사에 따르면 AGENTS.md의 "실행 전 훅이 차단한다"는 문장은 사실과 맞지 않음 |
| Hermes `pre_tool_call` 훅 | 연결 안 됨 (설정하면 쓸 수 있음) | guguroute `config.yaml`에 `hooks:` 블록이 없음. 후보 검사 스크립트 `workspace/disk-audit/proj_root_guard_candidate.py`를 격리 시험함: 만들기 6/6 거부, 정상 명령 4/4 허용. 변수로 조립한 경로, 스크립트 파일, Explorer는 막지 못함 |
| `C:\_proj`에 비상속 NTFS ACL로 폴더 만들기(AD) 거부 | 제안만 함 | 사용자 본인과 설치 프로그램도 막힘. 소유자는 ACL을 되돌릴 수 있음. 적용하지 않음 |

## 범위 밖 관찰

- `C:/_proj/mynews`(10-31 19:52 생성)는 myapp 프로필 세션 `local-1c4a62bd…`의 프로젝트다. 다른 프로필이므로 건드리지 않았다.
- `C:/_proj/h7407ba`(10-31 19:47 생성, 빈 폴더)는 만든 세션을 확정하지 못했다. 38개 대상이 아니다.

## 다음 결정 (사용자)

- 정책 거부 11개: 위 정식 경로 1, 2, 3 중 하나를 고른다.
- Explorer 2개: 사용자가 원할 때 Explorer 상태를 정리한 뒤 담당 스레드에 다시 보낸다.
- 루트 금지를 코드로 강제할지 정한다: hook이나 Hermes `pre_tool_call` 등록, 또는 ACL.
- AGENTS.md와 CLAUDE.md의 훅 문장을 정정할지 정한다.
