# S-GOLDEN-CAPABILITY-REAUDIT — golden.jsonl expected_capability 재감사

## 0. 배경 (읽기만)

- `docs/reports/2026-08-20_S-GOLDEN-EXPECTED-CAPABILITY_리포트.md` (직전
  작업) 가 `eval/datasets/golden.jsonl` 의 order/shipping/return/exchange
  60건에 `expected_capability` 를 채웠다. 원 계약서
  (`docs/handoff/_prompts/S-GOLDEN-EXPECTED-CAPABILITY.md`) 는 "판단이
  애매하면 `expected_capability: null` 로 남기고 이유를 notes 에 적어라"
  는 예외 규정을 뒀는데, **Claude 가 직접 표본 검증한 결과 이 규정이
  제대로 안 지켜졌다.**
- 구체적으로 확인된 오분류(원문과 라벨을 직접 대조함):
  - `g-order-04`: "아직 출고 전이라 배송지를 바꾸고 싶어요. 주문 전체를
    취소하지 않고 주소만 수정할 수 있나요?" → `order.create` 로 라벨됨.
    이건 **신규 주문 생성이 아니라 기존 주문 수정 요청**이다.
  - `g-order-06`: "주문 수량 하나만 줄이고 나머지 상품은 그대로 받고
    싶습니다." → `order.create` 로 라벨됨. **부분 취소** 요청이다.
  - `g-order-09`: "주문 일부 상품만 취소하고 싶은데 전체 주문이 취소될까
    봐 걱정됩니다." → `order.create` 로 라벨됨. **부분 취소** 요청이다.
  - 이 세 건은 `procurement_order_payment` Team 의 실제 capability
    목록(`procurement.quote`, `order.verify`, `order.create`,
    `payment.status`) 어디에도 정확히 맞는 게 없다 — "주문 변경/취소"
    라는 capability 자체가 팀 설계에 없다.

## 1. 할 일 (2단계)

### 1단계 — 전수 재검토

1. golden.jsonl 의 order/shipping/return/exchange 60건 **전부**를
   `message`/`expected_issue_code`/`notes` 와 현재 `expected_capability`
   를 나란히 놓고 다시 대조해라. 위 3건처럼 "실제 요청 내용이 라벨된
   capability 와 안 맞는" case 를 전부 찾아라.
2. 각 case 를 세 부류로 나눠라:
   - **정확함**: 그대로 둔다
   - **다른 기존 capability 가 더 맞음**: 라벨을 고친다(팀의 실제
     capability 4개 중에서만 골라야 한다 — 지어내지 마라)
   - **팀의 기존 capability 어디에도 안 맞음**(위 3건처럼): 이건 라벨을
     고치는 게 아니라 **`expected_capability: null` 로 남기고, notes 에
     "팀 capability 목록에 해당 동작(예: 주문 수정/부분취소)이 없음 —
     설계 갭"이라고 명시해라.** 팀 설계 자체를 바꾸는 건 이 작업 범위
     밖이다.

### 2단계 — 갭 집계

3. 2단계 결과, `null` 로 남긴 case 가 몇 건인지, 어떤 종류의 누락된
   동작(주문 수정, 부분취소 등)이 반복되는지 패턴을 집계해서 리포트에
   적어라. 이게 "팀 capability 설계에 실제로 빠진 게 뭔지"를 보여주는
   증거가 된다 — Claude 가 이 결과를 보고 팀 설계를 보강할지 판단한다.

## 2. 검증

- 재감사 전/후 `expected_capability` 값이 달라진 case 목록을 리포트에
  전부 나열해라(case_id, 이전 값, 이후 값, 이유).
- `eval/verify_expected_capability.py`(기존 검증 스크립트, 있다면 재사용
  — 없다면 어디 있는지 찾아라)를 다시 돌려서 허용값 검사가 여전히
  통과하는지 확인해라(단, `null` 허용을 반영하도록 스크립트를 고쳐야
  할 수도 있다 — 그렇다면 왜 고쳤는지 리포트에 적어라).
- `python -m pytest -q -m "not live"` 실행해서 golden.jsonl 스키마
  관련 기존 테스트가 깨지지 않는지 확인해라(현재 354 passed 기준).

## 3. 쓰기 대상

- `eval/datasets/golden.jsonl` (`expected_capability`/`notes` 필드만
  수정 — 다른 필드, case 수, case_id 변경 금지)
- `eval/verify_expected_capability.py` (수정 시에만, null 허용 로직 추가
  등 — 불필요하면 건드리지 마라)
- `docs/reports/2026-08-24_S-GOLDEN-CAPABILITY-REAUDIT_리포트.md` (신규)

## 4. 하지 말 것

- `eval/datasets/holdout.jsonl` 은 여전히 건드리지 않는다(기존 원칙 유지)
- 팀 manifest(`app/modules/customer_ops/procurement_order_payment.py`
  등)의 capability 목록을 추가·변경하지 마라 — 이건 갭을 "찾는" 작업이지
  "메우는" 작업이 아니다
- g-response-review 12건 건드리지 마라
