---
type: report
title: C: 8차 하드링크 독립 읽기 전용 검토 — 116개·5,616,292,684 B 내용 일치, 보존 지정 경로 18개 inode 공유는 사용자·소유자 결정 필요
description: 8차 정리의 하드링크 116개와 ETL 삭제 210개를 읽기 전용으로 다시 확인했다. 매니페스트, 해시, 합계, 동일 inode, 실행 중 변경, 프로젝트 보호를 점검했다. 바이트 손실과 프로젝트 보호 위반은 찾지 못했다. 다만 보존 지정 경로와 영구 백업이 작업 사본과 같은 inode를 공유한다. 그래서 그 경로들은 독립 보존본이 아니게 됐다. 복원·삭제·설정 변경은 하지 않았다
status: done
domain: travel
impl_scope: 읽기 전용 검토. 대상 파일·링크·속성·설정은 바꾸지 않았다. 쓴 것은 이 보고서, 증거 폴더 2026-10-31_disk-round8-review, 인계 문서 1개, 인계 색인 1줄, 그리고 guguroute scratch의 검토 작업 폴더 disk-r8-review-20261031(약 1MB)뿐이다
---

# C: 8차 하드링크 독립 검토 (2026-10-31 03:53–04:20)

대상 보고서: [8차](2026-10-31_c-drive-400gb-cleanup-round8.md). 단위는 GB=10⁹ B다. **실측**은 이 세션에서 직접 센 값이고, **추정**은 실험하지 않은 동작에 대한 판단이다.

## 결론

| 점검 | 결과 | 구분 |
|---|---|---|
| 116개 매니페스트·해시 | 116/116 경로가 있다. inode는 유지본 및 기록된 `keeper_ino`와 같고 크기도 같다. 임시 `.r8link`는 0개다. inode 24개(2,342,938,944 B)를 전체 sha256으로 다시 계산했고, **24/24가 기록과 일치**했다 | 실측 |
| 합계 | 링크 116개는 5,616,292,684 B다. 실패 1개는 110,265,344 B다(원본 그대로, nlink 1). 둘을 더하면 계획 5,726,558,028 B와 같다. ETL은 210개, 1,695,547,392 B이며 지금 남은 파일은 0개다. 회수량 합계는 링크 5,619,822,592 B와 ETL 1,695,539,200 B를 더한 **7,315,361,792 B**로, 보고서 값과 같다 | 실측 |
| 증거 사본 | wiki 증거 12개가 backups 사본과 바이트 단위로 같다. `scripts-r8_recent.py` 1개는 backups에 사본이 없다. `dedupe-result.json`의 sha256은 `1d6c4f7f…0461`이다 | 실측 |
| 링크 수 | inode 24개 모두에서 nlink가 알려진 경로 수와 같다. 매니페스트 밖의 다른 링크는 없다 | 실측 |
| 실행 중 변경 | 관련된 23개 이름(관련 트리 20개, `_preserved`, `scratch-candidates-20261029d`, `disk-round8`)을 참조하는 프로세스는 0/209개였다. 트리 20개 모두 24시간 안에 바뀐 파일이 0개였고, 가장 최근 쓰기도 29.8시간 전이었다. 실행 스크립트는 교체 직전에 크기·mtime·nlink를 다시 대조하고 양쪽 전체 해시를 다시 계산했다. 해시와 교체 사이의 몇 초 동안 생긴 쓰기는 막지 못한다. 그런 흔적은 없다 | 실측과 코드 검토 |
| 프로젝트 보호 (AGENTS.md) | 117개 항목 중 `C:/_proj/final_workspace`를 대상이나 유지본으로 쓴 항목은 **0개**다(`final_project_cs` 문자열 일치 1건은 scratch 안의 경로라 오탐이다). final_workspace에 쓴 것은 보고서, 증거, 색인 1줄뿐이다. 색인은 `handoff-index.before.md`와 비교해 그 1줄과 빈 줄만 늘어난 것을 확인했다. 다른 Hermes 프로필에는 쓰지 않았다. NOTICE는 `C:/Users/kcxsz/frog-npu-dev/_coord/`에 1개 썼다. 이 폴더는 NPU 소유자의 조율 폴더이고 프로필이 아니다 | 실측 |
| **독립 보존본** | **위험이 있다.** 보존 위치(`_preserved`, `backups`, 보존 지정 scratch 트리)를 포함하는 inode가 **18개, 938,329,044 B**다. 이 inode들은 이제 물리 사본이 하나뿐이다. 아래 표를 본다 | 실측(공유 여부), 추정(손상 경로) |

