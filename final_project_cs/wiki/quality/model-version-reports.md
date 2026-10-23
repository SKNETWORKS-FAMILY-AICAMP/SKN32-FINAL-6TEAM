---
type: guide
title: 모델 판본과 실험 보고서 목록
description: 현재 평가 절차가 인용하는 판본별 독립 보고서의 입구
status: draft
domain: travel
---

# 모델 판본과 실험 보고서 목록

[사용자 결정 2026-10-11] 현재 평가 절차와 판본별 독립 보고서를 함께 사용합니다. 상세 실험은 각각 새 보고서로 보존하고, 아래에서 필요한 보고서만 엽니다. 기존 보고서를 고쳐 최신 실험처럼 만들지 않습니다.

현재 실행 상태·판본 식별자는 [후보·판본 목록](../../../program/research/daily_rag_slm/model_release_watchlist.json)이 관리합니다. 새 중앙 모델 등록 서비스를 도입하는 C안과 다릅니다. A의 판본표와 B의 독립 보고서 보관 방식을 함께 쓰는 구조입니다.

## 판본 표기 예

정확한 모델 이름·원본 revision/가중치 해시·우리 추가 학습 여부·어댑터 해시·양자화·엔진·자료 해시를 구분합니다. 값이 보고서에 없으면 `[미확보]`로 표시합니다. 학습·평가 완료를 서비스 채택으로 해석하지 않습니다.

| 정확한 판본 | 우리 학습 | 실험 조건 | 독립 보고서 | 채택 |
|---|---|---|---|---|
| Winnow-E4B(Jev 계열) publisher release Q8_0 | 없음 | D3 · llama.cpp 4ebdf2c | [동일 문항 비교](../records/reports/2026-10-08_141018_winnow_d3_training_comparison.md) | 이 실험만으로 확정 안 함 |
| Winnow-E4B(Jev 계열) our-travel OOS adapter, Q8_0 기반 | 우리 여행 자료로 추가 학습 | D3 · 입력 360개 · 어댑터 해시는 연결 근거에서 확인 | [학습판 비교](../records/reports/2026-10-08_141018_winnow_d3_training_comparison.md) | 독립 보류 검증 전 보류 |

## 기존 실험 보고서 목록

현재 평가 기준이 직접 인용한 보고서의 연결 목록입니다. 저장소의 모든 실험을 수집한 목록이나 최종 채택 모델 목록이 아닙니다. 원본·학습판·양자화판·실험 제목을 유지하며, 상세 조건·실패·분모는 해당 보고서에서 판단합니다.

