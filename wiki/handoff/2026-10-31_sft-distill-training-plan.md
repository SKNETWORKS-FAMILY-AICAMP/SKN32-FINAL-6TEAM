---
type: handoff
title: SFT 지식 증류 학습·평가 계획 — 준비 완료, 학습 차단 인계 (2026-10-31)
description: RL 제외 SFT 시퀀스 증류 계획(구조화 결정 우선·자연어 답변 분리), manifest 검사기·readiness 실행 결과, 남은 승인 11건
status: draft
domain: travel
---

# SFT 지식 증류 학습·평가 계획 — 인계

보고: [계획 정본](../../final_project_cs/wiki/records/reports/2026-10-31_sft-distill-training-plan.md) · 준비물: [`program/research/sft_distill_plan_2026-10-31/`](../../program/research/sft_distill_plan_2026-10-31/README.md)

## 한 일
- 규칙, wiki 평가 기준, 이전 증류 근거(10-05 파일럿, distill-feasibility, insadong 전체 경로)를 확인했습니다. 평가자 보고 3건(골든 평가 보고·인계, sft-eval-discovery)은 사용자가 전달한 뒤에만 읽고 통합했습니다.
- 문헌: 사용자 지정 4편과 추가 3편(Gekhman·GRACE·RAFT)의 원문 해당 절을 확인했습니다. Codex·Claude 검색 목록은 초록 수준으로만 표시했습니다. 반영과 반대 판단(D1~D4)은 계획 §13에 적었습니다.
- 계획(한글): 현황·결함 분류·데이터·교사·학습·평가·망각·서빙·롤백·소유·승인을 담았고, 근거 등급을 구분했습니다.
- 준비물 실행: G 검증기 통과(14 checks, error 0), manifest 검사기 단위 시험 24/24 = 100%, 합성 예시 검사 통과. readiness는 **NOT_READY**입니다(pass 6 · fail 1 · blocked 4).

## 하지 않은 것
학습·제품 모델 추론·유료 API·업로드·배포·서버 중단 0. 평가자 폴더·골든·lease 쓰기 0. 고객 원문의 외부 전송 0. 원본 작업트리에서는 새 파일만 추가했고, 기존 파일 2개(이 index, `slm-model-evaluation.md`)에는 백업 후 한 줄씩만 더했습니다.

## 막힘과 다음 조건
현행 모델 기준선 0/47, 학습 툴체인 0/7, GPU 다른 세션 사용 90%, 커밋 메모리 8.2GB(필요 12GB), 학습 승인 없음. 남은 승인·실측은 0/11 = 0%입니다(계획 §12). 기준선이 나오면 manifest의 `integration_slots.current_model_baseline_report`에 경로를 넣고 readiness를 다시 실행합니다.
