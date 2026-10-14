# Winnow-E4B 여행 학습판 추가 평가 완료와 GPU 일감 보충

Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 D·D2·H 완료 답안5,051개를 보관·대조했다. QAT 배포 원본의 누락 평가3개를 기존 GPU 서버 A 실행기에 추가했고 GPU 서버 B 학습과 Oracle ARM 실제 추론을 유지했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 완료 답안 검증 | 완료 | 5,051/5,051 = 100% |
| GPU 서버 A 준비된 대기 평가 | 예약 | 3/3 = 100% |
| Oracle ARM 현재 설정 | 진행 | 7/360 = 1.94% |

## 같은 기반 모델·문항 비교

두 판은 같은 Q8_0 기반·입력 해시·실행 코드 해시·llama.cpp 버전이며 추가 학습 어댑터만 다르다. 원본은 우리 자료로 학습하지 않았고 개발사 결정 학습 역할은 실행 기록에 따로 적었다. 실패는 오답이며 분모에서 빼지 않았다. 오지목과 형식 실패는 별도다.

| 묶음 | 정상 요청 정답: 원본 → 여행 학습판 | 요청 없음 오지목: 원본 → 여행 학습판 | 형식 실패: 원본 → 학습판 |
|---|---|---|---|
| D | 709/883 → 793/883 | 90/1786 → 13/1786 | 53 → 0 |
| D2 | 대상 없음 | 77/1000 → 3/1000 | 13 → 0 |
| H | 401/461 → 434/461 | 403/855 → 141/855 | 19 → 0 |

[같은 문항 정답 유지·개선·손실과 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/2026-10-08_145604_winnow_three_completion_refill_paired.json).

원본 개발/회귀 자료의 각1회 실행이다. 일정별 문항 상관·여러 비교·반복 편차를 통제한 최종 검정이 아니다. MX는3057/4014개 저장 단계이며 완성 전 순위·제품 채택을 확정하지 않는다. 독립 보류 자료720개와 반복 검증은 아직 완료되지 않았다.

## 회수·예약·실제 환경

- [D 답안·실행 조건·검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_d/): GPU 서버 A 원본 SHA256, 전체ID·정답·유형, 고정 입력 해시와 독립 계수를 대조했다.
- [D2 답안·실행 조건·검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_d2/): GPU 서버 A 원본 SHA256, 전체ID·정답·유형, 고정 입력 해시와 독립 계수를 대조했다.
- [H 답안·실행 조건·검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_h/): GPU 서버 A 원본 SHA256, 전체ID·정답·유형, 고정 입력 해시와 독립 계수를 대조했다.

기존 Gemma-4-E4B-it QAT Q4_0 배포 원본의 D2·H·MX 총6,330문항을 예약했다. 로컬 결과 파일 목록과 GPU 서버 A 기존 답안 목록을 확인한 범위에서 해당 원본의 세 묶음은 완료 기록이 없으며, QAT 어댑터 시험과는 구분했다. 모델 파일5,154,939,136바이트·GGUF 헤더·전체SHA256을 검증했다. 다운로드는 필요 없다. 기존 Gemma 구조 실행기를 쓰며 이 가중치의 GPU 연결·정확도 성공은 아직 실행 전이다.
GPU 서버 A의 manifest 원본을 원격 _backup에 보관하고 같은 폴더의 임시 파일을 원자적으로 교체했다. 실행기 PID는 유지했고 중복 실행이나 진행 중인 작업 중단은 하지 않았다. 총25개49,360문항 예약이며 현재 계산1개, 준비된 다음 평가3개다.
GPU 서버 B는 Spark 본 학습1개, 기존 입력으로 준비된 학습4개, 기반 다운로드·공간 확인이 필요한 후보1개를 유지한다. Oracle ARM은 정상 추론 중 최근300.06초 두 코어 전체 대비CPU89.96%, host busy90.16%, steal0.16%, 작업 메모리8,924,016,640바이트(파일 캐시 포함), 남은 공간54,411,616,256바이트다. 목표 이상 연속 표본1,050.24초이며24시간 유지 증거는 아니다. 실제 답안7개는 모두 잡담이며 전체 정확도나 정상 요청 정답률로 해석하지 않는다.

## 수정 직전 백업

- [program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/arm_serving_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/arm_serving_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_145604_winnow_three_completion_refill/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_145604_winnow_three_completion_refill/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_145604_winnow_three_completion_refill/slm-model-evaluation.md)
- [final_project_cs/wiki/operations/_backup/2026-10-08_145604_winnow_three_completion_refill/gpu-work-queue.md](../../../../final_project_cs/wiki/operations/_backup/2026-10-08_145604_winnow_three_completion_refill/gpu-work-queue.md)
- [final_project_cs/wiki/_backup/2026-10-08_145604_winnow_three_completion_refill/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_145604_winnow_three_completion_refill/log.md)
