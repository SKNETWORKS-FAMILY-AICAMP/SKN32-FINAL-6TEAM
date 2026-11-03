---
type: report
title: EKS golden2 — 자전거 58 결정과 출발 문맥 충돌 판정·격리 수정
status: draft
domain: travel
---

# 자전거 58 충돌 판정·격리 수정

선행 보고서 기준 추가 해소 **1/5**, 누적 **2/5 = 40%**, 잔여 **3/5 = 60%**입니다. 이번에 해소한 시험은 `test_bike_not_called_by_default`입니다. PR110은 **HOLD를 유지**합니다. 판정은 Claude 독립 검토와 Codex 2회 검토가 같은 결론을 냈습니다(Codex 텍스트 검토만, 도구 실행 없음). push·배포·원본 수정은 0입니다.

## 판정: 충돌함 → 제품 수정

- 결정 58의 기록(plan.py 주석, 본인 9/27): 「지하철·버스와 섞어 주면 … 더 일찍 떠나야 하는 자전거는 봉투 left_out 에 **이유만** 남는다」.
- 2b22b09ff(10-23)는 `earlier_departure`·`mix_dominated` 후보를 `Planner.more_options`(확인 화면 경로 후보)와 `departure_context`로 내보냅니다. 고객이 그 경로를 고르면 `selected_context`가 등록합니다. 자전거 예외가 없어서, 섞어 준 자전거가 **고를 수 있는 경로**가 됐습니다. 이것은 「이유만」과 어긋납니다.
- 현재 제품 경로에서는 일어나지 않습니다. `SURVEY_MODES`와 `MOVE_MODES`에 bike가 없습니다. 채팅은 수단 하나만 넘깁니다. 출발 재검증은 None·walk·taxi만 씁니다. web-intakes 계약도 자전거를 구간에 넣지 않는다고 정합니다. 남는 경로는 라이브러리·CLI `plan()`뿐입니다. 그래도 계약 위반이라, 시험에서 출발 문맥을 떼는 쪽(가림)보다 제품 수정을 택했습니다. Codex R1 Q1·Q2도 같은 결론입니다.
- 조건: bike가 walk가 아닌 다른 탈것(지하철·버스·택시)과 함께 오면 bike 다리가 있는 후보를 extras에서 뺍니다. Codex는 bike+taxi도 막는 B안을 권했습니다. 자전거 테마(modes ⊆ {bike, walk})는 그대로입니다.

## golden 변경 정당성(513ab4cc 재검토)

- bike v2는 **조건부로 정당합니다.** 직접 도보는 fixture router(`BikeRouter(None, 요약)`)만 써서 기기와 무관합니다. 요약에 foot 키가 없으면 10-13 계약에 따라 제외되고 `skipped/arrive_late`가 됩니다. 이 골든은 「도보 근거 없는 fixture의 동작」을 잠급니다. 도보 성공 경로까지 덮으려면 GH 기기에서 foot 키를 담은 요약을 다시 기록해야 합니다. 이 일은 후속으로 남깁니다(Codex Q4).
- 기본 골든을 all_v2 생산 런타임에서 비교하도록 바꾼 것은 약화가 아닙니다. 자전거 판정 0회를 다시 단언합니다. 다만 `_runtime()` 출력과 골든의 직접 비교는 빠졌습니다.

## 수정(격리 사본 `/root/eksbike_policy_1029/review`, 로컬 커밋 `52f933e82dbb`, 기준 513ab4cc)

- `engine/plan.py`(+6줄): `bike_mixed`이면 extras에서 bike 다리 후보를 건너뜁니다. 그래서 `more_options`와 `departure_context`가 함께 정리됩니다.
- `test_plan_concurrency_v1`(+13줄, 기존 단언 수정 0)에 세 가지를 더했습니다.
  - 같은 rt2에서 기본 수단으로 돌린 대조군과 자전거 판정 0회 확인.
  - with_bike와 대조군이 left_out을 뺀 모든 칸에서 같아야 한다는 단언.
  - 출발 문맥에 bike 다리가 0이어야 한다는 단언.
- 대조군을 처음에는 전체 동일로 단언했다가 실패했습니다. 차이는 `walk_basis.reason` 하나였습니다(`no_router`와 `walking_router_unavailable`, 복사본 라우터 차이). 그래서 대조군은 몸통(items·routes)으로만 비교합니다. 선행 진단이 「대조군 차이 0」이라고 한 것은 items·routes만 비교한 결과였습니다.

## 실행 결과(Linux aarch64·Py3.12.16·offline guard·`MOBILITY_GH_URL=none`·고정 시계)

| 실행 | 결과 |
|---|---|
| golden2 기준(513ab4cc) | 1/2 통과(concurrency 실패 재현) |
| golden2 수정 최종(52f933e8) | **2/2 통과** |
| 변이(필터만 끔) | 실패(「left_out 밖 칸을 바꿨다」) — 검출력 확인 |
| 5파일 회귀(`-k "not concurrent and not interleave"`) | **22/24 통과**·실패 2·skip 0. 기준 21/24와 노드 24개가 같고, 해소 1·새 실패 0 |
| 기본층 4파일(intake 경로 후보 포함) | 78 통과·9 deselect |

- 남은 실패 2건은 기존과 같습니다: `test_mixed_v1::test_full_earliest_uses_mixed_when_stations_blocked`, `test_earliest_v1::test_full_earliest_waits_for_first_train[after_last_holiday]`.
- 다음은 실행하지 않았습니다: 전체 223개, concurrent/interleave, lint(py_compile만 통과), EKS AMD64.

## 남은 일

- 혼합 수단에서 자전거가 가장 늦게 떠나도 되는 후보이면 `_choose_planned`가 그것을 계획 수단으로 고를 수 있습니다. 이번 fixture에서는 일어나지 않습니다. 「이유만」 규칙과 맞추려면 담당자의 정책 확인이 필요하며, 이번에는 바꾸지 않았습니다.
- 다음도 남아 있습니다.
  - foot 키를 담은 bike 요약 재기록(GH 기기).
  - 혼합 1건과 새벽 1건.
  - 통합 예약(아직 없음).
  - 운영 reader fatal(미확정, PR110 HOLD).
- [증거](../evidence/2026-10-29_eks-golden-bike-policy-review/): diff·실행 로그·XML·진단·Codex 질문과 답·SHA256. 작업 폴더는 `C:/_proj/eksbike_policy_1029`입니다. 선행 사본 `claude_fix`와 `candidate`는 수정하지 않았습니다.
