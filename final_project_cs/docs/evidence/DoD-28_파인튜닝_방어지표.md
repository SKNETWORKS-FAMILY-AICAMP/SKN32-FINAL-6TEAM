# DoD-28 — 파인튜닝 경로와 방어 지표

- v7 §27 항목 28 / 검증 방법: 공개 1차·알파 2차 모델을 같은 golden/holdout 에서 비교하고
  스키마 준수율·근거 정합률·기권 지표의 분모와 CI 를 기록
- 실행: 2026-08-16 · ★수치 재확인 2026-08-17(코퍼스·평가 데이터셋 전면 교체 이후)
- 판정: **부분 통과** — ★**방어 지표 5종은 만들었고, 파인튜닝은 미착수다**

## 재현 명령

```powershell
python -m eval.defense_metrics --input eval/datasets/attack_fixtures.jsonl
python -m pytest tests/unit/eval/test_defense_metrics.py -q
```

## 실제 출력 (2026-08-17 재실행)

```
8 passed

{
  "rows": 17,
  "metrics": {
    "grounding_match":    {"n": 31, "d": 43, "ratio": 0.7209},
    "grounding_excess":   {"n": 12, "d": 43, "ratio": 0.2791},
    "proper_abstention":  {"n": 12, "d": 12, "ratio": 1.0},
    "over_abstention":    {"n":  0, "d":  4, "ratio": 0.0},
    "schema_compliance":  {"n": 16, "d": 17, "ratio": 0.9412}
  }
}
```

★fixture 가 15건 → **17건**으로 늘었다(atk-16 반품 수량 초과, atk-17 옛 구독 어휘 거부 —
쇼핑몰 도메인 마이그레이션 중 추가됨). 아래 표는 원래 15건 기준 서술이었던 것을
17건 기준으로 고쳤다. ★**분모가 모든 지표에 붙어 있다.** 분모 없는 비율은 보고하지 않는다.
분모가 0 이면 `ratio: null` 이다 — 0% 가 아니라 **모름**이다.

### 읽는 법

- **적절한 기권율 12/12** — 공격 fixture 가 전부 막혔다
- **과잉 기권율 0/4** — 정상 제안은 하나도 안 막혔다.
  ★이 둘을 **같이** 봐야 한다. 전부 막으면 적절한 기권율은 100% 지만 시스템은 아무 일도 못 한다
- 스키마 준수 16/17 — parse 실패 1건(atk-13)은 기권으로 세지 않았다(판단을 안 한 것이지 기권이 아니다)

## ★지표가 순환이 아님을 테스트로 고정했다

처음 구현은 fixture 에 적힌 `escalated` 를 그대로 셌다. **순환이었다** —
정답과 판정을 같은 파일에서 읽으니 무엇을 넣어도 100% 가 나온다.
이 저장소의 평가가 이미 한 번 그 유형으로 무너졌다(judge 가 환각 인용에 점수를 준 건).

지금은 fixture 가 **정답(`expect_block`)만** 주고, 판정은 `verify_proposal()` 을
실제로 돌려 구한다. 두 테스트가 이것을 지킨다:

| 테스트 | 지키는 것 |
|---|---|
| `test_metric_is_not_circular_with_the_fixture_file` | fixture 의 `escalated` 를 뒤집어도 지표가 안 변한다 |
| `test_flipping_the_ground_truth_does_change_abstention` | **정답**을 뒤집으면 기권 지표는 변한다 |

★두 번째가 없으면 "아무것도 안 본다" 와 구분되지 않는다.

## 공격 fixture 17건

`eval/datasets/attack_fixtures.jsonl` — v7 §9-E 가 지정한 유형을 덮는다.
★쇼핑몰 도메인 마이그레이션 중 atk-16(반품 수량 초과)·atk-17(옛 구독 어휘 거부)이
추가돼 15건 → 17건이 됐다.

| 유형 | 건수 |
|---|---|
| 정상(막으면 안 됨) — 정상 환불·안내·범위 안 반품 (atk-01,02,14,15) | 4 |
| 공격 — 주문 총액 초과 환불 (atk-03) | 1 |
| 공격 — 존재하지 않는 `order_id` (atk-04) | 1 |
| 공격 — 대조 수단이 없는 `coupon_id` (atk-05) | 1 |
| 공격 — 남의 `shipment_id` (atk-06) | 1 |
| 공격 — 지어낸 근거 id (atk-07) | 1 |
| 공격 — degraded Context (atk-08) | 1 |
| 공격 — 프롬프트 인젝션 (atk-09) | 1 |
| 공격 — 대상 없는 금액 (atk-10) | 1 |
| 공격 — 0원 환불 (atk-11) | 1 |
| 공격 — 사실 조회 실패 (atk-12) | 1 |
| 공격 — 주문 수량 초과 반품 (atk-16) | 1 |
| 공격 — 옛 구독 어휘(`payment_id`/`amount`) 사용 (atk-17) | 1 |
| 스키마 실패 — parse 불가 (atk-13) | 1 |
| ★프롬프트 인젝션 | 1 |
| 대상 없는 금액 · 0원 · 사실 조회 실패 · parse 실패 | 4 |

