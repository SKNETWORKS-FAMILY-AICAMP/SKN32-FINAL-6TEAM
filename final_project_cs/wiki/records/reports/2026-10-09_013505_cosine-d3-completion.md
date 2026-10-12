# cosine 학습판 D3 두 평가 완료·보관

확인일: 2026-10-09 01:35:05 KST. 새로 완료된 cosine 학습판의 Q4_K_M D3와 QAT Q4_0 D3 답안을 회수하고 집계했습니다. 완료된 두 세트는 모두 D3이며 H 완료로 해석하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 완료 답안 회수 | 완료 | 720/720 = 100% |
| 원격·로컬 SHA 및 크기 | 일치 | 2/2 = 100% |
| 고정 ID·정답·유형 검사 | 통과 | 720/720 = 100% |

| 기반 양자화 | 정상 요청 정답 | 요청 없음 오지목 | 실패·해석 불가 |
|---|---|---|---|
| Q4_K_M + 우리 cosine 어댑터 | 105/120 = 87.50% | 4/240 = 1.67% | 0/360 = 0% |
| QAT Q4_0 + 우리 cosine 어댑터 | 105/120 = 87.50% | 2/240 = 0.83% | 0/360 = 0% |

고정 문항의 입력 해시·전체 ID·정답·유형을 기존 도구로 확인했습니다. 두 판 모두 Gemma-4-E4B-it 개발사 Instruct 배포판을 기반으로 우리 여행 자료의 동일 cosine 어댑터를 적용했고 QAT는 해당 기반 양자화에만 해당합니다. 실패·미완료를 분모에서 빼지 않았습니다. QAT 답안은 같은 QAT 원본과 실행 입력·엔진·기반 및 어댑터 해시까지 대조했습니다. Q4_K_M의 과거 원본 기록에는 기반 SHA 필드가 없어 이 후속 작업에서 과거 기록을 고치거나 엄격한 원본 대조 완료로 표시하지 않았습니다.

이번 두 결과는 기존 개발·회귀 세트의 각 1회 실행입니다. 독립 보류·반복·다른 세트 완료 전 양자화 우열·모델 채택·상용화 결론을 내리지 않습니다.

부모의 01:30:48 KST 최종 관측에서 GPU 서버 A는 GPU 91%·3,480MiB, cosine D 1,905/2,735개, 기존 포함 완료 49개·실행 1개·준비 대기 7개였습니다. GPU 서버 B는 GPU 100%·12,899MiB, FINCH 20/654회 갱신이며 B57/B58 대기 프로세스가 살아 있었습니다. 순간 측정이며 지속 사용률 증명으로 해석하지 않습니다. 진행 중 작업을 중단하거나 새 GPU 작업을 띄우지 않았습니다.

날짜별 GPU 상태를 수정 직전에 _backup에 복사하고 최종 관측·이번 완료 답안을 연결했습니다. 이전 관측도 상태 JSON 안에 보존했습니다. 공통 날짜 기록·색인·quality/GPU wiki/log는 이 후속 작업에서 수정하지 않았습니다.

## 근거·백업

- [두 답안 원문 보관](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/cosine_D3_completed_20261009_0132)
- [원격 SHA·크기 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/cosine_D3_completed_20261009_0132/archive_verification.json)
- [Q4_K_M 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_cosine_s20261012_d3/choice_counts.json)
- [QAT Q4_0 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_cosine_s20261012_d3/choice_counts.json)
- [QAT 기반 원본과 문항별 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_cosine_s20261012_d3/matched_original.json)
- [최종 A 관측](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_parent_20261009_0130.json)
- [최종 B 관측](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_snapshot_parent_20261009_0130.json)
- [현재 GPU 상태](../../../../program/research/daily_rag_slm/gpu_backlog_2026-10-09.json)
- [상태 수정 직전 백업](../../../../program/research/daily_rag_slm/_backup/2026-10-09_013505_gpu_final_observation/gpu_backlog_2026-10-09.json)
