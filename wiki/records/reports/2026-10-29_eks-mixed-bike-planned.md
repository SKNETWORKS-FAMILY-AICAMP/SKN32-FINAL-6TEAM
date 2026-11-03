---
type: report
title: EKS golden2 후속 — 섞어 준 자전거가 계획 수단이 되는 58 충돌 수정
status: draft
domain: travel
---

# 섞어 준 자전거 계획 수단 58 충돌 — 판정·격리 수정

선행 [보고서](2026-10-29_eks-golden-bike-policy-review.md)가 「담당 확인 필요」로 남긴 `_choose_planned` 문제입니다. 사용자가 기술 판단을 위임해서 Claude와 Codex가 함께 판정하고 고쳤습니다. 이번 수정은 5개 실패 목록과 별개인 정책 결함이라 누적 해소율은 **2/5 = 40%** 그대로입니다. 잔여 3/5와 PR110 **HOLD**도 그대로입니다. push·배포·원본 수정은 0이고, 로컬 커밋 `56fc3ce151c8`만 만들었습니다(기준 52f933e8).

## 판정: 58 위반 → 제품 수정

- 58 원문은 plan.py 170–183행 주석입니다(본인 9/27). 「**자전거는 추천하지 않는다**」, 그리고 「지하철·버스와 섞어 주면 계획 수단 규칙이 그대로라 더 일찍 떠나야 하는 자전거는 left_out 에 이유만」이라고 적혀 있습니다.
- 시험 머리말(test_plan_concurrency_v1 B)은 「섞어 bike 를 주면 판정은 하되 **추천하지 않는다** — items·routes 는 기본과 같다」입니다.
- 「규칙이 그대로라」는 보장이 아니라 결과를 예측한 설명이었습니다. 자전거가 더 일찍 떠나야 할 때만 맞습니다. Claude R1과 Codex R1이 각각 따로 판단했고 둘 다 위반으로 결론 냈습니다.
- 실제 실행 결과입니다. 저장소 단위 시험의 가짜 판정기 `_fake`를 썼고 자료·네트워크는 쓰지 않았습니다. 기준 트리는 52f933e8입니다.

| 경우 | modes | 기준 52f933e8 | 수정 56fc3ce1 |
|---|---|---|---|
| 짧은 구간 · 자전거가 더 늦게 떠나도 됨 | subway,bus,walk,bike | **planned=bike**, options=[bike], 도보는 earlier_departure | walk + `bike_not_recommended` 1줄 |
| 같은 경우 · 택시와 섞음 | walk,bike,taxi | **planned=bike** | walk + 1줄 |
| 자전거가 더 일찍 떠나야 함 | subway,bus,walk,bike | walk, 자전거 earlier_departure | walk + 1줄(코드가 정직해짐) |
| 자전거만 성립(역 없음) | subway,bike | **planned=bike** | skipped + left_out 1줄 |
| 테마 · 자전거가 더 늦게 떠나도 됨 / 자전거만 | walk,bike / bike | bike | bike(변화 없음) |

- 제품 경로에는 지금 노출되지 않습니다. `SURVEY_MODES`·`MOVE_MODES`에 bike가 없기 때문입니다. 라이브러리·CLI `plan()`에만 노출됩니다. 그래도 계약 위반이라서 고쳤습니다.

## 수정(설계 A — Claude·Codex R1 합의)

- `Planner._bike_mixed()` 술어 하나만 둡니다. 정의는 bike가 있고 walk가 아닌 다른 탈것도 있는 경우입니다. 테마(modes ⊆ {bike, walk})는 해당하지 않습니다. 술어는 앞 판 B와 같습니다.
- `leg()` ④는 자전거를 계속 판정합니다(`_bike_direct`). 섞어 준 요청이면 자전거를 opts에 넣지 않습니다. 대신 구간 없는 left_out 줄 `bike_not_recommended`를 한 줄 남기고, 역산 출발과 소요를 적습니다. 그래서 계획 수단·options·more_options·departure_context·혼합(⑤) 앞설 축 비교가 모두 bike를 뺀 요청과 같아집니다.
- `_earliest_targets`는 섞어 준 요청에서 자전거 소스를 뺍니다. docstring의 「후보 공간은 leg() 와 같다」를 지키기 위해서입니다. 빼지 않으면 자전거 목표가 `tries`를 다 쓴 뒤 leg()에서 거절됩니다.
- 52f933e8의 extras 필터는 이제 닿지 않아서 지웠습니다. 규칙은 한 곳에만 있습니다.
- `PLAN_VERSION`은 올리지 않았습니다. 기본 출력이 같고 `test_earliest_v1`이 v2.10을 고정하기 때문입니다. 되돌릴 수 있는 선택입니다.
- `why = bike_why` 조건은 바꾸지 않았습니다. 이 조건은 성립하지 않는 자전거의 대표 이유에만 쓰입니다.
- 주석과 docstring에는 보장 범위를 적었습니다. 성립하는 자전거만 대상이고, 성립하지 않으면 종전 58 줄이 남습니다.

