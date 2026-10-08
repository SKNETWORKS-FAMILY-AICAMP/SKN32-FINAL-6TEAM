# Gemma E4B 배포 원본 MX 완료 — 2026-10-08

우리 자료 추가 학습 없는 Gemma-4-E4B-it Q4_K_M(개발사 지시 학습)의 혼합·대조 답안4,014개를 보관했다. 형식 실패1개를 전체 분모와 오답에 포함해 집계했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 회수·문항 일치 | 완료 | 4,014/4,014 = 100% |
| 혼합 정상 요청 정답 | 실측 | 960/1,033 = 92.93% |
| 혼합 요청 없음 오지목 | 실측 | 154/974 = 15.81% |
| 사전 합산 기준 | 일부 통과 | 1/4 = 25% |

## 원본·실패·집계

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/d_test_mx_backlog_e4bbase.jsonl) · [집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/mx_counts.json) · [검증 및 원본 두 판 비교](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/verification_and_pair_comparison.json).

로컬·GPU 서버 A 원본 SHA256은 `541960a76220dd7a9a38863218718074c462f6182256c6b3f80babdbd72ee29f`로 동일하다. 고정 입력 해시도 실행 시 기록과 같으며 입력 ID·정답·유형을 대조했다. 정상/요청 없음 혼합 문항은1,033/974개이며 각각 같은 수의 대조 문항이 있다.

대조 문항1201490의 `{"item": [9, 32]}`는 단일 번호 또는 null 계약에 맞지 않는다. null 정답으로 재해석하지 않고 전체 오답으로 보존했다. 미완료0, 해석 실패1이며 전부 분모에 남겼다. 요청 없음 대조 정답740개+오지목233개+형식 실패1개=974개다.

집계 도구의 오지목 증가 기준을 실제 오지목 계수 차이로 계산하도록 수정했다. 실패가 있으면 요청 없음 정답률 손실과 오지목 증가가 같지 않다: 이 실행은 각각−8.21%p와−8.11%p다. 오류가 없는 FrogNano 이전 집계에는 영향이 없고 기존 산출물을 다시 덮지 않았다. 누락·실패를 정답으로 세지 않는 직접 계수와 실패로 인한 정답률 변화가 실제 오지목으로 둔갑하지 않는 예제를 검증했다.

## 이 세트에서의 비교와 한계

Gemma 정상 요청 대조984/1,033에서 혼합960/1,033으로2.32%p 감소했다. 동일 일정59개 군집 부트스트랩2,000회·시드7의 감소95% 구간은1.28~3.30%p다. 지정 오지목 부류MX3·MX4·MX5a 기준은0/3 통과했다.

같은 혼합 문항에서 Gemma960/1,033 대 FrogNano898/1,033이며62개 차이(+6.00%p, 일정별95% 구간3.95~8.14%p)다. 오지목154/974 대167/974의13개 차이는 짝지은 검정p=0.1821·일정별 구간이0을 포함하므로 우열을 확정하지 않는다.

두 배포 원본 모두 우리 학습은 없으며 개발사 학습 역할은 Gemma 지시 학습·FrogNano 코딩 강화학습으로 다르다. Gemma는Q4_K_M, FrogNano 양자화는 이번 비교에서 검증하지 않았다. 따라서 이 저장된 배포판·한 세트의 관측 차이이며 같은 정밀도 아키텍처 비교나 일반 우열·전체 상위권 판정이 아니다. 모델 실행1회와 부트스트랩2,000회는 서로 다른 반복이다. 기존 개발/회귀 자료이며 독립 보류·모델 반복 실행 검증은 남아 있다. 토큰 확률과 말로 한 확신도·다른 실행 경로의 지연도 구분한다.

## 실행 유지·문서·백업

GPU 서버 A는 다음 원본 Gemma D평가를 시작했고 준비된 평가12개가 남아 있다. GPU 서버 B의 기존 Winnow-E4B 학습과 뒤 예약4개를 유지했다. 이중2개는 기반 다운로드 준비가 필요하며 공간은 다음 다운로드 직전에 재확인한다. 실행기를 추가하거나 기존 작업을 중단·반복하지 않았다. 완료 어댑터는 이번 관측에서 새로 발견되지 않았다.

일일 Markdown/JSON·GPU 상태·평가 wiki·cs wiki log를 동일 근거로 연결했다. 집계 도구 수정 전 판은 [도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1051_mx_failure_metrics/)에 보관했다. 다른 수정 직전 판:

- [program/research/daily_rag_slm/_backup/2026-10-08_105446_gemma_mx_completion/gpu_backlog_2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_105446_gemma_mx_completion/gpu_backlog_2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_105446_gemma_mx_completion/2026-10-08.json](../../../../program/research/daily_rag_slm/_backup/2026-10-08_105446_gemma_mx_completion/2026-10-08.json)
- [program/research/daily_rag_slm/_backup/2026-10-08_105446_gemma_mx_completion/2026-10-08.md](../../../../program/research/daily_rag_slm/_backup/2026-10-08_105446_gemma_mx_completion/2026-10-08.md)
- [final_project_cs/wiki/quality/_backup/2026-10-08_105446_gemma_mx_completion/slm-model-evaluation.md](../../../../final_project_cs/wiki/quality/_backup/2026-10-08_105446_gemma_mx_completion/slm-model-evaluation.md)
- [final_project_cs/wiki/_backup/2026-10-08_105446_gemma_mx_completion/log.md](../../../../final_project_cs/wiki/_backup/2026-10-08_105446_gemma_mx_completion/log.md)
