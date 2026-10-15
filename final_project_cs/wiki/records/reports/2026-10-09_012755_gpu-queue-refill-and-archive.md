---
type: report
title: GPU 대기열 보충과 완료 산출물 보관
description: 빈 평가 대기열 재보충·독립 시드 예약·어댑터와 답안 보존 근거
status: draft
domain: travel
tags: [gpu, evaluation, research]
---

# GPU 대기열 보충과 완료 산출물 보관 — 2026-10-09

확인일: 2026-10-09 01:27:55 KST. 기존 GPU 서버 A가 쉬는 상태를 확인한 뒤 누락 평가를 보충해 실제 계산을 재개했고, GPU 서버 B에는 독립 시드 비교 두 판을 추가 예약했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 두 GPU 실제 계산 확인 | 완료 | 2/2 = 100% |
| 신규 유효 작업 예약 | 완료 | 12/12 = 100% |
| 완료 직접 선택 답안 보관·대조 | 완료 | 8,470/8,470 = 100% |
| 두 학습판 기본 답안 보관 | 완료 | 1,670/1,670 = 100% |

위 진행률은 이번 보충·회수 작업의 범위입니다. 예약한 학습·평가 전체가 끝났다는 뜻은 아닙니다.

## 실제 계산과 준비 대기

| 기계 | 관측 시각(KST) | 현재 계산 | 준비 대기 | GPU 순간 측정 |
|---|---|---|---|
| GPU 서버 A | 01:19:06 | cosine 첫 D3, 93/360개 저장 | 평가 9개 | 3,482 MiB · 91% |
| GPU 서버 B | 01:25:32 | FINCH 초기 손실 2,613/2,613 완료 후 본 학습 | 본 학습 4개 | 12,417 MiB · 100% |

A는 기존 47개 완료 후 다음 준비 작업이 0개였고 기존 worker는 살아 있었습니다. 완료된 cosine 어댑터의 D·D2·D3·H·MX를 Q4_K_M와 QAT Q4_0 각각으로 10개·18,850문항 추가했습니다. 등록 합계는 57개·109,005문항이며 worker를 다시 띄우거나 진행 중 작업을 중단하지 않았습니다. 01:19 관측 당시 신규 완료는 0/10개이며 첫 평가만 실행 중입니다. 기록의 state.saved가 0인 동안에도 실제 답안 파일은 93줄이었으므로 답안 수는 파일로 확인했습니다.

A manifest 수정 직전에 원격 _backup에 복사한 뒤 같은 폴더의 임시 파일을 원자적으로 교체했습니다. 어댑터 SHA256, 기존 성공 어댑터와 516개 텐서 구조, 기반 파일 전체 SHA256, 고정 문항 해시·분모를 확인했습니다. 두 양자화 결과를 합치지 않으며 모두 우리 여행 자료로 학습한 cosine 어댑터 시험입니다.

B57의 seed20261013 두 판(FINCH→cosine)은 B56 종료 후, 새 B58의 seed20261014 두 판(cosine→FINCH)은 B57 종료 후 순차 실행됩니다. 새 예약 프로세스는 실제로 살아 있으며 종료 대기 로그가 있습니다. 입력 3/3개 해시·실행 문법·기존 스모크·새 출력 경로를 확인했습니다. 준비 대기 4개는 선행 작업 종료만 기다리는 실행 가능한 레시피이며 GPU를 미리 점유하지 않습니다. 독립 시드 편차 확인용으로, 같은 완료 작업의 중복 실행이나 독립 보류 검증이 아닙니다.

관측 코드는 qlora_train_finch.py를 놓쳐 GPU 100%인데 학습 목록을 비워 보였습니다. 기존 코드를 백업 후 실제 PID와 작업 폴더의 학습 로그를 읽도록 수정했고 실제 FINCH 프로세스 검출을 확인했습니다. B58 프로세스와 prepared/완료 표식도 후속 관측에서 확인되도록 추가했습니다.

## 새로 보관한 완료 답안

| 학습판·세트 | 보관 | 정상 요청 정답 | 요청 없음 오지목 | 실패·해석 불가 |
|---|---|---|---|---|
| QAT + oos2 · D2 | 1000/1000 | 해당 없음 | 5/1000 | 0/1000 |
| QAT + oos3 · D | 2735/2735 | 797/883 | 24/1786 | 0/2735 |
| QAT + oos3 · D2 | 1000/1000 | 해당 없음 | 15/1000 | 0/1000 |
| QAT + oos2r · D | 2735/2735 | 784/883 | 5/1786 | 0/2735 |
| QAT + oos2r · D2 | 1000/1000 | 해당 없음 | 1/1000 | 0/1000 |

위 다섯 답안은 원격/로컬 SHA와 크기 5/5개가 일치합니다. 기존 집계 도구로 전체 ID·정답·유형·고정 입력을 검사하고 같은 QAT 기반 원본과 문항별로 대조했습니다. D의 2,735문항 중 정상 883개·요청 없음 1,786개를 주 집계에 쓰며 복합 요청 66개는 별도 진단에 남깁니다. 원본 D에는 정상 요청 실패 12/883·요청 없음 실패 3/1,786이 있고, 원본 D2에는 실제 오지목 68/1,000과 해석 실패 1/1,000이 따로 있습니다. 실패를 실제 오지목에 합치거나 분모에서 제외하지 않았습니다. 학습판의 개발 자료 실측이며 제품 채택·전체 순위·속도 비교 결론이 아닙니다.

