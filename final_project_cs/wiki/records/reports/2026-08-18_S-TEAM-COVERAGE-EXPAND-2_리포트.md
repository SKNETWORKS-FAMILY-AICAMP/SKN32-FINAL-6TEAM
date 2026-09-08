# Team 시나리오 커버리지 확장 2차 리포트 (반품 기한, 배송 지연 보상)

- 담당: Claude(정책 문서 근거 확정·계약 설계·독립검증, 이 리포트 작성) + Codex(구현)
- 계획: `wiki/records/handoff/_prompts/S-TEAM-COVERAGE-EXPAND-2.md`

## 1. 변경 내용

- `return_exchange.py` — `knowledge/documents/11_return_period.md` 근거로
  반품 기한 대조를 기존 로직 앞단에 gate 로 추가했다. 단순변심 7일 /
  하자(`reason_code=="defective"`) 90일(3개월 근사)을 `orders.ordered_at`
  기준으로 계산해, 넘긴 신청은 제안을 만들지 않고
  `outcome="escalated", failure_code="return_period_expired"` 로 넘긴다
  (고지 누락 등 예외 사유 확인이 먼저 필요하다는 게 정책 원문 — 자동 승인
  대상이 아니다). 날짜가 없거나 파싱 실패하면 gate 를 건너뛰고 기존
  로직으로 진행(보수적 기본값).
- `order_shipping.py` — `knowledge/documents/02_shipping_delivery-schedule.md`
  근거로 배송 지연 보상 검토 제안을 미수령(`delivered`) 분기보다 앞에
  추가했다. `shipments` 중 미배송 상태이고 `shipped_at` 이 영업일(월~금,
  공휴일 달력 없음 — 근사치임을 코드 주석에 명시) 5일 이상 지난 것이
  있으면 `shipping.delay_compensation_propose` 제안을 만든다. **금액·
  보상 방식 필드는 넣지 않는다** — `doc_02` 가 "상담원이 임의로 금액이나
  방식을 제시하지 않는다"고 명시하므로 승인자가 결정한다.
- `order_payment_failed`/`order_duplicate_charge` — **코드 추가 없음.**
  `doc_10_order_payment-failure.md` 확인 결과 판정에 필요한 결제 시도
  이력 데이터가 이 저장소 스키마에 없다(`orders` 는 최종 상태만 저장).
  없는 데이터를 대조하는 척하면 지어내는 것이라 계약에서 명시적으로
  제외했다 — 계속 LLM 자유 응답 경로로 남는다. 이건 TODO 가 아니라
  **현재 스키마로는 애초에 할 수 없는 것**으로 분류한다. 스키마에
  결제 시도 이력 테이블을 추가하면 다시 열 수 있다.
- 신규 테스트 8건, 총 16건(`tests/unit/teams/test_team_scenarios.py`) —
  Codex 가 계약이 요구한 8건에 더해 방어적 케이스(날짜 없음, 미수령
  분기와의 우선순위) 추가로 8건을 더 넣었다.

## 2. Claude 독립 검증

- `git diff` 로 `return_exchange.py`·`order_shipping.py`·
  `test_team_scenarios.py` 세 파일 전부 줄 단위 대조 — 계약 §2·§3·§4
  정확히 구현됨. 기한 계산 timezone-aware 처리, 영업일 카운트가 시작일
  자체는 빼고 다음 날부터 세는 것(§2 "경과일" 정의와 일치), 금액 필드
  미포함까지 확인.
- `git status`로 `verification_policy.py`·마이그레이션·Core·Application
  전부 미변경 확인.
- `grep` 으로 `order_payment_failed`/`order_duplicate_charge` 관련 코드가
  정말 추가되지 않았음을 직접 확인.
- `python -m pytest tests/unit/teams -v` → **16 passed**(요구 8건 +
  Codex 가 자체적으로 추가한 방어적 케이스 8건).
- `python -m pytest -q` → **307 passed, 2 deselected**(기존 299 + 신규 8,
  회귀 0).
- 계약 §1 "쓰기 대상" 목록에 이 리포트 파일 경로를 넣는 걸 또 빠뜨려서
  (1차 때와 같은 실수) Codex 가 계약대로 리포트를 안 쓰고 멈췄다 —
  코드 3개 파일 변경은 전부 정상 완료했음을 로그로 확인한 뒤, 이 리포트는
  Claude 가 직접 작성한다.

## 3. 남은 issue_code 커버리지 상태

| issue_code | 처리 | 근거 |
|---|---|---|
| `shipping_delivered_not_received` | 결정론적 제안 (1차) | doc_01 |
| `order_change_or_cancel` | 결정론적 제안/pass-through (1차) | doc_08 |
| `return_quantity_exceeded` | 결정론적 제안 (기존) | doc_14 |
| `exchange_stock_or_period` | 결정론적 제안, 재고 미확인 명시 (1차) | doc_15 |
| `return_fee_or_period` | 결정론적 기한 대조 (★2차) | doc_11 |
| `shipping_delayed` | 결정론적 보상 검토 제안 (★2차) | doc_02 |
| `order_payment_failed` | LLM 자유 응답만 (스키마 한계로 보류) | doc_10 |
| `order_duplicate_charge` | LLM 자유 응답만 (스키마 한계로 보류) | doc_10 |
| `order_other`/`shipping_other`/`return_other`/`exchange_other` | LLM 자유 응답 (의도된 설계 — 범용 문의) | — |

`order_payment_failed`/`order_duplicate_charge` 를 열려면 결제 시도
이력 테이블(실패 코드·시도 시각·수단)을 스키마에 추가해야 한다 —
이건 마이그레이션이 필요한 별도 결정이라 이번 범위에 넣지 않았다.
