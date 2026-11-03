---
type: report
title: 11-03 백업 푸시 독립 교차검증 — 원격 상태·범위·시크릿·x600·복원 안내 실행 25/27 통과(92.6%)
description: 17:17 팀 SKN·개인 A-COP role-manager 4커밋(4c2f82a3b)과 개인 A-COP backup/2026-11-03/* 83개를 읽기 전용으로 다시 확인했다. 원격 상태·파일 범위·시크릿·x600 무영향·private 여부는 모두 맞았다. 복원 안내의 `git switch role-manager` 는 실제로 실패하고, 「workspace 보류 커밋은 외장에만 있다」는 설명은 사실과 다르다(54개 커밋이 8월부터 개인 A-COP 에 참조 없는 객체로 남아 있다)
status: done
domain: ops
impl_scope: 읽기 전용 검증. 쓴 것은 이 보고서 1개뿐이다. 원격 push·삭제·force-push 0, 원본 C:/_proj/final_workspace 는 GIT_OPTIONAL_LOCKS=0 읽기 조회만 했다. x600 은 읽기 조회만 했다(로그·상태 파일·journal, 서비스 변경 0). 임시 clone 은 scratch/xv1103/rt 에 만들고 지웠다
---

# 11-03 백업 푸시 독립 교차검증 (2026-11-03 17:20–18:17 KST)

검증 대상: 직전 작업자가 17:17 에 올린 팀 SKN·개인 A-COP `role-manager` 4커밋(끝 `4c2f82a3b`, 부모 `fab3da50a`, 727 파일)과 개인 A-COP `backup/2026-11-03/*` 83개. 작업자 자료(`scratch/bk1103/VERIFY.md`·`expected_backup_refs.json`)와 비교했다. 시크릿 검사는 작업자의 `secscan.py` 를 쓰지 않고 따로 만든 규칙으로 다시 했으며, 값은 출력하지 않고 파일·규칙 이름·개수만 남겼다.

## 결과 요약: 25/27 통과 (92.6%)

| # | 항목 | 결과 | 근거 |
|---|---|---|---|
| 1 | 팀 SKN role-manager = `4c2f82a3b9236327e5515781d3a572ef94086e12` | 통과 | `git ls-remote`, `gh api …/branches/role-manager` (17:20, 18:17 두 번) |
| 2 | 개인 A-COP role-manager = 같은 커밋 | 통과 | 같음 |
| 3 | 새 커밋 4개가 `fab3da50a` 위 일직선(4fc6ded17→897532bde→ce789a6a1→4c2f82a3b, 병합 커밋 0) | 통과 | `rev-list --parents`, GitHub activity before=`fab3da50a` after=`4c2f82a3b`(일반 push) |
| 4 | 팀 develop `3463b30c6`·main `57f3d2f00` 변화 없음 | 통과 | 마지막 변경이 10-28(develop push, main PR 병합). 오늘 이 두 브랜치에 activity 없음 |
| 5 | 개인 develop `da35486cb`·main `b0485d05f` 변화 없음 | 통과 | 마지막 변경 10-27·08-17 |
| 6 | 개인 backup/2026-11-03/* 83개 = `expected_backup_refs.json` | 통과 | 이름·해시 83/83 일치, 빠짐 0·남는 것 0. 스냅숏 `final-workspace-worktree` = `2a18a8c1c` |
| 7 | 팀 SKN 에 backup/* 0개, 보류 `workspace-52c7fcd56` ref 어디에도 없음 | 통과 | 팀 `refs/heads/backup` 0, 문자열 backup 0. 두 저장소에 52c7fcd56 ref 0 |
| 8 | 오늘 force-push 0 | 통과 | A-COP 오늘 activity: branch_creation 83, 스냅숏 브랜치 일반 push 3(970d5344e→9f71d0758→f30e2a17c→2a18a8c1c), role-manager push 1. 팀: role-manager push 1 |
| 9 | 변경 727 파일이 `wiki/`·`final_project_cs/wiki/`·`tools/`·루트 md·`.gitignore` 안 | 통과 | wiki 445, final_project_cs/wiki 274, tools 4, AGENTS·CLAUDE·README·.gitignore 각 1. 범위 밖 0. 추가 713·수정 14, 삭제 줄 5 |
| 10 | 제품 코드(app·web·frontend·deploy·program 등) 0 | 통과 | 코드 확장자는 tools 4개(disk_guard.py·json·guarded_clone.sh·테스트)와 옛 인계 자료 `wiki/handoff/2026-10-14_1500_commit-handoff/{changes.patch,log_reorder.py}` 뿐. `final_project_cs/{app,config,prompts,scripts,deploy,frontend/apps/web,admin}`·requirements 트리 해시가 fab3da50a 와 같다 |
| 11 | role-manager 변경분 실제 자격증명 0 | 통과 | 추가 39,616줄. 토큰·키·JWT·DSN·password 규칙 0건. 로컬 비밀 파일 값 일치 47개 파일은 전부 경로·커밋 해시·식별자(ACOP_GUARDRAILS_PATH, ACOP_MOBILITY_DATA_DIR, *.private.json 안의 파일 이름) |
| 12 | backup 표본 실제 자격증명 0 | 통과 | 아래 「시크릿 재검사」 |
| 13 | role-manager 개인정보 0 | 통과 | 휴대전화·주민번호·카드·개인 메일·도로명+호수·주문/배송 필드 0. PNG 7개 중 4개 눈으로 확인(앱 화면·차트, 개인정보 없음) |
| 14 | backup 표본 고객 개인정보 0 | 통과(참고 있음) | 아래 「개인정보」 |
| 15 | 개인 A-COP 이 private | 통과 | `gh api repos/roroblack/A-COP` private=true, visibility=private |
| 16 | 백업 내용이 팀 SKN 에 없음 | 통과 | 팀 저장소에 `2a18a8c1c` 조회 시 422(없음), workspace 고유 커밋 54개 중 팀에 0 |
| 17 | role-manager push 가 GitHub Actions 를 돌리지 않음 | 통과 | 두 저장소 `head_sha=4c2f82a3b` 실행 0, 오늘 실행 0, deployments 0 |
| 18 | x600 자동 반영이 서비스에 영향 없음 | 통과 | 아래 「x600」 |
| 19 | 복원 1단계 `git clone A-COP` | 통과 | 53초, `.git` 1.1GB |
| 20 | `git remote add team` + `git fetch team` | 통과 | rc 0 |
| 21 | `git switch role-manager` | **실패** | `fatal: 'role-manager' matched multiple (2) remote tracking branches` (origin·team 둘 다 있음). `git switch -c role-manager --track origin/role-manager` 로는 성공, HEAD=`4c2f82a3b`, 작업 트리 깨끗 |
| 22 | 2단계 backup refspec fetch | 통과 | rc 0 |
| 23 | `git worktree add ../fw-snapshot origin/backup/2026-11-03/final-workspace-worktree` | 통과 | 42초, HEAD=`2a18a8c1c`, 추적 파일 51,292, `final_project_cs/legacy` 하위 23개 폴더, `_backup` 경로 파일 6,794, `evidence` 경로 파일 6,456, status 깨끗 |
| 24 | 3단계 로컬 전용 브랜치 fetch·`git log`·`git diff <b>~1 <b>` | 통과 | `local/fix-place-quality-20261027-f5edf4784` 단독 fetch → FETCH_HEAD `f5edf4784374`, diff 2 파일 |
| 25 | 6단계 확인 명령 | 통과 | `git log -1 role-manager`, `python tools/safe_git.py --self-test` 12/12, `python tools/disk_guard.py --help` rc 0 |
| 26 | 안내 문서 「workspace 보류 커밋은 외장 .git 에만 있다」 | **실패** | 아래 「새로 찾은 것」 |
| 27 | 임시 폴더 정리 | 통과 | clone·worktree(`scratch/xv1103/rt`, `.git` 1.1GB + 체크아웃 2개)와 diff 덤프(스냅숏 diff 1.72GB 와 조각 사본)를 지웠다(삭제량 전체는 따로 재지 않음). 남은 것은 결과 표·스크립트 7.5MB(scratch 24시간 자동 정리 대상). 새 `C:\c` 경로를 만들지 않았다(기존 10-30 것만 있음) |

디스크: clone 전 `tools/disk_guard.py check --need-bytes 6e9` 허용(여유 353.76GB, 최소 30GiB 위, 목표 400GB 아래). 같은 출처(GitHub A-COP)의 등록된 유휴 clone 이 없어 새 clone 이 맞다. 끝난 뒤 여유 351.63GB — 내가 남긴 것은 7.5MB 이고 그 사이 다른 세션 쓰기가 있었을 수 있다(원인 미확인).

## 시크릿 재검사 (값 출력 없음)

- 규칙(작업자와 다르게): PEM 개인키 머리+본문 여부, AWS 키 ID·secret 대입, GitHub·LLM(sk-/sk-ant-/sk-or)·Google·HF·Slack/Discord webhook·Telegram 토큰, JWT(payload 키만 해독), Bearer 리터럴, DSN 비밀번호(호스트만 분류), `password|비밀번호 =`, URL 질의 키, 이름이 secret/token/key 인 대입의 엔트로피 4.0 이상 값. 그리고 로컬 `.env*`·Hermes `.env`·`auth.json`·`*private*.json` 163개 파일의 값 1,689개 정확 일치(변수 이름으로 분류). 경로 규칙: `.env`, 키 파일(pem/key/p12/id_rsa), credentials/token json, sqlite/쿠키, `.ssh`/`.aws`, `datasets/commerce`·주문 상세.
- 대상: role-manager 추가 39,616줄 / 스냅숏 `efeb873a8..2a18a8c1c` 추가 10,773,768줄(34,225 파일, legacy·_backup·evidence 포함) / 무작위(seed 1103) 백업 브랜치 8개의 고유 커밋 28개 추가 25,196줄 / 83개 끝 커밋 트리의 경로 54,067개.
- 결과: **실제 자격증명 0건.**
  - 스냅숏에서 규칙에 걸린 파일 3,369개는 분류 결과 모두 오탐: 로컬 값 일치는 경로·모델 이름·커밋 해시·시험 이름·공개 Turnstile site key(설계상 공개), 프록시 URL 일치 65건은 사용자 정보 없는 주소; `sk-` 26건은 시험 문맥 33자 가짜 키; PEM 25건은 머리 글자만 있고 본문 없음; Discord webhook 2종은 id 가 `123…`(18자리) 시험값; JWT 3건은 payload 키가 `some` 하나(PyJWT 예시); DSN 비밀번호 9건은 모두 127.0.0.1 시험 DB; URL 키 1건은 시험 문맥.
  - 표본 브랜치: DSN 26건 모두 127.0.0.1 시험 DB(4자), 로컬 값 일치는 파일 이름·시험 식별자.
  - 경로: 실제 `.env` 0(있는 것은 `.env*.example` 19개), 키 파일 0. `*.private.json` 이름의 evidence 20개는 내용이 위 검사를 통과했다.

## 개인정보

- role-manager: 0건.
- 백업 표본(개인 private 저장소에만 있음): 고객 개인정보로 판단되는 것 0건. 참고로 걸린 것:
  - 휴대전화 꼴 번호(하이픈) 고유 40개 — `program/research/…/dining-build/load_200.sql`(관광공사 `infocenterfood` 필드)과 `_backup/2026-10-0*_place_catalog*`(`tel`·`phone` 필드) 의 **공개 장소·식당 안내 번호**. 나머지는 시험 문장(「연락처 010-…」 날짜 읽기 시험)·가짜 꼴.
  - 개인 메일 도메인 18개 — pip `dry-run.json`·`install-report.json` 의 **공개 패키지 작성자 메일**, `terms-content.ts` 1개는 약관 문의 메일로 팀 develop(공개)에 이미 같은 값이 있다.
  - 도로명 주소 8건 — 장소 카탈로그 원본의 공개 장소 주소.
  - `wiki/_migration/datasets/commerce/**` 문서 10개(주문·배송 데이터셋 설명 문서)는 팀 develop·두 role-manager·원본 HEAD 에 원래 있던 것으로 이번 푸시가 새로 올린 것이 아니다.
- 인프라 정보(개인정보는 아님, 공개 팀 저장소): role-manager 추가분에 Windows 사용자 경로 409회(189 파일), 사설 IP 23회(15 파일), `사용자@IP` 7회(6 파일). 이전부터 팀 저장소에 같은 꼴이 있다(fab3da50a 트리에 사용자 경로 21 파일, 사설 IP 9 파일).

## x600

- 반영 장치: x600 WSL `tripilot-autodeploy.timer`(약 5분 간격) → `/root/tripilot-docker/auto_deploy.sh`, 대상 = 팀 SKN `role-manager`.
- 확인: x600 저장소 `FETCH_HEAD` = `4c2f82a3b`(새 커밋을 받았다). 스크립트는 배포 폴더(app·config·knowledge·prompts·scripts·deploy·frontend/apps/web·admin·requirements.txt) 지문이 `state/deployed_fp` 와 같으면 빌드 없이 끝난다. 이 9개 경로 트리 해시는 fab3da50a 와 4c2f82a3b 가 모두 같다.
- 결과: 17:19~18:12 실행이 모두 1~2초 만에 성공 종료, `deploy.log` 마지막 수정 10-29 03:41(새 줄 없음), `state/current_tag` = `fab3da50ab`, 공지 보드 최신 deployId `fab3da50ab-…`, `/health` 200(17:22·17:31·18:17). **배포 실패도 서비스 변경도 없었다.** 보고서의 「push 하면 x600 에 자동 배포」는 「받기만 하고 다시 빌드하지 않음」이 정확하다.

## 새로 찾은 것 (보고만, 삭제·force-push 하지 않음)

1. **보류한 `workspace` 커밋이 이미 개인 A-COP 에 있다.** 원본 로컬 `workspace`(끝 `52c7fcd5613760120bfd93a03552a3b92287f796`)의 고유 커밋 54개를 `gh api repos/roroblack/A-COP/commits/<sha>` 로 조회하면 54/54 가 나온다. 그중 `datasets/commerce` 를 건드리는 47개도 47/47 조회된다. 어느 브랜치에서도 닿지 않는 객체이고(새 clone 에는 없음), A-COP `workspace` 브랜치 기록상 08-18~08-29 push 뒤 09-14 force-push 로 되감긴 흔적이다. 오늘 푸시가 만든 것은 아니다(오늘 activity 에 관련 ref 없음). 팀 SKN 에는 0/54. 저장소가 private 라 외부 공개는 아니지만, 안내 문서 1절 「외장 백업의 원본 .git 에만 있다」는 틀렸다. GitHub 의 참조 없는 객체는 사용자가 지울 수 없고 GitHub 지원 요청이 필요하다 — 결정은 사용자 몫.
2. **복원 안내 2절 1단계 `git switch role-manager` 가 실패한다.** `git fetch team` 뒤에는 원격 추적 브랜치가 둘이라 모호하다. `git switch -c role-manager --track origin/role-manager`(또는 team 을 나중에 추가) 로 고쳐야 한다. 문서는 고치지 않았다(지시 범위 밖).
3. 안내 문서 5절이 「role-manager 에 올린 3개 커밋」이라 적었지만 커밋은 4개다(4번째가 안내 문서 자체이며 작업자 `rm_staged4.tsv` 로 따로 검사됨). 내용상 문제는 없다.
4. 팀 SKN 은 public 이다. 이번 role-manager 727 파일(문서·도구)은 공개 저장소에 올라갔고, 위 검사로 비밀·개인정보는 없었다.

## 다시 해 보는 법

- 원격: `git ls-remote <팀|개인> …`, `gh api repos/<repo>/activity?time_period=day`, `gh api repos/<repo>/actions/runs?head_sha=4c2f82a3b…`.
- 범위: 새 clone 에서 `git -c core.quotepath=false diff --name-only fab3da50a 4c2f82a3b`.
- 시크릿·개인정보: `scratch/xv1103/xscan.py`(diff·paths 모드), 분류 `triage3.py`·`triage4.py`·`phones.py`(24시간 뒤 자동 정리될 수 있음; 결과 개수는 이 보고서에 있다).
- x600(읽기만): `ssh -i ~/.ssh/id_ed25519_x600 … "wsl -u root -e env GIT_OPTIONAL_LOCKS=0 git -C /root/tripilot-docker/repo rev-parse FETCH_HEAD"`, `… cat /root/tripilot-docker/state/current_tag`, `… journalctl -u tripilot-autodeploy.service -n 6`.

후속(2026-11-03 18:3x): 21·26번 실패와 「새로 찾은 것」 1–4를 [복원 안내](../../handoff/2026-11-03_new-pc-restore-guide.md)에 정정·기록했다(정정 세션. 이 보고서 본문은 그대로).
