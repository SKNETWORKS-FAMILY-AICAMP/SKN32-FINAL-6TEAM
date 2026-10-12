# QAT 선택 시험 회수와 누락 회귀 평가 예약

QAT 원본 D와 여행 학습판 D3 두 판의 답안을 보관하고 실패를 분모에 남겼다. 관측 대기2건에 누락 D/D2 평가8건을 보충해 일반 정상 요청 회귀와 요청 없음 오지목을 함께 확인한다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·전체 문항 검증 | 완료 | 3,455/3,455 = 100.00% |
| 실패·해석 불가 | 원문·분모 보존 | 17/3,455 = 0.49% |
| 누락 평가 예약 | 완료 | 8/8 = 100% |

## 같은 QAT 기반의 직접 선택 D3

| 모델 역할 | 정상 요청 정답 | 요청 없음 오지목 | 오류·해석 실패 |
|---|---:|---:|---:|
| 우리 여행 추가 학습 없는 원본 | 102/120 = 85.00% | 22/240 = 9.17% | 1/360 |
| 우리 여행 학습판 oos1 | 108/120 = 90.00% | 0/240 = 0.00% | 0/360 |
| 우리 여행 학습판 oos2 | 108/120 = 90.00% | 0/240 = 0.00% | 0/360 |

입력·전체 문항 ID·정답·유형·실행 코드·엔진·기반 가중치 해시가 같다. 등록된 어댑터 해시를 대조했다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분한다. 학습판별1회 실행이며 서로 다른 혼합 문장 시험에서 발견된 정상 요청 손실을 무효화하지 않는다.
[같은 문항 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_170810_qat_choice_completion_and_regression_refill_paired.json). 반복 편차·독립 보류·다중 비교를 대신하지 않으며 최종 순위·제품 채택은 보류한다.

## 원본 D의 전체 실패 보존

정상 요청 정답730/883 = 82.67%, 기존 일정 항목 선택 없음 오지목76/1,786 = 4.26%다. 전체2,735개 중 단일 선택2,669개·복합 진단66개를 분리한다. 실패17개(정상12·항목 없음3·복합2)는 원문과 해당 분모에 보존했다. 형식 실패를 실제 오지목 계수에 합하거나 배열 출력을 정답으로 바꾸지 않는다.

## 원본 기록·예약·자원

- [Gemma-4-E4B-it QAT Q4_0 original D 답안·직접 검증·실패 원문](2026-10-08_170613_e4bqat_original_d-completion.md).
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter D3 답안·직접 검증·실패 원문](2026-10-08_170616_e4bqat_oos1_d3-completion.md).
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos2 adapter D3 답안·직접 검증·실패 원문](2026-10-08_170627_e4bqat_oos2_d3-completion.md).

GPU 서버 A 실행기PID342497를 유지했다. 원자적 manifest 갱신으로 여행 학습판 oos1/oos2/oos3/oos2r의 D·D2 각각1개, 총8개·14,940문항을 예약했다. 2026-10-08T08:05:21.849534+00:00 기준 준비된9개가 대기한다. 등록47개·계획90,155문항은 완료 수가 아니다.
[수정 전 manifest 백업·입력/어댑터 해시·중복 등록 방지](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_regression_refill_hb1703.json). 원본 모델 전체 해시는 이번 준비에서 재계산하지 않고 기존 검증된 파일을 사용했다. 실행 중 작업 중단·추가 worker·새 모델 다운로드·삭제·결제는 없다.
GPU 서버 B는 기존 Spark 학습과 기존 기반으로 실행 가능한4개·다운로드/공간 준비가 필요한1개 예약을 유지한다. B56/B57을 중복 실행하지 않는다.
Oracle ARM 최근300.07초의 두 코어 대비 작업 CPU89.96%, host busy90.11%, steal0.16%다. 24시간 유지나 cs 프로젝트 전체 배포 완료로 해석하지 않는다.
[예약 재현 도구](../../../../program/scripts/plan_qa_bench/server/queues/refill_qat_regression_20261008.py) · [회수 집계 도구](../../../../program/scripts/plan_qa_bench/backlog_choice_report.py) · [기록 검증 도구](../../../../program/scripts/plan_qa_bench/record_qat_choice_refill_summary.py). 예약 재현 도구를 다시 실행하면 중복 등록을 거부한다.

## 수정 직전 백업

- [program/research/daily_rag_slm/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/2026-10-08.md)
- [final_project_cs/wiki/operations/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/gpu-work-queue.md](../../../../final_project_cs/wiki/operations/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/gpu-work-queue.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_170810_qat_choice_completion_and_regression_refill/log.md)
