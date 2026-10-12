# Gemma E4B 배포 원본 D/D2/D3 회수 완료 — 2026-10-08

우리 자료 추가 학습 없는 Gemma-4-E4B-it Q4_K_M(개발사 지시 학습)의 나머지 세 묶음을 회수했다. 앞서 보관한 어려운 문장·혼합 문장 시험까지 합쳐 이 배포판의 예정된 다섯 묶음이 완료됐다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| D 답안 보관 | 완료 | 2735/2735 = 100% |
| D2 답안 보관 | 완료 | 1000/1000 = 100% |
| D3 답안 보관 | 완료 | 360/360 = 100% |
| 다섯 묶음 답안 보관 | 완료 | 9425/9425 = 100% |

## 수치·분모·실패

D 정상 요청738/883=83.58%, 요청 없음 전체 오지목75/1786=4.20%·형식 실패2/1786이며 그중 잡담 오지목54/1300=4.15%·형식 실패2/1300이다. 단일 선택 전체2669개와 복합66개를 분리한다. D 형식 실패13개 중 복합7개·단일 선택 정상4개·잡담2개다. 복합66개는 진단 원문에 보존했으며 전체 지시 수행 성공이나 단일 선택 정확도로 채택하지 않는다.

D2는 요청 없는1000개뿐이며 오지목69/1000=6.90%·정답931/1000=93.10%·실패0이다. D3는 정상 요청103/120=85.83%, 잡담 오지목19/240=7.92%·형식 실패2/240·정답219/240이다. 두 실패는 null 정답으로 재해석하지 않았다.

세 묶음4095개에서 누락0·형식 실패15개다. 전체 다섯 묶음9425개에는 D13·D3 2·H1·MX1로 형식 실패17개가 있다. 배열·문자열 출력을 고쳐 정답 처리하거나 실패·미완료를 해당 유형의 분모에서 제외하지 않는다. 실제 오지목 계수와 형식 실패를 따로 표시하고 실패는 정확도에서 오답으로 센다.

## 실행 근거와 한계

- [D 답안·집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_d/choice_report.md)
- [D2 답안·집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_d2/choice_report.md)
- [D3 답안·집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_d3/choice_report.md)
- [독립 직접 계수·GPU 서버 A 원본 해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/gemma_choice_verification_20261008.json)
- [앞선 어려운 문장 완료](2026-10-08_gemma-original-h-completion.md) · [앞선 혼합 문장 완료](2026-10-08_gemma-original-mx-completion.md)

세 답안의 SHA256을 GPU 서버 A 원본과 대조했다. 집계에는 실행 기록·고정 입력 해시·실패 원문이 있으며 고정 입력 SHA256과 ID·유형·정답이 모두 일치했다. 개발/회귀 문항의 모델 실행1회이며 토큰 확률은 말로 한 확신도와 같지 않다. 기존 다섯 묶음 완료가 모든 과거 모델·모든 역할·새 독립 보류 시험 완료를 뜻하지 않는다. 남은 원본 모델과 같은 범위 비교 및 반복·독립 보류 검증 전에 상위권·학습 후보·제품 채택을 확정하지 않는다.

GPU 서버 A는 Gemma12B 원본 H를 시작했고 입력 준비된 평가9개가 대기한다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 데이터로 학습)를 실행하며 뒤4개 레시피가 대기한다.2개는 기존 기반,2개는 자동 다운로드 준비가 필요하므로 다운로드 직전 공간을 다시 확인한다. 새로운 실행기나 중복 작업을 시작하지 않았다.

## 문서와 백업

일일 연구 Markdown/JSON, GPU 대기열 상태, 모델 평가 wiki와 cs wiki 변경 기록에 같은 근거를 연결했다. 이번 수정 직전 판은 아래에 보관했다. 이전 완료 리포트는 수정하지 않았다.

- [program/research/daily_rag_slm/_backup/2026-10-08_110706_gemma_choice_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_110706_gemma_choice_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_110706_gemma_choice_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_110706_gemma_choice_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_110706_gemma_choice_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_110706_gemma_choice_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_110706_gemma_choice_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_110706_gemma_choice_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_110706_gemma_choice_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_110706_gemma_choice_completion/log.md)
