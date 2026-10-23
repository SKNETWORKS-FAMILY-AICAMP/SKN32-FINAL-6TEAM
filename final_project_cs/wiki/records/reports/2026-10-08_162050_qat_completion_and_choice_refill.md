# QAT 평가 완료와 누락 선택 시험 보충

[실측] QAT 여행 학습판의 새 평가2건·5,330개를 보관했다. 정상 요청 정답과 요청 없음 오지목을 함께 대조했고 합격·반복·독립 보류 검증 전 채택하지 않는다. 입력이 준비된 누락 비교5개를 같은 실행기에 보충했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·전체 문항 검증 | 완료 | 5,330/5,330 = 100% |
| 오류·해석 실패 | 원문·분모 보존 | 0/5,330 = 0.00% |
| 누락 시험 예약 | 완료 | 5/5 = 100% |

## 같은 QAT 원본과 여행 학습판

| 시험 | 항목 | 우리 학습 없는 원본 | 우리 여행 학습판 |
|---|---|---:|---:|
| e4bqat_oos2_mx | 정상 요청 정답 | 978/1,033 = 94.68% | 939/1,033 = 90.90% |
| e4bqat_oos2_mx | 요청 없음 오지목 | 207/974 = 21.25% | 65/974 = 6.67% |
| e4bqat_oos3_h | 정상 요청 정답 | 424/461 = 91.97% | 425/461 = 92.19% |
| e4bqat_oos3_h | 요청 없음 오지목 | 489/855 = 57.19% | 230/855 = 26.90% |

e4bqat_oos2_mx 대조 정상990/1033에서 혼합939/1033로4.94%p 손실이다. 일정별95% 구간3.42~6.50%p, 사전 합산1/4 기준 통과다. 세부 기준은 원본 집계에 보존한다.
자연 작성 혼합239개는 정상92/93·요청 없음 오지목11/146이다. 코드 조합1,768개와 분리한다. 전체 E 혼합2,007개를 전부 자연 자유 문장이라고 부르지 않는다.


입력·전체 ID·정답·유형·실행 코드·엔진4ebdf2c·기반 가중치 해시가 원본과 같다. 어댑터 해시는 실제 등록 내용과 대조했다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분한다. 오류·미완료를 분모에서 빼지 않는다. 모델별 실행1회·기존 개발/회귀 자료이며 속도 직접 비교나 독립 고객 표본으로 해석하지 않는다.
[같은 문항의 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_162050_qat_completion_and_choice_refill_paired.json). 정확 검정은 일정별 상관·반복 편차·다중 비교·새 보류 검증을 대신하지 않는다. 보류240개 정상+480개 요청 없음은 작성·검수·중복 검사·해시 고정이 필요하며 최종 채택을 보류한다.

## 답안·재현 도구·백업

- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos2 adapter 답안·로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_mx/) · [집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_mx/mx_counts.json) · [직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_mx/verification.json). 답안 원격/로컬 SHA256`46ad12393811a9bcfc5e5fcafc505242b76ce360ea50334f4963f7082065fbdb`.
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos3 adapter 답안·로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_h/) · [집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_h/h_counts.json) · [직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos3_h/verification.json). 답안 원격/로컬 SHA256`4ae572ec79c96d0a07729a61604546d235ab6d5ac6d4dda29bcff07ef4caf1f9`.

관측2026-10-08T07:16:03.055835+00:00 기준 GPU 서버 A는 기존 평가를 수행하고 준비된7개가 대기한다. 원본 QAT D1개와 oos1/oos2/oos3/oos2r D3각1개·총4,175문항을 새 이름으로 추가했다. 등록은 완료가 아니며 완료·실패·실행 중 작업을 재시작하지 않는다.
[manifest 수정 직전 백업·원자적 교체·입력 및 어댑터 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_choice_refill_hb1612.json). 원본 모델 전체 해시를 이번 준비에서 재계산한 것은 아니며 기존 검증된 파일을 사용했다. 새 모델 다운로드·기존 모델 삭제·추가 실행기·결제는 없다.
GPU 서버 B는 기존 Spark 학습과 기존 기반으로 준비된4개 레시피·다운로드/공간 재확인이 필요한1개 후보를 유지한다. B56와B57을 중복 실행하지 않는다.
Oracle ARM 최근300.07초 작업CPU는 두 코어 전체 대비89.79%, host busy90.21%, steal0.17%다. 답안52/360개로 진행 중이며24시간 유지나 cs 전체 배포 완료를 주장하지 않는다.
[예약 재현 도구](../../../../program/scripts/plan_qa_bench/server/queues/refill_qat_choice_20261008.py) · [로컬 회수 검증 도구](../../../../program/scripts/plan_qa_bench/record_qat_completion_batch.py). 예약 도구는 등록 중복을 거부하므로 같은 예약을 반복 실행하지 않는다.

수정 직전에 보관한 이전 상태와 wiki를 연결한다. 과거 답안·실행 메타데이터·리포트는 수정하지 않았다.

- [program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_162050_qat_completion_and_choice_refill/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_162050_qat_completion_and_choice_refill/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_162050_qat_completion_and_choice_refill/slm-model-evaluation.md)
- [final_project_cs/wiki/operations/_backup/2026-10-08_162050_qat_completion_and_choice_refill/gpu-work-queue.md](../../../../final_project_cs/wiki/operations/_backup/2026-10-08_162050_qat_completion_and_choice_refill/gpu-work-queue.md)
- [final_project_cs/wiki/_backup/2026-10-08_162050_qat_completion_and_choice_refill/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_162050_qat_completion_and_choice_refill/log.md)
