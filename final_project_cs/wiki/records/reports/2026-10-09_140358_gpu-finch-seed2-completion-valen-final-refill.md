---
type: report
title: 두 번째 FINCH 학습판 보관과 Valen 최종 회수 및 GPU 대기열 보충
description: 고정 원본 SHA와 전체 문항 분모를 보존하고 유휴 GPU 서버 A의 실제 계산을 재확인한 6시간 관측
status: draft
domain: travel
tags: [gpu, evaluation, finetuning]
---

# 두 번째 FINCH 학습판 보관과 GPU 대기열 보충

[실측] 빈 GPU 서버 A에 완료 학습판의 누락 평가 10개를 보충해 실제 계산을 확인했습니다. 새 답안과 어댑터를 보관했으며, Valen 원본 경로는 시험 완료와 성능 기준 통과를 구분합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 답안 보관 | 완료 | 4,340/4,340 = 100% |
| 원격·로컬 SHA 대조 | 통과 | 46/46 = 100% |
| 두 번째 FINCH 본 학습 | 완료 | 654/654 = 100% |
| 누락 추가 평가 등록 | 완료 | 10/10 = 100% |
| Valen 본 평가 답안 | 완료 | 9,425/9,425 = 100% |

[실측] GPU 서버 A 2026-10-09T05:02:29.201849+00:00 (한국 시각 UTC+9), GPU 3482 MiB, 98 %; 기존 실행기 PID 342497 유지. 현재 ['e4bbase_finch_s20261013_d3'], 저장 {'e4bbase_finch_s20261013_d3': 209}, 준비 9개, 조건 대기 입력 0개. 전체 manifest 103개 중 완료 91·실패 2·실행 1개이며, 과거 실패를 완료로 바꾸지 않았습니다.
[실측] GPU 서버 B 2026-10-09T05:02:29.639026+00:00, GPU 12781 MiB, 100 %; cosine 두 번째 시드 180/654 진행. 세 번째 시드 cosine/FINCH 두 학습이 기존 순서에서 기다립니다. 준비 2개로 운영 목표3개에는 미달합니다. 불필요한 추가 시드는 등록하지 않았습니다.
[실측] 남은 파일시스템 공간 A 4,191,072,256바이트, B 6,305,652,736바이트. 이 df 관측은 계정 quota 보장이 아닙니다.

## 새 복수 선택 역할 결과

B는 정답 중 하나 이상 선택, C는 선택 전체가 정답 집합과 정확히 일치한 수입니다. 동일835문항(단일583·요청없음186·복합66)의 별도 역할이며 실패도 분모에 남깁니다.

| 우리 여행 학습판 | B | C | 복합 C | 요청없음 오지목 | 해석실패 |
|---|---|---|---|---|---|
| Jev 계열 Winnow-E4B Q8_0 | 826/835 | 793/835 | 56/66 | 2/186 | 0/835 |
| Gemma E4B QAT Q4_0 oos1 | 822/835 | 801/835 | 52/66 | 2/186 | 4/835 |
| Gemma E4B QAT Q4_0 oos3 | 826/835 | 814/835 | 59/66 | 0/186 | 1/835 |
| Gemma E4B QAT Q4_0 oos2r | 819/835 | 791/835 | 53/66 | 1/186 | 2/835 |

## Valen 원본 D2와 경로 검증

[실측] 수정 시도 D2는 1,000/1,000 답안·호출/해석 실패0/1,000·미완료0/1,000이며 요청없음 오지목999/1,000, 정답1/1,000입니다. 앞선 메모리 사전 조건 실패(로드 전0/1,000)는 별도 시도로 계속 보존합니다. 시험 완료는 성능 통과를 뜻하지 않습니다.
[실측] 고정 원문→선택지 변환1,000/1,000, 질문·일정·판정 규칙·NONE·정답/유형·native 최고확률→번호/NONE 매핑1,000/1,000을 직접 대조했습니다. U+FFFD 인코딩 손상0건. 현재 고정 여행/native-choice 경로의 성능 기준 실패이며 원인이 분리되지 않아 모델 전체 일반 능력으로 확대하지 않습니다.
native 선택지 확률은 다음 토큰 확률·말로 한 확신도와 다르며 JSON 생성 경로와 속도를 직접 비교하지 않습니다.

