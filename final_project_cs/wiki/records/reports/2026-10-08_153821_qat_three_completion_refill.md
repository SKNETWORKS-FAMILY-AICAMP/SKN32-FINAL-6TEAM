# QAT 새 완료·학습판 비교·대기열 보충

QAT 배포 원본 D3·혼합 문장과 우리 여행 oos1 학습판의 어려운 문장5,690개를 회수했다. 학습판은 어려운 잡담 오지목을 줄였지만 정상 요청도 함께 확인해야 하므로 제품 채택을 보류한다. 기존 어댑터의 누락 QAT 비교6개를 같은 실행기에 보충했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·전체 문항 대조 | 완료 | 5,690/5,690 = 100% |
| 형식 실패 | 원문·분모 보존 | 5/5,690 = 0.09% |
| 추가 QAT 비교 예약 | 완료 | 6/6 = 100% |

## 배포 원본 비교와 학습 효과

| 시험 | 항목 | 비교 기준 | 새 결과 |
|---|---|---:|---:|
| QAT 원본 D3 | 정상 요청 정답 | 103/120 = 85.83% | 102/120 = 85.00% |
| QAT 원본 D3 | 요청 없음 오지목 | 19/240 = 7.92% | 22/240 = 9.17% |
| QAT 원본 MX / user E | 정상 요청 정답 | 960/1,033 = 92.93% | 978/1,033 = 94.68% |
| QAT 원본 MX / user E | 요청 없음 오지목 | 154/974 = 15.81% | 207/974 = 21.25% |
| oos1 학습판 H | 정상 요청 정답 | 424/461 = 91.97% | 422/461 = 91.54% |
| oos1 학습판 H | 요청 없음 오지목 | 489/855 = 57.19% | 90/855 = 10.53% |

원본 D3·혼합 비교 기준은 우리 추가 학습 없는 Q4_K_M 배포판이다. oos1 H 비교 기준은 같은 QAT 가중치의 우리 추가 학습 없는 원본이다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분했다. 입력·전체ID·정답·유형·실행 코드 해시·llama.cpp 4ebdf2c가 같다. 가중치/양자화 변경의 정확도 비교이며 같은 모델 엔진 속도 시험이 아니다.
[같은 문항의 개선·손실·정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_153821_qat_three_completion_refill_paired.json). 각 모델 실행1회이며 일정별 상관·다중 비교·반복 편차를 통제한 최종 우열로 해석하지 않는다.

## 혼합 문장 범위·실패·채택 한계

혼합2,007개와 대조2,007개다. 각 부류 정상1,033개·요청 없음974개이며 E 전체를 자연 자유 문장이라고 부르지 않는다. 자연 작성 혼합239개와 코드 조합1,768개를 분리한다. 자연 작성에도 아직 사람 정답 검수가 필요하다. 기존 개발/회귀 자료이고 독립 보류240+480개는 작성·검수·해시 고정 후 별도 최종 검증해야 한다.0/720 완료 상태다.
QAT 원본 자연 작성 혼합 정상 정답91/93 = 97.85%, 요청 없음 오지목35/146 = 23.97%. 사전 합산2/4 기준 통과, 세부 MX3·MX4·MX5a는 실패했다. 정상 정답 개선과 오지목 증가가 함께 있으므로 Q4_K_M보다 전체적으로 우수하다고 채택하지 않는다.
혼합 형식 실패0개·대조 요청 없음 형식 실패4개다. D3의 정상 요청 형식 실패1개와 합쳐5개다. 단일 번호/null 계약에서 배열을 출력한 원문을 보존했으며 배열에서 번호 하나를 골라 정답으로 고치지 않았다. 실패와 실제 오지목은 따로 표시하되 전체 정답률에서는 실패도 오답이다.

## 답안·직접 계수·역할 기록