Spark-S1-4B 우리 여행 학습판과 Gemma-4-E4B-it cosine 우리 여행 학습판의 HF 원본·GGUF 각각을 새 로컬 이름으로 보관하고 가중치 SHA를 대조했습니다. 기본 평가 5파일·835문항씩(합계 10파일·1,670문항), 호출 오류 0/1,670개와 실행·실패 로그 8파일을 보관했습니다. cosine의 완료 레시피에는 654회 갱신·학습 시간 298.2분이 있고 Spark 로그에는 429회 계획 대비 종료 표시 430/429가 있어 로그 표시와 실제 학습 레시피를 구분해야 합니다. 이번 보관을 두 판의 정확도 합격으로 해석하지 않습니다.

## 실패와 조건 대기

Jevify-E4B는 가중치 다운로드 ReadTimeout 뒤 스모크에서 model.safetensors 누락으로 실패했고, 학습 완료 어댑터가 없습니다. 실패 로그를 원문으로 보관했습니다. B54의 ALLDONE은 대기열 스크립트 종료 표식으로, 각 후보가 모두 성공했다는 근거가 아닙니다. 원인 수정 없는 재실행은 하지 않았습니다.

Saluki는 공식 자료·계획·정상 6개/요청 없음 6개 스모크 문항이 준비됐으나 설치 엔진의 구조 호환과 정본 입력 대조가 미완료여서 준비 대기 수에 넣지 않았습니다. A 여유 8,675,635,200bytes에 후보 7,898,369,152bytes를 더 받으면 3GiB 안전 여유가 안 남습니다. B 여유 22,522,556,416bytes는 파일시스템 값이며 계정 quota·현재 및 후속 네 학습의 산출물 증가 예산을 재확인하기 전 다운로드를 보류합니다. Spark의 A 추가 평가도 맞는 기반 GGUF 및 실행기 호환 확인 뒤 준비 작업으로 올립니다. 새 모델 다운로드·결제·임대·기존 모델 삭제를 하지 않았습니다.

관측된 91%·100%는 서로 다른 시각의 순간 사용률입니다. 24시간 사용률이나 향후 항상 일정한 사용을 증명하지 않습니다. Oracle ARM 및 실서비스 배포는 이번 GPU 점검 범위 밖입니다. 독립 보류 자료·후속 반복·남은 신규 평가 완료 전 상용화 판정을 내리지 않습니다.

## 재개 근거와 백업

- [날짜별 GPU 상태](../../../../program/research/daily_rag_slm/gpu_backlog_2026-10-09.json)
- [A 실제 실행](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_gpu_20261009_after_refill.json)
- [A 입력·공간](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_conditions_gpu_20261009_after_refill.json)
- [B FINCH·B58 실제 프로세스](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_snapshot_gpu_20261009_final.json)
- [B57/B58 준비 상태](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_conditions_gpu_20261009_final.json)
- [A 보충·원격 manifest 백업 위치](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/cosine_refill_20261009_0123.json)
- [A 완료 답안 해시 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_completed_hashes_20261009_0125.json)
- [HF/GGUF 보관 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/adapters_archived_20261009_0115.json)
- [기본 답안·완료 및 실패 로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_completed_20261009_0121)
- [B58 실제 대기 로그와 기본 원격 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B58_and_basic_20261009_0120.json)
- [B58 준비 입력·레시피](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B58_prepared_20261009_0125.json)
- [새 B58 실행 스크립트](../../../../program/scripts/plan_qa_bench/server/queues/run_B58_seed3_20261009.sh)
- [A 기존 worker 보충 스크립트](../../../../program/scripts/plan_qa_bench/server/queues/refill_cosine_additional_20261009.py)
- [FINCH 관측 코드](../../../../program/scripts/plan_qa_bench/server/queues/check_backlog_20261008.py)
- [FINCH 수정 직전 백업](../../../../program/scripts/plan_qa_bench/server/queues/_backup/2026-10-09_0120_finch_process_observer/check_backlog_20261008.py)
- [B58 관측 수정 직전 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-09_0133_B58_observation)
- [보충 스크립트 수정 직전 백업](../../../../program/scripts/plan_qa_bench/server/queues/_backup/2026-10-09_0122_cosine_refill/refill_cosine_additional_20261009.py)
- [Saluki 조건부 평가 계획](../../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/evaluation_plan.json)
- [QAT + oos2 · D2 집계·원본 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_d2/matched_original.json)
- [QAT + oos3 · D 집계·원본 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_d/matched_original.json)
- [QAT + oos3 · D2 집계·원본 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_d2/matched_original.json)
- [QAT + oos2r · D 집계·원본 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_d/matched_original.json)
- [QAT + oos2r · D2 집계·원본 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_d2/matched_original.json)