| 보고일 | 모델·판본·실험 제목 | 독립 보고서 |
|---|---|---|
| 2026-10-15 | Claude 평가 세션(10-07~10-08) 한 일 목록 — 어려운 세트 H · 검토자 후보 · MX 세트 · 규모 판정 근거 · 학습법 검토 · 부하시험 계획 | [한 일 목록·한계·확인 안 한 것](../records/reports/2026-10-15_평가세션_한일목록과_위키연결.md) |
| 2026-10-09 | E 혼합 평문 평가셋의 고도화 범위와 검수 상태 | [구성·검수 감사](../records/reports/2026-10-09_0214_e-testset-maturity-audit.md) |
| 2026-10-08 | RAG·모델 비교 문서 관리 점검 — 2026-10-08 | [문서 점검 기록](../records/reports/2026-10-08_rag-wiki-document-audit.md) |
| 2026-10-08 | FrogNano 배포 원본의 혼합 요청 평가 완료 — 2026-10-08 | [완료·집계·한계 기록](../records/reports/2026-10-08_frog-original-mx-completion.md) |
| 2026-10-08 | Gemma E4B 원본 H 완료·형식 실패 보존 — 2026-10-08 | [원문·완료 근거](../records/reports/2026-10-08_gemma-original-h-completion.md) |
| 2026-10-08 | Gemma E4B 배포 원본 MX 완료 — 2026-10-08 | [완료·집계 수정·같은 세트 비교 근거](../records/reports/2026-10-08_gemma-original-mx-completion.md) |
| 2026-10-08 | Gemma E4B 배포 원본 D/D2/D3 회수 완료 — 2026-10-08 | [범위·수치·실패 보존 근거](../records/reports/2026-10-08_gemma-original-choice-completion.md) |
| 2026-10-08 | Gemma12B 배포 원본 H 완료 — 2026-10-08 | [완료·한계 근거](../records/reports/2026-10-08_gemma12b-original-h-completion.md) |
| 2026-10-08 | B/C/D/E 현재 결과와 사용자 E 명칭 연결 — 2026-10-08 | [명칭·재집계 근거](../records/reports/2026-10-08_bcde-results-and-e-alias.md) |
| 2026-10-08 | Gemma12B 배포 원본 E 혼합 문장 평가 완료 — 2026-10-08 | [완료·유형별 실패·검증 근거](../records/reports/2026-10-08_1218_gemma12b-original-mx-completion.md) |
| 2026-10-08 | Gemma-4-12B-it Q4_K_M — D 완료 | [완료·검증 근거](../records/reports/2026-10-08_124929_g12bbase_d-completion.md) |
| 2026-10-08 | Gemma-4-12B-it Q4_K_M — D2 완료 | [완료·검증 근거](../records/reports/2026-10-08_130924_g12bbase_d2-completion.md) |
| 2026-10-08 | Winnow-E4B 여행 학습 산출물 보관 | [완료·조건·재개 근거](../records/reports/2026-10-08_131541_winnow_training_completion.md) |
| 2026-10-08 | Gemma-4-12B-it Q4_K_M — D3 완료 | [완료·검증 근거](../records/reports/2026-10-08_132022_g12bbase_d3-completion.md) |
| 2026-10-08 | Winnow-E4B 원본·여행 학습판 평가 회수와 추가 예약 | [집계·한계·추가 평가 근거](../records/reports/2026-10-08_133908_winnow_eval_queue.md) |
| 2026-10-08 | Jev 계열 모델 중 Winnow-E4B publisher release Q8_0 — 혼합 문장 완료 | [완료·기준·한계 근거](../records/reports/2026-10-08_135441_winnow_original_mx_completion.md) |
| 2026-10-08 | Jev 계열 모델 중 Winnow-E4B publisher release Q8_0 — D 완료 | [완료·검증 근거](../records/reports/2026-10-08_140520_winnow_original_d-completion.md) |
| 2026-10-08 | Jev 계열 모델 중 Winnow-E4B publisher release Q8_0 — D2 완료 | [완료·검증 근거](../records/reports/2026-10-08_140624_winnow_original_d2-completion.md) |
| 2026-10-08 | Jev 계열 모델 중 Winnow-E4B publisher release Q8_0 — D3 완료 | [완료·검증 근거](../records/reports/2026-10-08_140625_winnow_original_d3-completion.md) |
| 2026-10-08 | Jev 계열 모델 중 Winnow-E4B our-travel oos adapter Q8_0 base — D3 완료 | [완료·검증 근거](../records/reports/2026-10-08_140836_winnow_oos_d3-completion.md) |
| 2026-10-08 | Winnow-E4B (Jev 계열) — 원본과 우리 여행 학습판 D3 비교 | [비교 근거](../records/reports/2026-10-08_141018_winnow_d3_training_comparison.md) |
| 2026-10-08 | Winnow-E4B 여행 학습판 추가 평가 완료와 GPU 일감 보충 | [근거](../records/reports/2026-10-08_145604_winnow_three_completion_refill.md) |
| 2026-10-08 | Jev 계열 모델 중 Winnow-E4B our-travel oos adapter Q8_0 base — 혼합 문장 완료 | [완료·기준·한계 근거](../records/reports/2026-10-08_150227_winnow_oos_mx_completion.md) |
| 2026-10-08 | Winnow 추가 다섯 시험 회수와 QAT 대기열 보충 | [완료·재개 근거](../records/reports/2026-10-08_150608_qat_refill_five_suite.md) |
| 2026-10-08 | Gemma QAT 원본 D2·H 완료 | [근거](../records/reports/2026-10-08_151129_qat_original_d2_h_completion.md) |
| 2026-10-08 | QAT 새 완료·학습판 비교·대기열 보충 | [근거](../records/reports/2026-10-08_153821_qat_three_completion_refill.md) |
| 2026-10-08 | QAT 여행 학습판 두 평가 완료 | [완료·채택 보류 근거](../records/reports/2026-10-08_155803_qat_two_trained_completion.md) |
| 2026-10-08 | QAT 평가 완료와 누락 선택 시험 보충 | [근거](../records/reports/2026-10-08_162050_qat_completion_and_choice_refill.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos3 adapter — 혼합 문장 완료 | [완료·기준·한계 근거](../records/reports/2026-10-08_163509_e4bqat_oos3_mx_completion.md) |
| 2026-10-08 | QAT 평가 완료·같은 문항 검증 | [근거](../records/reports/2026-10-08_164532_qat_completion_verified.md) |
| 2026-10-08 | QAT 평가 완료·같은 문항 검증 | [근거](../records/reports/2026-10-08_165415_qat_completion_verified.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 original — D 완료 | [완료·검증 근거](../records/reports/2026-10-08_170613_e4bqat_original_d-completion.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter — D3 완료 | [완료·검증 근거](../records/reports/2026-10-08_170616_e4bqat_oos1_d3-completion.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos2 adapter — D3 완료 | [완료·검증 근거](../records/reports/2026-10-08_170627_e4bqat_oos2_d3-completion.md) |
| 2026-10-08 | QAT 선택 시험 회수와 누락 회귀 평가 예약 | [근거](../records/reports/2026-10-08_170810_qat_choice_completion_and_regression_refill.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos3 adapter — D3 완료 | [완료·검증 근거](../records/reports/2026-10-08_171441_e4bqat_oos3_d3-completion.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos2r adapter — D3 완료 | [완료·검증 근거](../records/reports/2026-10-08_171445_e4bqat_oos2r_d3-completion.md) |
| 2026-10-08 | QAT 원본·여행 어댑터 네 판의 직접 선택 D3 | [근거](../records/reports/2026-10-08_171630_qat_d3_five_variants.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter — D 완료 | [완료·검증 근거](../records/reports/2026-10-08_172547_e4bqat_oos1_d-completion.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter — D2 완료 | [완료·검증 근거](../records/reports/2026-10-08_173726_e4bqat_oos1_d2-completion.md) |
| 2026-10-08 | Gemma-4-E4B-it QAT Q4_0 with our-travel oos2 adapter — D 완료 | [완료·검증 근거](../records/reports/2026-10-08_174041_e4bqat_oos2_d-completion.md) |
| 2026-10-09 | Saluki 원본 검토와 조건부 여행 질의 시험 준비 | [근거](../records/reports/2026-10-09_0117_saluki-official-review.md) |
| 2026-10-09 | Saluki 원본 설치·연결검사 및 실제 평가 시작 | [실행·조건·보관 근거](../records/reports/2026-10-09_023533_saluki-install-smoke-and-evaluation.md) |
| 2026-10-09 | Saluki 원본과 cosine 학습판 완료 회수 및 FINCH GPU 대기열 보충 | [원본·집계·실행 조건](../records/reports/2026-10-09_0810_gpu-saluki-cosine-completion-finch-refill.md) |
| 2026-10-09 | 새 통합 여행 평가 계획·Saluki 학습 준비·Jev 비교 | [검토·예시·학습 비교 근거](../records/reports/2026-10-09_1150_selection-answer-plan-and-training-review.md) |
| 2026-10-09 | 통합 여행 평가 예시의 독립 검토와 정답 표시 수정 | [현재 평가 준비 근거](../records/reports/2026-10-09_1158_pilot-independent-review-corrections.md) |
| 2026-10-09 | Saluki 첫 학습을 기존 검토 여행 자료 적용으로 단순화 | [자료·검토 범위·단계 분리 근거](../records/reports/2026-10-09_1208_saluki-reviewed-set-baseline.md) |
| 2026-10-09 | 두 번째 FINCH 학습판 보관과 GPU 대기열 보충 | [최신 회수·원본 대조와 조건](../records/reports/2026-10-09_140358_gpu-finch-seed2-completion-valen-final-refill.md) |
| 2026-10-09 | 20시 완료 평가 회수와 ARM 캐시 교대 비교 결과 | [유형별 분자/분모·반복·검수 상태](../records/reports/2026-10-09_2000_six-hour-gpu-arm-report.md) |
| 2026-10-10 | 2026-10-10 14시 GPU·Oracle ARM 6시간 현황 | [관측·회수·검증·백업](../records/reports/2026-10-10_1400_six-hour-gpu-arm-report.md) |
| 2026-10-10 | 2026-10-10 20시 GPU·Oracle ARM 6시간 현황 | [완료·구간·원본](../records/reports/2026-10-10_2000_six-hour-gpu-arm-report.md) |
| 2026-10-11 | GPU 비교와 Oracle ARM 6시간 현황 — 2026-10-11 02시 | [원본·구간·검증 경계](../records/reports/2026-10-11_0200_six-hour-gpu-arm-report.md) |
| 2026-10-11 | 08시 정기 설명·현황 | [관측·회수·재개 조건](../records/reports/2026-10-11_0800_six-hour-gpu-arm-report.md) |

## 관계

- [현재 평가 절차](slm-model-evaluation.md) — 비교·학습·최종 채택 기준
- [날짜별 연구 기록](../../../program/research/daily_rag_slm/index.md) — 후속 실행 기록
