# Gemma QAT 원본 D2·H 완료

우리 여행 자료로 추가 학습하지 않은 Gemma-4-E4B-it QAT Q4_0 원본의 D2·H2,316개를 회수했고 형식 실패2개를 원문·분모에 보존했다. 같은 문항의 Q4_K_M 원본과 대조했으며 QAT 원본이 더 좋다고 채택하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·전체 문항 대조 | 완료 | 2,316/2,316 = 100% |
| 형식 실패 | 보존 | 2/2,316 = 0.09% |
| GPU 서버 A 다음 일감 | 준비됨 | 3/3개 = 100% |

## 같은 문항의 배포 원본 비교

| 시험 | 항목 | Q4_K_M 원본 | QAT Q4_0 원본 |
|---|---|---:|---:|
| D2 | 요청 없음 오지목 | 69/1000 = 6.90% | 68/1000 = 6.80% |
| H | 정상 요청 정답 | 433/461 = 93.93% | 424/461 = 91.97% |
| H | 요청 없음 오지목 | 402/855 = 47.02% | 489/855 = 57.19% |

두 판은 모두 우리 여행 추가 학습이 없는 배포 원본이다. 개발사 지시 학습·QAT 역할은 우리 추가 학습과 구분한다. 입력 해시·전체 문항ID·정답·유형·코드 해시·llama.cpp 버전4ebdf2c를 맞췄다. 서로 다른 가중치/양자화 배포판의 비교이며 같은 모델 엔진 속도 시험으로 해석하지 않는다. 모델 실행각1회·기존 개발/회귀 문항이며 전체 원본 비교군·반복·독립 보류 검증 전 순위나 제품 채택은 확정하지 않는다.
[같은 문항 개선·손실·정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_151129_qat_original_d2_h_completion_paired.json). 문항별 검정은 일정별 상관·여러 비교와 반복 편차를 통제한 최종 검정이 아니다.

## 형식 실패·보관·검증

두 실패는 호출 오류가 아니라 단일 번호/null 계약에 배열을 출력한 사례다. 배열 중 번호 하나를 골라 정답 처리하지 않았다. 현재16토큰 출력 제한에서 미완성 배열이며 번호 배열이 완성돼도 단일 선택 계약을 위반한다. 실패한 null을 요청 없음 정답으로 세지 않았고 실패와 실제 오지목을 따로 표시한다. 재실행하지 않는다.

| 시험 | 문항 ID | 유형 | 원문 |
|---|---|---|---|
| D2 | 900505 | chitchat_holdout_aihub | `{"item": [10, 16, 26, ` |

[D2 답안·로그·실행 조건·해시/직접 계수 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d2/). GPU 서버 A 원본 SHA256은`a40db4a5e853db2c28331843575e23e3b4aed64ebbb196b0e7d8be456607845e`로 로컬 사본과 같다.

| H | 951127 | hard_N5 | `{"item": [10, 17, 31, ` |

[H 답안·로그·실행 조건·해시/직접 계수 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_h/). GPU 서버 A 원본 SHA256은`68f3f8e2ca5f25c26f336f5c5e274b7937c9aa951797862283ce810688f45ec3`로 로컬 사본과 같다.

## 실행 유지·다음 일감·백업

GPU 서버 A는 기존 실행기로 QAT 원본 MX를 수행하며 원본 D3·oos1 QAT H·MX3개가 준비됐다. GPU 서버 B는 기존 Spark 본 학습과 뒤4개 기존 입력 학습·1개 다운로드/공간 확인 후보를 유지한다. Oracle ARM은 최근300.06초 두 코어 전체 대비CPU89.83%, host busy90.22%, steal0.17%, 메모리8,925,679,616바이트(파일 캐시 포함), 공간54,411,526,144바이트다. 답안14/360개 저장, 재시작0회이며 목표 이상 연속 표본1,895.43초다.24시간 유지 증거는 아니다.
실행기 추가·중복 평가·작업 중단·새 결제·기존 모델 삭제는 하지 않았다. 과거 기록은 수정하지 않았고 새 결과를 해당 wiki와 일일 기록에 연결했다. 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_151129_qat_original_d2_h_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_151129_qat_original_d2_h_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_151129_qat_original_d2_h_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_151129_qat_original_d2_h_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_151129_qat_original_d2_h_completion/log.md)
