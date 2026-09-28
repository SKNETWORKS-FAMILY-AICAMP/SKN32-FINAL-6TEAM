# S-SEED-DEMO 작업 리포트

일자: 2026-08-17

## 변경 범위

- `scripts/seed_demo_cases.py`를 쇼핑몰 도메인으로 재작성했다.
  - `cust_01`의 `ORD-0101` 주문과 배송을 실행 시점에 조회한다.
  - 배송완료 미수령 시나리오는 `order_shipping` / `order.investigate`로 라우팅하고 `refund.request` 승인 대기에서 멈춘다.
  - `cust_02`의 `ORD-0201` 주문을 조회해 교환 기한 안내를 완료한다.
  - 정책 근거는 `doc_01#환불 금액의 산정`, `doc_15#교환 기한의 원칙`을 사용한다.
  - seed 데이터가 없으면 고객·주문·배송을 새로 만들지 않고 즉시 예외를 발생시킨다.
- `scripts/seed.py`는 요청된 docstring의 주문번호만 `ORD-0103`에서 `ORD-0101`로 수정했다.

## 검증 명령

```powershell
python -m scripts.seed
python -m scripts.seed_demo_cases
python -m scripts.seed_demo_cases
```

## 실행 로그 원문

첫 번째 실행:

```text
{'customers': 10, 'orders': 30, 'order_items': 30, 'shipments': 20, 'returns': 2}
{
  "tenant_id": "demo",
  "scenario_1": {
    "case_id": "af8a48a3-db6b-5a72-bdd0-9a06e5376cdb",
    "expected_version": 4
  },
  "scenario_2": {
    "case_id": "ca6ad34c-4e0f-5159-8fca-60b10ad2f577",
    "expected_version": 4
  },
  "observed": [
    {
      "case_id": "af8a48a3-db6b-5a72-bdd0-9a06e5376cdb",
      "status": "waiting_approval",
      "version": 4
    },
    {
      "case_id": "ca6ad34c-4e0f-5159-8fca-60b10ad2f577",
      "status": "resolved",
      "version": 4
    }
  ],
  "cases_in_tenant": 2
}
```

두 번째 `python -m scripts.seed_demo_cases` 실행:

```text
{
  "tenant_id": "demo",
  "scenario_1": {
    "case_id": "af8a48a3-db6b-5a72-bdd0-9a06e5376cdb",
    "expected_version": 4
  },
  "scenario_2": {
    "case_id": "ca6ad34c-4e0f-5159-8fca-60b10ad2f577",
    "expected_version": 4
  },
  "observed": [
    {
      "case_id": "af8a48a3-db6b-5a72-bdd0-9a06e5376cdb",
      "status": "waiting_approval",
      "version": 4
    },
    {
      "case_id": "ca6ad34c-4e0f-5159-8fca-60b10ad2f577",
      "status": "resolved",
      "version": 4
    }
  ],
  "cases_in_tenant": 2
}
```

## 결과

- 두 명령 모두 예외 없이 종료했다.
- 시나리오 1 종단 상태: `waiting_approval`
- 시나리오 2 종단 상태: `resolved`
- 재실행 전후 `cases_in_tenant`: `2 → 2`
- `python -m py_compile scripts/seed_demo_cases.py scripts/seed.py` 및 `git diff --check` 통과.
