# S-EVAL-HARNESS-FIXTURE-SEED — golden 평가용 가상 고객에 실제 DB 픽스처 시딩

## 0. 배경 — 실측으로 확인된 구조적 결함(Team 버그 아님)

`eval/runners/common.py::_team_context()`가 각 golden case마다
`customer_id = str(uuid5(NAMESPACE_URL, case["case_id"]))`로 **가상
고객 ID**를 만든다(line ~273). 이 ID는 실제 `customers`/`orders`/
`returns`/`shipments` 테이블 어디에도 없다.

2026-08-24 Proposed arm 재측정(`eval/reports/2026-08-24_reeval_Proposed.jsonl`,
216행, seed=7, provider=openai)에서 다음을 실측했다:

- `procurement_order_payment` team이 처리한 54건은 전부 `completed`
  (policy/RAG 근거만으로 답이 가능한 capability라서).
- `return_refund`가 처리한 108건은 **전부** `escalated` +
  `failure_code="required_evidence_missing"`.
- `fulfillment_logistics`가 처리한 54건은 **전부** `escalated` +
  `failure_code="fulfillment_data_unavailable"`.

`app/modules/customer_ops/return_refund.py::execute()`를 직접 읽어서
확인한 근거: `order = self.tools.call("read.order", ...)` → 가상
고객이라 `orders`에 행이 없어 `order=None` → `if not order or not
policy: escalated required_evidence_missing`(이 파일의 해당 줄).
`app/modules/customer_ops/fulfillment_logistics.py::execute()`도
동일하게 `order`/`shipments`가 없어 `fulfillment_data_unavailable`/
`shipment_status_unknown`으로 떨어진다.

★이건 Team 코드 결함이 아니라 **eval harness가 새로 만들어진 3개
DB-fact 의존 Team(`return_refund`·`procurement_order_payment`·
`fulfillment_logistics`)용 픽스처를 한 번도 시딩한 적이 없어서
생기는 구조적 갭**이다. `CLAUDE.md` §0.1 "근거 없으면 확정 답변을
만들지 않는다"가 정확히 의도한 대로 정직하게 거부하고 있는 것 —
Team을 고치면 안 된다, **harness를 고쳐야 한다.**

추가로 확인한 것: `return_refund.py`의 `return.check_eligibility`
분기는 `order`/`policy`가 있어도, `current_state`에
`reason_code`/`return_quantity`가 **둘 다** 있어야 `completed`까지
간다(없으면 `waiting`/`WAIT_FOR_INPUT`). 지금 `_team_context()`가
만드는 `current_state`(line ~275 근처, `{"case_id":..., "customer_id":...,
"intent":..., "issue_code":..., "status": "open", "version": 1}`)엔
이 두 필드가 없다. golden.jsonl 자체에도 구조화된 reason_code/quantity
필드가 없다(자유 텍스트 `message`만 있음) — harness가 만들어 넣어야
한다.

## 1. 할 일

### 1.1 picture: golden case → 픽스처 매핑

`eval/datasets/golden.jsonl`을 열어서 각 case의 `expected_capability`
필드를 확인해라(이미 있다 — 이번 세션에 추가된 필드다). 이 값에 따라
어떤 테이블에 무엇을 시딩할지 결정한다:

- `expected_capability`가 `shipment.*`나 `fulfillment.track`이면:
  `orders` 1행 + `shipments` 1행이 필요하다.
- `expected_capability`가 `return.*`나 `refund.*`면: `orders` 1행 +
  (선택) `returns` 이력 + `current_state`에 `reason_code`/
  `return_quantity` 주입이 필요하다.
- `expected_capability`가 `order.*`/`payment.*`/`procurement.*`면:
  `orders` 1행이면 충분해 보인다(이 팀은 이미 100% completed였으니
  **건드리지 마라** — 지금 통과하는 걸 깨뜨리면 안 된다).
- `expected_capability`가 `None`인 12건은 이번 계약 범위 밖이다
  (건드리지 마라 — 원래도 특정 capability를 안 겨냥한 케이스다).

### 1.2 `orders` 픽스처

모든 golden case에 대해(이미 픽스처가 있으면 건너뛰는 게 아니라 —
아래 idempotent 방식으로) 하나의 `orders` 행을 만들어라:

- `customer_id = uuid5(NAMESPACE_URL, case_id)`(harness가 이미 쓰는
  것과 정확히 같은 계산식을 재사용해라 — `app/core/idempotency.py`나
  `uuid5(NAMESPACE_URL, ...)` import 위치를 `common.py` 상단에서
  확인해라).
- `ordered_at`은 "지금부터 며칠 전"으로 설정하되, `return_refund.py`의
  `_policy_days()` 기본값(일반 반품 7일, defective 90일)과 정책
  문서(`knowledge/documents/` 중 반품 기간 관련 문서, `doc_15` 등을
  참고해라 — golden.jsonl의 `doc_ref` 필드가 힌트다)를 감안해
  **기간 내로** 잡아라(예: 3일 전). 이렇게 해야
  `return_period_expired`로 잘못 걸리지 않는다.
