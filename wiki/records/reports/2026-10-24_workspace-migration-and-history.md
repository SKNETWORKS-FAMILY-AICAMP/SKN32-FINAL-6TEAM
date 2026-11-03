---
type: report
title: 작업공간 복사 검증과 D 드라이브 인계자료 조사
description: 복사 당시 경로·크기 비교와 대화자료 조사 범위 및 현재 문서 반영 근거를 구분합니다
status: draft
tags: [documentation, testing]
---

# 작업공간 복사 검증과 인계자료 조사

## 체크포인트 1 — 독립 비교

[실측 2026-10-24 19:40 KST] 문서 수정 전 `D:/Documents/final_workspace` → `C:/_proj/final_workspace` 양쪽 파일 552,857개, 합계 44,939,093,521바이트가 일치했습니다. 상대경로 누락·추가·크기 차이·디렉터리 열거 오류는 각각 0건입니다. 개수 일치만으로 완전 복사를 확정한 이전 설명은 부정확합니다. 전체 바이트 동일성 검증은 별도입니다.

180초 한도 최초 SHA-256 검사에서 9,272쌍이 일치했고 불일치는 없었습니다. 긴 경로 이미지 캐시 18개에서 일반 Win32 경로 읽기 오류가 발생했고, 당시에는 후속 읽기 검사 완료 결과를 확보하지 못했습니다(아래 후속 완료 검토로 해소). 이 수치는 최종 해시 범위가 아닙니다.

## 복구 시점 검증 한계

[실측: 기존 JSON] 해시는 9,272/552,857쌍(1.6771%) 일치, 불일치 0·읽기 오류 18·미검증 543,585개입니다. 이전 child의 full readcheck는 420초 timeout으로 완료 증거를 확보하지 못했습니다. 이번에는 전체 해시·대규모 탐색을 재실행하지 않았습니다. 상태 조회에서 기존 `migration_readcheck_20261024.py` Python PID 20324가 남아 있음을 확인했고 종료하지 않았습니다. 이 프로세스 존재만으로 진행률·완료·성공을 확정하지 않습니다.

이번 작업은 문서만 수정했습니다. 추가 복사·D 원본 삭제/수정·코드/앱/서비스 변경·raw chats 공개 복사는 하지 않았습니다. 위 메타데이터 수치는 문서 변경 전 스냅샷이며 문서 변경 뒤 양쪽 동일성을 주장하지 않습니다. 이 문단은 timeout 당시 관측 기록입니다. 긴 경로 읽기 오류 18건은 아래 완료 결과로 해소됐으며, 전체 내용 동일성은 여전히 미확보입니다.

## 후속 완료 검토

[기존 완료 JSON 직접 검토] `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/migration-readcheck-20261024.json`은 2026-10-24 **19:52:43 KST** 완료를 기록합니다. extended-length 절대경로로 양측 **open + 첫 바이트 읽기 552,857/552,857쌍 = 100% 성공**, 읽기 오류 0건입니다. 최초 긴 경로 18건의 읽기 오류는 해소됐습니다. 이는 전체 payload 읽기·전체 바이트 동일성 검증이 아닙니다.

우선 SHA-256은 eligible 1,706개 중 completed **1,706/1,706 = 100%**, match **1,705/1,706 = 99.9414%**, mismatch 1개(`wiki/index.md`), 해시 오류 0건입니다. `changed_since_initial_manifest`도 destination의 같은 파일 1개입니다. 기존 child transcript `cache/delegation/live/deleg_9036e03f/task-0.log`의 19:41:58 수정 요청·19:42:01 성공 기록과 scratch 백업 `migration-wiki-backup-20261024/wiki/index.md` → `resume-docs/wiki/index.md` 비교에서 복사 검증·자료 조사 안내 단락 추가를 확인했습니다. 따라서 이 차이는 복사 누락 증거가 아니라 의도된 목적지 문서 수정입니다.

이번 검토는 기존 완료 근거만 사용했고 새 해시·읽기 검사를 실행하지 않았습니다. 최초 9,272쌍과 우선 해시 범위는 중복 가능하므로 합산하지 않습니다. **전체 해시 미실시·raw chats 전체 미확보**는 유지합니다. root/cs index는 추가 수정하지 않았고 D 원본은 변경·삭제하지 않았습니다. 이번 보고서·인계·root/cs log 4개 수정 직전 백업은 scratch의 `migration-wiki-backup-20261024/final-review/`에 보존했습니다.

## 기존 검사 JSON과 백업 정확한 위치

