---
type: guide
title: 여행 프로젝트 평가 안내
description: 여행 평가 자료·검사기·모델 비교 기준을 안내하며 쇼핑몰 실험과 분리한다
status: draft
tags: [evaluation, testing]
domain: travel
impl_scope: cs — 현재 릴리스 대상인 여행 cs의 평가 안내다. sample의 계약 검증을 대신하지 않는다
---

# 여행 프로젝트 평가 안내

현재 guguroute의 평가 재료는 여행 도메인입니다. 과거 쇼핑몰 실험의 통과율·원가·정확도를 현재 여행 제품 성능으로 옮겨 쓰지 않습니다.

| 확인할 내용 | 현재 자료·도구 | 이 결과가 말하는 범위 |
|---|---|---|
| 분류 자료의 형식·분리 | [자료 검사기](../../final_project_cs/scripts/verify_travel_eval_datasets.py) | 자료 검증이며 모델 정확도 시험이 아님 |
| 여행 요청 분류 | [분류 재생 도구](../../final_project_cs/eval/travel_classification/replay.py) | 고정된 입력·모델·프롬프트 조건에서 별도 실행 |
| 여행 골든·홀드아웃 | [golden](../../final_project_cs/eval/datasets/travel_golden.jsonl), [holdout](../../final_project_cs/eval/datasets/travel_holdout.jsonl) | 정답·독립성 검토가 필요한 평가 입력 |
| 여행 시나리오 | [시나리오 자료](../../final_project_cs/eval/datasets/travel_scenarios.jsonl) | 분류 결과와 전체 일정 처리 결과를 구분 |
| 릴리스 완료 조건 | [기존 v11 검사기](../../final_project_cs/scripts/verify_dod_v11.py) | 현재 계약과 대조가 필요한 기존 관문. 파일 존재는 통과가 아님 |
| 소형 모델·학습 모델 | [현재 모델 평가 기준](../../final_project_cs/wiki/quality/slm-model-evaluation.md), [학습 평가 안내](finetuning.md) | 원본·우리 데이터 학습 모델을 구분해 비교 |

2026-10-11 디스크의 비어 있지 않은 JSONL 행 수: 골든 **72개**, 홀드아웃 **24개**, 여행 시나리오 **10개**. 행 수는 정답 확정 수·모델 성공 수와 다릅니다.

## 결과를 보고할 때

평가 대상, 자료 판본·해시, 정확한 모델 이름과 우리 데이터 학습 여부, 프롬프트, 실행 조건, 성공/전체 수, 실패·건너뜀·미실행 수를 함께 남깁니다. 자료 검사·모델 평가·코드 회귀·실환경 확인을 구분합니다. 과거 수치를 오늘 날짜의 실측으로 표시하지 않습니다.

## 기존 평가 문서의 범위

기존 [지표](metrics.md)·[골든셋 설명](golden-set.md)·[프로토콜](protocol.md)·[Judge](judge.md)에는 쇼핑몰 시절 예시와 결과가 남아 있습니다. 현재 여행 평가의 입력·합격 근거로 쓰지 않으며, 필요한 방법만 여행 자료와 현재 계약으로 다시 검증합니다. 쇼핑몰 사용 금지 결정은 [D-023](../decisions/D-023-no-commerce-assets-in-use.md)입니다.

## 이전 문서

2026-10-11 정정 전 본문은 [보존본](_backup/2026-10-11_193844_current-facts/index.md)에 있습니다. 이전 측정·실험 결과를 현재 제품의 완료 증거로 사용하지 않습니다.

## 시점별 기록

[과거 평가 본문](../records/reports/2026-10-11_before-index.md) — 당시 실험 기록이며 현재 여행 평가 기준이 아닙니다.

## 관계

- [문서 작성 표준](../governance/document-standard.md) — 정본·근거·이력 분리 규칙

## 확인 범위

[실측 2026-10-11 작업 트리] 파일 수·입력 행 수·현재 경로는 [변경·계수 기록](../../program/research/wiki_review_2026-10-11/applied-current-facts-v3.json)에 남겼습니다. 배포 상태나 DB 적용 완료 수가 아닙니다.