- `status`, `total_cents`, `item_count`은 합리적인 기본값을 써라
  (예: `status='delivered'`, `total_cents=39800`, `item_count=1`).
- `tenant_id`는 harness가 이미 쓰는 `settings.tenant_id`를 그대로
  써라.

### 1.3 `shipments` 픽스처 (shipment/fulfillment capability에만)

`fulfillment_logistics.py`가 `shipments[0].status`를 읽고, "unknown"/
"unavailable"이면 거부한다는 걸 확인했다 — 실제 상태 문자열을 넣어라.
`expected_issue_code`를 대충 훑어서(예: "delivered_not_received"면
`status='delivered'`, "dispatch_delay"/"carrier_reply_pending"이면
`status='delayed'`, 그 외엔 `status='in_transit'` 같은 무난한 기본값)
너무 정교하게 맞추려 하지 마라 — **완벽한 시나리오 재현이 목적이
아니라, "가짜 고객이라 데이터가 아예 없어서 100% 거부"라는 구조적
문제를 없애는 게 목적이다.** 몇 개 case가 여전히 escalate/wait로
나와도 된다(그게 진짜 판정일 수 있다) — 지금처럼 **전부 다** 막히는
상태만 벗어나면 된다.

### 1.4 `current_state`에 reason_code/return_quantity 주입

`_team_context()`가 만드는 `current` dict(§0에서 인용한 부분)에
`return.*`/`refund.*` capability 케이스에 한해
`reason_code`/`return_quantity`를 추가해라. 정교한 매핑표를 만들 필요
없다 — 합리적인 기본값(`reason_code="customer_request"`,
`return_quantity=1`)이면 충분하다. 시간이 남으면 몇 가지 뚜렷한
패턴만 반영해라(예: `expected_issue_code`에 "defective"/"불량"류가
있으면 `reason_code="defective"` — 있으면 좋고 없어도 된다).

### 1.5 시딩 시점·멱등성

`_team_context()` 호출 전에 한 번만 시딩되면 된다 — 매 case마다 매번
INSERT를 시도하면 `--repeats 3` 때 중복이 생긴다. `ON CONFLICT DO
NOTHING`이나 사전 존재 확인으로 멱등하게 만들어라(이 프로젝트의 다른
seed 스크립트, `scripts/seed_demo_cases.py`가 이미 이 패턴을 쓴다 —
참고해라). 시딩 함수는 `execute()`(또는 그에 준하는 최상위 함수)
시작 시 한 번 호출되게 해라 — 매 `_one()` 호출마다 부르지 마라(불필요한
반복 쓰기).

## 2. 검증

- 시딩 함수 자체의 단위 테스트는 필요 없다(이건 eval 도구 코드다,
  프로덕션 코드가 아니다) — 대신 **실제로 재실행해서 확인**해라:
  ```powershell
  python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --concurrency 2 --limit 20 --output eval/reports/_fixture_check.jsonl
  ```
  ★`--provider openai`는 실제 OpenAI 호출이 필요하다 — 네 샌드박스는
  외부 네트워크가 막혀 있을 수 있다. 안 되면 그 사실을 리포트에
  정직하게 적고, `--provider mock`으로 최소한 harness 코드 자체가
  에러 없이 도는지만 확인해라. **실제 성공률 검증은 Claude가 실
  환경에서 다시 한다.**
- `python -c "import json; [print(json.loads(l)['team_result']['outcome'], json.loads(l)['team_result'].get('failure_code')) for l in open('eval/reports/_fixture_check.jsonl', encoding='utf-8')]"`
  같은 방식으로 `escalated`/`required_evidence_missing`
  /`fulfillment_data_unavailable` 비율이 눈에 띄게 줄었는지 확인해라
  (100% → 상당히 낮은 비율로).
- `python -m pytest -q -m "not live"` 전체 실행 결과도 리포트에
  붙여라(이 계약은 `eval/`만 건드리므로 회귀는 없어야 하지만
  확인해라).

## 3. 쓰기 대상

- `eval/runners/common.py`
- `docs/reports/2026-08-24_S-EVAL-HARNESS-FIXTURE-SEED_리포트.md` (신규)

## 4. 하지 말 것

- `app/modules/customer_ops/return_refund.py`,
  `app/modules/customer_ops/fulfillment_logistics.py`,
  `app/modules/customer_ops/procurement_order_payment.py` 등 **실제
  Team 코드는 건드리지 마라** — 이건 harness 픽스처 문제지 Team
  버그가 아니다.
- `eval/datasets/golden.jsonl`을 고치지 마라 — 케이스 내용 자체는
  그대로 둔다.
- `procurement_order_payment`가 처리하는 capability(`order.*`,
  `payment.*`, `procurement.*`) 경로는 이미 100% completed였다 —
  그쪽 로직·픽스처를 새로 건드려서 회귀를 만들지 마라.
- 모든 issue_code를 완벽하게 매핑하려 하지 마라 — §1.3이 명시한
  대로, 구조적 100% 차단만 없애면 된다.
