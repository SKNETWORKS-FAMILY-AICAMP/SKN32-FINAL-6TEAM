---
type: handoff
title: x600 F: guguroute 폴더 5개 실측 · 출처 · 사용 여부 · 조치 분류 (2026-10-29)
description: 10-28 미완 조사를 x600 복귀 뒤 읽기 전용으로 재개했다. F: 루트 4개와 F:\_work\projects 아래 1개, 모두 2026-10-18 x600 복구 세션이 만든 것이다. 합계 18,936,180,159 B. 삭제 0
status: draft
domain: travel
impl_scope: 기록만. x600 쓰기 · 삭제 · 이동 0, 코드 · 서비스 변경 0
---

# x600 F: guguroute 폴더 — 실측 완료, 삭제 대기

- 앞 문서: [10-28 미완 인계](2026-10-28_x600-f-drive-guguroute-folders-readonly.md). 2026-10-29 00:35 KST `ssh Yeon@192.168.0.8` 접속 성공(호스트 `x600_251214`). 공개 `/health` 는 00:43 에 HTTP 200 이었다.
- 확인 방법: SSH 로 PowerShell 을 stdin 에 넣어 실행했다(`iex ([Console]::In.ReadToEnd())`, x600 에 스크립트 파일을 만들지 않음). 비밀 키워드가 들어간 줄은 출력 단계에서 가렸다.
- `F:\c` 가설(MSYS 경로 실수)은 틀렸다. 그런 폴더는 없다.

