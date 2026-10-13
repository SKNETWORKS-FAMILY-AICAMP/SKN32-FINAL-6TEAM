---
type: report
title: Saluki를 포함한 모든 일정 선택 평가 역할 비교
description: 보관 답안의 A·B·C·D·E와 추가 지표 재집계 및 누락 범위
status: draft
domain: travel
---

# Saluki와 전체 측정 비교

Saluki 배포 원본의 E 정상 요청 점수는 높지만 요청없음 오지목 기준을 실패했습니다. 단일 선택22판과 Valen 완료3세트, 복수JSON6판, 과거HF/CLI16역할을 분리해 원본으로 재계수했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 원본SHA 재검사 | 완료 | 365/365 = 100.00% |
| 기본문항과D 대조 | 완료 | 835/835 = 100.00% |
| 채택·독립검증 | 대기 | 0/1 = 0% |

[전체 비교표](C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/results/comparison_abcde_20261009_111621/comparison-complete.md)・[검색 가능한 표](C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/results/comparison_abcde_20261009_111621/comparison.html)・[검증](C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/results/comparison_abcde_20261009_111621/verification.json). 각 표에 분자/분모·실패·반복·학습 여부·조건 차이를 기록했습니다. 과거 산출물을 덮어쓰지 않고 새 이름으로 보존했습니다.

A·B·C는 같은835문항의 서로 다른채점, E는MX평문혼합입니다. 단일출력C0/66을 복수역할 실패로 읽지 않으며 새로운 복수역할누락은 기존GPU일꾼에 보충 중입니다. 양자화·모델변경 정확도와 엔진속도, 말로한확신도와 선택지/토큰확률을 구분했습니다. Saluki와Gemma12B E정상4문항차이를 일반우열로 확정하지 않습니다. 모델실행1회·개발세트이며 사람검수·독립보류·최종제품채택 미완료입니다.

새 코드: [재계수 도구](C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/comparison_snapshot_20261009.py)・[표 생성/근거 검증](C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/finalize_comparison_20261009.py). 기존집계도구 수정전 보관: [백업](C:/Users/playdata2/Documents/final_workspace/program/scripts/plan_qa_bench/_backup/2026-10-09_1116_comparison_before_valen).
