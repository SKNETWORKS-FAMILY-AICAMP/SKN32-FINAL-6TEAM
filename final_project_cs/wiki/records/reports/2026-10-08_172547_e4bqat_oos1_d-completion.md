# Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter — D 완료

우리 여행 자료로 추가 학습함의 시험 답안을 회수하고 실패를 보존했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 2,735/2,735 = 100% |
| 정상 요청 정답 | 실측 | 798/883 = 90.37% |
| 항목 선택 없음 오지목 | 실측 | 13/1,786 = 0.73% |
| 실패·해석 불가 | 보존 | 0/2,735 = 0.00% |

## 원본·조건·검증

Gemma-4-E4B-it QAT Q4_0 with our-travel oos1 adapter(우리 여행 자료로 추가 학습함)의 D 답안2,735/2,735개를 보관했다. 정상 요청 정답798/883 = 90.37%, 기존 항목 선택 없음 오지목13/1,786 = 0.73%, 형식 실패0개다. 실패·미완료는 분모에서 빼지 않았다.

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d/d_test_d_backlog_e4bqat_oos1.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d/started.json) · [유형별 집계·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d/choice_counts.json) · [독립 직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d/verification.json).

GPU 서버 A 원본·로컬 사본 SHA256은 `91f9f9a8de1852472602f1dd98d1ec1161408c9ce761416d59d78584fff504f0`로 같다. 고정 입력 해시·전체ID·정답·유형 및 정상/항목 없음 독립 직접 계수를 확인했다. 미완료0이며 배열이나 문자열 출력을 번호·null로 고쳐 정답 처리하지 않았다. 개발사 학습 역할 기록은 `Google Instruct release and quantization-aware training; our-travel adapter recorded separately`이다.

전체2,735개 중 단일 선택 집계2,669개, 복합 문항66개는 별도 진단이다. 복합 문항을 단일 선택 전체 정확도로 해석하지 않는다.

## 같은 기반 원본과 여행 어댑터

개발사의 지시 학습·양자화 학습이 있는 배포 원본에 우리 여행 어댑터를 적용한 결과다. 같은 기반·전체 ID·정답·유형·입력·실행 코드·엔진을 대조했다. 원본의 실패도 해당 분모에 남겼다.

| 항목 | 우리 여행 학습 없는 원본 | 우리 여행 어댑터 |
|---|---:|---:|
| 정상 요청 정답 | 730/883 = 82.67% | 798/883 = 90.37% |
| 항목 선택 없음 오지목 | 76/1,786 = 4.26% | 13/1,786 = 0.73% |

[같은 문항 정확 검정·전체 해시 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bqat_oos1_d/matched_original.json). 실행1회이며 다중 비교·일정별 상관·시드 편차·독립 보류 검증을 대신하지 않는다. 다른 시험의 정상 요청 손실을 무효화하거나 최종 우열로 해석하지 않는다.
[원본 대조 도구](../../../../program/scripts/plan_qa_bench/verify_choice_matched_original.py) · [대조 결과 연결 전 기록 도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_172455_matched_original_choice_report/record_backlog_choice_completion.py).

잡담만의 오지목은 7/1,300 = 0.54%이며 형식 실패0개다. 항목 선택 없음 전체와 잡담만의 분모는 다르다.

## 한계·실행 유지·백업

기존 개발/회귀 자료의 모델 실행1회다. 전체 원본 비교군의 모든 시험·반복·독립 보류 검증 전 최종 순위나 제품 채택을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 모델 변경 정확도와 같은 모델 엔진 속도를 구분한다.
GPU 서버 A의 같은 실행기가 다음 평가를 수행하며 입력까지 준비된6개가 대기한다. GPU 서버 B의 기존 학습과 예약을 유지했다. 다음 기반 다운로드 직전 공간을 재확인한다. 중복 실행·실행기 추가·작업 중단·새 결제·모델 삭제는 하지 않았다.

일일 Markdown/JSON·GPU 상태·평가 wiki·cs wiki log에 근거를 연결했다. 기존 원본 기록은 수정하지 않았다. 수정 직전 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_172547_e4bqat_oos1_d_completion/log.md)
