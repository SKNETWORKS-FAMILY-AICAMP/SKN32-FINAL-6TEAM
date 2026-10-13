---
type: guide
title: 불변식 등록 집계
description: 카탈로그의 정의 행만 집계하며 실행 통과율과 구분한다
status: draft
domain: neutral
domain_note: 코드·카탈로그 파일의 자동 집계이며 제품 도메인 사례를 판정하지 않는다
automation:
  command: python program/scripts/build_wiki_catalogs.py
  owner: process:wiki-catalogs
  manual_edit: false
---

# 불변식 등록 집계

[실측: 작업 트리] [불변식 카탈로그](invariants.md)의 정의 표 첫 열만 집계했습니다. 본문에 반복된 ID·과거 요약·코드 주석 수를 불변식 등록 수와 섞지 않습니다.

| 영역 | 등록 수 | automated | review | manual |
|---|---:|---:|---:|---:|
| ACT | 12 | 12 | 0 | 0 |
| ARCH | 7 | 7 | 0 | 0 |
| CTX | 2 | 2 | 0 | 0 |
| EVAL | 1 | 1 | 0 | 0 |
| RT | 26 | 26 | 0 | 0 |
| SEC | 10 | 10 | 0 | 0 |
| TEAM | 5 | 2 | 3 | 0 |
| VER | 7 | 7 | 0 | 0 |
| 합계 | 70 | 67 | 3 | 0 |

등록·automated 표시는 이번 실행의 시험 통과 수가 아닙니다. 사용 종료된 SEC-008·EVAL-001은 현재 정의 표에서 제외하고 번호를 재사용하지 않습니다. VER 항목은 합성 철도 패스 정책으로 검증합니다. 전체 항목이 현재 여행 제품에서 유효하고 통과했다고 해석하지 않습니다.

중복 ID가 있으면 생성기가 실패합니다. 실제 함수 연결은 wiki 검사기로, 동작은 해당 시험 실행으로 별도 확인합니다.

## 관계

- [불변식 카탈로그](invariants.md) — 개별 규칙과 시험 연결의 정본
- [시험 지도](test-map.md) — 동작 검증 위치
