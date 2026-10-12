# QAT 평가 완료·같은 문항 검증

[실측] QAT 여행 학습판의 새 평가1건·4,014개를 보관했다. 정상 요청 정답과 요청 없음 오지목을 함께 대조했고 합격·반복·독립 보류 검증 전 채택하지 않는다. 기존 실행기와 준비된 대기 평가4개를 유지했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·전체 문항 검증 | 완료 | 4,014/4,014 = 100% |
| 오류·해석 실패 | 원문·분모 보존 | 0/4,014 = 0.00% |

## 같은 QAT 원본과 여행 학습판

| 시험 | 항목 | 우리 학습 없는 원본 | 우리 여행 학습판 |
|---|---|---:|---:|
| e4bqat_oos2r_mx | 정상 요청 정답 | 978/1,033 = 94.68% | 926/1,033 = 89.64% |
| e4bqat_oos2r_mx | 요청 없음 오지목 | 207/974 = 21.25% | 5/974 = 0.51% |

e4bqat_oos2r_mx 대조 정상984/1033에서 혼합926/1033로5.61%p 손실이다. 일정별95% 구간4.06~7.21%p, 사전 합산2/4 기준 통과다. 세부 기준은 원본 집계에 보존한다.
자연 작성 혼합239개는 정상93/93·요청 없음 오지목0/146이다. 코드 조합1,768개와 분리한다. 전체 E 혼합2,007개를 전부 자연 자유 문장이라고 부르지 않는다.


입력·전체 ID·정답·유형·실행 코드·엔진4ebdf2c·기반 가중치 해시가 원본과 같다. 어댑터 해시는 실제 등록 내용과 대조했다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분한다. 오류·미완료를 분모에서 빼지 않는다. 모델별 실행1회·기존 개발/회귀 자료이며 속도 직접 비교나 독립 고객 표본으로 해석하지 않는다.
[같은 문항의 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_165415_qat_completion_verified_paired.json). 정확 검정은 일정별 상관·반복 편차·다중 비교·새 보류 검증을 대신하지 않는다. 보류240개 정상+480개 요청 없음은 작성·검수·중복 검사·해시 고정이 필요하며 최종 채택을 보류한다.

## 답안·재현 도구·백업

- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos2r adapter 답안·로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_mx/) · [집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_mx/mx_counts.json) · [직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos2r_mx/verification.json). 답안 원격/로컬 SHA256`ca8ef1a6562ba1ca52def89d99b64c4eeca2c956bffe1a9d794c765ddb597bce`.

관측2026-10-08T07:53:06.383406+00:00 기준 GPU 서버 A는 기존 평가를 수행하고 준비된4개가 대기한다. 기존 실행기와 준비된 대기 평가4개를 유지했다. 등록은 완료가 아니며 완료·실패·실행 중 작업을 재시작하지 않는다.
새 모델 다운로드·기존 모델 삭제·추가 실행기·결제는 없다.
GPU 서버 B는 기존 Spark 학습과 기존 기반으로 준비된4개 레시피·다운로드/공간 재확인이 필요한1개 후보를 유지한다. B56와B57을 중복 실행하지 않는다.
Oracle ARM 최근300.07초 작업CPU는 두 코어 전체 대비89.79%, host busy90.19%, steal0.16%다. 답안74/360개로 진행 중이며24시간 유지나 cs 전체 배포 완료를 주장하지 않는다.
[예약 재현 도구](../../../../program/scripts/plan_qa_bench/server/queues/refill_qat_choice_20261008.py) · [로컬 회수 검증 도구](../../../../program/scripts/plan_qa_bench/record_qat_completion_batch.py). 예약 도구는 등록 중복을 거부하므로 같은 예약을 반복 실행하지 않는다.

수정 직전에 보관한 이전 상태와 wiki를 연결한다. 과거 답안·실행 메타데이터·리포트는 수정하지 않았다.

완료 회수와 예약 보충을 각각 실제 수행 여부로 기록하도록 도구를 보완했다. 기존 답안·원본 대조·오류 포함 전체 분모를 직접 검증한다. [도구 수정 직전 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_164453_optional_refill_evidence/record_qat_completion_batch.py).

- [program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_165415_qat_completion_verified/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_165415_qat_completion_verified/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_165415_qat_completion_verified/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_165415_qat_completion_verified/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_165415_qat_completion_verified/log.md)
