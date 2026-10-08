# 쇼핑몰 시절 평가 자료·도구 (기록 — 쓰지 않는다)

`[2026-10-03 사용자 지시]` 쇼핑몰(커머스) 시절의 자료·코드·데이터는 지금 프로젝트에서 쓰지 않는다 — 결정 [D-023](../../../wiki/decisions/D-023-no-commerce-assets-in-use.md).

여기 있는 것은 옛 평가 하네스(golden 72 · holdout 24 문장, 비교 러너 셋, 채점 · 심판 · 라벨링 · 시간 측정, 시험 · 검사 스크립트)를 **경로 그대로** 옮긴 것이다
(`git mv` — 이력이 남는다). 쇼핑몰 어휘(주문 · 배송 · 반품 · 교환)와 쇼핑몰 지식 문서를 전제로 하므로 **지금 저장소에서 돌지 않는다.**

- 여행 분류 평가: `eval/datasets/travel_golden.jsonl` · `travel_holdout.jsonl` + `python -m eval.travel_classification.replay`
- 여행 시나리오 평가: `python -m eval.runners.travel_scenarios`
- 일반 통계(부트스트랩 · 맥니마 · 일치도): `eval/stats/` — 도메인 무관이라 그대로 둔다
