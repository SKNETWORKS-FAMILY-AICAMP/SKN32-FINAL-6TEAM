-- ★반품이 "어느 품목" 인지를 담는다 (2026-09-01, D-001 1-A 후속).
--
--   `returns` 에는 `order_id`·`reason_code`·`quantity` 만 있었다. "주문 X에서
--   3개 반품" 은 알지만 어느 품목인지를 몰라서, 환불 금액을 주문 총액의 균등
--   분할로 **추정**하고 있었다. 품목 값이 서로 다르면 그 액수는 근거가 없다
--   (docs/reports/debugs/2026-09-01_환불금액_균등분할_가정.md).
--
-- ★NULL 을 허용한다. 이미 쌓인 반품 행에는 품목 정보가 **없다** — 지금 와서
--   채우면 그건 지어낸 값이다. NULL 은 "모른다" 이고, 모르면 다품목 주문에서
--   금액을 만들지 않고 사람에게 넘긴다.
--
-- ★러너가 모든 SQL 을 이어붙여 한 트랜잭션에 돌린다. 재실행해도 안전해야
--   여기서 죽지 않고 뒤 마이그레이션까지 적용된다.
ALTER TABLE returns ADD COLUMN IF NOT EXISTS order_item_id uuid REFERENCES order_items;

CREATE INDEX IF NOT EXISTS returns_order_item_idx ON returns (order_item_id);
