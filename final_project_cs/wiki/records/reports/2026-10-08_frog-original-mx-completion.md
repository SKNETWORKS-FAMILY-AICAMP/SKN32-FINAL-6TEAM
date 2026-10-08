# FrogNano 배포 원본의 혼합 요청 평가 완료 — 2026-10-08

우리 여행 자료로 추가 학습하지 않은 FrogNano-4B-2609의 MX 답안4,014개를 회수·집계했다. 개발사 코딩 강화학습은 있음으로 구분한다. 같은 일정의 요청만 있는 대조와 잡담이 섞인 요청을 비교한 시험이며 다른 모델 간 최종 순위를 확정하지 않았다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 회수·문항 일치 | 완료 | 4,014/4,014 = 100% |
| 집계 검증 | 통과 | 7/7 = 100% |
| 혼합 정상 요청 정답 | 실측 | 898/1,033 = 86.93% |
| 혼합 요청 없음 오지목 | 실측 | 167/974 = 17.15% |

## 실행·원본 보호

기존 GPU 서버 A 지속 실행기가 완료한 작업을 회수했으며 실행기를 추가로 띄우지 않았다. GPU 서버 B의 기존 학습도 중단하지 않았다. 이번에 새 GPU 시험을 중복 시작하거나 모델 파일을 삭제하지 않았다. Strata와 완료 MAI 시험은 재실행하지 않았다.

[원본 답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/d_test_mx_backlog_frog.jsonl) · [실행 버전·입력 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/started.json) · [상세 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/mx_counts.json) · [집계 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/verification.json).

회수한 답안 SHA256은 GPU 서버 A 완료 원본과 동일하다: `46aefc1479b5ccc378fd1f9178a761955b98976f968992dfab2928e0a26d59df`. llama.cpp commit4ebdf2c, 기존 조건·한 번 실행이다. 양자화와 모델 역할이 다른 실행기의 지연을 직접 비교하지 않았다.

## 결과와 해석

정상 요청 분모는 혼합 문장 중 항목 정답이 있는1,033개, 오지목 분모는 혼합 문장 중 정답 없음974개이다. 요청만 있는 대조에도 각각 같은 수가 있다. 누락·호출 오류·해석 실패는0개이며 실패를 분모에서 제외하지 않는 집계로 검증했다.

대조 정상 요청955/1,033=92.45%에서 혼합898/1,033=86.93%로5.52%p 감소했다. 일정59개를 단위로 군집 부트스트랩2,000회·시드7로 계산한95% 감소 구간은3.98~6.96%p이다. 요청 없음 오지목은 대조173/974에서 혼합167/974로6개 줄었다. 변화 구간이0을 포함하므로 잡담이 오지목을 개선했다고 일반화하지 않는다.

사전 합산 기준1/4 통과, 지정 부류 MX3·MX4·MX5a 오지목 기준0/3 통과다. 유형별 및 코드 연결/자연 혼합별 계수는 상세 집계에 보관했다. 토큰 p_null을 보정된 확률이나 MAI가 말한 확신도와 같은 값이라고 해석하지 않았다.

기존 개발·회귀 자료이며 새 독립 보류 자료와 구분한다. 모델 실행은1회이고 부트스트랩2,000회는 모델 실행 반복이 아니다. 사람 정답 검수와 독립 보류 자료의 최종 검증은 남아 있다. 원본 비교군의 부족한 시험을 이어가며 최종 상위권 판정을 보류한다.

## 문서 연결·보관 범위

[모델 평가 wiki](../../quality/slm-model-evaluation.md)와 cs wiki log에 결론·리포트를 연결했다. 일일 Markdown/JSON과 GPU 상태도 같은 완료 근거를 반영했다. 기존 시험 감사는 과거 관측으로 보존하고 [FrogNano 다섯 세트 보관 확인](../../../../program/scripts/plan_qa_bench/results/frog_original_coverage_2026-10-08_1030.md)을 별도로 작성했다. [집계 도구](../../../../program/scripts/plan_qa_bench/backlog_mx_report.py)는 누락·실패도 전체 문항 분모에 남긴다.

## 다음 실행과 백업

관측 시 GPU 서버 A는 원본 Gemma-4-E4B-it H를 실행하며 준비된 평가14개가 대기했다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B에 우리 자료 학습을 계속하며 뒤 본 학습4개가 예약돼 있다. 기존 스크립트의 기반 다운로드2개와 기존 기반으로 준비된 학습률 비교2개를 구분했고 공간은 다음 다운로드 직전에 다시 확인한다. 새 완료 어댑터는 이번 확인 범위에서 발견되지 않았다.

수정 직전 판은 아래 위치에 보존했다.

- [program/research/daily_rag_slm/_backup/2026-10-08_1035_frog_mx_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_1035_frog_mx_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_1035_frog_mx_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_1035_frog_mx_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_1035_frog_mx_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_1035_frog_mx_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_1035_frog_mx_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_1035_frog_mx_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_1035_frog_mx_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_1035_frog_mx_completion/log.md)
