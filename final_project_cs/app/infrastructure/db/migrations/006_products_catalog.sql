CREATE TABLE IF NOT EXISTS products (
    product_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   text NOT NULL,
    sku         text NOT NULL,
    name        text NOT NULL,
    unit_cents  int NOT NULL,
    status      text NOT NULL DEFAULT 'active',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sku)
);

CREATE INDEX IF NOT EXISTS products_tenant_idx ON products (tenant_id);
