---
type: guide
title: 현재 여행 평가 도구
description: 현재 여행 기준과 사용 종료된 기록을 구분한다
status: draft
domain: travel
---

# 현재 여행 평가 도구

현재 평가는 여행 자료만 사용합니다. 과거 A/B/Proposed 쇼핑몰 자료·점수·평가 명령은 보존 기록으로 분리합니다.

## 실행 경로

| 목적 | 현재 입력·도구 | 판정 범위 |
|---|---|---|
| 여행 분류 | `eval/datasets/travel_golden.jsonl`·`travel_holdout.jsonl`, `python -m scripts.verify_travel_eval_datasets` | 스키마·intent·issue_code·재유입 검사. 모델 정확도 측정과 구분 |
| 모델 분류 재생 | `python -m eval.travel_classification.replay <자료>` | 실제 모델·지연·잘못된 Team 라우팅. 실패도 분모에 포함 |
| 여행 일정 회귀 | `eval/runners/travel_scenarios.py`, `tests/scenario/test_travel_eval_scenarios.py` | 합성 여행의 판단·적용 검사. 실시간 외부 API·실제 여행 성공률을 대신하지 않음 |
| 행동·대상 결정 | `eval/decision_unit/` | 해당 자료·출력 계약의 판단 품질 |

위 명령은 cs 폴더에서 실행합니다. 모델·DB·외부 호출 여부를 실행 전에 해당 도구 설정으로 확인합니다. 분류 자료 검사 통과는 실제 모델 평가 완료가 아닙니다.

## 결과를 보고하는 기준

자료 버전·학습 여부·모델·프롬프트·seed·반복·실패·표본·환경을 함께 남깁니다. holdout으로 프롬프트를 고치지 않습니다. 사람 검수 전 합성 라벨을 확정 정답으로 과장하지 않습니다. 현재 모델 비교·채택은 [모델 평가](slm-model-evaluation.md) 및 그 문서가 가리키는 최신 기록으로 확인합니다. 2026-09-22 시나리오 10건 결과는 과거 실행 기록이며 오늘 전체 제품 통과 수가 아닙니다.

## 과거 기록

[수정 전 문서](../records/commerce_2026-10-11/wiki--quality--eval-harness.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="평가-하네스"></a>
<a id="구조"></a>
<a id="여행-시나리오-측정-2026-09-22"></a>
<a id="실행"></a>
<a id="결과-형식"></a>
<a id="-어느-파일이-유효한가"></a>
<a id="지금-비어-있는-것"></a>
<a id="재현성"></a>
<a id="judge"></a>
<a id="자주-걸리는-함정"></a>
<a id="관계"></a>
<a id="일정-항목-인식-모델의-비교"></a>
