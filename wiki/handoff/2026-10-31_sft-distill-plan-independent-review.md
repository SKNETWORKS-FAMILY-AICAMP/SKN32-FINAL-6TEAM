---
type: handoff
title: SFT 증류 계획 독립 검토 인계 — 자연어 목표·형식·승인 문구 정정 필요 (2026-10-31)
description: 원 계획과 충돌하지 않게 별도 작성. 심각 3건(자연어 칸 분리 충돌, G 0행 대응, 허위 승인 대기), x600 num_ctx 12288 확인, 단위시험 24/24 재실행
status: draft
domain: travel
---

# SFT 증류 계획 독립 검토 — 인계

보고: [독립 검토](../../final_project_cs/wiki/records/reports/2026-10-31_sft-distill-plan-independent-review.md) · 원 계획: [계획 정본](../../final_project_cs/wiki/records/reports/2026-10-31_sft-distill-training-plan.md) · 근거: [`program/research/sft_distill_review_2026-10-31/`](../../program/research/sft_distill_review_2026-10-31/README.md)

## 한 일
- 원 준비물 단위시험을 재실행했습니다. 24/24 = 100% OK, 예시 manifest rc=0.
- x600 문맥 길이를 직접 확인했습니다. Modelfile과 API env 모두 12288, 배포 `fab3da50ab`, blob은 로컬과 같습니다. 로컬 Modelfile은 8192입니다.
- 메모리 실패 원인을 읽기 전용으로 확인했습니다. 원인은 Windows 커밋 한도 소진이고(Qwen llama-server private 36.7GB), GPU 메모리는 원인이 아닙니다. 다른 작업자(`deleg_f6cad80d`)와 겹치지 않게 했습니다.
- 계획 §12-7을 진행했습니다. G → `decision_unit` 대응은 0행이고, 자연어 학습행도 0행입니다.
- 384 표본 근거, 실험군, 누출, 비용, 승인 문구를 검토했습니다.

## 하지 않은 것
학습, 모델 적재·추론, 유료 호출, 운영 변경, lease 획득은 모두 0건입니다. 원저자 파일·준비물은 수정하지 않았습니다. 라우팅 세션에 전달하지 않았습니다.

## 원 계획 담당에게 요청(정정 제안)
1. Track A/B를 adapter로 나누지 말고, **배포 JSON 전체를 학습 목표로 두고 칸별로 평가**하도록 바꿔 주십시오. `E_TARGET_TYPE_MIX`는 「한 manifest = 한 서빙 호출 계약」으로 바꿉니다.
2. 비교군에 **A′(무학습 코드·프롬프트 개선)**를 넣어 주십시오.
3. R09와 「학습 승인 없음」 문구를 기술 차단 사유로 고쳐 주십시오. 근거는 `slm-model-evaluation.md` 「자동으로 이어갈 학습과 재평가」입니다.
4. 384 대신 관문별 짝 수를 계산해 주십시오. manifest에 지시문 해시·num_ctx 12288·템플릿 칸을 추가해 주십시오.
5. 시간·메모리 추정은 8~9k 토큰 기준으로 다시 잡아 주십시오.

## 라우팅 구현 세션 전달(사용자가 Desktop에서 직접 보낼 경우의 문안)
대상 `20261024_213155_36cd5c` 「라우팅 에이전트 구현」은 열려 있고 유휴 상태입니다. CLI resume는 쓰지 마십시오.

> [SFT 증류 검토에서 넘어온 코드 쪽 할 일] 채팅의 「대안+이유」에서 이유가 답에 실리지 않는 문제(`pick_reason` 미저장·미노출), 일정 밖 지역 질문 경로, 후속 「왜」 읽기 계약은 학습으로 고칠 수 없는 코드 결함입니다(계획 C13·S 분류). 학습 비교의 무학습 대조군 A′로 쓰려 하니, 고친 판과 시험 결과를 남겨 주세요. 근거: `final_project_cs/wiki/records/reports/2026-10-31_sft-distill-plan-independent-review.md` §4·§8.
