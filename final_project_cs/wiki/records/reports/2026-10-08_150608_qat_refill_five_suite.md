# Winnow 추가 다섯 시험 회수와 QAT 대기열 보충

Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로학습)의 추가 다섯 시험9,425개를 모두 회수했다. 혼합 오지목20/974=2.05%는 사전1% 이하 기준을 넘으므로 제품 채택은 보류한다. 기존 QAT 기반의 누락 비교를 보충했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 추가 답안 전체 회수 | 완료 | 9,425/9,425 = 100% |
| 다섯 묶음 | 완료 | 5/5 = 100% |
| 혼합 합산 기준 | 일부 통과 | 3/4 = 75% |
| GPU 서버 A 다음 일감 | 15시01분 관측 | 5/5개 준비 = 100% |

## 혼합 문장과 사전 기준

혼합2,007개와 대조2,007개를 합한4,014개다. 혼합 실제 요청1,000/1,033=96.81%, 혼합 요청 없음 오지목20/974=2.05%, 오류·해석 실패·미완료0이다. 오지목 상한1%를 넘었으며 세부 MX4도5/121=4.13%로 해당 상한3%를 넘었다. 정상 요청 대조1,006/1,033에서 혼합1,000/1,033으로 손실0.58%p, 일정별95% 구간-0.20~1.27%p다.

같은 Q8_0 기반·고정 입력·코드·엔진의 우리 학습 없는 Winnow-E4B 원본은 혼합 요청945/1,033, 오지목176/974, 전체 형식 실패42/4,014였다. 학습판은1,000/1,033·20/974·0/4,014다. 실패를 분모에 보존했다. 각1회 실행·기존 개발/회귀 자료이며 독립 보류 검증·반복·전체 원본 비교군 순위를 대신하지 않는다.

[혼합 답안·실행 조건·직접 계수 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_mx/) · [원본/학습판 같은 문항 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_150608_qat_refill_five_suite_paired.json).

## QAT 기반 누락 비교와 실행 유지

QAT 원본의 기존 D는 과거 실행 로그의 같은 모델 blob과2,735개 답안으로 확인했고 다시 예약하지 않았다. 원본 D3만 추가했다. 기존 oos1 어댑터는 같은 QAT 기반에서 D2·D3·D를 실행한 기록이 있으며 D2,735개·오류0으로 호환을 확인했다. QAT 기반 oos1 H·MX 완료는 이번 QAT 이름의 답안 목록과 해당 실행 스크립트 범위에서 확인되지 않아1,316개와4,014개를 추가했다. 다른 이름의 과거 실행을 모두 배제한 검색은 아니며 발견되면 입력·모델 해시를 대조한다. 모델·어댑터·고정 입력 해시를 기록하고 양자화에 따른 회귀를 맞춘 조건으로 검증한다. 새 학습·다운로드·기존 D 반복은 아니다.

원격 manifest 직전 백업과 원자적 교체로 보충했으며 실행기를 추가하거나 현재 추론을 중단하지 않았다. 총28개55,050문항 예약이다. 15시01분 관측 QAT 원본 D2가848/1,000개 저장, 준비된 후속5개였다. 실제 GPU 모델 연결·추론 로그도 확인했다.

[원본 D3 등록·백업·GPU 실행 로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_d3_refill_1459.txt) · [oos1 QAT 누락 평가·호환·해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_oos1_missing_refill_1501.json).

GPU 서버 B는 Spark 본 학습과 뒤4개 기존 입력 학습·1개 다운로드/공간 확인 후보를 유지한다. B57은 B56 완료 뒤 실행한다. Oracle ARM은14시57분 최근300.07초 CPU89.62%, host busy90.28%, steal0.17%, 작업 메모리8,968,011,776바이트(파일 캐시 포함), 공간54,411,599,872바이트, 답안10/360개·서비스 재시작0회다. 목표 이상 연속 표본1,295.29초이며24시간 유지 증거는 아니다.

## 준비 도구 오류·문서·백업

첫 추가 예약 준비에서 계수 자료형 오류가 있었으나 manifest 변경 전에 멈췄고 bool 계수로 고친 뒤 등록했다. 비교 문서 생성에서도 폴더 접미사 누락을 발견해 파일 변경 전에 고쳤다. 실행 중 GPU·Oracle 추론에는 영향이 없었다. 혼합 완료 기록 도구는 B57을 포함한 현재 후속 예약 수로 설명을 고쳤고 문법 검사를 통과했다.

[기록 도구 수정 직전 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1500_mx_followup_counts/record_backlog_mx_completion.py). 기존 날짜별 원본은 수정하지 않았다. 상태·wiki 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_150608_qat_refill_five_suite/2026-10-08.md)
- [final_project_cs/wiki/operations/_backup/2026-10-08_150608_qat_refill_five_suite/gpu-work-queue.md](../../../../final_project_cs/wiki/operations/_backup/2026-10-08_150608_qat_refill_five_suite/gpu-work-queue.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_150608_qat_refill_five_suite/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_150608_qat_refill_five_suite/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_150608_qat_refill_five_suite/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_150608_qat_refill_five_suite/log.md)
