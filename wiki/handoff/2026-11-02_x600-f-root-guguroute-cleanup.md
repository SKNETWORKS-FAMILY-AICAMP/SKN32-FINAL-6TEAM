---
type: handoff
title: x600 F: 루트 guguroute 폴더 4개 정리 — 삭제 2 · 이관 1 · 보존 결정으로 중단 1 (2026-11-02)
description: 사용자 승인으로 x600 F:\ 루트 guguroute 폴더 4개를 실측 후 처리했다. 압축 전 안전 사본 2개는 E 원본 SHA 일치 뒤 삭제, E 링크 5개가 가리키던 offline 폴더는 F:\_work\backups 로 이관하고 링크를 다시 걸었다. qemu-cow-probe 는 보존 복구 VM 의 실행 자원이고 기존 명시 보존 결정이 있어 중단했다
status: draft
domain: travel
impl_scope: x600 F:/E: 파일 정리만. 서비스 · 코드 · DB 변경 0, 운영 중단 0
---

# x600 F: 루트 guguroute 폴더 4개 — 처리 결과

- 앞 문서: [10-29 실측](2026-10-29_x600-f-drive-guguroute-folders-inspected.md). 그 문서의 수치는 과거 값이다. 아래는 2026-11-02 19:00~19:11 KST 에 `ssh Yeon@192.168.0.8`(호스트 `x600_251214`, 기존 키 · BatchMode)로 새로 잰 값이다.
- 담당 세션: 10-18 생성 세션의 ID 는 지금도 복구할 수 없다(10-29 문서 근거 그대로). 10-29 조사 subagent `20261029_003450_7af370` 는 종료됐다. 둘 다 부모 `20261027_205452_5fbd35ab` 가 위임했고, 이번 처리도 그 부모의 subagent `20261102_185857_dcecf9` 가 맡았다. 같은 시간대에 x600 을 쓴 다른 세션은 myapp 프로필 오라클 리포트 세션뿐이다. 그 세션은 x600 을 SSH 경유지로만 쓰고 F: 폴더는 건드리지 않는다.

## 실측 (19:02 KST, 처리 전)
F:\ 루트에서 이름에 gugu 가 들어간 폴더는 정확히 **4개**였다. reparse 는 따라가지 않았다.

| 폴더 | 파일 | 바이트 | 내용 |
|---|---:|---:|---|
| `F:\guguroute-space-safety-20261018-041356` | 3 | 811,556,893 | E `dod28_ft` 의 `torch_cuda.dll` 를 압축하기 전에 만든 사본과 manifest |
| `F:\guguroute-cpu-review-backup-20261018-041722` | 4 | 717,177,763 | `torch_cpu.dll`(dod28_ft) · `libtorch_cpu.so`(jikimi_ft) 의 압축 전 사본과 승인 json |
| `F:\guguroute-offline-20261018-1155` | 21,646 | 4,352,058,217 | 10-18 사용자 지시로 E→F 보존 이동한 5그룹. E 쪽 junction 3개와 symlink 2개의 실체다 |
| `F:\guguroute-qemu-cow-probe-20261018-135636` | 549 | 515,897,273 | portable QEMU, 합성 디스크 COW/NBD 검사 기록, 고객 런타임 메타데이터 비공개 tar |

- 네 폴더 모두 ADS 는 0이고 SMB 공유는 기본 관리 공유만 있다. 서비스와 예약 작업의 참조는 0이다. 실행 중인 qemu · python · cloudflared · caddy 프로세스는 0이고, WSL fstab 과 docker mount 의 참조도 0이다.
- 삭제되지 않았던 이유는 다음과 같다. 10-29 조사는 읽기 전용이었다. A 분류(사본 2개)는 사용자 승인을 기다리는 상태로 남았다. offline 은 E 링크 5개의 실체였다. qemu 는 보존 복구 VM 이 실행 자원으로 고정한 폴더였다. 10-29 이후 이 폴더를 맡아 처리한 세션은 없었다.

