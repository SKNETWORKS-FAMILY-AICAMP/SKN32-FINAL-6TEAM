-- 운영자 웹앱의 저장·변경 기록. 기존 고객/Case 상태와 분리한다.
CREATE TABLE IF NOT EXISTS admin_records (
 tenant_id text NOT NULL REFERENCES tenants, kind text NOT NULL, id text NOT NULL,
 value jsonb NOT NULL, revision bigint NOT NULL DEFAULT 1,
 updated_at timestamptz NOT NULL DEFAULT now(), customer_id uuid REFERENCES customers ON DELETE CASCADE,
 PRIMARY KEY(tenant_id,kind,id)
);
ALTER TABLE admin_records ADD COLUMN IF NOT EXISTS customer_id uuid;
ALTER TABLE admin_records DROP CONSTRAINT IF EXISTS admin_records_customer_id_fkey;
ALTER TABLE admin_records ADD CONSTRAINT admin_records_customer_id_fkey FOREIGN KEY(customer_id) REFERENCES customers ON DELETE CASCADE;
UPDATE admin_records r SET customer_id=c.customer_id FROM customers c
 WHERE r.tenant_id=c.tenant_id AND ((r.kind='user' AND r.id=c.customer_id::text)
 OR (r.kind='inquiry' AND r.value->>'userId'=c.customer_id::text)) AND r.customer_id IS NULL;
CREATE TABLE IF NOT EXISTS admin_audit (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), seq bigserial NOT NULL,
 tenant_id text NOT NULL REFERENCES tenants, actor text NOT NULL, action text NOT NULL,
 target text NOT NULL, before_value jsonb, after_value jsonb, reason text NOT NULL,
 at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_audit_tenant_idx ON admin_audit(tenant_id,seq DESC);
CREATE OR REPLACE FUNCTION admin_audit_append_only() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'admin_audit is append-only'; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS admin_audit_no_change ON admin_audit;
CREATE TRIGGER admin_audit_no_change BEFORE UPDATE OR DELETE ON admin_audit
 FOR EACH ROW EXECUTE FUNCTION admin_audit_append_only();
CREATE TABLE IF NOT EXISTS admin_chat_usage (
 tenant_id text NOT NULL, customer_id uuid NOT NULL REFERENCES customers ON DELETE CASCADE, day date NOT NULL,
 used integer NOT NULL DEFAULT 0 CHECK(used>=0), PRIMARY KEY(tenant_id,customer_id,day)
);
ALTER TABLE admin_chat_usage DROP CONSTRAINT IF EXISTS admin_chat_usage_customer_id_fkey;
ALTER TABLE admin_chat_usage ADD CONSTRAINT admin_chat_usage_customer_id_fkey FOREIGN KEY(customer_id) REFERENCES customers ON DELETE CASCADE;
-- 결제 계정 전체 상한이며, 테넌트 별로 나눠 한도를 늘릴 수 없다.
CREATE TABLE IF NOT EXISTS admin_api_caps (
 meter text PRIMARY KEY, daily bigint NOT NULL CHECK(daily>0), monthly bigint NOT NULL CHECK(monthly>=daily),
 updated_by text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
