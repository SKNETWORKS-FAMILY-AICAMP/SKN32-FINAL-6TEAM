---
type: report
title: Saluki 첫 학습을 기존 검토 여행 자료 적용으로 단순화
description: 신규 자료를 첫 학습의 필수조건에서 빼고 기존 2613행과 검토 범위를 고정한 기록
status: draft
domain: travel
tags: [finetuning, evaluation]
---

# Saluki 첫 학습을 기존 검토 여행 자료 적용으로 단순화

살루키 첫 실험은 **이미 검토한 여행 보강 자료 2,613행을 그대로 적용**하는 단일 학습판으로 정했습니다. 새 대조문·새 F 평가셋·독립 최종 보류 자료를 먼저 만들 필요는 없습니다. 동일 살루키의 학습 표현·CUDA 호환·기존 자원 조건이 충족되면 기존 자료로 연결 검사와 학습을 이어갑니다. 지금 학습을 시작한 것은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 첫 판 학습 정답 계약 | 확인 | 2,613/2,613 = 100% |
| 추가 어려운 문장 AI 합의 | 확인 | 900/900 = 100% |
| 기존 행 그대로 유지 | 확인 | 1,713/1,713 = 100% |
| 본 학습 시작 조건 | 기술 조건 대기 | 3/9 = 33.33% |
| GPU 연결·본 학습 | 미실행 | 0/2 = 0% |

## 정확한 자료와 검토 범위

[실측] [기존 train_oos2](../../../../datasets/core/pointing/trainset/train_oos2/train_oos2.jsonl)는 정상1,377행·NONE1,236행이며 추가 H-train900행에는 정상300행·NONE600행이 있습니다. 원본 해시는 [전용 상태](../../../../program/research/daily_rag_slm/saluki_finetune_2026-10-09.json)에 고정했습니다. [직접 대조 결과](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/reviewed_train_oos2_audit_1206.json)는 추가900행 모두 원 H-train의 `agree` 상태·정답과 일치하고, 기존1,713행 전체가 유지됨을 확인했습니다.

[실측] [H 자료 생성기](../../../../program/scripts/plan_qa_bench/build_hard_set.py)의 생성 모델은 `gpt-6.1-sol`, 별도 라벨 모델은 `gpt-6-luna`입니다. 추가900행은 이 둘의 **AI 합의**이며 사람900행 검수를 확인한 것은 아닙니다. 첫1,713행은 증류1,313＋잡담 부정400으로, 전체가 동일한 두 AI 검토를 받았다고 넓혀 말하지 않습니다. [보강판 생성 근거](../../../../program/scripts/plan_qa_bench/results/train_oos2_report.json)는 H-test/D2/D3와 높은 표현 중복 후보99개 제외 및 H-train에서 기존 모델 오답 우선 채굴을 기록합니다.

## 바뀐 실행 계획

기존2,613행의 정상/NONE 비율·행을 그대로 쓰고 임의 재샘플링하지 않습니다. 별도1,713행 학습을 선행 조건으로 추가하지 않습니다. 새 D/E 평가 문장을 학습으로 옮기지 않습니다. 처음에는 작은 어댑터·낮은 학습률의 단일 cosine 판을 시험하고 **정상 요청 손실과 잡담 오지목을 동시에** 원본과 비교합니다. 다른 모델의 회귀가 살루키에도 반드시 생긴다고 단정하지 않습니다.

[단계별 실행 검사기](../../../../program/scripts/plan_qa_bench/server/queues/saluki_train_gate_20261009.py)는 연결 검사·본 학습·제품 채택을 분리했습니다. 신규 대조문/F/독립 보류 완성은 첫 학습 조건이 아닙니다. 제품 채택에는 사람 검수·별도 고정 보류 평가·정상/NONE 회귀 판정이 필요합니다. 정확한 동일 모델·역전파·실제 공간·잠금 조건은 유지했습니다. 새 GPU 작업·모델 다운로드·기존 작업 중단은 하지 않았습니다.

## 검증·백업·관계

- [현재 학습 계획](../../../../program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md) — 첫 판 실행 범위입니다.
- [수정 직전 문서·상태·색인 백업](../../../../program/research/daily_rag_slm/_backup/2026-10-09_120606_saluki_existing_reviewed_baseline/) — 과거 계획을 보존했습니다.
- [수정 직전 검사기 백업](../../../../program/scripts/plan_qa_bench/server/queues/_backup/2026-10-09_120606_saluki_stage_gates/) — 기존10조건 검사기를 보존했습니다.
- [단계별 CPU 계약 확인](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/stage_gate_contract_checks_1208.json) — 새 보류 자료가 없어도 baseline에 접근 가능하고, 제품 채택은 차단되는지 확인합니다. GPU 학습 성공이나 정확도 개선을 뜻하지 않습니다.
- [모델 평가 정본](../../quality/slm-model-evaluation.md) · [GPU 운영 정본](../../operations/gpu-work-queue.md) — 채택·실행 경계를 따릅니다.

[실측] 단계별 CPU 계약 **10/10 = 100%** 통과, Python 구문 검사1/1 통과입니다. 선택한2,613행 전체를 개발 평가9,425행과 다시 정확 대조하여 질문·전체입력 중복0/9,425, 정답완성문2,613/2,613 일치, 전체학습입력중복0/2,613을 확인했습니다. [전체자료 대조](../../../../program/scripts/plan_qa_bench/results/saluki_finetune_preflight_20261009_113242/data_audit_oos2_1208.json). 정확중복0은 의미·일정군 독립성 통과가 아닙니다.
