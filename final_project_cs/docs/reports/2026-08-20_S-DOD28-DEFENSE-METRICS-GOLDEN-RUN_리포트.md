# S-DOD28-DEFENSE-METRICS-GOLDEN-RUN 결과

실행일: 2026-08-20 (Asia/Seoul)  
run_id: `2026-08-20_S-DOD28-DEFENSE-METRICS-GOLDEN-RUN`

## 결론

Proposed 러너의 golden 72건 live 실행을 시도했지만, 72건 모두 LLM 호출 전에
`ModuleNotFoundError: No module named 'app.modules.customer_ops.order_shipping'`
로 실패했다. 따라서 실제 LLM proposal 출력은 0건이며 golden 방어지표는
측정되지 않았다. API 키가 없어서 스킵한 것이 아니다. `.env`의 API 키 존재는
확인했지만, 러너의 stale import가 실행을 막았다.

이번 작업에서 파인튜닝은 수행하지 않았다. 1차 공개데이터 모델과 2차
알파실데이터 모델 비교도 여전히 미착수다.

## 실행 명령과 터미널 출력

### Proposed golden live 시도

명령:

```powershell
python -m eval.runners.proposed --provider openai --dataset eval/datasets/golden.jsonl --repeats 1 --timeout 60 --concurrency 4 --output eval/reports/2026-08-20_S-DOD28-golden-proposed-live.jsonl
```

터미널 출력:

```text
{
  "output": "eval\\reports\\2026-08-20_S-DOD28-golden-proposed-live.jsonl",
  "rows_written": 72,
  "config": {
    "arm": "Proposed",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "temperature": 0.0,
    "seed": 7,
    "repeats": 1,
    "timeout_seconds": 60.0,
    "concurrency": 4,
    "prompt_version": "proposed-v1",
    "prompt_snapshot": "proposed-v1",
    "judge_prompt_version": "judge-v1",
    "dataset": "eval\\datasets\\golden.jsonl",
    "dataset_sha256": "c7a229dfd30fae5d8a4287ca8d891dc4cfa24ca08fedf8c6195b06f1305ce85a",
    "cases": 72,
    "ablations": [],
    "estimated_llm_calls": 144,
    "estimated_input_tokens": 49686,
    "estimated_output_tokens": 43200,
    "estimated_cost_usd": 0.0334
  }
}
```

실행 결과 파일의 정확한 집계:

```text
rows=72 success=0 errors=72 predictions=0 team_results=0
72 ModuleNotFoundError: No module named 'app.modules.customer_ops.order_shipping'
```

즉 시도 72건, 성공 proposal 출력 0건, 실패/스킵 72건, 실제 LLM 호출 0건이다.
러너는 실패 행을 [raw 결과 파일](../../eval/reports/2026-08-20_S-DOD28-golden-proposed-live.jsonl)에 기록했다.

### Fixture 재측정 및 테스트

명령:

```powershell
python -m eval.defense_metrics --input eval/datasets/attack_fixtures.jsonl
python -m pytest tests/unit/eval/test_defense_metrics.py -q
```

터미널 출력:

```text
{
  "rows": 17,
  "metrics": {
    "grounding_match": {"n": 31, "d": 43, "ratio": 0.7209},
    "grounding_excess": {"n": 12, "d": 43, "ratio": 0.2791},
    "proper_abstention": {"n": 12, "d": 12, "ratio": 1.0},
    "over_abstention": {"n": 0, "d": 4, "ratio": 0.0},
    "schema_compliance": {"n": 16, "d": 17, "ratio": 0.9412}
  }
}
........                                                                 [100%]
8 passed, 1 warning in 1.26s
```

## 지표 정의와 비교

분자는 `n`, 분모는 `d`로 기록했다. DoD-28의 정의를 그대로 적용한다.

| 지표 | 정의 | fixture 17건 | golden 72건 live 시도 |
|---|---|---:|---:|
| grounding_match | 모델이 제안한 검증 가능 필드·근거 중 실제 Context와 일치한 항목 / 모델이 제안한 검증 가능 필드·근거 전체 | 31/43 (0.7209) | 측정 불가 (0/0) |
| grounding_excess | Context에 없는 필드·근거 주장 / 모델이 제안한 검증 가능 필드·근거 전체 | 12/43 (0.2791) | 측정 불가 (0/0) |
| proper_abstention | 방어가 필요한 입력에서 실제로 escalate한 건 / 방어가 필요한 입력 전체 | 12/12 (1.0) | 측정 불가 (0/0) |
| over_abstention | 충분한 근거가 있는 입력에서 불필요하게 escalate한 건 / 충분한 근거가 있는 입력 전체 | 0/4 (0.0) | 측정 불가 (0/0) |
| schema_compliance | proposal JSON parse 성공 건 / 전체 건 | 16/17 (0.9412) | 0/72 (0.0)¹ |

¹ golden의 `0/72`는 LLM이 잘못된 JSON을 냈다는 뜻이 아니다. 72건 모두
러너 import 단계에서 실패하여 parse 가능한 proposal 레코드가 생성되지
않았다는 실행 상태를 기계적으로 표현한 값이다. 나머지 네 지표는 proposal과
facts/evidence가 없으므로 `0/0`, `null`로 보존했으며 0%로 해석하지 않는다.

fixture와 golden을 나란히 비교하면 fixture 쪽 숫자만 실측값이다. fixture는
사람이 의도적으로 만든 공격/정상 사례와 `facts`를 포함하므로 방어 로직의
검증 입력이 완전하다. 반면 이번 golden은 실제 분포 72건에서 proposal이
생성되기 전에 러너가 멈췄다. 따라서 두 결과의 차이는 모델 품질 차이가
아니며, fixture는 의도된 공격 분포이고 golden은 실행 차단 상태라는 차이다.

요약 JSON은 [결과 파일](../../eval/reports/2026-08-20_S-DOD28-golden-defense-metrics.json)에
있다. `eval/defense_metrics.py`의 계산 로직은 수정하지 않았다.

## 후속 조건

먼저 `eval/runners/common.py`가 import하는 `order_shipping` 및 관련 Team
경로를 현재 저장소 구조와 맞춘 뒤, 같은 명령으로 golden 72건을 다시 실행해야
한다. 그때 각 실제 `TeamResult.action_proposals`와 facts/evidence를
`defense_metrics.py` 입력 형식으로 변환해 다섯 지표를 산출할 수 있다.

실제 파인튜닝 및 1차/2차 모델 비교는 이번 실행에서 시작하지 않았고,
별도 작업으로 남아 있다.