- [Gemma-4-E4B-it QAT Q4_0 original 답안·로그·집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d3/) · [해시·문항·직접 계수 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d3/verification.json). 원격/로컬 답안 SHA256`44bca575d39ae68eb0917c154bcbd423427da95c27aeee57efe54f90be820318`.
- [Gemma-4-E4B-it QAT Q4_0 original 답안·로그·집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_mx/) · [해시·문항·직접 계수 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_mx/verification.json). 원격/로컬 답안 SHA256`149be4a1435c642368b3868e5ecd4e1d77819c4c9c9b205e7fc532b9eb05ea02`.
- [Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter 답안·로그·집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_h/) · [해시·문항·직접 계수 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_h/verification.json). 원격/로컬 답안 SHA256`4fc2c0359be7c7e9bdb36f8bcd00ee674c681fe4c2a65fb5626939c573a15854`.

oos1 실행 기록의 개발사 설명에는 원본에서 복사한 “우리 학습 없음” 문구가 남아 있었다. 실제 어댑터 인자·해시·our_training=True를 확인하고 파생 집계의 개발사 설명을 수정 직전 백업 후 바로잡았다. 원본 started.json·답안·과거 리포트는 수정하지 않았다. 새 예약의 개발사 설명도 우리 어댑터 학습과 분리했다.

## 예약·자원·재개

GPU 서버 A 등록34개·71,040문항이며 oos1 혼합 평가가 실행 중이고 준비된6개가 기다린다(관측2026-10-08T06:34:59.527270+00:00). oos2·oos3·oos2r 각H/MX6개를 새 이름으로 예약했다. 기존oos1 H가 성공한 동일 QAT 기반에서 세 어댑터의516개 텐서 이름·형태·자료형이 모두 일치했다. 각 새 판의 실제 로딩·정확도 성공을 미리 주장하지 않으며 첫 실행 결과에서 확인한다. 기존 Q4_K_M 완료를 QAT 시험 완료로 옮기지 않는다.
[원자적 manifest 교체·수정 직전 원격 백업·입력/어댑터 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_adapter_refill_hb1527.json). 기존 실행기는 살아 있으며 추가 실행기·중복 평가·작업 중단·새 모델 다운로드·기존 모델 삭제·새 결제가 없다.
GPU 서버 B는 기존 Spark 본 학습과 뒤5개 예약을 유지한다.4개는 기존 입력을 쓰고1개는 다운로드/공간 확인이 필요하다. Oracle ARM 관측2026-10-08T06:28:01.167961+00:00 최근300.07초 작업CPU는 두 코어 전체 대비88.89%, host busy90.25%, steal0.29%다. 목표 이상 연속 표본3110.70초이며24시간 유지 증거는 아니다. 답안25/360개·메모리8,948,330,496바이트(파일 캐시 포함)·공간54,412,320,768바이트다.
다음 확인에서는 새 어댑터 로딩/실패를 확인하고 완료 답안부터 회수한다. 실패는 원인 수정 없이 반복하지 않는다. 원본 비교군 완료·반복·별도 보류 검증 전 제품 모델 승격을 하지 않는다.

## 수정 직전 백업

- [program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_h/_backup/2026-10-08_153821_qat_three_completion_refill/h_counts.json](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_h/_backup/2026-10-08_153821_qat_three_completion_refill/h_counts.json)
- [program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_h/_backup/2026-10-08_153821_qat_three_completion_refill/h_report.md](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_h/_backup/2026-10-08_153821_qat_three_completion_refill/h_report.md)
- [program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_153821_qat_three_completion_refill/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_153821_qat_three_completion_refill/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_153821_qat_three_completion_refill/slm-model-evaluation.md)
- [final_project_cs/wiki/operations/_backup/2026-10-08_153821_qat_three_completion_refill/gpu-work-queue.md](../../../../final_project_cs/wiki/operations/_backup/2026-10-08_153821_qat_three_completion_refill/gpu-work-queue.md)
- [final_project_cs/wiki/_backup/2026-10-08_153821_qat_three_completion_refill/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_153821_qat_three_completion_refill/log.md)
