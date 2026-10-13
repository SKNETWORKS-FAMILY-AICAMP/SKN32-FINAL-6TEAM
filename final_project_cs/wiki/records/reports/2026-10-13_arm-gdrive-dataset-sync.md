# 구글 드라이브 → 오라클 ARM 서버 자료 폴더 자동 맞추기 (Claude, 2026-10-13)

사용자 지시: 「구글 드라이브 공유 폴더(dataset)에 올라오는 폴더·파일 경로 그대로 오라클 서버에 반영되게」.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 오라클 서버에 rclone 설치 (Ubuntu 저장소 1.60.1) | 끝 | 1/1 |
| 동기화 스크립트 · 10분 예약 작성 | 끝 | 3/3 파일 |
| 서버 안 시험(드라이브 대신 시험 폴더) | 통과 | 6/6 = 100% |
| 오라클 서버에 설치 · 예약 켜기 | 끝 | 1/1 |
| 구글 로그인 한 번(사람이 PC 에서) | 대기 | 0/1 |
| 실제 드라이브에서 받아 보기 | 안 함(로그인 뒤) | 0/1 |

## 무엇이 어디로 가나

- 드라이브 `dataset` 폴더 안의 경로가 그대로 서버 `/home/ubuntu/tripilot-serving/datasets/` 아래로 간다. 예: 드라이브 `dataset/mobility/processed/a.json` → 서버 `.../datasets/mobility/processed/a.json`.
- 10분마다 확인한다(`tripilot-arm-dataset-sync.timer`). 바뀐 파일만 받는다.
- 드라이브에서 지우거나 덮어쓴 파일은 서버에서 지우지 않고 `/home/ubuntu/tripilot-serving/_backup/datasets-sync/<시각>/` 로 옮긴다. 백업은 자동으로 지우지 않으므로 쌓인다.
- 앱(cs 프로젝트 서버 컨테이너)은 이 폴더를 읽지 않는다. 앱이 쓰는 이동 자료 자리(`control/.env` 의 `MOBILITY_DIR=.../mobility/processed`)는 바꾸지 않았다. 드라이브 자료를 앱이 쓰게 하려면 `MOBILITY_DIR` 을 `.../datasets/<드라이브 안 경로>` 로 바꾸고 앱을 다시 띄워야 한다 — 사용자 결정 전이라 하지 않았다.

## 안전장치

| 상황 | 동작 | 시험 |
|---|---|---|
| 로그인 정보 없음 | 아무것도 안 하고 `waiting_login` | 통과 · 실서버 현재 상태 |
| 드라이브가 비어 보이는데 서버에 파일 있음(로그인 만료·권한 회수) | 지우지 않고 `skipped_empty_remote` | 통과 |
| 받은 뒤 남는 공간 < 12GiB | 받지 않고 `skipped_disk` | 통과 |
| 파일 추가 · 수정 · 삭제 | 경로 그대로 반영, 옛 판은 백업 | 통과 |
| 이전 회차 실행 중 | 이번 회차 건너뜀(flock) | 시험 안 함 |

★**공간 한도**: 오라클 서버 디스크는 2026-10-13 측정 96GB 중 15GB 남음이다. 앱 자동 배포가 빌드에 10GiB 여유를 요구해서 12GiB 를 남기도록 했다. **그래서 지금 받을 수 있는 자료는 약 3GiB 까지다.** 이 PC 의 `datasets/travel`(9.6GB) 같은 큰 자료는 공간을 비우기 전에는 받지 않는다. 한도는 `/etc/tripilot-arm-dataset-sync.env` 에 `MIN_FREE_GIB=` 로 바꿀 수 있다.

## 사람이 한 번 할 일 — 구글 로그인

무료다. 만드는 것은 없다(구글 클라우드 계정·키 생성 불필요). 약 2분 걸린다. **이 PC 앞에서** 해야 한다(브라우저 로그인).

| 단계 | 하는 일 | 끝나면 보이는 것 |
|---|---|---|
| 1 | PowerShell 에서 `powershell -ExecutionPolicy Bypass -File final_project_cs\deploy\arm\gdrive_login.ps1` (작업 폴더 `final_workspace` 에서) | rclone 이 없으면 winget 설치 화면이 지나간다 |
| 2 | 브라우저가 열리면 `dataset` 폴더를 볼 수 있는 구글 계정을 고른다 | 「rclone 이(가) Google 계정에 액세스하려고 합니다」 화면 |
| 3 | **허용** 을 누른다(권한은 「Google Drive 파일 보기」 읽기 전용) | 브라우저에 「Success!」, PowerShell 에 「완료: 오라클 서버로 로그인 정보를 보냈고…」 |
| 4 | 확인: `ssh dr-a2 cat /home/ubuntu/tripilot-serving/dataset-sync.json` | `"result": "ok"` |

| 막힐 때 | 원인 | 고치는 법 |
|---|---|---|
| `rclone 설치 뒤에도 명령을 못 찾았습니다` | 새 PATH 가 이 창에 안 들어옴 | PowerShell 창을 새로 열고 다시 실행 |
| `로그인이 끝나지 않았습니다` | 브라우저에서 허용 전에 창을 닫음 | 다시 실행 |
| 결과가 `remote_error` · `directory not found` | 로그인한 계정이 그 폴더를 못 봄 | 폴더를 볼 수 있는 계정으로 다시 실행 |
| 결과가 `skipped_disk` | 오라클 서버 공간 부족 | 공간을 비우거나 `MIN_FREE_GIB` 조정(앱 빌드 10GiB 를 생각해서) |

로그인 정보는 이 PC 임시 파일 → 오라클 서버 `control/rclone-gdrive.conf`(권한 600)로 바로 가고, PC 사본은 지운다. 화면·저장소에 남지 않는다. 폴더 ID 는 오라클 서버 `/etc/tripilot-arm-dataset-sync.env`(권한 600)에만 있다.

## 파일

- [dataset_sync.sh](../../../deploy/arm/dataset_sync.sh) — 서버 `/usr/local/lib/tripilot/dataset_sync.sh` 로 설치
- [tripilot-arm-dataset-sync.service](../../../deploy/arm/tripilot-arm-dataset-sync.service) · [.timer](../../../deploy/arm/tripilot-arm-dataset-sync.timer) — `/etc/systemd/system/`
- [gdrive_login.ps1](../../../deploy/arm/gdrive_login.ps1) — 사람이 PC 에서 한 번 실행

## 확인 범위

mock 서버 시험(화면 반응): 해당 없음.
실서버 확인(서버 응답): 반쯤 했음 — 오라클 서버에서 스크립트를 실제로 돌렸다(드라이브 대신 서버 안 시험 폴더를 원본으로 6가지). 실제 구글 드라이브 목록 읽기·받기는 로그인 전이라 **안 했다**. PC 로그인 스크립트는 문법 검사만 했고 실행은 안 했다. 2026-10-13 기준 드라이브 `dataset` 폴더는 비어 있었다(브라우저로 봄).
