# Gemma-4-E4B-it QAT Q4_0 original — D 완료

우리 여행 자료로 추가 학습하지 않은 배포 원본의 시험 답안을 회수하고 실패를 보존했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 2,735/2,735 = 100% |
| 정상 요청 정답 | 실측 | 730/883 = 82.67% |
| 항목 선택 없음 오지목 | 실측 | 76/1,786 = 4.26% |
| 실패·해석 불가 | 보존 | 17/2,735 = 0.62% |

## 원본·조건·검증

Gemma-4-E4B-it QAT Q4_0 original(우리 여행 자료로 추가 학습하지 않은 배포 원본)의 D 답안2,735/2,735개를 보관했다. 정상 요청 정답730/883 = 82.67%, 기존 항목 선택 없음 오지목76/1,786 = 4.26%, 형식 실패17개다. 실패·미완료는 분모에서 빼지 않았다.

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d/d_test_d_backlog_e4bqat_original.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d/started.json) · [유형별 집계·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d/choice_counts.json) · [독립 직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_original_d/verification.json).

GPU 서버 A 원본·로컬 사본 SHA256은 `c5bc8426c21ad27ae6de5ae6a1c43f68e5d69fb5982f280665de1e26c01b042c`로 같다. 고정 입력 해시·전체ID·정답·유형 및 정상/항목 없음 독립 직접 계수를 확인했다. 미완료0이며 배열이나 문자열 출력을 번호·null로 고쳐 정답 처리하지 않았다. 개발사 학습 역할 기록은 `Google Instruct release; publisher quantization-aware training; no our-travel additional training`이다.

전체2,735개 중 단일 선택 집계2,669개, 복합 문항66개는 별도 진단이다. 복합 문항을 단일 선택 전체 정확도로 해석하지 않는다.

잡담만의 오지목은 57/1,300 = 4.38%이며 형식 실패2개다. 항목 선택 없음 전체와 잡담만의 분모는 다르다.

## 형식 실패 원문

| 문항 ID | 유형 | 출력 |
|---|---|---|
| 1337 | duplicate_place | `{"item": [8, 31]}` |
| 1361 | tourist_synth_in | `{"item": [37, 41, 42]}` |
| 1494 | tourist_synth_in | `{"item": [18, 36]}` |
| 1524 | confusable_name | `{"item": [10, 34]}` |
| 1607 | tourist_synth_in | `{"item": [8, 31]}` |
| 1627 | confusable_name | `{"item": [20, 38]}` |
| 1918 | tourist_synth_in | `{"item": [26, 33]}` |
| 1936 | nameless_description | `{"item": [16]}` |
| 2064 | tourist_synth_in | `{"item": [27, 32]}` |
| 2115 | compound_intent | `{"item": [9, 10]}` |
| 2267 | tourist_synth_in | `{"item": [3, 4, 5, 6]}` |
| 2476 | tourist_synth_in | `{"item": [9, 36]}` |
| 2537 | chitchat | `{"item": [16, 17, 19, ` |
| 2652 | compound_intent | `{"item": [25, 23]}` |
| 380 | nameless_description | `{"item": [5]}` |
| 893 | chitchat | `{"item": [4, 16, 36]}` |
| 1002 | tourist_synth_in | `{"item": [11, 33]}` |

## 한계·실행 유지·백업

기존 개발/회귀 자료의 모델 실행1회다. 전체 원본 비교군의 모든 시험·반복·독립 보류 검증 전 최종 순위나 제품 채택을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 모델 변경 정확도와 같은 모델 엔진 속도를 구분한다.
GPU 서버 A의 같은 실행기가 다음 평가를 수행하며 입력까지 준비된9개가 대기한다. GPU 서버 B의 기존 학습과 예약을 유지했다. 다음 기반 다운로드 직전 공간을 재확인한다. 중복 실행·실행기 추가·작업 중단·새 결제·모델 삭제는 하지 않았다.

일일 Markdown/JSON·GPU 상태·평가 wiki·cs wiki log에 근거를 연결했다. 기존 원본 기록은 수정하지 않았다. 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_170613_e4bqat_original_d_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_170613_e4bqat_original_d_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_170613_e4bqat_original_d_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_170613_e4bqat_original_d_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_170613_e4bqat_original_d_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_170613_e4bqat_original_d_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_170613_e4bqat_original_d_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_170613_e4bqat_original_d_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_170613_e4bqat_original_d_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_170613_e4bqat_original_d_completion/log.md)
