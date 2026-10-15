---
type: guide
title: 고정 1,448문장 회귀 — 회수·채점·제품 경로 재측정 인계 (2026-10-15)
description: 오지목 · 규정 질문 놓침의 현재 값을 확정하고 제품 경로로 다시 잰 한 일 목록
status: draft
domain: travel
---

# 인계 — 고정 1,448문장 회귀 (2026-10-15)

본문 보고서: [고정1448_회수채점과_제품경로재측정](../../final_project_cs/wiki/records/reports/2026-10-15_고정1448_회수채점과_제품경로재측정.md)

## 한 일 목록

| 일 | 결과 | 근거 |
|---|---|---|
| 10-12 회귀 저장 답안 회수 · 채점 | 끝 | 답안 1,448줄 · 채점 파일은 GPU 서버 B 에 있었음 |
| 최신 코드로 원답 재검증(GPU 없음) | 끝 | 규정 인식 78 → 105/148 |
| 제품 경로(학습 E4B + a1edea43) 재생 | 끝 | [결과 폴더](../../program/research/daily_rag_slm/2026-10-15_frozen1448_product_path/) |
| 잡담 100건 「해석 실패」 코드 수정 | 끝(커밋 전) | [패치](../../program/research/daily_rag_slm/_patches/2026-10-15_decision_unit_empty_general_with_social.patch) · [시험](../../final_project_cs/tests/unit/travel/test_decision_empty_general_with_social.py) |
| 잡담 오지목 · 규정 질문 말투 모델 수정 | 사용자 결정 대기 | 보고서 §3 |

## 커밋 대상 경로(commit 세션)

- `final_project_cs/wiki/records/reports/2026-10-15_고정1448_회수채점과_제품경로재측정.md`
- `final_project_cs/tests/unit/travel/test_decision_empty_general_with_social.py`
- 패치 적용: `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` (패치 파일 한 곳 변경, origin/develop a1edea43 기준)
- `program/scripts/rag_gate/frozen_decision_runner_ollama.py`
- `program/research/daily_rag_slm/_patches/2026-10-15_decision_unit_empty_general_with_social.patch`
- `program/research/daily_rag_slm/2026-10-15_frozen1448_product_path/`
- 이 문서

## 시험 결과

- 새 시험 5/5 통과, 수정 전 코드에서는 2건 실패(의도한 대로).
- 기존 결정 단위 시험 7개 파일 128건: 수정 전후 동일(97 통과 · 31 환경 오류 — 이 PC 에 시험 설정이 없어 단순화한 설정으로 돌림). **전체(ci-main 순서)는 못 돌림.**
- 제품 경로 재생 결과는 mock 서버 시험이 아니라 GPU 서버 B 재현 환경의 모델 응답이며, 테스트 서버 응답은 확인하지 않음.

## 남은 일 · 승인 필요

- 모델 교체(잡담 보강판)와 해석 지침 보강 중 무엇을 할지 — 사용자 결정(승인 전 테스트 서버 모델 교체 금지).
- 규정 질문 148건 라벨 점검(경계 사례 존재).
- 잡담 보강판 시드 3개 이상 · 독립 보류 문제 근거.
- 수정 코드를 develop 에 올릴 때는 최신 develop CI → 그 위 시험 → 푸시 순서(기억: develop 푸시 전 순서).
