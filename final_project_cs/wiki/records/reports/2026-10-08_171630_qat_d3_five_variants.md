# QAT 원본·여행 어댑터 네 판의 직접 선택 D3

같은 QAT 기반 원본과 여행 어댑터 네 판의 D3를 모두 보관했다. 정상 요청과 잡담 오지목을 함께 대조하며 기존 혼합 문장 손실·독립 보류·반복 검증 전 채택하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 같은 문항 평가 회수 | 완료 | 5/5판 = 100% |
| 전체 답안 | 완료 | 1,800/1,800 = 100% |
| 오류·해석 실패 | 원본의 실패 보존 | 1/1,800 = 0.06% |

## 원본과 추가 학습 역할

기반은 Gemma-4-E4B-it QAT Q4_0다. 개발사의 지시 학습·양자화 학습은 원본에도 있으며, 우리 여행 학습 없음과 구분한다. 여행 어댑터를 QAT 원본에 적용해 추론한 결과이며 어댑터 자체를 QAT 방식으로 새 학습했다는 뜻이 아니다.

| 우리 여행 추가 학습 | 정상 요청 정답 | 잡담 오지목 | 오류·해석 실패 |
|---|---:|---:|---:|
| 없음 — 배포 원본 | 102/120 = 85.00% | 22/240 = 9.17% | 1/360 |
| 어댑터 oos1 | 108/120 = 90.00% | 0/240 = 0.00% | 0/360 |
| 어댑터 oos2 | 108/120 = 90.00% | 0/240 = 0.00% | 0/360 |
| 어댑터 oos3 | 109/120 = 90.83% | 3/240 = 1.25% | 0/360 |
| 어댑터 oos2r | 105/120 = 87.50% | 0/240 = 0.00% | 0/360 |

정상 요청 분모120개는 정답 일정 항목이 있는 문항이고 잡담 분모240개는 항목 선택이 없어야 하는 문항이다. 실패는 해당 분모에 남기고 정확도에서 오답으로 처리한다. 실제 오지목은 형식 실패와 분리한다. 같은 항목을 반복한 soak 자료를 추가 정확도 표본으로 합치지 않는다.
[원본과 같은 문항 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_171630_qat_d3_five_variants_paired.json). 전체 ID·정답·유형·기반 해시·입력·실행 코드·엔진을 대조했다. 각 실행1회이고, 원본과의 검정이 어댑터끼리 우열·반복 편차·다중 비교·독립 보류 검증을 대신하지 않는다.

## 완료 답안·직접 검증·한계

- [Gemma-4-E4B-it QAT Q4_0 original 답안·실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d3/) · [집계·Wilson 구간·오류 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d3/choice_counts.json). 답안SHA256 `44bca575d39ae68eb0917c154bcbd423427da95c27aeee57efe54f90be820318`.
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter 답안·실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d3/) · [집계·Wilson 구간·오류 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d3/choice_counts.json). 답안SHA256 `f984f043c8a013dee58c7dc57cb19a9a7517b03a7537ecd5af0189dd016047ff`.
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos2 adapter 답안·실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_d3/) · [집계·Wilson 구간·오류 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_d3/choice_counts.json). 답안SHA256 `afa2bacb039270348c5d4f667fa7aa08028aa1a28a4cf02714741efb22436296`.
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos3 adapter 답안·실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_d3/) · [집계·Wilson 구간·오류 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_d3/choice_counts.json). 답안SHA256 `cf9f6a28e10f550dc2bacc5d50d364cd21540778ddc06d61a53578ac35fce96f`.
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos2r adapter 답안·실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_d3/) · [집계·Wilson 구간·오류 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_d3/choice_counts.json). 답안SHA256 `c3d84c60037aced8b3361432139a6d60d55009e4ce55451668d398efde0193cf`.

기존 개발/회귀 자료이며 새 독립 보류720개 검증은 완료되지 않았다. D3 전체가 끝났다는 것이 일반 D·어려운 H·혼합 E·원본 비교군 전체 완료를 뜻하지 않는다. 기존 혼합 문장에서 발견된 정상 요청 손실도 그대로 유지한다. 모델 정확도와 같은 모델 엔진 속도를 구분하고 속도를 직접 비교하지 않는다.
GPU 서버 A 기존 실행기는 일반 D를 수행하며 관측시 준비된7개가 대기한다. GPU 서버 B의 기존 Spark 학습과 뒤 예약을 유지하며 새 실행기·중단·중복·새 결제·모델 삭제는 없다.

## 수정 직전 백업

- [program/research/daily_rag_slm/_backup/2026-10-08_171630_qat_d3_five_variants/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_171630_qat_d3_five_variants/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_171630_qat_d3_five_variants/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_171630_qat_d3_five_variants/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_171630_qat_d3_five_variants/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_171630_qat_d3_five_variants/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_171630_qat_d3_five_variants/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_171630_qat_d3_five_variants/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_171630_qat_d3_five_variants/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_171630_qat_d3_five_variants/log.md)
