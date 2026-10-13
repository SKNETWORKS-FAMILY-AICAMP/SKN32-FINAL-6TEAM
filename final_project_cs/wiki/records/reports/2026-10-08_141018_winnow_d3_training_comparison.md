# Winnow-E4B (Jev 계열) — 원본과 우리 여행 학습판 D3 비교

Jev 계열 모델 중 Winnow-E4B의 동일 D3에서 우리 여행 학습판은 원본보다 정상 요청 정답이 95/120에서 109/120으로 늘고 잡담 오지목이 27/240에서 0/240으로 줄었다. 형식 실패는 13/360에서 0/360이다. 한 번의 개발/회귀 시험이며 나머지 세트·반복·독립 보류 자료 검증 전 제품 채택을 확정하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 동일 문항·정답·입력·실행 조건 검증 | 완료 | 360/360 = 100% |
| 우리 학습판 추가 시험 5종 | 진행 | 1/5 = 20% |

| 지표 | 우리 여행 학습 없음 원본 | 우리 여행 학습판 |
|---|---|---|
| 정상 요청 정답 | 95/120 = 79.17% | 109/120 = 90.83% |
| 잡담 오지목 | 27/240 = 11.25% | 0/240 = 0.00% |
| 잡담 정답(null), 실패 포함 | 203/240 = 84.58% | 240/240 = 100% |
| 형식 실패 | 13/360 = 3.61% | 0/360 = 0.00% |

## 조건·통계·한계

같은 Q8_0 기반 가중치, 입력 문항·정답·평가 코드 해시, llama.cpp 4ebdf2c를 확인했다. 우리 학습판의 시작 기록에는 보관한 어댑터 SHA256이 있고 실제 실행 명령의 --lora 지정을 확인했다. 360개 응답·해석이 완료됐으므로 이전 구조 검사만 통과한 상태에서 실제 엔진 평가 완료로 변경했다. 원본 오류13개(정상3·잡담10)는 오답으로 처리하며 분모에서 빼지 않았다. 오지목27개와 잡담 형식 실패10개를 혼동하지 않는다.

같은 문항에서 정상 요청 원본만 정답0, 학습판만 정답14; 양측 정확검정 p=0.00012207031. 잡담 원본만 정답0, 학습판만 정답37; p=1.4551915e-11. 이는 고정된 개발 자료의 같은 문항 비교이며 일반 질의 전체의 우열이나 독립 보류 성능을 뜻하지 않는다.

다른 개발 세트·어려운 함정·혼합 문장과 독립 보류 자료, 반복 검증이 남아 있다. 원본 보존·별도 어댑터 학습은 완료했고 제품 채택은 보류한다. 모델 정확도 비교이며 엔진 속도 비교는 하지 않았다.

[분자·분모·같은 문항 검정 JSON](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_vs_oos_d3_2026-10-08_141018.json) · [원본 답안 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_d3/verification.json) · [학습판 답안 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_d3/verification.json).

GPU 서버 A는 다음 D 평가 실행, 준비된 D2/H/MX 세 작업 대기를 확인했다. GPU 서버 B는 Spark 학습 실행과 기존 두 학습 예약 및 다운로드 준비 후보 한 개를 유지한다. 다운로드 준비 후보의 공간은 직전에 재확인한다. 실행기를 추가하거나 작업을 중단하지 않았다.

## 수정 직전 백업

- [program/research/daily_rag_slm/_backup/2026-10-08_141100_winnow_d3_comparison/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_141100_winnow_d3_comparison/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_141100_winnow_d3_comparison/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_141100_winnow_d3_comparison/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_141100_winnow_d3_comparison/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_141100_winnow_d3_comparison/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_141100_winnow_d3_comparison/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_141100_winnow_d3_comparison/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_141100_winnow_d3_comparison/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_141100_winnow_d3_comparison/log.md)
