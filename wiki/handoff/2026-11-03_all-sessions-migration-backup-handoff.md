---
type: handoff
title: 모든 Hermes 세션 이관 패키지 — default·guguroute·myapp 세션 1,146개·행 120,876 일관 사본 (2026-11-03)
description: 이 PC를 더 안 쓰기로 해 세 프로필 state.db·세션 export·sessions/·spillover·Codex/Claude 세션·설정을 guguroute backups에 복사했다. 행 대조 불일치 0, 복원 시험 315세션 불일치 0. 목적지·암호화·비밀 교체는 사용자 결정
status: active
domain: ops
impl_scope: 운영 기록. 원본 삭제·수정 0, 커밋·푸시·업로드 0, 제품 코드·서비스 변경 0
---

# 모든 Hermes 세션 이관 패키지 (2026-11-03)

- 사용자 지시: 「모든세션백업시작해 이 컴퓨터 이제 안쓸거야」. 보관 목적지(외장/클라우드/다른 PC)는 **답을 기다리는 중**.
- 패키지: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/all-sessions-migration-20261103/` — **1,950,553,062 B · 3,063 파일**. 정본 설명·복원 방법은 그 폴더의 `MANIFEST.md`. `sha256sum -c SHA256SUMS` 실패 0.
- 스냅샷 16:05 KST. 그 뒤 대화는 빠져 있다. PC를 끄기 직전에 한 번 더 뜨면 된다(스크립트: guguroute `cache/scratch/allsess/stage1~6_*.py`, 24시간 지나면 지워질 수 있음).

## 한 일 `[실측]`

1. 세 프로필 `state.db`를 읽기 전용으로 열어 sqlite `backup()` 한 번으로 복사(WAL 반영, `quick_check=ok`, 사본은 DELETE 모드 단일 파일). 부속 DB(projects·kanban·shared-state)와 Codex `state_5`·`thread_history_1.sqlite`도 같은 방식.
2. DB 사본을 임시 HERMES_HOME에 놓고 `hermes sessions export <file> --format jsonl`(가림 없음, 모든 저장 행)로 내보내 세션별 파일로 나눔. DB 사본 해시는 export 전후 동일.
3. **행 대조**: default 523/523 세션·38,544/38,544행, guguroute 582/582·79,938/79,938, myapp 41/41·2,394/2,394. 세션별 행 id 집합 불일치 0, 누락·초과 0.
4. `sessions/`(23 파일), `cache/spillover/`(272), `~/.codex/sessions`(275), `~/.claude/projects`(57), 프로필 `config.yaml`·`SOUL.md`·`skills/`·`memories/` 복사. 비밀 파일은 이름·크기만 기록.
5. **복원 시험 1회**: 버리는 저장소에 Hermes `import_sessions`로 315세션(10,892행: myapp 41 전부, guguroute 113, default 161) 가져와 되읽기 → 오류 0·불일치 0. DB 사본 3개는 `SessionDB(read_only=True)`로 세션 수 523·582·41 확인.
6. 기존 `backups/session-5fbd35ab-export-20261103/`(154세션)는 다시 복사하지 않았다. 같은 154세션의 새 export와 메시지 154/154 동일(`last_active` 계산값·`tool_names` 1건만 다름).

## 이관 대상 크기 (16:17–16:40 실측, robocopy /L 논리 바이트)

| 항목 | 크기 | 이관 | 비고 |
|---|---|---|---|
| 이 패키지 | 1.95 GB | **필수** | 세션 전부 |
| guguroute `backups/` 나머지 | 7.86 GB (폴더 전체 9.82 GB) | **필수** | 이전 보존본·bundle·export. 폴더째 옮긴다 |
| `C:/_proj/final_workspace` | 52.21 GB (524,973 파일) | 필수(원본 저장소) | datasets 34.07·.tmp 5.47·.git 1.45·scratch 0.56(삭제 작업 진행 중이라 변동)·wiki 0.07 |
| `C:/_proj` 기타 | guguroute 10.31·_unified_mall_3 25.31·test_workspace 12.65·postgresql 1.57·_3rd_project_4 0.95 GB | 사용자 결정 | |
| `~/frog-npu-dev` | 94.87 GB | 사용자 결정 | 하드링크 363개가 중복 계산된 논리 크기 |
| Hermes `models/` | 116.12 GB | 사용자 결정 | 다시 받을 수 있는지 확인 필요 |
| Hermes `cache/`(default 44.71·guguroute 38.49 GB) | 83.2 GB | 사용자 결정 | 대부분 scratch, 다른 세션 작업물 |
| `~/models`·`llama.cpp`·`_preserved` | 2.80·0.39·0.75 GB | 사용자 결정 | |
| **필수 합계** | **약 62.0 GB** | | 패키지 + backups 나머지 + final_workspace |

## 비밀·암호화

- 패키지는 **가림 없는 원문**이다. 정규식 개수만 셌다(값 미출력, 오탐 포함 상한): guguroute export 472/582 파일, default 200/523, myapp 21/41, Codex 세션 153/275(개인키 머리 2·GitHub 토큰 꼴 4), Claude 14/57. 상세 `_work/secret_candidate_counts.json`.
- 복사 안 한 비밀: 각 프로필 `.env`·`.env.bak-*`·`auth.json`, `~/.codex/auth.json`, `~/.claude/.credentials.json`, `~/.claude.json`. `vault/`·`pairing/`·`platforms/`·`gateway/`·`home/`는 내용 목록화도 하지 않았다(목록 조회 승인이 철회됨).
- 목적지가 외부(클라우드·외장)면 **암호화 필수**(예: 7-Zip AES-256 + 별도 보관 암호, 또는 BitLocker To Go). 다른 PC로 직접 옮겨도 이 PC 폐기 전 비밀 교체가 필요하다.

## 남은 일

1. **사용자 결정**: 목적지, 암호화 방식, 비밀 파일을 옮길지 새로 발급할지, 「사용자 결정」 행 이관 여부.
2. **정리 대기(삭제 안 함)**: 시험용 임시 파일 1,559,359,589 B — guguroute `cache/scratch/allsess/{home-default,home-guguroute,home-myapp,out,restore-home}`(DB 사본·전체 export·복원 시험 저장소, 비밀 원문 포함). 작업 중 다른 명령의 승인 요청이 철회돼(사용자 응답 전 파괴적 작업 금지 안내) 지우지 않았다. 담당자가 지우거나 24시간 자동 정리를 기다린다.
3. PC 끄기 직전 최종 스냅샷을 한 번 더 뜰 것(새 대화 반영).