공통 디렉터리: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/`

- `migration-compare-20261024.json`: 상대경로·크기·제한 시간 해시 집계.
- `migration-compare-20261024.manifest.json`: 양쪽 파일 메타데이터 각 552,857개.
- `migration-compare-20261024.hashes.json`: 완료 해시 9,272쌍.
- `d-drive-conversation-candidates-20261024.json`: 이름 후보·조사 제외·열거 오류 인벤토리.
- `migration-wiki-backup-20261024/`: 이전 백업 유지. `resume-docs/`에 이번 수정 직전 문서 6개 별도 보존.

위 파일은 로컬 조사 근거이며 공개 wiki에 원본 경로 목록/대화 전문을 복제하지 않습니다.

## 대화자료 inventory 집계와 미확보

[실측: 기존 inventory JSON 재집계] 디렉터리 203,425개 방문·파일 1,517,435개 관찰, 이름 후보 116,801개(파일 106,255·디렉터리 10,546)입니다. `content_scanned: false`이므로 raw chats 전체 본문은 미확보입니다. 후보에는 코드·평가 JSONL·복제본이 섞여 대화/세션 수나 확보율이 아닙니다. 전체 대화 분모는 모릅니다.

- 조사 제외 5,209개: 재생성/무관 대량 트리 5,208개·reparse-point 미추적 1개. 제외 트리 내부 파일 수는 모릅니다.
- 오류 25개: 접근 거부 WinError 5 4개·잘못된 인자 Errno 22 12개·경로 없음 WinError 3 9개. 모두 접근 거부로 합치지 않습니다.
- 이번 선별 본문 열람은 아래 outputs 4개와 최신 인계 원문 3개입니다. 전체 채팅 정독/내용 검색은 하지 않았습니다.

## 2026-10-10 Codex outputs 4개 — 과거 기록/제안

[실측: 실제 파일 열람] 원본 디렉터리는 `D:/Documents/Codex/2026-10-10/db-x-llm/outputs/`입니다. 아래는 **10월 10일 당시 조사**이며 10월 24일 현재 코드·배포 현황이 아닙니다.

| 파일 | 내용과 한계 |
|---|---|
| `채팅_팀실행_검색실패_점검결과.txt` | 당시 웹 5경로의 담당 이름 기록과 Team.execute 실행이 달랐고 일부 공통 계산은 호출됨. 검색 notes가 화면 전달에서 소실되는 문제와 구조화 문맥 전달을 제안. 관련 79/79는 로컬 DB·모델/일부 외부자료 대역이며 계측 7개와 독립 합산 불가. 원격 조회 거절·실서버/휴대폰 미검증. 오늘 결함으로 단정하지 않음. |
| `team-execution-trace.json` | 모델 대역+실제 로컬 DB 범위에서 passed 7행(웹 5·활동 팀 직접 실행 대조 2). 계산 입구 호출 수가 추천 품질이나 모든 경로의 팀 실행을 증명하지 않음. |
| `context-forwarding-check.json` | 당시 새 root context 미전달(false), 기존 interpretation 전달(true), 이름 없는 좌표 입력에 name missing. 현재 계약과 전달 허용 목록 재확인이 필요. |
| `place-search-context-v1-draft.json` | `draft:true`·`example_only:true`. 검색 중심/목적지, 정상 0건/조회 실패, 판 번호와 선택을 구분하는 제안. 2030년 시각·좌표는 예시이며 현재 적용 계약·실제 고객 기록 아님. |

[cs context](../../../final_project_cs/wiki/context/index.md)·[Team 계약](../../../final_project_cs/wiki/teams/team-contract/index.md)과 대조할 후속 자료로만 연결합니다. 제안을 현 계약에 자동 편입하거나 과거 결함을 닫지 않습니다.

## 별도 D 작업공간 최신 인계 3개 — 충돌/후속 구분

[실측: 실제 원문 열람] `D:/Documents/파이널스페이스/wiki/handoff/index.md`의 최신 세 항목이 가리킨 아래 원문을 읽었습니다. 상대경로는 이 D 작업공간 기준입니다. C wiki의 기존 인계가 10월 13일 이전이라고 해서 D 변경이 C 코드에 자동 존재하는 것은 아닙니다.

| 원문 | 현재 wiki와의 관계·미완료 |
|---|---|
| `wiki/records/reports/2026-10-18_intake-risk-trip-date.md` | 먼 일정에 현재 경보를 붙이던 문제의 격리 수정. 24시간 밖은 문제 없음이 아니라 `unknown/too_early`; 신규4/4·기존17/17은 당시 기록. 두 매니저 원격·오라클 배포·실화면 미반영, 24시간 기준 사용자 확인 대기. **후속 참고**이지 C 수정/배포 완료 증거가 아님. |
| `wiki/records/reports/2026-10-18_plan-reading-redesign-session.md` | D-025의 E4B 이해·분류/코드 사실검사·담당연결 방향은 구 규칙 우선 읽기와 **방향 충돌 가능**. 원문은 두 role-manager 반영을 기록하지만 이번 원격 확인은 아님. develop·x600 배포·실제 고객 미확인, 읽기 실패 처리 두 결정 충돌·Winnow-E4B 2차 측정 미결. D-020 승인 경계는 유지한다고 기록. 현 제품 안내에 무조건 병합하지 않음. |
| `final_project_cs/wiki/records/reports/2026-10-16_6주차_발표_자체sLLM_산출물_사람검수모음_작업기록.md` | 「실제 사람이 쓴 고객 문장 시험 없음」의 **정정 근거**. 769 합성 문제와 별도 사용자 채팅·일부 직접 검수 구분. 사용자 질의 건수/검수 구간 미확정, 사람 검수 시트 0개 기입은 10월 16일 값. 발표·sLLM 묶음은 git 밖 당시 로컬 산출물이며 제출·배포 증거가 아님. |

이 자료의 원격·점수·운영 주장은 과거 기록으로 한정합니다. C의 현재 결정·계약·코드·환경 실행과 대조하는 검토는 후속 범위이며, 원문 코드·링크 전체 검사나 현재 서비스 확인을 수행한 것은 아닙니다.

## 관계

- [현재 wiki](../../index.md) — 현재 확정 사양을 우선합니다.
- [인계 목차](../../handoff/index.md) — 다음 세션의 시작점입니다.
