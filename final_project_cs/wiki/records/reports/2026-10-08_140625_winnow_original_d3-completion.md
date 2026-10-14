# Jev 계열 모델 중 Winnow-E4B publisher release Q8_0 — D3 완료

우리 여행 자료로 추가 학습하지 않은 배포 원본의 시험 답안을 회수하고 실패를 보존했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 360/360 = 100% |
| 정상 요청 정답 | 실측 | 95/120 = 79.17% |
| 항목 선택 없음 오지목 | 실측 | 27/240 = 11.25% |
| 실패·해석 불가 | 보존 | 13/360 = 3.61% |

## 원본·조건·검증

Jev 계열 모델 중 Winnow-E4B publisher release Q8_0(우리 여행 자료로 추가 학습하지 않은 배포 원본)의 D3 답안360/360개를 보관했다. 정상 요청 정답95/120 = 79.17%, 기존 항목 선택 없음 오지목27/240 = 11.25%, 형식 실패13개다. 실패·미완료는 분모에서 빼지 않았다.

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_d3/d_test_d3_backlog_winnow_original.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_d3/started.json) · [유형별 집계·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_d3/choice_counts.json) · [독립 직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_d3/verification.json).

GPU 서버 A 원본·로컬 사본 SHA256은 `f11b69bdc1d630d585b5035c75ba8a00de33d4b5a64a2fe34f6be23150eba910`로 같다. 고정 입력 해시·전체ID·정답·유형 및 정상/항목 없음 독립 직접 계수를 확인했다. 미완료0이며 배열이나 문자열 출력을 번호·null로 고쳐 정답 처리하지 않았다. 개발사 학습 역할 기록은 `See publisher model card; exact training method not verified in this run`이다.

전체360개 중 단일 선택 집계360개, 복합 문항0개는 별도 진단이다. 복합 문항을 단일 선택 전체 정확도로 해석하지 않는다.

## 형식 실패 원문

| 문항 ID | 유형 | 출력 |
|---|---|---|
| 800108 | synth_chat_A | `{"item": "null"}` |
| 800121 | synth_chat_B | `{"item": "12"}` |
| 800146 | synth_chat_B | `{"item": "null"}` |
| 800154 | synth_chat_B | `{"item": "36"}` |
| 800160 | synth_chat_B | `{"item": "null"}` |
| 800168 | synth_chat_B | `{"item": "22"}` |
| 800186 | synth_chat_B | `{"item": "null"}` |
| 800205 | synth_chat_B | `{"item": "12"}` |
| 800208 | synth_chat_B | `{"item": "30"}` |
| 800216 | synth_chat_B | `{"item": "null"}` |
| 810015 | nameless_description | `{"item": "37"}` |
| 810035 | nameless_description | `{"item": [9]}` |
| 810051 | tourist_synth_in | `{"item": [26, 33]}` |

## 한계·실행 유지·백업

기존 개발/회귀 자료의 모델 실행1회다. 전체 원본 비교군의 모든 시험·반복·독립 보류 검증 전 최종 순위나 제품 채택을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 모델 변경 정확도와 같은 모델 엔진 속도를 구분한다.
GPU 서버 A의 같은 실행기가 다음 평가를 수행하며 입력까지 준비된4개가 대기한다. GPU 서버 B의 기존 학습과 예약을 유지했다. 다음 기반 다운로드 직전 공간을 재확인한다. 중복 실행·실행기 추가·작업 중단·새 결제·모델 삭제는 하지 않았다.

일일 Markdown/JSON·GPU 상태·평가 wiki·cs wiki log에 근거를 연결했다. 기존 원본 기록은 수정하지 않았다. 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_140625_winnow_original_d3_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_140625_winnow_original_d3_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_140625_winnow_original_d3_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_140625_winnow_original_d3_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_140625_winnow_original_d3_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_140625_winnow_original_d3_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_140625_winnow_original_d3_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_140625_winnow_original_d3_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_140625_winnow_original_d3_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_140625_winnow_original_d3_completion/log.md)
