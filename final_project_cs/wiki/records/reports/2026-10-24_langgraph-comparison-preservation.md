---
type: report
title: 비교 실험 및 고객 답 읽기 설명 자료 선별 보존
description: 과거 자료의 경로 보완과 재측정 한계; 기존 보고서 본문 동결 유지
status: draft
domain: neutral
---

# 실험·설명 자료 선별 보존 — 2026-10-24

## 범위

[실측] [당시 비교 보고서](2026-10-11_langgraph-comparison.md)의 `_experiments/langgraph_compare/` 자료 중 비밀 없는 원본 다섯 개와 결과 다섯 개, `_explain/2026-10-13_reply_reader/`의 HTML/PNG 두 개를 선별 보존했습니다. 원문 보고서는 수정하지 않았습니다. 선별 사본과 원본의 SHA-256을 비교했습니다. 전체 복제·baseline·환경 파일·캐시·빈 오류 로그는 Git 보존 대상에 넣지 않았습니다.

## 새 위치

| 옛 상대경로 (`_experiments/langgraph_compare/` 기준) | 선별 보존 |
|---|---|
| `behaviors.py`, `bench.py`, `complex.py`, `crash.py`, `fair.py` | [연구 원본과 실행 경계](../../../../program/research/langgraph-comparison/README.md) |
| `beh_out.json` | [당시 동작 비교 결과](../evidence/2026-10-11_langgraph-comparison/beh_out.json) |
| `complex_out.json` | [당시 복합 흐름 결과](../evidence/2026-10-11_langgraph-comparison/complex_out.json) |
| `fair_out.json` | [당시 보장 조건 비교 결과](../evidence/2026-10-11_langgraph-comparison/fair_out.json) |
| `tp_fair.json` | [당시 건별 커밋 비교 결과](../evidence/2026-10-11_langgraph-comparison/tp_fair.json) |
| `tp_out.json` | [당시 초기 처리량 결과](../evidence/2026-10-11_langgraph-comparison/tp_out.json) — 트랜잭션 조건이 달라 공정 비교로 쓰지 않음 |

결과 JSON은 위 다섯 개입니다. `crash_out.json`은 개인 기계 경로와 DB 연결 실패 기록을 포함해 외부 D 보관처에만 유지합니다. 연결 실패·빈 부작용 장부는 복구 성공 증거가 아닙니다. 원본 스크립트·결과의 비교상 한계는 보존하고 최신 일반 성능 주장으로 확대하지 않습니다.

- 설명 자료 원본: [HTML](../evidence/2026-10-13_reply_reader/reply-reader-flow.html) · [PNG](../evidence/2026-10-13_reply_reader/reply-reader-flow.png). 비밀·개인정보 없는 예시 흐름을 확인했으며 당시 설명이지 현재 구현 검증이 아닙니다. HTML은 외부 Google Fonts를 참조하며 오프라인에서는 대체 글꼴을 사용합니다.
- [외부 D 보관 안내와 상대경로 manifest](../../../../wiki/records/reports/2026-10-24_root-aux-cleanup.md): 제외한 원본도 두 D 보관 루트의 동일 상대경로에서 찾습니다. 외부 경로는 보관 안내이며 실행 설정이 아닙니다.

## 한계·상태

보존 작업은 코드 실행·DB 변경·의존성 설치를 하지 않았습니다. baseline·환경을 넣지 않아 이 사본만으로 당시 실행 환경을 재현할 수 없습니다. 루트 규칙 참조 수정 승인 차단으로 지정 세 루트 삭제는 보류했습니다. 과거 기록의 옛 경로는 신규 매핑으로만 보완합니다.

## 관계

- [cs wiki](../../index.md) · [원본 연구 보존 안내](../../../../program/research/langgraph-comparison/README.md)
