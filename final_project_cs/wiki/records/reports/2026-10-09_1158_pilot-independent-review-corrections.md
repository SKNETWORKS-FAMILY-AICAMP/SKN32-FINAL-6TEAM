---
type: report
title: 통합 여행 평가 예시의 독립 검토와 정답 표시 수정
description: 문항 ID·일정군·근거 상태·인용 ID를 모델 실행 전에 바로잡는다
status: draft
domain: travel
---

# 통합 여행 평가 예시의 독립 검토와 정답 표시 수정

독립 로컬 에이전트 검토에서 개발 예시의 ID에 정답 범위가 들어가고 같은 일정 내용을 독립군처럼 세는 문제가 발견됐습니다. 아직 모델 호출0/24였으며 v1·v2는 원본 보존, 실행 대상은 새 v3로 교체했습니다.

| 검사 | 현재 결과 |
|---|---|
| 문항 ID의 정답 유형 노출 | 0/24 =0% |
| 정식 출처 ID 인용·필수 사실 | 24/24 =100% |
| 필수 근거 상태 필드 | 24/24 =100% |
| 실제 고유 일정 내용 | 1개; 명목 범위ID3개와 구분 |
| 사람 검수·모델 실측 | 각각0/24 =0% |

v1의 정답 ID 노출24/24·근거 상태 부재0/24와 ‘independent_families3’ 표시는 초기 구현 문제였습니다. 초기 보고의 해당 표현은 현재 독립성 근거로 쓰지 않습니다. 평가 자료 독립성이 확인됐다는 주장도 철회합니다. AI의 독립 검토는 사람 정답 검수로 세지 않습니다.

새 v3는 모든 ID를 무의미한 번호로 만들고, 참고 답변의 인용을 실제 출처 ID로 바꿨습니다. 정답 근거 상태는 충분15개·불필요9개입니다. 대체 소스·조회 실패 사례가 없으므로 완전한 계약 구현은 여전히 대기입니다. 모델의 실제 요청 payload는 실행기를 만들 때 입력 허용 목록으로 다시 검사해야 합니다.

- [현재 개발 예시·원본·검수 대기](../../../../datasets/core/answer_selection/selection_answer_bench/2026-10-09_pilot_v3/REPORT.md)
- [수정 반영한 설계 계획](../../../../program/research/daily_rag_slm/selection_answer_plan_2026-10-09_v2.md)
- [현재 단계 상태](../../../../program/research/daily_rag_slm/selection_answer_review_2026-10-09_v2.json)
- [초기 작업 기록](2026-10-09_1150_selection-answer-plan-and-training-review.md)
- [첫 생성 도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-09_1157_pilot-label-review/selection_answer_pilot_20261009.py)
- [근거 상태 보강 전 도구](../../../../program/scripts/plan_qa_bench/_backup/2026-10-09_1159_evidence-status/selection_answer_pilot_20261009.py)

Saluki 조건 대기·Jev 관련 모델 재계수·GPU 후속 등록은 초기 보고와 별도 전담 근거를 계속 사용합니다. 이번 수정은 데이터 표현·설계 정합성 보완이며 모델 정확도 개선이나 제품 적용을 뜻하지 않습니다.