## 폴더 5개 (크기는 reparse 를 따르지 않은 파일 바이트 합)
| 경로 | 바이트 | 파일 | 생성(KST) · 마지막 쓰기 | 내용 |
|---|---:|---:|---|---|
| `F:\guguroute-space-safety-20261018-041356` | 811,556,893 | 3 | 10-18 04:13 · 04:14 | `E:\dod28_ft\venv312\...\torch_cuda.dll` 을 NTFS 압축하기 전에 만든 사본과 manifest |
| `F:\guguroute-cpu-review-backup-20261018-041722` | 717,177,763 | 4 | 10-18 04:17 · 05:00 | `torch_cpu.dll`(dod28_ft) · `libtorch_cpu.so`(jikimi_ft) 압축 전 사본과 `approved-compression-v30.json` |
| `F:\guguroute-offline-20261018-1155` | 4,352,058,217 | 21,646 | 10-18 11:58 · 11:59 | E 공간 확보용 E→F 보존 이동 5그룹(`etc\home-root-archive-20260905` · `etc\pagejob` · `npu-rebuild\_rec\backup` · `tripilot-eks-build-context-v3.zip` 2개) |
| `F:\guguroute-qemu-cow-probe-20261018-135636` | 515,897,273 | 549 | 10-18 13:56 · 15:07 | portable QEMU(`portable\`) · 합성 디스크 COW/NBD 검사 기록 · 설치본 부분 다운로드 2개(261,010,808 B) |
| `F:\_work\projects\guguroute-x600-independent-20261018` | 12,539,490,013 | 753 | 10-18 15:04 · 19:11 | 「독립 복구 가상환경」 qcow2 들(`runtime-independent-v2.qcow2` 7.42 GB, v1 1.78 GB, 고객 사본 1.78 GB 등) · 주입 번들 · 기록 |
| 합계 | **18,936,180,159** | | | 약 18.9 GB(십진). F: 여유 124,256,641,024 B |

## 누가 만들었나
- **2026-10-18 x600 가상환경 · 고객 앱 복구 세션**이다. 이 PC 에서 SSH 로 x600 에 작업했다. 근거는 다음과 같다.
  - `records/reports/2026-10-18_x600-e-to-f-preserved-move.md` 는 목적지를 `guguroute-offline-20261018-1155` 로 명시한다. 파일 수 21,643 과 바이트 수가 F: 의 `result.json` · `progress.json` 과 일치한다.
  - `delivery/x600-preserved-boot-recovery.md` · `handoff/2026-10-18_chat-model-and-api-outage.md` · `records/reports/2026-10-18_festival-traffic-alert-recovery.md` 에는 QEMU 공식 배포 서명 만료, NBD/COW 합성 검사, 독립 OS · 고객 사본 · WHPX 가속 · TLS 사본 단계가 적혀 있다. 이 문서들의 `_backup` 시각(15:08~16:56)이 폴더 하위 디렉터리 생성 시각(15:04~16:49)과 맞물린다. 위 3개 문서와 E→F 보고서는 Git 에 **untracked** 상태다.
  - 같은 기록 109행에 「새 상위 작업 폴더는 F 지침대로 기존 작업 영역 하위에만 만들고, **기존 시험 폴더는 이동 · 삭제하지 않는다**」는 결정이 있다. 그래서 15:04 이후 폴더는 `F:\_work\projects` 아래에 생겼다. 그 전 4개는 `F:\AGENTS.md`(F: 루트에 작업 · 백업 폴더 신규 생성 금지)를 어긴 상태로 남아 있다.
  - 04:13 · 04:17 의 torch 압축 사본 2개는 wiki 에 직접 기록이 없다. 같은 날 E 공간 부족 대응이었고(`freeBefore` 13.98~17.06 MB), 파일명에 `approved-compression` 이 있다. **같은 세션이라는 것은 추정**이다.
- **세션 ID 는 확인하지 못했다.** Hermes `state.db` 는 기본 프로필이 10-19, guguroute 프로필이 10-24 부터만 있다. 로컬 Codex threads 는 10-26 부터다. x600 쪽 `.codex` · `.claude` jsonl 에는 이 폴더 이름이 0건이다. x600 OpenSSH/Operational 로그는 10-28 15:11 부터만 남아 있다. 현재 기록에서 이 폴더 이름이 나오는 것은 10-25 세션 `20261025_042230_d5c9df` 의 tool 출력 1건(offline)과 이번 조사뿐이다. 둘 다 생성자는 아니다.

## 사용 여부 (00:36~00:40 실측)
- 실행 중 프로세스 · 서비스 · 예약 작업에서 이 경로를 참조하는 것은 0건이다. QEMU · python · cloudflared · caddy 프로세스는 0개다. 현재 운영은 WSL Ubuntu(00:07 기동, `wslrelay` 80/443)이고 독립 복구 VM 은 꺼져 있다. 10-19 01:49 에 `host_memory_guard` 로 강제 종료됐고, 그때 `database_crash_recovery_may_be_required=true` 가 기록됐다.
- **`guguroute-offline` 은 사용 중이다.** `E:\etc\home-root-archive-20260905` · `E:\etc\pagejob` · `E:\npu-rebuild\_rec\backup` 3개는 이 폴더를 가리키는 junction 이고, `E:\tmp\…zip` · `E:\ssh-home\…zip` 2개는 symlink 다. 이 폴더를 지우면 E 쪽 경로 5개가 깨진다.
- torch 사본 3개: E 원본이 그대로 있고 `Compressed` 속성이다. SHA256 이 manifest · F 사본과 3/3 일치한다.
- `qemu-cow-probe\portable\qemu-system-x86_64.exe` 의 LastAccess 가 10-29 00:26 이다. 실행 중 프로세스와 Prefetch 기록은 없다. 부팅 직후 백신 검사 같은 단순 읽기로 보이지만 원인은 확인하지 않았다.
- `guguroute-x600-independent` 의 `contract-before-run.json` 은 `qemu-cow-probe` 의 `portable\qemu*` · `linux-bootstrap-140149\installed-kernel.bzImage` 해시를 실행 자원으로 고정했다. 그래서 두 폴더는 서로 의존한다.

## 조치 분류 (모두 사용자 승인 전 · 미실행)
| 분류 | 대상 | 이유 · 조건 |
|---|---|---|
| A. 승인 시 바로 삭제 가능 | `F:\guguroute-space-safety-20261018-041356`, `F:\guguroute-cpu-review-backup-20261018-041722`(합 1,528,734,656 B) | 압축 전 안전 사본이다. E 원본 SHA 3/3 일치, 참조 0. 삭제 직전에 해시를 다시 확인한다 |
| B. 보존 · 이름만 정리 후보 | `F:\guguroute-offline-20261018-1155`(4.35 GB) | E junction/symlink 5개의 실체라 삭제하면 안 된다. F 규칙에 맞추려면 `F:\_work\backups\<이름>` 으로 옮기고 E 링크 5개를 다시 거는 승인 작업이 필요하다. 하위 `npu-rebuild\_rec\backup` 은 `CLEANUP_LATER.md` 1절 「npu_sm8735 복원 확인 뒤 삭제」 대상이고, 이 조건은 따로 확인해야 한다 |
| C. 보존(롤백 · 증거) | `F:\_work\projects\guguroute-x600-independent-20261018`(12.54 GB) | 고객 DB · 고객 도메인 인증서/키 사본이 들어 있는 독립 복구 VM 이다(**민감**, 내용은 출력하지 않았다). 원래 WSL 운영이 며칠 안정적인지 확인한 뒤 은퇴 여부를 결정한다. 은퇴하면 비밀이 든 사본까지 함께 지우거나 암호화 보관하도록 별도 승인을 받는다 |
| C'. C 와 함께 판단 | `F:\guguroute-qemu-cow-probe-20261018-135636`(0.52 GB) | C 의 실행 자원(portable QEMU · kernel)이다. 원 세션이 「기존 시험 폴더 이동 · 삭제 금지」를 정했다. 다만 부분 다운로드 `*.exe.download` 2개(261 MB)는 실행에 쓰이지 않으므로 C 와 별도로 지울 수 있는 후보다 |
- 삭제 · 이동은 `verified-root-aux-cleanup` 절차(정확한 절대 경로 허용 목록, reparse 미추적, 직전 해시 재확인)로만 한다. `F:\AGENTS.md` 의 「링크 따라 재귀 삭제 금지」에 따라 offline 폴더를 정리할 때도 E 링크를 먼저 처리한다.

## 범위 밖 · 미확인
- 10-18 세션이 WSL 에 걸었던 방화벽 fence(AnyBlock 2개 + LoopbackEnabled=False)가 지금 남아 있는지는 보지 않았다. 운영 health 200 이라 영향은 없어 보인다.
- 독립 VM 디스크 안의 DB 정합성(강제 종료 뒤)은 확인하지 않았다.

## 남긴 것
- 이 문서와 `handoff/index.md` 맨 위 1줄.
- scratch `x600-froot-readonly/`: `f3`~`f5.ps1`, 출력 `f2.run1.out` · `f3~f5.out`, 기록 조회 py 5개(모두 수십 KB 이하).
- x600 쓰기 0, 삭제 0.
