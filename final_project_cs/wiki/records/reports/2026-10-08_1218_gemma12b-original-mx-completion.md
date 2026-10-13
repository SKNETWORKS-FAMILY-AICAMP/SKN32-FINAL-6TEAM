# Gemma12B 배포 원본 E 혼합 문장 평가 완료 — 2026-10-08

우리 여행 자료로 추가 학습하지 않은 Gemma-4-12B-it Q4_K_M의 혼합 문장 평가를 보관했다. 정상 요청을 잘 짚었으나 항목을 고르면 안 되는 감상·잡담도 자주 지목해 제품 채택 기준 전체를 통과하지 못했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 혼합·대조 답안 보관·문항 대조 | 완료 | 4,014/4,014 = 100% |
| 혼합 정상 요청 정답 | 실측 | 993/1,033 = 96.13% |
| 혼합 요청 없음 오지목 | 실측 | 201/974 = 20.64% |
| 사전 합산 기준 | 일부 통과 | 3/4 = 75% |

## 범위와 결과

사용자 명칭 E는 실행 기록의 MX 혼합 문장 시험이다. 혼합2,007개(정상1,033·항목 선택 없음974)와 같은 요청의 대조2,007개를 함께 실행했다. 항목 선택 없음에는 일반 여행 질문·새 항목 추가·일정 전체 변경도 포함하며 여행과 무관한 잡담만을 뜻하지 않는다.

| 작성 방식 | 정상 요청 정답 | 항목 선택 없음 오지목 |
|---|---:|---:|
| 코드 이어 붙인1,768개 | 901/940 = 95.85% | 164/828 = 19.81% |
| 모델 자연 혼합239개 | 92/93 = 98.92% | 37/146 = 25.34% |

대조 정상 요청1,010/1,033에서 혼합993/1,033으로 정답률1.65%p 감소했다. 동일 일정59개 군집 부트스트랩2,000회·시드7의 손실95% 구간은0.87~2.38%p로 사전 상한2%p를 넘는 값도 포함한다. 점추정 합산 기준은3/4 통과이며 정상 요청≥95%·선택 손실≤2%p·오지목 증가≤1%p를 통과하고 오지목≤1% 기준을 실패했다. 반복으로 안정성을 확인한 합격은 아니다. 대조 오지목192/974에서 혼합201/974로 실제 오지목 증가0.92%p다.

| 항목 선택 없음 유형 | 오지목 |
|---|---:|
| 일정 밖 장소·일반 여행 질문 | 46/457 = 10.07% |
| 장소 언급 감상·잡담 | 118/121 = 97.52% |
| 새 항목 추가·일정 전체 변경 | 17/236 = 7.20% |
| 일정 전체 감정·불만 | 20/160 = 12.50% |

지정된세 부류의 오지목≤3% 기준은0/3 통과다. 정상 요청 점수 하나로 채택하거나12B 이름의 모델을 기본 소형 범위약8B 이하에 자동 포함하지 않는다.

## 원본·검증·한계

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/d_test_mx_backlog_g12bbase.jsonl) · [조건·버전](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/started.json) · [유형별 집계·구간](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/mx_counts.json) · [원본 해시·독립 직접 계수](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/verification.json).

GPU 서버 A 원본과 로컬 답안 SHA256은 `1c0963a3adc6aa7f24d89c8b38434b8aaf69672556b8d303ca82d8ed2e1d5729`로 같다. 고정 입력과 실행 당시 입력 해시가 같고 전체ID·정답·유형을 대조했다. 독립 직접 계수로 혼합/대조의 정상·항목 없음 분모·정답·오지목을 모두 확인했다. 미완료·호출 오류·해석 실패0이며 실패·미완료를 분모에서 빼지 않았다.

배포 Instruct 원본이며 우리 자료로 추가 학습하지 않았다. Q4_K_M, llama.cpp commit4ebdf2c, 모델 실행1회다. 문항별Wilson 구간·일정 군집 부트스트랩 반복은 모델 반복 실행을 대신하지 않는다. 기존 개발/회귀 자료이고 사람 정답 검수·독립 보류 검증은 남았다. 전체 원본 비교군 상위권이나 일반 우열을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 다른 모델 정확도와 같은 모델 엔진 속도를 구분한다.

## 실행 유지·문서·백업

GPU 서버 A의 같은 실행기가 다음Gemma12B D평가를 시작했고 준비된평가7개가 남아 있다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 기존 본 학습을 계속하며 뒤4개 학습이 예약돼 있다.2개는 기존 기반·입력,2개는 자동 다운로드 준비가 필요하다. 다음 다운로드 직전 공간을 재확인한다. 실행기 추가·중복 시험·작업 중단·새 결제·모델 삭제는 하지 않았다.

일일연구 Markdown/JSON·GPU 대기열 상태·평가 wiki·cs wiki log에 같은 근거를 연결했다. 과거 결과 리포트는 수정하지 않았다. 수정 직전 판 백업:

- [program/research/daily_rag_slm/_backup/2026-10-08_121955_gemma12b_mx_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_121955_gemma12b_mx_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_121955_gemma12b_mx_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_121955_gemma12b_mx_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_121955_gemma12b_mx_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_121955_gemma12b_mx_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_121955_gemma12b_mx_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_121955_gemma12b_mx_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_121955_gemma12b_mx_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_121955_gemma12b_mx_completion/log.md)
