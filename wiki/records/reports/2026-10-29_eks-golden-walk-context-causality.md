---
type: report
title: EKS Linux golden2 — 도보·시간·출발 문맥 원인과 격리 수정
status: draft
domain: travel
---

# golden2 원인 추적·격리 수정

추가 해소 **1/5 = 20%**(test_golden_bike), 잔여 **4/5 = 80%**, PR110 **HOLD 유지**입니다. `test_bike_not_called_by_default`는 golden 단언까지 통과하지만, 그동안 가려져 있던 뒤쪽 단언이 실제 차이 1건으로 실패합니다. 이 차이는 Mobility 담당 결정이 필요해 실패로 그대로 둡니다. 중단된 Codex 작업(`C:/_proj/eksgolden_causality_1029`)을 Claude가 이어받았습니다. 기존 파일은 고치지 않았고 `claude_*` 파일만 추가했습니다. 자체 검증만 했으며 독립 검토 승인과 통합 예약은 없습니다.

## 보존·환경

- 기존 Codex 사본 `/root/eksgolden_causality_1029/candidate`(ee8ca880)는 tracked diff 0이고 원본 입력 113/113 SHA256이 일치합니다. 수정은 새 no-hardlinks 사본 `/root/eksgolden_causality_1029/claude_fix`, 브랜치 `fix/linux-golden-walk-context-20261029`, 로컬 커밋 `513ab4cc0e3a`에만 했습니다. push는 하지 않았습니다. 이 사본도 입력 113/113이 일치합니다.
- 원래 golden 5개(v1 3개·v2 2개), 픽스처, 입력 해시는 Codex `source-hashes.json`과 같습니다. **v1 golden·픽스처·입력·제품 코드 변경은 0입니다.**
- 환경은 Linux ARM64·Python 3.12.16이며 Codex 회귀와 같은 offline guard, 접속 불가 DB, `MOBILITY_GH_URL=none`을 썼습니다. EKS AMD64 운영 검증이 아닙니다. 운영·모델 호출, DB·리스너 생성, 권한 변경은 하지 않았습니다.

## 원인(원문·코드·이력 근거)

| 갈래 | 근거 | 영향 |
|---|---|---|
| ① 출발 문맥 | 10-13 이후 `items[].detail.departure_context` 추가(벽시계 `captured_at` 포함). `test_plan_v1`은 `_customer_values`로 이 문맥만 떼고 비교하지만(2c7378182), 두 시험은 원값 그대로 비교 | 두 시험 모두 golden과 다름 |
| ② 직접 도보 | bike v1(09-30)의 식당→롯데마트 도보 194m·4분은 직선 138.53m×1.4=193.94m·ceil(3.1)=4분과 정확히 같습니다. 즉 옛 직선 대체값입니다. 픽스처에 이 구간 `foot` 키는 없습니다. 현행 계약(cs wiki teams/mobility.md: 직접 도보를 직선×계수로 대신하지 않고 후보에서 제외)에 따라 도보 후보가 빠지고 `arrive_late` 처리됩니다 | bike golden 차이의 전부 |
| ③ 골든 판·런타임 | `plan_example_out_all_v1`은 e4965a542(10-14)가 v2를 만들기 전 판입니다(v1은 그대로 남김). 그 커밋은 v2의 원인으로 서울 안 걸음, 실제 다음 열차, 「롯데마트 보행 접근 미검증」을 기록했습니다. concurrency 시험은 계속 v1을 가리켰고, GH 설정에 따라 결과가 달라지는 `build_verifier(quiet=True)`를 썼습니다 | 기본 수단 결과와 golden 차이 |
| 가림 | 두 시험은 `mobility_full`이라 기본 pytest에서 deselect됩니다. 그래서 10-13·10-14 계약 변경 때 갱신되지 않았습니다 | — |

Codex trace를 다시 대조했습니다. ① 라우터 없이 저장된 실행(`default.json`)은 접근 도보가 다르고(993/825/214m) 직접 도보가 빠집니다. ② test_plan_v1 런타임(로컬 그래프·GH/실시간 끔)으로 저장된 실행(`local-router-diagnostic.json`)은 출발 문맥만 떼면 **all_v2와 차이 0**입니다.

## 수정(시험·기대 파일만, 격리 사본)

- `plan_example_out_bike_v2.json`을 새로 만들었습니다(v1 보존). 제품 실행에서 뽑지 않았습니다. v1에 위 ② 계약 변환만 적용해 독립 도출했습니다(경로 제거, 항목 seq 재부여, plan.py 1736–1747 문구 틀로 `skipped` 생성). 도출 결과가 실제 출력과 같은 것을 확인한 뒤 기록했습니다(`derived_equals_actual: true`).
- `test_plan_bike_v1`은 v2를 기준으로, 출발 문맥만 떼고 비교합니다(test_plan_v1과 같은 규칙). 나머지 단언은 그대로입니다.
- `test_plan_concurrency_v1`은 golden 비교만 all_v2를 만든 test_plan_v1 런타임에서 합니다. 이 실행에서도 자전거 판정 0회를 다시 단언합니다. 원래 런타임의 호출 수·with_bike 단언은 유지합니다. 기존 `stable_plan_clock`을 호출 시점에 적용해 with_bike 비교가 `captured_at`까지 모든 칸을 보도록 했습니다. 허용오차·마커·비교 범위 완화는 0입니다.

## 실행 결과

- golden2 단독: bike **통과**, concurrency 실패 1건(아래). 기본층(두 파일): 12/12 통과.
- Codex와 같은 5파일 회귀(`-k "not concurrent and not interleave"`): 24개 중 **21개 통과·3개 실패·skip 0**입니다(이전 20/24). 노드 집합은 같고 새 실패 0, 해소 1(test_golden_bike)입니다. 남은 실패 3개는 혼합 1·새벽 1·아래 1입니다. concurrency의 concurrent/interleave 시험과 전체 223개는 재실행하지 않았습니다. ruff·pyflakes가 없어 lint는 하지 않았고 py_compile만 통과했습니다.
- 가려졌던 차이([진단](../evidence/2026-10-29_eks-golden-walk-context-causality/claude-withbike-diagnostic.json)): 지하철·버스에 bike를 섞으면 `seongsu_to_dinner` 출발 문맥 `options`에 `bike`(17:02 출발·48분)가 추가됩니다. 고객 칸 items·routes의 나머지는 같습니다. 자전거 없는 픽스처 사본 대조군의 차이는 0입니다. 원인은 2b22b09ff(10-23)부터 문맥에 「조금 일찍 떠나면 닿는」 more_options를 싣게 된 것입니다. 확인 화면 후보 목록에 자전거가 나오는 것이 58 「섞어 주면 판정은 하되 추천하지 않는다」와 충돌하는지는 담당 결정 사항입니다. 그래서 단언을 완화하지 않았습니다.

## 남은 일·근거

- Mobility 담당: bike v2 도출과 all_v2 런타임 고정 수락, with_bike 출발 문맥의 자전거 more_option 허용 여부를 정해야 합니다. 허용하면 비교 범위 결정 후 시험을 고치고, 금지하면 제품 수정이 필요합니다. 혼합 1·새벽 1은 기존 인계대로입니다.
- 실제 EKS reader fatal은 미확정이며 PR110 draft/HOLD는 유지됩니다.
- [증거 묶음](../evidence/2026-10-29_eks-golden-walk-context-causality/): diff·도출·XML/로그·실행 정보·SHA256 목록. 원 작업 폴더 `C:/_proj/eksgolden_causality_1029`(Codex 원본 보존)·Linux `/root/eksgolden_causality_1029/{candidate,claude_fix}`.
