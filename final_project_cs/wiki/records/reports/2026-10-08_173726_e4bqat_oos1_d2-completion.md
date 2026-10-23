# Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter — D2 완료

우리 여행 자료로 추가 학습함의 시험 답안을 회수하고 실패를 보존했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 1,000/1,000 = 100% |
| 항목 선택 없음 오지목 | 실측 | 5/1,000 = 0.50% |
| 실패·해석 불가 | 보존 | 0/1,000 = 0.00% |

## 원본·조건·검증

Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter(우리 여행 자료로 추가 학습함)의 D2 답안1,000/1,000개를 보관했다. 정상 요청 정답대상 문항 없음, 기존 항목 선택 없음 오지목5/1,000 = 0.50%, 형식 실패0개다. 실패·미완료는 분모에서 빼지 않았다.

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d2/d_test_d2_backlog_e4bqat_oos1.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d2/started.json) · [유형별 집계·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d2/choice_counts.json) · [독립 직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d2/verification.json).

GPU 서버 A 원본·로컬 사본 SHA256은 `673fbdf6154233d97387b8c2a2f265c2a98e0665ba140db59ab0800a9f098581`로 같다. 고정 입력 해시·전체ID·정답·유형 및 정상/항목 없음 독립 직접 계수를 확인했다. 미완료0이며 배열이나 문자열 출력을 번호·null로 고쳐 정답 처리하지 않았다. 개발사 학습 역할 기록은 `Google Instruct release and quantization-aware training; our-travel adapter recorded separately`이다.

전체1,000개 중 단일 선택 집계1,000개, 복합 문항0개는 별도 진단이다. 복합 문항을 단일 선택 전체 정확도로 해석하지 않는다.

## 같은 기반 원본과 여행 어댑터

개발사의 지시 학습·양자화 학습이 있는 배포 원본에 우리 여행 어댑터를 적용한 결과다. 같은 기반·전체 ID·정답·유형·입력·실행 코드·엔진을 대조했다. 원본의 실패도 해당 분모에 남겼다.

| 항목 | 우리 여행 학습 없는 원본 | 우리 여행 어댑터 |
|---|---:|---:|
| 항목 선택 없음 오지목 | 68/1,000 = 6.80% | 5/1,000 = 0.50% |

[같은 문항 정확 검정·전체 해시 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d2/matched_original.json). 실행1회이며 다중 비교·일정별 상관·시드 편차·독립 보류 검증을 대신하지 않는다. 다른 시험의 정상 요청 손실을 무효화하거나 최종 우열로 해석하지 않는다.
[원본 대조 도구](../../../../program/scripts/plan_qa_bench/verify_choice_matched_original.py) · [대조 결과 연결 전 기록 도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_172455_matched_original_choice_report/record_backlog_choice_completion.py).

## 한계·실행 유지·백업

기존 개발/회귀 자료의 모델 실행1회다. 전체 원본 비교군의 모든 시험·반복·독립 보류 검증 전 최종 순위나 제품 채택을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 모델 변경 정확도와 같은 모델 엔진 속도를 구분한다.
GPU 서버 A의 같은 실행기가 다음 평가를 수행하며 입력까지 준비된5개가 대기한다. GPU 서버 B의 기존 학습과 예약을 유지했다. 다음 기반 다운로드 직전 공간을 재확인한다. 중복 실행·실행기 추가·작업 중단·새 결제·모델 삭제는 하지 않았다.

일일 Markdown/JSON·GPU 상태·평가 wiki·cs wiki log에 근거를 연결했다. 기존 원본 기록은 수정하지 않았다. 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_173726_e4bqat_oos1_d2_completion/log.md)