## 처리 (19:10 KST, 실행 로그 `F:\_work\logs\guguroute-root-cleanup-20261102\run-20261102-191006.log`)
| 폴더 | 결과 | 보존 위치 · 근거 |
|---|---|---|
| space-safety | **삭제** | 삭제 직전에 E 원본 · F 사본 · manifest 의 SHA256 과 크기가 1/1 일치했다. `manifest.json` · `compression-result.json` 은 `F:\_work\backups\guguroute-root-cleanup-20261102\guguroute-space-safety-20261018-041356\` 에 해시를 확인하고 보존했다 |
| cpu-review-backup | **삭제** | 같은 방식으로 2/2 일치했다. `manifest.json` · `approved-compression-v30.json` 은 같은 보존 폴더 아래 `guguroute-cpu-review-backup-20261018-041722\` 에 있다 |
| offline | **F 루트에서 제거(이관)** | 같은 볼륨 안에서 이름만 바꿔 `F:\_work\backups\guguroute-offline-20261018-1155` 로 옮겼다(F:\AGENTS.md 의 backups 규칙). E 의 junction 3개와 symlink 2개는 새 경로로 다시 걸었다. 21,646파일, 4,352,058,217 B 는 이동 전후 SHA256 이 21,646/21,646 일치했다. 링크를 거쳐 센 파일 수는 313/19,331/1,997 이고, zip 2개는 링크 경유 SHA 가 직접 SHA 와 같다 |
| qemu-cow-probe | **중단 · 그대로 둠** | 아래 「남은 것」 참고. 파일 549개, 515,897,273 B 는 처리 전과 같다 |

- `F:\_work\storage-layout.json` 에 대응 3줄을 추가했다(mappings 29→32, JSON 파싱 확인). 원본은 `...\guguroute-root-cleanup-20261102\storage-layout.json.before-20261102`(5,792 B, SHA `E8120013…DF17`)에 있다.
- F: 여유는 124,125,229,056 B 에서 125,650,436,096 B 로 늘었다(19:10:55, +1,525,207,040 B). 삭제한 사본은 1,528,731,345 B 였다. 차이는 그 사이 다른 쓰기와 보존 json · 매니페스트 몫이다. E: 여유 97,606,230,016 B 는 변하지 않았다.
- 처리 뒤 F:\ 루트에 남은 guguroute 폴더는 `guguroute-qemu-cow-probe-20261018-135636` 1개다. 공개 `/health` 는 200 이었다.

## 남은 것 — qemu-cow-probe (해결 전 삭제 · 이동 금지)
- `F:\_work\projects\guguroute-x600-independent-20261018`(보존 중인 독립 복구 VM)의 감독기와 가드가 이 폴더를 절대경로 `LAB=Path('F:/guguroute-qemu-cow-probe-20261018-135636')` 로 고정했다. 해당 파일은 `preserved_independent_service_supervisor_v2.py` 와 `runtime-independent-v2/*` 등이고, 실행 파일 허용 목록도 이 경로에 묶여 있다. `runtime-plan/prepare_runtime_private.py` 는 이 폴더 안의 `customer-runtime-metadata-private.tar.gz` 를 읽는다. 이 폴더를 지우거나 옮기면 복구 VM 을 다시 띄울 수 없다.
- 10-18 복구 계약(`delivery/x600-preserved-boot-recovery.md`)에는 두 결정이 있다. 26행은 「백업·증거·실패한 시험 파일은 삭제하지 않는다」, 109행은 「기존 시험 폴더는 이동/삭제하지 않는다」이다. 지시대로 해결 전에는 중단했다.
- 해결하려면 둘 중 하나가 필요하다. (1) 복구 VM(C 분류, 12.54 GB, 고객 DB 와 인증서 사본 포함)의 은퇴를 결정하고, 그 VM 과 함께 이 폴더를 삭제하거나 암호화 보관한다. (2) VM 을 계속 보존한다면 이 폴더를 `F:\_work\projects\` 아래로 옮기고 VM 스크립트의 절대경로와 해시 계약을 새 경로로 고치는 별도 작업을 승인한다. 부분 다운로드 `*.exe.download` 2개(261,010,808 B)는 실행에 쓰이지 않지만, 서명 만료 증거 기록과 이어져 있어 함께 판단한다.

## 남긴 것
- x600: `F:\_work\backups\guguroute-root-cleanup-20261102\`(json 4개, storage-layout 원본, `offline-relocated-manifest-sha256.tsv` 21,646행 SHA `C1FF7AB7…2078`), `F:\_work\logs\guguroute-root-cleanup-20261102\`.
- 이 PC: `%LOCALAPPDATA%/hermes/profiles/guguroute/backups/x600-froot-guguroute-cleanup-20261102/`. 실행/조회 스크립트와 출력, 이동 전후 상대경로 SHA256 매니페스트 2개, `MANIFEST.sha256.tsv` 가 있다. 파일명에 자격 정보 이름이 섞여 있어 매니페스트는 git 밖에만 둔다. scratch 원본은 `cache/scratch/x600-froot-cleanup-20261102/` 에 있다.
- 이 문서와 `handoff/index.md` 맨 위 1줄. 코드 · 커밋 · 푸시는 0이다.