## 시험(test_plan_bike_v1 U축 +3, 기존 단언 수정 0)

| 실행 | 결과 |
|---|---|
| 새 3개 RED(52f933e8) | 2 실패 · 1 통과(테마 대조군은 기준에서도 통과하도록 설계) |
| 새 3개 GREEN(최종) | 3/3 |
| 변이 M1 차단 끔 · M2 술어 `modes & {subway,bus}` · M3 술어 `"bike" in modes` · M4 earliest 차단 끔 | 각각 2 · 1 · 2 · 1 실패(전부 검출 · sha 복원 확인) |
| golden2(실자료) | 2/2 |
| mobility_full 전체 223(concurrent·interleave 포함) | 220/223. 기준과 nodeid 집합이 같고, 실패 3개도 같은 nodeid라 **새 실패 0** |
| 기본층(mobility 전체 + intake 경로 후보) | 1619 통과 · 1 skip(기준 1616+새 3 · skip 동일) |
| ruff 0.16.8(CI 고정판 · 루트 ruff.toml) | 통과 |

- 남은 3실패는 기존과 같습니다. `test_earliest_v1 …[after_last_holiday]`, `test_mixed_v1 …stations_blocked`, `test_station_fallback_v1 …only_blocked_stations`입니다.
- 실행 환경은 Linux aarch64, Py3.12.16, offline guard, `MOBILITY_GH_URL=none`입니다. 최종 plan.py sha256 앞자리는 `64b8880222fd8130`입니다.

## 독립 검토(Claude opus-5-5 · Codex gpt-6.1-sol, 텍스트 전용)

- R1(설계): 둘 다 위반으로 판정했고 A안과 새 코드·earliest 제외를 권했습니다.
- R2는 **무효**입니다. 변이 실행 중에 diff를 떠서 `if False: # MUTATION`이 섞였고, 두 검토자 모두 이를 잡아 커밋 차단을 권했습니다. 트리는 이미 복원돼 있었고(sha 일치), 시험 결과는 복원된 트리 기준입니다. R2의 유효 지적 두 가지(보장 범위 한정, skipped 분기 more_options 단언)는 반영했습니다.
- R3(최종 diff): 둘 다 「필수 수정 없음 · 로컬 커밋 OK」입니다.

## 남은 일

- 후속(검토 권고, 필수 아님):
  - 공개 결과 departure_context에 섞어 준 자전거가 없는지 단위로 직접 단언하기. 지금은 golden2와 more_options 동치로 간접 확인만 합니다.
  - 성립하지 않는 자전거와 `earliest_on_late`의 혼합 회귀 시험.
  - 앞 일정보다 먼저 떠나야 하는 자전거 이유 문구를 구분하기.
- 이전부터 이어진 일:
  - foot 키를 담은 bike 요약 재기록(GH 기기).
  - 3실패.
  - 통합 예약.
  - 운영 reader fatal(PR110 HOLD).
- [증거](../evidence/2026-10-29_eks-mixed-bike-planned/): diff, 탐침, 로그·XML·exit, 변이, 검토 질문·답·호출 id, SHA256이 있습니다. 작업 폴더는 `C:/_proj/eksbike_planned_1029`, 사본은 `/root/eksbike_planned_1029/review`(브랜치 `fix/mobility-mixed-bike-planned-20261029`)입니다. 선행 사본 `review`·`claude_fix`·`candidate`는 수정하지 않았습니다.
