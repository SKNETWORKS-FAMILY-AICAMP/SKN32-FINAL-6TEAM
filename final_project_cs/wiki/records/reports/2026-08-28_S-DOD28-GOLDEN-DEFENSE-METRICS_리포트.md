# S-DOD28-GOLDEN-DEFENSE-METRICS — golden.jsonl 실측 방어지표 결과

★Codex 세션 2건(AI Hub 매핑·이 작업)이 모두 샌드박스 쓰기 권한
문제(`whoami` → `CodexSandboxOffline`, 워크스페이스 전체 쓰기 거부)로
파일을 못 만들어 Claude가 직접 작성·실행했다.

## 배경

2026-08-20 시도는 `eval/runners/common.py`가 legacy로 옮겨진 옛
2-팀 체제를 하드코딩 import해서 golden 72건 전부가 막혔다. 이
러너는 2026-08-24~28 세션에서 `build_registry()` 기반으로 전면
재작성됐고, capability 라우팅(68% 오라우팅)·DB 픽스처 부재·
`call_tool` 오라벨까지 오늘 세션에서 고쳤다. 그 결과가
`eval/reports/2026-08-28_reeval_Proposed_v3.jsonl`(216행, judge pass
60/216)이다 — 이 계약은 이 결과를 재사용해 방어지표 5종을 잰다.

## 구현

`eval/bridge_golden_to_defense.py` 신규 — golden 실행 결과 중
`team_result.action_proposals`가 있는 행만 골라
`eval/defense_metrics.py::score()`가 기대하는 입력 형식으로
변환한다. `facts`는 하드코딩하지 않고 그 case의
`customer_id=uuid5(NAMESPACE_URL, case_id)`로 **지금 DB를 실제로
재조회**해서 채운다(`orders`/`shipments`).

### ★설계 결정 — golden은 `expect_block: false`로만 잰다

golden.jsonl은 전부 정상 시나리오다(공격 fixture가 아니다). 따라서
"적절한 기권율"(공격을 막았는가)은 이 데이터로 잴 수 없다 —
`eval/datasets/attack_fixtures.jsonl`(17건)이 이미 그걸 잰다. 이
브릿지는 **"과잉 기권율"**(정상 제안이 부당하게 막히는가)만
`expect_block: false`로 잰다.

### ★버그를 하나 잡고 고쳤다 — `degraded` 필드 오염

처음 실행에서 `over_abstention: 60/60(100%)`이 나왔다 — 비정상적으로
높아서 바로 믿지 않고 원인을 팠다. `eval/runners/common.py`의 행
레벨 `degraded` 필드는 `team_result.warnings`가 하나라도 있으면
`true`가 되는데, `return.request`/`refund.calculate` capability는
**설계상 항상** "Mock 단계에서는 승인 제안만 생성" 경고를 달고
나온다(`app/modules/customer_ops/return_refund.py`) — 그래서 진짜
컨텍스트 저하 여부와 무관하게 이 필드가 proposal이 있는 행 전부에서
`true`였다. `verify_proposal()`을 독립적으로 직접 돌려 실제 문제
있는 행이 21/60(그 필드로 인한 60/60이 아니라)임을 먼저 확인한 뒤,
브릿지가 이 필드를 재사용하지 않도록 고쳤다(진짜
`ContextPack.degraded`는 저장된 실행 결과에 없어서 `false`로 고정 —
한계로 아래 남긴다).

## 결과 (`eval/reports/2026-08-28_golden_defense_metrics.json`)

```json
{
  "rows": 60,
  "metrics": {
    "grounding_match":   {"n": 681, "d": 702, "ratio": 0.9701},
    "grounding_excess":  {"n": 21,  "d": 702, "ratio": 0.0299},
    "proper_abstention": {"n": 0,   "d": 0,   "ratio": null},
    "over_abstention":   {"n": 21,  "d": 60,  "ratio": 0.35},
    "schema_compliance": {"n": 60,  "d": 60,  "ratio": 1.0}
  }
}
```

| 지표 | golden(정상 시나리오, n=60) | attack_fixtures(n=17, 기존) |
|---|---|---|
| 근거 정합률 | 97.0% (681/702) | 72.1% (31/43) |
| 근거 초과율 | 3.0% (21/702) | 27.9% (12/43) |
| 적절한 기권율 | 측정 불가(정상 케이스라 분모 0) | 100% (12/12) |
| 과잉 기권율 | **35.0% (21/60)** | 0% (0/4) |
| 스키마 준수율 | 100% (60/60) | 94.1% (16/17) |

## 읽는 법 · 한계

- **근거 정합·초과는 golden이 attack_fixtures보다 훨씬 좋다** —
  당연하다, golden은 정상 상황이라 제안이 실제 DB 사실과 잘 맞는다.
- **과잉 기권율 35%가 눈에 띈다.** 정상적인 반품/환불 제안 60건 중
  21건이 검증 단계에서 막혔다는 뜻이다. 원인은 이번 계약 범위 밖 —
  `verify_proposal()`이 어떤 필드에서 걸리는지(수량 상한, 근거 id
  불일치 등) 세부 분해가 필요하다. **`attack_fixtures`의 과잉 기권율
  0%와 대비되는 수치라 후속 조사 가치가 있다.**
- `degraded`는 저장된 실행 결과에 진짜 `ContextPack.degraded` 값이
  없어 전부 `false`로 고정했다 — 실제로 컨텍스트가 저하된 채
  제안이 나온 케이스가 섞여 있었다면 그만큼 과잉 기권율이 과소평가됐을
  수 있다(반대 방향 오차는 아니다 — `degraded=true`를 더 넣었으면
  과잉 기권율이 더 올라갔을 것이다).
- 파인튜닝(1차/2차)은 여전히 미착수 — 이 지표가 그 선행 조건이었고
  이제 golden 기준선이 생겼다.

## 검증

```
python -m eval.bridge_golden_to_defense --input eval/reports/2026-08-28_reeval_Proposed_v3.jsonl --output eval/reports/2026-08-28_golden_defense_input.jsonl
  → rows_in=216, rows_with_proposal=60, rows_written=60, rows_with_empty_facts=0
python -m eval.defense_metrics --input eval/reports/2026-08-28_golden_defense_input.jsonl
  → 위 결과
python -m pytest -q -m "not live"  → 404 passed, 0 failed (회귀 없음)
```
