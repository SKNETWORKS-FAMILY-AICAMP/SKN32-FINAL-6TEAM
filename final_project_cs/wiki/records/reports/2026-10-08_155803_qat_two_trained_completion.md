# QAT 여행 학습판 두 평가 완료

[실측] QAT 기반의 여행 oos1 학습판 혼합 문장과 oos2 학습판 어려운 문장5,330개를 보관했다. oos1은 혼합 정상 요청의 손실이 커 사전 합산 기준1/4 통과로 채택하지 않는다. oos2 H는 정상 요청과 잡담 오지목의 균형을 계속 비교한다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·해시·전체 ID 대조 | 완료 | 5,330/5,330 = 100% |
| 오류·해석 실패 | 실측 | 0/5,330 = 0% |

## 같은 QAT 원본 대비 학습 효과

| 시험 | 항목 | 우리 학습 없는 QAT 원본 | 우리 여행 학습판 |
|---|---|---:|---:|
| oos1 혼합 / E | 정상 요청 정답 | 978/1,033 = 94.68% | 865/1,033 = 83.74% |
| oos1 혼합 / E | 요청 없음 오지목 | 207/974 = 21.25% | 28/974 = 2.87% |
| oos2 어려운 문장 H | 정상 요청 정답 | 424/461 = 91.97% | 433/461 = 93.93% |
| oos2 어려운 문장 H | 요청 없음 오지목 | 489/855 = 57.19% | 186/855 = 21.75% |

각 기준 원본의 전체 직접 계수는 해당 보관 폴더를 따른다. 입력·문항·정답·유형·실행 코드·엔진4ebdf2c·QAT 기반 가중치 해시를 일치 확인하고, 적용 어댑터 해시를 대조했다. 각 실행1회·기존 개발/회귀 자료다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분한다. 모델 정확도 변화이며 같은 모델 엔진 속도 우열 시험이 아니다.

oos1은 대조 정상996/1,033에서 혼합865/1,033으로12.68%p 손실, 일정별95% 구간10.70~14.78%p다.59개 일정 군집 부트스트랩2,000회·시드7이며 합산 기준1/4, 세부 MX3 실패다. 잡담 개선만으로 채택하지 않는다. 같은 QAT 기반 oos1 H는422/461·오지목90/855였으므로 oos2 H의 정상 정답 증가와 오지목 증가도 함께 기록한다.

자연 작성 혼합239개에서는 정상90/93·요청 없음 오지목0/146이다. 코드로 이어 붙인1,768개와 분리한다. 자연 작성 문항의 사람 정답 검수 전이며 E 전체2,007개를 모두 자연 자유 질의라고 부르지 않는다. 전체 혼합2,007·대조2,007개를 합해4,014개다. H는 정상461·요청 없음855개다. 실패·미완료는 분모에서 빼지 않는다.

[같은 문항 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_155803_qat_two_trained_completion_paired.json)은 실행1회에서의 차이다. 일정 상관·반복 편차·독립 보류 검증을 대신하지 않는다. 최종 모델 순위나 제품 채택을 확정하지 않는다. 별도 보류720개는 아직 작성·검수·해시 고정이 필요하다.

## 원본 답안·검증·역할 정정

- [e4bqat_oos1_mx 답안·로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_mx/) · [집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_mx/mx_counts.json) · [해시·직접 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_mx/verification.json). 원격/로컬 답안 SHA256`8bedebf62ab472638704c8f6a3941cbc15f732538a30b9a492dba6d2c7b4da51`.
- [e4bqat_oos2_h 답안·로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_h/) · [집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_h/h_counts.json) · [해시·직접 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2_h/verification.json). 원격/로컬 답안 SHA256`55a5ea719e6233409258cb81ba27a0eeb4f6690a1d20091c61ee102b0947696c`.

oos1의 원본에서 복사된 개발사 설명 중 “우리 학습 없음” 문구는 파생 집계만 직전 백업 후 바로잡았다. our_training=True와 어댑터 해시를 확인했고 원본 started.json은 보존했다. oos2는 새 어댑터 실제 로딩 뒤1,316개를 완료했다. 준비 단계의 텐서 구조 일치를 정확도 성공으로 쓰지 않았다.

## 이어지는 작업과 자원

관측2026-10-08T06:53:17.718743+00:00 기준 GPU 서버 A는 oos2 혼합을 실행하며 준비된4개가 기다린다. GPU 서버 B는 Spark 여행 학습 중이며 기존 기반의4개 학습 레시피와 다운로드/공간 재확인이 필요한1개 후보를 뒤에 유지한다. 현재 계산·준비 작업·조건 대기를 구분했다. 실행기 추가·중단·재학습·새 결제·기존 모델 삭제는 하지 않았다.

Oracle ARM은 최근300.06초 두 코어 전체 대비 작업CPU89.99%, 기계 busy90.11%, steal0.16%다. 답안41/360개는 진행 중이며 정확도 결론을 내지 않는다. 최근5분 목표를 충족했지만24시간 유지·cs 프로젝트 전체 배포 완료라고 쓰지 않는다.

## 수정 직전 백업

- [program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_mx/_backup/2026-10-08_155803_qat_two_trained_completion/mx_counts.json](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_mx/_backup/2026-10-08_155803_qat_two_trained_completion/mx_counts.json)
- [program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_mx/_backup/2026-10-08_155803_qat_two_trained_completion/mx_report.md](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_mx/_backup/2026-10-08_155803_qat_two_trained_completion/mx_report.md)
- [program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_155803_qat_two_trained_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_155803_qat_two_trained_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_155803_qat_two_trained_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_155803_qat_two_trained_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_155803_qat_two_trained_completion/log.md)
