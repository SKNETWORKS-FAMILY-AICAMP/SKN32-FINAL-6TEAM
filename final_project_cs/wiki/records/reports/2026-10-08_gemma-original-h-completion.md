# Gemma E4B 원본 H 완료·형식 실패 보존 — 2026-10-08

우리 자료로 학습하지 않은 Gemma-4-E4B-it Q4_K_M의 H평가를 보관했다. 개발사 지시 학습은 있음으로 구분했다. 같은 원본 비교군의 전체 시험과 반복 검증 전에는 최종 순위를 확정하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·정답 일치 | 완료 | 1,316/1,316 = 100% |
| 정상 요청 정답 | 실측 | 433/461 = 93.93% |
| 함정·잡담 오지목 | 실측 | 402/855 = 47.02% |
| 형식 실패 | 보존 | 1/1,316 = 0.08% |

요청 없음 분모855개는 정답452개·오지목402개·형식 실패1개로 이루어진다. 실패 문항951127은 `{"item": [31]}`을 출력했다. 계약은 단일 번호 또는 null이므로 배열을 유효한 번호나 null로 재해석하지 않았다. 실패·미완료는 전체 분모에서 빼지 않았다.

[원본 답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/d_test_h_backlog_e4bbase.jsonl) · [집계·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/h_counts.json) · [집계 표](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/h_report.md) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/started.json).

답안 SHA256은 GPU 서버 A 완료 원본과 동일한 `03690687044e0ceed2dac04b12da2d22fb7152d9d3055498570ab162db63a214`이다. llama.cpp commit4ebdf2c·기존 고정 세트·모델 실행1회이며 Wilson 구간은 문항별 구간이라 동일 일정의 상관을 반영하지 않는다. 새 독립 보류 자료와 반복 측정을 대신하지 않는다.

기존 지속 실행기는 다음 원본 Gemma 혼합 요청 평가를 실행한다. 새 실행기를 띄우거나 진행 중 GPU 서버 B 학습을 중단하지 않았다. 형식 실패1개 때문에 같은 H 전체를 반복하지 않았다. 실패 원문을 별도 회귀 진단으로 보존했으며 모델 정확도 개선이나 채택으로 표시하지 않았다.

이번 확인에서 새로 완료·회수한 것은 [FrogNano 원본 MX](2026-10-08_frog-original-mx-completion.md)와 이 Gemma H이다. 서로 다른 세트의 점수를 동일 조건의 모델 간 순위로 비교하지 않는다. 관련 정본과 cs wiki log·일일 기록을 연결했다.

수정 전 판의 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_103915_e4b_h_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_103915_e4b_h_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_103915_e4b_h_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_103915_e4b_h_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_103915_e4b_h_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_103915_e4b_h_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_103915_e4b_h_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_103915_e4b_h_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_103915_e4b_h_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_103915_e4b_h_completion/log.md)
