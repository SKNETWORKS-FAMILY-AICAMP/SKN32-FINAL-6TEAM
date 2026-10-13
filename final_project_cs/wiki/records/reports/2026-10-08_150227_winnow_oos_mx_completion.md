# Jev 계열 모델 중 Winnow-E4B our-travel oos adapter Q8_0 base — 혼합 문장 완료

[실측] Jev 계열 모델 중 Winnow-E4B our-travel oos adapter Q8_0 base(우리 여행 자료로 추가 학습함)의 혼합 문장 답안4,014개를 보관했다. 정상 요청 정답1,000/1,033 = 96.81%, 요청 없음 오지목20/974 = 2.05%, 형식 실패0개·미완료0이다. 사전 합산3/4 기준 통과다. 실패는 분모에서 빼지 않았다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 4,014/4,014개 = 100% |
| 혼합 정상 요청 정답 | 실측 | 1,000/1,033 = 96.81% |
| 혼합 요청 없음 오지목 | 실측 | 20/974 = 2.05% |
| 사전 합산 기준 | 실측 | 3/4 = 75% |

## 원본·분모·검증

혼합2,007개·대조2,007개이며 각 부류의 정상 요청1,033개·요청 없음974개다. 혼합의 정상 형식 실패0개·요청 없음 실패0개, 대조의 정상 실패0개·요청 없음 실패0개로 전체 실패0개다. 요청 없음 혼합은 정답954개·오지목20개·실패0개를 합해974개다. 실패는 실제 오지목 계수와 구분하지만 전체 정답률에는 오답으로 포함한다.

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_mx/d_test_mx_backlog_winnow_oos.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_mx/started.json) · [집계·유형·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_mx/mx_counts.json) · [독립 직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_mx/verification.json) · [작업 로그](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_mx/job.log). GPU 서버 A 원본/로컬 답안 SHA256은`8e18f91b3e902e108a0deaab5b8162b496f4390fd2c826655962c02949e406ac`로 같다. 고정 입력 해시·전체ID·정답·유형과 대조/혼합 각 정상/요청 없음 직접 계수를 확인했다. 배열 등 계약 밖 출력을 번호나 null로 고쳐 정답 처리하지 않았다. 개발사 역할 기록은`Decision model release; exact publisher training method not reverified in this run`이며 우리 여행 추가 학습과 구분한다.

## 대조·자연 혼합·채택 한계

정상 요청 정답은 대조1006/1033에서 혼합1000/1033으로 변화했고 손실0.5808%p다. 일정별95% 구간-0.1970~1.2708%p, 59개 일정의 군집 부트스트랩2,000회·시드7이다. 점 추정 기준과 불확실성 구간을 구분한다. 요청 없음 정답률 손실과 실제 오지목 증가는 실패가 있으면 같지 않으며 실제 오지목 증가는-1.1294%p다. 사전 기준의 통과/실패 원문은 집계JSON을 따른다.

자연스럽게 작성한 혼합239개는 정상 요청92/93 = 98.92%·요청 없음 오지목8/146 = 5.48%이다. 코드로 이어 붙인1,768개와 분리했다. 사람 정답 검수 전이고 모델 합의로 선정된 기존 개발/회귀 자료이므로 실제 고객 자유 대화 전체를 대표하지 않는다.

모델 실행1회이며 전체 원본 비교군의 같은 세트 완료·반복·독립 고정 보류 검증 전 일반 우열·상위권·제품 채택을 확정하지 않는다. 원본의 이 결과를 우리 여행 학습판의 결과로 옮기지 않는다. 모델 변경 정확도와 같은 모델 엔진 속도, 토큰 확률과 말로 한 확신도를 구분한다.

## 다음 작업·도구·백업

GPU 서버 A는 같은 실행기로 다음 평가를 수행하고 입력까지 준비된5개가 대기한다. GPU 서버 B의 기존 Spark 여행 학습과 뒤5개 예약을 유지했다. 그중4개는 기존 기반·1개는 다운로드와 공간 재확인이 필요하다. B57 두 번째 시드 비교는 B56 완료 뒤 이어진다. 새 실행기·중복 시험·작업 중단·새 결제·기존 모델 삭제는 하지 않았다.

집계 스크립트는 원본과 학습판 모두의 실행 조건을 읽고 Winnow의 Jev 계열과 정확한 이름을 표시한다. 후속 예약 설명은 현재 B57을 포함하도록 보완했다. [수정 직전 기록 도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1500_mx_followup_counts/record_backlog_mx_completion.py). [수정 직전 스크립트 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1353_mx_model_role/backlog_mx_report.py). 변경된 일일 Markdown/JSON·GPU 상태·평가 wiki·cs log는 수정 직전에 보관했다. 과거 리포트·원본 답안은 수정하지 않았다.

- [program/research/daily_rag_slm/_backup/2026-10-08_150227_winnow_oos_mx_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_150227_winnow_oos_mx_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_150227_winnow_oos_mx_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_150227_winnow_oos_mx_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_150227_winnow_oos_mx_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_150227_winnow_oos_mx_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_150227_winnow_oos_mx_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_150227_winnow_oos_mx_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_150227_winnow_oos_mx_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_150227_winnow_oos_mx_completion/log.md)