## 두 번째 FINCH 학습판

[실측] 동일 고정2613행·시드20261013·rank16·2에폭·accum8, 본654/654 완료. 학습17880.20초, 초기 loss 측정2186.62초를 구분합니다. 학습률 상한 적용639/654 = 97.71%, 연속 구간16~654, 실제 최저3.986732956153178e-5·최대5e-5입니다. 상한 도달은 학습 실패를 뜻하지 않습니다.
[실측] 기본 HF NF4 평가835/835·오류0·B 814/835, 단일 정답 748/769입니다. 한 번호 출력 계약에서 복합 C0/66은 진단값이며 새 strict 복수 선택 역할의 성능이나 학습 실패로 읽지 않습니다. 새 독립 보류 시험·제품 채택·최종 순위는 미완료입니다.
[실측] 영구 보관 데이터 정본은 [HF/GGUF 어댑터 폴더](../../../../datasets/core/pointing/trainset/train_oos/oos2r_finch_5e5_seed20261013_20261009). GGUF69,798,944바이트, SHA256 `efbfc01207517ace92b4bde9b880b006ee5b4fc84c488e3844d809367ec60429`. 로그·원본 기본 답안·recipe를 함께 회수해18/18 SHA 대조했습니다.

## 대기·다음 6시간

GPU 서버 A의 새10평가는 두 양자화 기반의 D3→D→D2→H→E(MX) 순서, 총18,850개입니다. 전체 모델 SHA·어댑터 텐서 구조·고정 입력 SHA·잠금을 확인해 백업 후 manifest를 원자 교체했고 새 worker를 만들지 않았습니다. E 전체4,014개=혼합2,007·대조2,007이며 동일 쌍 반복을 독립 정확도 표본으로 합치지 않습니다.
GPU 서버 B는 현재 cosine 완료 시 어댑터·변환·기본 평가를 회수하고, 이후 기존 B58의 세 번째 시드 두 판을 유지합니다. 추가 유효 후보의 기존 파일 목록을 확인했으나 Saluki 동일 가중치의 학습 표현/역전파/16GB 적재·공간, Spark 대응 기반, StandardOne 공간/실행기 호환, Jevify 이전 미해결 다운로드 실패가 조건 대기입니다. 준비된 세 번째 작업으로 세지 않습니다. 새 임대·결제·모델 삭제·중단·원인 미수정 반복은 하지 않았습니다.
다음6시간 확인에서 완료된 새 FINCH 평가를 즉시 회수·실패 포함 집계하고, 새 cosine 완료판의 동일 입력 추가 평가를 우선 보충합니다. 현재 관측을 6시간 내내 풀가동한 증거로 쓰지 않습니다.

## 근거와 재개 경로

- [GPU 서버 A 보충 전 유휴 관측](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_hb1355_20261009.json)
- [GPU 서버 A 실제 계산 관측](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_hb1405_20261009.json)
- [GPU 서버 B 학습 관측](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_snapshot_hb1405_20261009.json)
- [새 답안46파일 중 A28 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/A_verification.json)
- [학습 산출물 B18 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/B_verification.json)
- [Valen D2 전체 계약 대조](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/Valen_D2_mapping_audit.json)
- [Valen D2 최종 계수](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_d2_a2/native_counts.json)
- [FINCH 기본 계수·학습률 구간](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/FINCH_seed13_basic_counts.json)
- [호환·잠금·백업·10작업 등록](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/A_seed13_registration.json)
- [기존 후보 파일 읽기 확인](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/B_existing_candidates.json)
- [상태 수정 전 백업](../../../../program/research/daily_rag_slm/_backup/2026-10-09_140358_gpu_hb1355_completion_refill/gpu_backlog_2026-10-09.json)
- [GPU 운영 정본](../../../../final_project_cs/wiki/operations/gpu-work-queue.md)
- [winnow_oos_multi_items_bc_a1](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_multi_items_bc_a1/multi_items_counts.json)
- [e4bqat_oos1_multi_items_bc_a1](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_multi_items_bc_a1/multi_items_counts.json)
- [e4bqat_oos3_multi_items_bc_a1](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_multi_items_bc_a1/multi_items_counts.json)
- [e4bqat_oos2r_multi_items_bc_a1](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_multi_items_bc_a1/multi_items_counts.json)