**바이트 손실과 프로젝트 보호 위반은 찾지 못했다.** 다만 8차 보고서의 표현은 범위를 좁게 적었다. 보고서는 `_preserved`와 backups를 유지본으로만 썼다고 적었는데, 그 문장은 사실이다. 그러나 **보존 지정 scratch 트리(`_archive_20261027`, `finalspace_preservation`, Hi 감사 보존물 `place-quality-20261027`) 안의 파일 17개도 링크 대상이었다.** 6차 보고서는 이 트리들을 「그대로 지킨다」고 적었다. 내용은 같다. 그러나 파일 정체(inode), mtime, 읽기 전용 속성이 바뀌었고, 작업 사본과 저장 공간을 공유하게 됐다.

## 보존본이 공유하는 inode (실측)

| 보존 경로 | 함께 묶인 경로 | 크기 | 의미 |
|---|---|---:|---|
| `C:/Users/kcxsz/_preserved/finalspace_20261028/finalspace_full_20261028.bundle` | `guguroute/cache/scratch/finalspace_preservation/finalspace_full_20261028.bundle` (nlink 2) | 729,960,395 | 「영구 사본」과 scratch 보존본, 두 독립 보존본이 물리 사본 1개가 됐다. 읽기 전용이 아니다. `SHA256SUMS.txt` 기준 내용은 지금 일치한다 |
| `guguroute/backups/scratch-candidates-20261029d/files/...` 8개: `gh.exe`, `primp.pyd`, mingit `msys-2.0/crypto-3/sqlite3-0/iconv-2.dll`, `sh.exe`, `awk.exe` | scratch `st4f711-backend-20261029-v1/{gh.exe, deps/primp/primp.pyd}`, `date_risk_independent_review_01/mingit/usr/bin/*` | 67,341,823 | 4차의 「영구 보존」이 작업 도구 사본과 공유된다. 도구를 덮어쓰기 방식으로 다시 풀면 백업도 함께 바뀐다(추정) |
| `_archive_20261027/chat-stream-20261026-043045/{v9_base,v9_source}/unpushed.bundle` | 서로 (nlink 2) | 41,046,748 | 보존 bundle 두 개가 물리 사본 1개가 됐다 |
| `_archive_20261027/fixture-clock-fix-*` 7개, `place-quality-20261027/program` 7개 (`.gguf`, `.zip`, `.tar.gz`) | 14-링크 묶음. `allpast-hotfix-20261025-2005`의 체크아웃 5개(허브), `latest-serving-6c345-20261025/source-v2·v3`(롤백 원본), `modelq-G-20261027/rm`(미커밋 변경 109개), `schedule-explain-impl-20261029/wt`, `remaining_dod_validation`, `local_admin_3300_v2` 등 | 97,488,447 (inode 7개) | 활성 작업 사본에서 제자리 쓰기가 일어나면 보존 사본 2벌도 함께 바뀐다(추정) |
| `finalspace_preservation/restore.git/objects/pack/pack-42e735….pack` | `bundle11-20261027/iso.git`, `unmerged-audit-20261027/iso.git` (nlink 3) | 2,491,631 | Git pack이다. Git은 pack을 고쳐 쓰지 않고 새로 만든다(추정) |

기타 메타데이터 변화(실측):
- 대상 116개 중 111개의 mtime이 원래 값에서 유지본의 mtime으로 바뀌었다. 원래 값은 `dedupe-result.json`의 `target_mtime`에 남아 있다.
- 원래 읽기 전용이던 대상 6개 중 2개가 읽기 전용이 아니게 됐다. `final_integration_preparation/repo/.git/objects/pack/pack-601a49c9….{pack,idx}`이며, 읽기 전용이 아닌 유지본과 속성을 공유하기 때문이다.
- Git 인덱스 영향을 확인했다. `place-quality-20261027/program`의 `status`는 0줄이었다. `modelq-G-20261027/rm`은 109줄로, 이미 기록된 미커밋 변경 수와 같다. 두 검사 모두 `--no-optional-locks`로 실행했다. 나머지 checkout은 300초 시간 초과로 **확인하지 못했다**.
- 별도로 발견한 것이 있다(8차와 무관): `latest-serving-6c345-20261025/source-v2`의 `.git/objects/info/alternates`는 없어진 `team12-history-integration-20261025-135501/candidate/.git/objects`를 가리킨다. 그래서 `bad object HEAD`가 난다. 8차는 이 트리의 작업 트리 파일만 링크했다.

## 앞으로 바뀔 때의 공유 영향 (추정, 실험하지 않음)

