# S-PROCUREMENT-ORDER-MODIFY-CAPABILITY — 주문 수정/취소 capability 추가

## 0. 배경 (읽기만)

- `docs/reports/2026-08-24_S-GOLDEN-CAPABILITY-REAUDIT_리포트.md` — golden
  데이터 재감사에서 6건(`g-order-04`~`g-order-09`)이 `procurement_order_payment`
  Team 의 기존 capability(`procurement.quote`, `order.verify`, `order.create`,
  `payment.status`) 어디에도 안 맞아 `null` 로 남았다. 실제 요청 내용은
  전부 "주문 수정"(배송지 변경, 옵션 변경) 또는 "주문 취소"(전체/부분)다.
- v8 설계문서의 Action Gateway 어휘(action_type 후보)에도 `order.modify`/
  `order.cancel` 류가 없다 — **이건 원 설계에 없던 걸 이번에 추가하는
  것이다.** 새 capability 이름은 기존 명명 규칙(`도메인.동사`, 예:
  `order.verify`, `order.create`)을 따르되, 정확한 이름은 네가 정해도
  된다(예: `order.modify`, `order.cancel` — 수정과 취소를 하나로 합칠지
  나눌지도 6건의 실제 내용을 보고 판단해라).

## 1. 확정해야 할 것

`g-order-04`~`09` 6건의 실제 요청을 다시 봐라(파일:
`eval/datasets/golden.jsonl`):
- 04: 배송지 변경(출고 전)
- 05: 옵션(색상) 변경
- 06: 수량 일부 감소(부분 변경)
- 07: 판매자 귀책 취소 승인 여부
- 08: 물류센터 전달 후 취소 가능 여부
- 09: 부분 취소

이게 "수정"(04,05,06)과 "취소"(07,08,09)로 자연스럽게 나뉜다 — 별개
capability 로 만드는 걸 권장하지만, 근거를 들어 다르게 판단해도 된다.

## 2. 할 일

1. `app/modules/customer_ops/procurement_order_payment.py` 의
   `TeamManifest.capabilities` 에 새 capability(들)를 추가해라.
   `accepted_case_types` 는 이미 `order` 를 포함하므로 안 바꿔도 된다
   (case_type 라우팅은 그대로, capability 선택만 새로 생긴다).
2. `execute()` 에 새 capability 처리 로직을 추가해라 — 다른 capability
   들과 같은 원칙: **side effect 없음, 전부 `ActionProposal`**.
   - 주문 수정(배송지/옵션/수량): 아직 출고 전인지 등 조건을 근거로
     확인한 뒤 수정 **제안**(승인 필요)
   - 주문 취소(전체/부분): 판매자 귀책 여부·물류센터 전달 여부 등을
     근거로 확인한 뒤 취소 **제안**(승인 필요, 귀책 관련 케이스는
     risk_level 을 신중히 정해라)
   - 근거(주문 상태, 출고 여부 등) 없이 확정하지 마라 — 없으면 escalate.
3. `tests/unit/teams/test_procurement_order_payment.py` 에 새 capability
   테스트를 추가해라(정상 제안 1건 이상 + evidence 없을 때 escalate).
4. **golden.jsonl 의 6건을 갱신해라** — `null` 이던 `expected_capability`
   를 새로 만든 capability 이름으로 채우고, notes 에서 "설계 갭" 문구를
   지우고 "capability 추가로 해소됨(2026-08-24)" 로 바꿔라. 이 6건
   외의 다른 case 는 건드리지 마라.

## 3. 쓰기 대상

- `app/modules/customer_ops/procurement_order_payment.py`
- `tests/unit/teams/test_procurement_order_payment.py`
- `eval/datasets/golden.jsonl` (해당 6건의 `expected_capability`/`notes`만)
- `docs/reports/2026-08-24_S-PROCUREMENT-ORDER-MODIFY-CAPABILITY_리포트.md` (신규)

## 4. 하지 말 것

- `config/project.yaml` 수정 금지(capability 추가는 manifest 안에서
  끝난다 — Team 등록 자체는 이미 돼 있다)
- `eval/datasets/holdout.jsonl` 건드리지 마라
- 다른 Team 파일 수정 금지
- golden.jsonl 의 6건 외 다른 case 수정 금지

## 5. 검증

- `python -m pytest -q -m "not live"` 결과를 리포트에 실제 출력 그대로
  붙여라(현재 354 passed 기준 변화 명시).
- `python eval/verify_expected_capability.py` 재실행 결과도 붙여라 —
  이제 order 그룹에 null 이 0건이어야 한다.
