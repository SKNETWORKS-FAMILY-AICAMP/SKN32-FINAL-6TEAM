---
type: handoff
title: x600 F: 드라이브 「guguroute 뭐시기」 폴더 읽기 전용 조사 — 접속 불가로 미완 (2026-10-28)
description: 사용자 정정(C:가 아니라 F:)에 따라 x600 F: 의 GuguRoute 관련 폴더를 조사하려 했으나 22:19~22:36 KST x600 이 네트워크에서 사라져 원격 확인 0. 로컬 기록으로 확인한 F: 쓰기 이력과 재개 절차를 남긴다
status: draft
domain: travel
impl_scope: 기록만. x600 · 코드 · 서비스 · 세션 DB 변경 0, 삭제 0
---

# x600 F: 「guguroute 뭐시기」 폴더 조사 — 미완(접속 불가)

- 요청: 2026-10-28 18:58 「x600 c드라이브에 … 구구루트 뭐시기」 → 22:18 정정 「x600 의 f 드라이브라고」.
- 결론: **F: 를 한 번도 열지 못했다.** 폴더 이름 · 크기 · 생성 시각 · 생성자는 **미확인**이다. 삭제 · 정리 가능 여부도 판단하지 않았다(판단 근거 없음).

## 접속 실패 (실측, 이 PC 192.168.0.15 Wi-Fi 기준)
| 시각(KST) | 확인 | 결과 |
|---|---|---|
| 22:19 · 22:29 · 22:33 · 22:36 | `ssh -i ~/.ssh/id_ed25519_x600 Yeon@192.168.0.8` (BatchMode) | port 22 `Connection timed out` 4/4 |
| 22:2x | `ping 192.168.0.8` | 「대상 호스트에 연결할 수 없음」(192.168.0.15 응답) · ARP 표에 0.8 없음 |
| 22:29 · 22:33 · 22:36 | `https://tripilot.devroro.click/health` | HTTP **523**(Cloudflare origin unreachable) 3/3 |
| 22:3x | 10.8.0.2~4(wg0 대역 추측) SSH | timeout — x600 의 WireGuard 주소는 문서에 없음 |

- 같은 날 19:11 에는 같은 경로로 접속됐다(앞선 C: 조사, `F:\dod28_ft absent` · `F:\bench absent` · F: 여유 124,255,064,064 B). 그 뒤 22:19 이전 어느 시점에 x600 이 꺼졌거나 네트워크가 끊겼다. 원인(전원 · 절전 · 재부팅 · 공유기)은 미확인. **운영 공개 서버도 같이 내려가 있다(523).**

## 로컬 기록으로 확인한 「우리 작업이 x600 F: 에 쓴 것」
`state.db` `mode=ro` 로 x600 대상 SSH/SCP 명령 전체를 훑었다(비밀 가림).
- F: 경로를 직접 쓰는 SSH · SCP 명령: **0건**. SCP 대상은 `C:/Users/Yeon/Documents/ollama-modelfile-20261026/` 2건뿐이다.
- 간접 쓰기 1건: 10-26 08:32 세션 `20261026_082118_88a41b` 가 x600 에서 `ollama create tripilot-pointer:e4b-ft` 를 실행했다. x600 사용자 환경변수 `OLLAMA_MODELS=F:\_work\models\ollama`(보고서 `final_project_cs/wiki/records/reports/2026-10-26_x600_채팅해석_유료넘김_원인.md`)이므로 manifest/blob 은 `F:\_work\models\ollama` 아래에 생긴다. 이름은 `tripilot-…`이고 「guguroute」가 아니다. 실제 파일은 미확인.
- 이 밖에 `guguroute` 이름이 x600 원격 경로로 쓰인 기록은 찾지 못했다(이 프로필 기록 범위 한정 — 다른 프로필 · Codex · x600 에서 직접 실행한 세션은 범위 밖).
- 가설(미검증): 이 PC 스킬 기록에 「네이티브 프로그램에 MSYS `/c/...` 경로를 주면 현재 드라이브에 `\c\Users\...` 폴더가 생긴다」는 사례가 있다. x600 에서 cwd 가 F: 인 프로세스가 같은 실수를 했다면 `F:\c\Users\kcxsz\...\guguroute\...` 형태가 생길 수 있다. 접속 후 `F:\c` 존재로 바로 확인할 것.

## 재개 절차 (x600 복귀 후, 읽기 전용)
1. 스크립트: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/x600-froot-readonly/f2.ps1` — F: 볼륨 · 루트 전 항목(속성 · 크기 · 생성/수정 시각 · 소유자) · `F:\_work` · 깊이 3 이내 `gugu|route|tripilot|acop|hermes|jikimi` 폴더.
   실행: `ssh -i ~/.ssh/id_ed25519_x600 -o BatchMode=yes Yeon@192.168.0.8 "powershell -NoProfile -Command -" < f2.ps1` (`-EncodedCommand` 는 승인 대기에 걸린다).
2. 찾은 폴더마다: 파일 수 · 바이트 · 가장 오래된/새 파일, 대표 파일 앞부분, `Get-CimInstance Win32_Process` 명령줄 · 서비스 · 예약 작업 · `wsl -u root -e docker inspect` mounts 에 경로가 있는지, 생성 시각을 `state.db` 의 x600 명령 시각과 대조.
3. 삭제 · 이동은 사용자 승인 뒤 `verified-root-aux-cleanup` 절차로만. Ollama 모델 폴더(`F:\_work\models\ollama`)는 운영 로컬 모델이 쓰므로 정리 대상에서 뺀다.

## 디스크 · 변경
- 새로 만든 것: scratch `x600-froot-readonly/`(ps1 2 · 기록 조회 py 6 · 조회 결과 txt 3, 모두 수 KB). 이 문서 1개와 `handoff/index.md` 맨 위 1줄.
- x600 쓰기 · 삭제 0, 원본 코드 변경 0.
