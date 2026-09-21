-- 002 — 도메인 테이블 (쇼핑몰 CS)
--
-- ★basement 가 아니다. 001_schema.sql(core 14 테이블)은 손대지 않는다.
--   이 파일은 `docs/handoff/10_도메인_교체_가이드.md` §1-1 이 말하는 교체 지점이다.
--
-- 구독·결제(sample)에서 커머스로 바뀐 대응:
--   subscriptions → (없음. 쇼핑몰은 구독이 아니라 주문 단위다)
--   payments      → orders          (금액 상한의 출처)
--   entitlements  → order_items     (수량 상한의 출처)
--   incidents     → shipments · returns

CREATE TABLE IF NOT EXISTS orders (
    order_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers,
    order_no     text NOT NULL,
    total_cents  int  NOT NULL,
    item_count   int  NOT NULL DEFAULT 0,
    status       text NOT NULL,          -- placed / paid / shipped / delivered / cancelled
    ordered_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, order_no)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    order_id      uuid NOT NULL REFERENCES orders,
    sku           text NOT NULL,
    name          text NOT NULL,
    quantity      int  NOT NULL,
    unit_cents    int  NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers,
    order_id     uuid NOT NULL REFERENCES orders,
    carrier      text NOT NULL,
    tracking_no  text,
    status       text NOT NULL,          -- ready / in_transit / delivered / lost
    shipped_at   timestamptz,
    delivered_at timestamptz
);

CREATE TABLE IF NOT EXISTS returns (
    return_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers,
    order_id     uuid NOT NULL REFERENCES orders,
    reason_code  text NOT NULL,
    quantity     int  NOT NULL,
    status       text NOT NULL,          -- requested / approved / rejected / refunded
    requested_at timestamptz NOT NULL DEFAULT now()
);

-- ★조회는 항상 tenant_id + customer_id 로 좁힌다(설계 원칙 §1).
CREATE INDEX IF NOT EXISTS orders_tenant_customer_idx     ON orders (tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS shipments_tenant_customer_idx  ON shipments (tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS returns_tenant_customer_idx    ON returns (tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS order_items_order_idx          ON order_items (tenant_id, order_id);
