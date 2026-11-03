---
type: report
title: 루트 보조 폴더 보관 안내 및 정리 실행 보류
description: 외부 D 보관 경로와 선별 증거의 경로 매핑; 삭제 미실행
status: draft
domain: neutral
---

# 루트 보조 폴더 보관 안내 — 2026-10-24

## 결과와 경계

[실측] 지정 범위는 작업공간 루트 `_backup`, `_experiments`, `_explain` 세 곳뿐입니다. 삭제 준비 전수검사에서 871/871파일 = 100% (11,313,717바이트)가 기존 감사와 일치했고, 아래 두 D 보관처 각각에서 같은 상대경로·크기·SHA-256을 확인했습니다. 파일·디렉터리 전체 ADS와 reparse 검사는 0건, 접근 오류는 0건이었습니다.

**삭제하지 않았습니다.** 루트 `AGENTS.md`의 옛 참조를 새 안내로 연결하는 정식 수정 승인 요청이 시간 초과로 차단되었습니다. 거절·차단을 우회하지 않았으며 `CLAUDE.md`도 수정하지 않았습니다. 두 파일의 참조 동기 수정과 삭제 직전 재검증이 남았습니다. 현재 보고서는 정리 완료 증거가 아닙니다.

## 외부 보관 안내 (실행 설정 아님)

아래 경로는 확인된 외부 보관 위치입니다. 기계별 경로를 실행 코드·설정의 기본값으로 사용하거나, 백업의 `.env`·baseline을 현행 환경으로 복원하지 않습니다. D 보관본은 읽기 검증만 했으며 변경하지 않았습니다.

- 1차 보관 루트: `D:/Documents/final_workspace`
- 독립 대응 보관 루트: `D:/Documents/파이널스페이스`
- [상대 원본 경로 → 보관 상대경로·크기·SHA-256 manifest](../evidence/2026-10-24_root-aux-cleanup/archive-manifest.json): 각 `source_relative`를 보관 루트에 연결한 경로가 원본 대응 보관 파일입니다. 871개 모두 두 보관 루트에서 확인했습니다. 두 번째 보관처에는 범위 내 추가 파일 180개가 있으며 삭제·동기화하지 않습니다.

| 옛 루트 경로 | 외부 보관 위치 안내 |
|---|---|
| `_backup/2026-10-12_claude-md-line-endings/` | 각 보관 루트의 같은 상대경로. 옛 규칙 사본은 D에만 보관하고 현행 지시로 재사용하지 않음 |
| `_backup/2026-10-12_1830_remote_merge/` 및 그 안 `removed_after_bring_in/` | 각 보관 루트의 같은 상대경로. 전체 과거 복제본을 Git에 넣지 않음 |
| `_experiments/langgraph_compare/` | 각 보관 루트의 같은 상대경로. 비밀 검토한 원본·결과만 아래 선별 보존 |
| `_explain/2026-10-13_reply_reader/` | 각 보관 루트의 같은 상대경로. HTML/PNG는 아래 evidence에도 선별 보존 |

## 선별 보존과 동결 기록

- [실험 원본 보존·재측정 경계](../../../program/research/langgraph-comparison/README.md): 비밀 없는 Python 원본 다섯 개. baseline·환경·캐시·DB·전체 복제는 제외했습니다.
- [실험 결과·설명 그림 경로 안내](../../../final_project_cs/wiki/records/reports/2026-10-24_langgraph-comparison-preservation.md): 검토한 JSON 결과 다섯 개와 설명 HTML/PNG 두 개를 보존합니다. `crash_out.json`은 개인 기계 경로와 연결 실패 기록을 포함하여 D 보관으로만 남깁니다.
- [당시 LangGraph 비교 보고서](../../../final_project_cs/wiki/records/reports/2026-10-11_langgraph-comparison.md)와 [당시 세션 정리](../../../final_project_cs/wiki/records/reports/2026-10-12_1800_코덱스_세션_작업_정리.md)는 동결 본문을 수정하지 않았습니다. 과거 경로는 이 안내의 manifest로 찾습니다.

## 검증·남은 일

전수 재검증과 실행 감사는 로컬 프로필 scratch `root_aux_cleanup_audit/execution_preflight.json`에 있으며, 이 경로는 보관 안내일 뿐 실행 설정이 아닙니다. 원본 감사의 `backup_inventory.json`, `verification.json`과 결합해 확인했습니다. 선별 사본은 복사 후 SHA-256을 비교했습니다. 비밀 패턴 검사와 텍스트 검토, 설명 PNG 시각 검토를 수행했으며 baseline·환경 파일은 복사하지 않았습니다.

남은 일: 정식 승인 후 루트 규칙 두 파일 동기 수정 → 목록·해시·ADS·reparse 재검증 → 통과 시 지정 세 루트만 삭제 → 부재·D 해시 유지·문서 링크·ignore 실파일 probe·범위 밖 불변 확인. Git ignore는 추적 유입 방지이지 파일시스템의 폴더 생성을 막는 권한 제어가 아닙니다. 커밋·push하지 않았습니다.

## 관계

- [wiki](../../index.md) · [인계](../../handoff/index.md)
