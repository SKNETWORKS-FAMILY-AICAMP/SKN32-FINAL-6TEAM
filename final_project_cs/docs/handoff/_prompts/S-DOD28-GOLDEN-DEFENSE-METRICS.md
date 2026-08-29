# S-DOD28-GOLDEN-DEFENSE-METRICS — golden.jsonl 실측으로 방어지표 5종 측정

## 0. 배경 — 막혔던 원인은 오늘 이미 풀렸다

`docs/evidence/DoD-28_파인튜닝_방어지표.md`가 기록한 대로,
2026-08-20 시도는 `eval/runners/common.py`가 legacy로 옮겨진
`order_shipping`/`return_exchange` 팀을 하드코딩 import해서 golden
72건 전부가 `ModuleNotFoundError`로 막혔다. **이 러너는 오늘
(2026-08-24~28) 세션에서 `build_registry()` 기반으로 전면 재작성됐고,
capability 라우팅·DB 픽스처 부재 버그도 오늘 다 고쳤다** — 지금은
`python -m eval.runners.proposed --provider openai ...`가 golden
72건을 정상적으로 real LLM으로 돌린다(216행/72건×3회, judge pass
60/216 — `eval/reports/2026-08-28_reeval_Proposed_v3.jsonl` 참고).
그러니 이번 계약이 막을 이유가 없다.

`eval/defense_metrics.py::score()`는 golden 실행 결과가 아니라
**다른 입력 형식**을 기대한다:

```json
{"case_id":..., "expect_block": bool, "parse_ok": bool, "degraded": bool,
 "proposal": {"arguments": {...}, "rationale_evidence_ids": [...]} | null,
 "facts": {"<collection>": {...}, "evidence_ids": [...]}}
```

(`eval/datasets/attack_fixtures.jsonl` 예시를 봐라.) golden.jsonl
실행 결과(`TeamResult.action_proposals`)를 이 형식으로 **변환하는
다리(bridge)가 없다** — 이게 이번 계약의 핵심 작업이다.

## 1. 할 일

### 1.1 golden 실행 → defense_metrics 입력 변환 스크립트

새 스크립트 `eval/bridge_golden_to_defense.py`(또는 적당한 이름)를
만들어라:

1. `eval/reports/2026-08-28_reeval_Proposed_v3.jsonl`(오늘 만든
   실측 결과, 216행)을 읽어라. 새로 실행할 필요 없다 — 이미 있는
   결과를 재사용해라(비용 절약).
2. 각 행의 `team_result.action_proposals`가 **비어있지 않은** 행만
   골라라(action_proposal이 없는 행은 애초에 검증 대상이 아니다 —
   `respond`/`escalate`로 끝난 행은 제외).
3. 각 행에 대해:
   - `parse_ok`: `team_result`가 정상 파싱됐으면 `true`(golden 실행은
     이미 구조화된 `TeamResult`라 거의 항상 `true`일 것이다 — 언제
     `false`가 될 수 있는지 판단해서 반영해라).
   - `degraded`: 그 행의 `team_result`가 참조한 원래 `ContextPack.degraded`
     값. 실행 결과 jsonl에 이 필드가 없다면, 어디서 구할 수 있는지
     확인해라(원본 `eval/runners/common.py`의 실행 경로를 읽어서 —
     없으면 `false`로 두고 그 사실을 리포트에 적어라).
   - `proposal`: `action_proposals[0]`에서 `arguments`와
     `rationale_evidence_ids`를 그대로 옮겨라.
   - `expect_block`: **golden.jsonl 케이스는 전부 정상 시나리오다
     (공격 fixture가 아니다)** — 따라서 원칙적으로 `expect_block:
     false`가 맞다(정상 제안이 부당하게 막히면 안 된다는
     "과잉 기권율"만 golden에서 잴 수 있다, "적절한 기권율"은
     attack_fixtures.jsonl이 이미 재고 있다). 이 판단이 맞는지 코드
     주석·`CLAUDE.md` §0.2를 다시 읽고 확인해라 — 틀렸다고 판단되면
     왜 그런지 리포트에 명확히 적고 다르게 처리해라.
   - `facts`: **이게 제일 까다롭다.** `verify_proposal()`이 실제로
     대조할 수 있게, 그 golden case가 실행 시점에 seed됐던 DB 상태를
     반영해야 한다. `eval/runners/common.py::_seed_golden_fixtures()`
     (오늘 추가됨)가 어떤 `orders`/`shipments` 행을 만들었는지 보고,
     같은 `tenant_id`+`customer_id=uuid5(NAMESPACE_URL, case_id)`로
     **지금 DB에 실제로 남아있는 그 행을 다시 조회**해서
     `facts.orders`/`facts.shipments` 등을 채워라(하드코딩하지 마라
     — DB가 정본이다). `evidence_ids`는 `team_result.evidence`의
     `evidence_id` 목록을 그대로 써라.
4. 결과를 `eval/reports/2026-08-28_golden_defense_input.jsonl`로
   저장해라.

### 1.2 방어지표 측정

```powershell
python -m eval.defense_metrics --input eval/reports/2026-08-28_golden_defense_input.jsonl
```

출력을 `eval/reports/2026-08-28_golden_defense_metrics.json`으로
저장해라(`--input`만 있고 `--output`이 없으면 stdout을 파일로
리다이렉트해라 — `main()`의 실제 인자를 확인해라).

## 2. 검증

- 변환된 행 수가 실제 `action_proposals`가 있는 golden 실행 결과
  행 수와 일치하는지 확인해라.
- `facts`가 빈 dict인 행이 있으면 왜인지 확인해라(DB 조회가 실패했나,
  애초에 그 케이스엔 seed가 없었나 — `_seed_golden_fixtures()`가
  `shipment` capability에만 shipments를 시딩했다는 걸 기억해라).
- `python -m pytest tests/unit/eval -q`(방어지표 관련 기존 테스트)가
  그대로 통과하는지 확인해라(이 계약은 새 스크립트만 추가하고
  `eval/defense_metrics.py` 자체는 건드리지 않는다).
- `docs/reports/2026-08-28_S-DOD28-GOLDEN-DEFENSE-METRICS_리포트.md`에
  다섯 지표 결과 + 분모 + 한계(특히 `expect_block`을 전부 `false`로
  둔 것이 의미하는 바 — "과잉 기권만 잰다, 적절한 기권은
  attack_fixtures가 이미 잰다"는 걸 명확히)를 적어라.

## 3. 쓰기 대상

- `eval/bridge_golden_to_defense.py` (신규)
- `eval/reports/2026-08-28_golden_defense_input.jsonl` (신규)
- `eval/reports/2026-08-28_golden_defense_metrics.json` (신규)
- `docs/reports/2026-08-28_S-DOD28-GOLDEN-DEFENSE-METRICS_리포트.md` (신규)

## 4. 하지 말 것

- `eval/defense_metrics.py`, `app/core/verification.py` 등 검증 로직
  자체를 수정하지 마라 — 이번 계약은 입력을 만드는 다리만 놓는다.
- golden.jsonl을 다시 실행하지 마라(비용 낭비) — 오늘 만든
  `2026-08-28_reeval_Proposed_v3.jsonl`을 재사용해라.
- 파인튜닝(1차/2차 모델)은 이 계약 범위가 아니다 — 지표를 먼저
  만드는 게 이 계약의 목적이다(`docs/evidence/DoD-28...md`의 "선행
  관계" 표 그대로).
- `facts`를 지어내지 마라 — 실제 DB 조회 결과만 써라, 조회가 안 되면
  빈 값으로 두고 그 사실을 기록해라.