- **안전한 쓰기**: 경로를 삭제하거나 새 파일을 만든 뒤 이름을 바꾸는 쓰기다. Git checkout·pack 생성·gc, `git bundle create`(lock 뒤 이름 변경), pip·npm의 제거 후 설치가 여기에 든다. 해당 경로만 분리되고 다른 링크는 그대로 남는다.
- **전파되는 쓰기**: 열린 파일을 잘라내고 다시 쓰는 경우다. PowerShell `Set-Content`/`Out-File`/`>`, Python `open(p,'wb')`, `Expand-Archive -Force`, `copy /Y`, robocopy 덮어쓰기, 압축 해제 도구의 덮어쓰기가 여기에 든다. 이런 쓰기는 **같은 inode의 모든 경로**를 바꾼다. 보존 경로도 예외가 아니다.
- 속성 변경(읽기 전용)과 mtime 갱신도 모든 링크에 전파된다.
- 링크 하나를 지워도 다른 경로의 바이트는 남는다. 그래서 scratch가 만료되어도 `_preserved`나 backups 쪽은 안전하다.
- C: 디스크가 하나뿐이므로 디스크 고장에 대한 중복은 원래 없었다. 이번에 사라진 것은 **잘못된 제자리 쓰기와 섹터 손상에 대한 사본 간 독립성**이다.

## 복원·승인 경계 (실행하지 않음)

| 선택지 | 대상 | 디스크 비용 | 승인 |
|---|---|---:|---|
| A. 보존본 링크 분리 | `_preserved` bundle 1개 (scratch 쪽 경로를 복사한 뒤 이름 변경) | +729,960,395 | 사용자 |
| B. 영구 백업 링크 분리 | backups `scratch-candidates-20261029d/files` 8개 | +67,341,823 | 사용자 또는 guguroute 백업 소유자 |
| C. 보존 지정 scratch 트리 분리 | `_archive_20261027` 8개 138,535,195 B와 `place-quality` 7개 97,488,447 B | 최대 +236,023,642 | 사용자 또는 보존 지정자 |
| D. 비용 없는 완화 | 보존 경로와 공유되는 inode에 읽기 전용 속성 지정. 모든 링크에 전파된다 | 0 | 사용자(보존 파일 속성 변경) |
| E. 원래 독립 상태로 전부 복원 | 116개 | +5,616,292,684 | 사용자 |

- 분리 절차는 backups `README.md`에 있다: 일반 복사로 `<path>.tmp`를 만든 뒤 원래 경로 위로 rename한다. 실행 전에 inode와 sha256을 다시 확인한다.
- **mtime과 읽기 전용 속성 복원**은 `dedupe-result.json`의 `target_mtime`과 `target_readonly`로 할 수 있다. 다만 이 값들도 분리 뒤에만 경로별로 따로 지정된다.

## 추가 비활성·재생성 후보 (삭제하지 않음)

| 후보 | 크기 (실측 논리 B) | 판단 |
|---|---:|---|
| 사용자 Temp `playwright_chromiumdev_profile-*` 23개 (24시간 넘은 것 22개) | 330.0 MB | 브라우저 테스트 프로필이다. 재생성 가능하다고 추정한다. 소유 세션과 실행 중 브라우저는 확인하지 않았다 |
| 사용자 Temp `hermes_agy_*` 19개 (모두 146시간 이상 유휴) | 282.8 MB | Hermes 임시 폴더로 추정한다. 어느 프로필 것인지 확인하지 않았다 |
| 사용자 Temp `agent-browser-chrome-*` 24개 (24시간 넘은 것 23개) | 255.4 MB (유휴 238.2) | 1개는 지금 쓰는 중이다. 나머지 소유자는 확인하지 않았다 |
| Temp `WinGet` (70시간 유휴) | 116 MB | 설치 캐시로 추정한다 |
| guguroute scratch의 72시간 넘은 유휴 항목 717개 | 45.2 GB (하드링크를 중복으로 센 논리값) | 보존 지정, 롤백 원본, 미커밋 트리, HOLD가 섞여 있다. 이전 회차가 재현 가능한 부분을 이미 정리했다. 항목별 판정 없이는 후보가 아니다 |
| 8차가 제외한 제자리 쓰기 형식 중복 | 약 18 GB (8차 추정) | 하드링크로 묶지 않는 것이 맞다. 해당 체크아웃을 반납할 때 함께 결정한다 |

- Temp에서 정리할 수 있는 양은 많아야 약 0.95GB다(추정). 192GB 부족분에는 의미 있는 크기가 아니다. 큰 덩어리는 8차 표의 사용자·소유자 결정 항목이다.
- 이 세션의 디스크 사용량: 검토 작업 폴더 `guguroute/cache/scratch/disk-r8-review-20261031`은 1,035,997 B다. 증거 사본은 이 보고서 증거 폴더에 있다. 정리 바이트는 0이다(읽기 전용 범위).
- 측정 시점의 C: 여유: 207,942,475,776 B (207.94GB). 400GB 대비 51.99%다.

## 증거

[review evidence](../evidence/2026-10-31_disk-round8-review/) 폴더:
- `live-verify-hash.json`: 116개 실측값과 inode 24개의 재해시
- `review-summary.json`: 보존 공유, 합계, ETL, 실패 항목
- `inv-summary.txt`: 트리 활동과 Temp 후보
- 스크립트: `a3.py`, `a5.py`, `inv.py`, `procs.ps1`
