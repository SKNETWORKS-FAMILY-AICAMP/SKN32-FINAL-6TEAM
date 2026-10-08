# Gemma12B 배포 원본 H 완료 — 2026-10-08

우리 자료로 추가 학습하지 않은 Gemma-4-12B-it Q4_K_M(개발사 지시 학습)의 어려운 문장 시험을 회수했다. 정상 요청은 잘 맞췄지만 요청 없는 문장을 잘못 지목하는 비율도 높으므로 이 결과만으로 채택하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 1316/1316 = 100% |
| 정상 요청 정답 | 실측 | 453/461 = 98.26% |
| 요청 없음 오지목 | 실측 | 374/855 = 43.74% |
| 예정 다섯 묶음 | 진행 | 1/5 = 20% |

## 원본·조건·검증

요청 없음855개는 정답481개와 오지목374개다. 미완료·호출 오류·해석 실패0이며 실패나 미완료 문항을 분모에서 빼는 처리를 하지 않았다.

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/d_test_h_backlog_g12bbase.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/started.json) · [유형별 계수·구간](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/h_counts.json) · [직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/verification.json).

답안 SHA256은 GPU 서버 A 원본과 같은 `89d099fb7d219298306fbe3da1e98d8218f4b9cac94e7d38cbd7163a8fc1dd62`다. 고정 입력 해시와 실행 당시 입력 해시가 같고 문항 ID·정답·유형을 대조했다. JSON 출력은 단일 번호 또는 null 계약으로 판정했다. 독립 직접 계수에서도 정상/요청 없음 분모·정답·오지목이 같았다. llama.cpp commit4ebdf2c, 모델 실행1회, 기존 개발/회귀 문항이다.

Wilson 구간은 문항별 구간이며 같은 일정 문항 간 상관을 제거하지 않는다. 반복 모델 실행·새 독립 보류 검증을 대신하지 않는다. 토큰 확률을 말로 한 확신도와 같다고 해석하거나 다른 모델·경로의 지연을 같은 모델 엔진 속도로 비교하지 않는다. 정상 요청 점수 하나만으로 전체 상위권이나 제품 채택을 확정하지 않는다. 모델 이름12B를 기본 소형 기준약8B 이하와 혼동해 파인튜닝 후보로 자동 선정하지 않는다.

## 후속 작업·문서·백업

GPU 서버 A의 같은 지속 실행기가 다음 Gemma12B 혼합 문장 시험을 실행하며 준비된 평가8개가 남았다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 기존 본 학습을 계속하며 뒤4개 학습이 예약돼 있다.2개는 기존 기반,2개는 자동 다운로드 준비가 필요하다. 다음 다운로드 직전 공간을 다시 확인한다. 실행기 추가·중복 시험·진행 중 작업 중단·모델 삭제·새 결제는 하지 않았다.

일일 연구 Markdown/JSON·GPU 대기열 상태·평가 wiki·cs wiki log에 같은 근거를 연결했다. 이전 날짜별 원본 리포트는 수정하지 않았다. 수정 직전 판의 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_112247_gemma12b_h_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_112247_gemma12b_h_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_112247_gemma12b_h_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_112247_gemma12b_h_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_112247_gemma12b_h_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_112247_gemma12b_h_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_112247_gemma12b_h_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_112247_gemma12b_h_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_112247_gemma12b_h_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_112247_gemma12b_h_completion/log.md)
