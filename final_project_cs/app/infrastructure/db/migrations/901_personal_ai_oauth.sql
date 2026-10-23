-- 개인 AI OAuth 저장. 기존 migration을 바꾸지 않는 추가 SQL.
-- 무작위 자격은 record_key에 SHA-256 해시만 저장한다.
CREATE UNIQUE INDEX IF NOT EXISTS idx_personal_ai_oauth_customer_tenant ON customers(tenant_id,customer_id);
CREATE TABLE IF NOT EXISTS personal_ai_oauth_records (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('client','pending','grant','code','access','refresh')),
    record_key text NOT NULL,
    customer_id uuid,
    body jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, kind, record_key),
    FOREIGN KEY(tenant_id,customer_id) REFERENCES customers(tenant_id,customer_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_personal_ai_oauth_customer
    ON personal_ai_oauth_records(tenant_id, customer_id, kind);
