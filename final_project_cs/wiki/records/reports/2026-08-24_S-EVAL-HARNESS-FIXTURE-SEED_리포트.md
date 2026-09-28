# S-EVAL-HARNESS-FIXTURE-SEED 검증 리포트

## ★2026-08-24/25 — Claude 실 환경 최종 재측정 결과

Codex 구현을 독립 검증(404 passed 회귀 없음, `read.order`가 seed된
주문을 실제로 조회하는 것을 20건 스팟체크로 확인)한 뒤, A/B/Proposed
72건×3회(216행)를 **순차 실행**(`--concurrency 2`, 이전 동시 실행이
OpenAI TPM 한도를 공유해 18~47% rate-limit 오염을 냈던 결함을
피하려고)으로 다시 측정했다.

```
A:        216 rows, 0 rate-limited, success 0/216
B:        216 rows, 0 rate-limited, success 213/216 (98.6%)
Proposed: 216 rows, 0 rate-limited, success 21/216 (9.7%)
```

**픽스처 수정 효과 (수정 전 → 후, Proposed team_result outcome)**:
`completed` 54/216(25%) → **166/216(77%)**.
`required_evidence_missing`/`fulfillment_data_unavailable`로 인한
escalation은 **완전히 사라졌다**(구조적 100% 차단 해소 확인).

**남은 escalation은 전부 다른 원인이다** — `degraded_context` 49건,
전부 `g-exchange-*` 케이스에만 몰려 있다(RAG policy 검색이 exchange
관련 질의에서 실패하는 것으로 보임 — 이 계약의 범위 밖, 별도 조사
필요). NONE 1건은 측정 도중 PostgreSQL이 일시 재기동하며 생긴 접속
실패(`FATAL: the database system is in recovery mode`) — 환경
플레이크, 무시 가능한 수준(1/216).

**통계 (`eval/stats/bootstrap.py`, `eval/stats/mcnemar.py`, n=10000, seed=7)**:

| 비교 | score 평균차 (95% CI) | McNemar (b/c, p-value) |
|---|---|---|
| Proposed − A | −2.09 [−2.84, −1.37] | b=0, c=21, p≈9.5e-07 (Proposed가 binary pass에서 A를 유의하게 앞섬) |
| Proposed − B | −7.70 [−8.44, −7.00] | b=194, c=2, p≈2.2e-42 (B가 Proposed를 압도적으로 앞섬) |

★raw score와 binary pass 방향이 갈리는 지점(Proposed가 A보다 평균
점수는 낮은데 binary pass는 유의하게 이김)은 judge rubric의
`next_action` 축이 원인으로 보인다 — 216행 중 71건(33%)의 judge
사유가 명시적으로 "next action does not align"이었고, `next_action`
세부점수 분포가 0~1점에 65%가 몰려 있다. golden.jsonl의
`expected_next_action`이 `call_tool` 같은 값을 쓰는데 Team이 실제로
내는 `next_action`(respond/escalate/wait_for_approval/wait_for_input)
enum과 어휘가 안 맞는 것으로 보인다 — **이것도 이 계약 범위 밖이며
별도 확인이 필요하다.**

**결론**: 이 계약이 고치기로 한 문제(가짜 고객이라 DB 근거가 아예
없어 구조적으로 100% 거부되던 것)는 확인·해소됐다. Proposed가 B보다
낮게 나온 것은 이 수정과 무관한 두 가지 별개 원인(exchange RAG 실패,
next_action 어휘 불일치)이 남아있어서다 — Team 품질 자체가 나쁘다는
결론으로 바로 이어지지 않는다.

## 구현

`eval/runners/common.py`에 golden 평가용 멱등 픽스처 시딩을 추가했다.

- `execute()`가 `Proposed` 실행을 시작할 때 한 번만 호출한다. worker의 `_one()`/`_team_context()`마다 INSERT하지 않으므로 `--repeats`에서도 중복되지 않는다.
- 모든 로드된 golden case에 `uuid5(NAMESPACE_URL, case_id)` 고객을 만들고, 같은 고객의 최근 `delivered` 주문 1건을 UPSERT한다.
- `shipment.status`, `shipment.exception`, `fulfillment.track` case에만 배송 1건을 UPSERT한다.
- `delivered_not_received`는 `delivered`, `dispatch_delay`/`carrier_reply_pending`은 `delayed`, 나머지는 `in_transit`으로 시딩한다.
- `return.*`/`refund.*` capability의 current state에 `reason_code`와 `return_quantity=1`을 넣는다. issue code에 `defective`가 포함된 경우 reason code는 `defective`다.
- 주문일은 실행 시각 기준 3일 전으로 설정해 일반 7일 및 defective 90일 기본 반품 기간 안에 둔다.
- `orders`에 필요한 FK인 `customers`도 동일한 결정적 UUID와 tenant로 보장한다. `returns` 이력은 active 반품으로 오인되지 않도록 만들지 않는다.

실제 Team 모듈 파일과 `eval/datasets/golden.jsonl`은 수정하지 않았다.

## 실행 검증

명령:

```powershell
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --concurrency 2 --limit 20 --output eval/reports/_fixture_check.jsonl
```

결과: 프로세스는 정상 종료하고 20행을 생성했다. DB 확인 결과 `demo` tenant에 평가용 고객 20건, 주문 20건, shipment capability 대상 5건의 배송이 존재했다. 다만 20개 live 결과 모두 `APIConnectionError: Connection error.`로 끝나 `team_result` outcome 비교는 수행할 수 없었다. 샌드박스에서 `api.openai.com:443` 연결이 `WinError 10013`으로 차단된 환경 제약이다.

mock smoke 실행도 완료했다.

```powershell
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider mock --concurrency 2 --limit 20 --output eval/reports/_fixture_check_mock.jsonl
```

전체 비-live 테스트:

```text
381 passed, 3 deselected, 3 failed, 20 errors
```

실패 원인은 이번 변경과 무관한 환경/기존 통합 의존성이다. 20개 error는 `C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2` 접근 권한 문제와 관련된 e2e fixture setup 실패였고, RAG 3개 failure는 테스트 중 OpenAI embeddings 호출이 네트워크 차단으로 실패했다. 변경 파일의 문법 검사는 `python -m py_compile eval/runners/common.py`로 통과했다.

실환경에서는 동일한 live 명령을 네트워크가 허용된 상태로 다시 실행해 `required_evidence_missing` 및 `fulfillment_data_unavailable` 비율 감소를 확인해야 한다.