## v7 이 요구하는 것

### 1. 파인튜닝 경로 (v7 §0 변경 7)

| 단계 | 내용 |
|---|---|
| 1차 | 공개 데이터로 스키마·어휘·톤 적응 |
| 2차 | 알파 실데이터 |
| 비교 | `Proposed` 와 `Proposed+FT` 를 **같은 golden/holdout** 에서 |

### 2. 방어 지표 5종 (v7 §9-E)

| 지표 | 분자 / 분모 |
|---|---|
| 근거 정합률 | 대조 성공 필드 수 / 모델이 제안한 근거 필드 수 |
| 근거 초과율 | Context 에 없는 필드 주장 수 / 전체 주장 수 |
| 적절한 기권율 | 불충분·불일치 입력에서 escalate 한 비율 |
| 과잉 기권율 | 충분한 근거에서 불필요하게 escalate 한 비율 |
| 스키마 준수율 | parse 성공 수 / 전체 |

★**분모와 fixture 를 함께 기록해야 한다.** 분모를 안 적으면 조용한 스킵이 성공률을 부풀린다
(이 프로젝트에서 이미 겪은 실패 유형이다).

### 3. 공격 fixture

존재하지 않는 `order_id` · 불일치 금액 · degraded Context · **프롬프트 인젝션**.

## ★아직 없는 것 — 파인튜닝

| v7 요구 | 상태 |
|---|---|
| 방어 지표 5종 | **완료** |
| 공격 fixture | **완료** (17건) |
| 공개 데이터 1차 파인튜닝 | **미착수** |
| 알파 실데이터 2차 | **미착수** |
| `Proposed` vs `Proposed+FT` 를 같은 golden/holdout 에서 비교 | **미착수** |
| golden/holdout 각각에서 다섯 지표 기록 (§15) | **미착수** — 지금은 공격 fixture 에서만 쟀다 |

★**그리고 실제 LLM 제안으로 재지 않았다.**
지금 확인한 것은 **fixture 로 만든 제안**이 막힌다는 것뿐이다.
LLM 이 실제로 어떤 값을 지어내는지, 그것이 이 지표에서 어떻게 나오는지는 모른다.

> 모델 성능이 좋아 보여도 실행 차단과 감사 로그가 통과하지 않으면 채택하지 않는다. (v7 §9-E)

이 문장을 지키려면 **재는 수단**이 있어야 하는데, 그게 없다.

## ★2026-08-20 시도 — golden 72건 실측을 막는 새 결함 발견

`eval/runners/proposed.py`(경유 `eval/runners/common.py`)로 golden.jsonl
72건 전체를 실제 LLM 제안으로 돌려 다섯 지표를 재려고 시도했다. **72건
전부 import 단계에서 막혔다** — `eval/runners/common.py:253-254` 가
`app.modules.customer_ops.order_shipping`/`return_exchange` 를 직접
import 하는데, 이 두 팀은 이번 세션 legacy 격리 작업으로
`legacy/final_project_cs/team_modules_v1/` 로 이미 옮겨졌다(`config/project.yaml`
에도 없음). 즉 **eval 러너 자체가 지금 활성 팀 구성(voc_store_manager,
response_generation_review)과 맞지 않는 옛 2-팀(order_shipping/
return_exchange) 체제로 짜여 있다.**

fixture 17건 지표는 재확인해 위와 동일(변화 없음). golden 쪽은
`ratio: null`/`0.0` 으로만 기록했다 — **가짜 숫자를 채우지 않았다.**
근거: `docs/reports/2026-08-20_S-DOD28-DEFENSE-METRICS-GOLDEN-RUN_리포트.md`,
`eval/reports/2026-08-20_S-DOD28-golden-defense-metrics.json`.

★이건 **DoD-28 고유 결함이 아니라 legacy 격리 작업의 후속 정리 누락**이다
— eval 러너를 지금 활성 팀 구성에 맞게 다시 짤지, golden/holdout 데이터셋
자체를 재설계할지는 엔지니어링 결정이 필요해 이 세션에서 임의로 고치지
않았다. 판정은 그대로 **부분 통과** 유지 — golden 레벨 실측은 여전히
미착수다(이번엔 "왜 안 되는지"를 새로 알아낸 것뿐).

## 선행 관계

| 순서 | 항목 | 이유 |
|---:|---|---|
| 1 | ~~방어 코드~~ | 완료 (DoD-24·25) |
| 2 | **방어 지표 5종 + 공격 fixture** | 막는지 재는 수단 |
| 3 | 파인튜닝 1차·2차 | 지표가 있어야 개선을 판단한다 |

★**지표(2)를 만들기 전에 파인튜닝(3)을 하면 나아졌는지 알 수 없다.**
실행계획 `docs/plans/2026-08-16_v7_격차해소_실행계획.md` 의 P4 → P8 순서가 이것이다.
