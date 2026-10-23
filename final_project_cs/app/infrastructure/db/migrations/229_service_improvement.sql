-- 선택 동의에 따른 합성 후보. 원본·이용자 연결표·실제 표본 수는 저장하지 않는다.
CREATE TABLE IF NOT EXISTS service_improvement_budget (
    tenant_id text PRIMARY KEY,
    generations integer NOT NULL DEFAULT 0 CHECK (generations BETWEEN 0 AND 4)
);
CREATE OR REPLACE FUNCTION keep_improvement_budget() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'service improvement budget cannot be reset';
    END IF;
    IF NEW.generations < OLD.generations OR NEW.tenant_id <> OLD.tenant_id THEN
        RAISE EXCEPTION 'service improvement budget cannot decrease';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS improvement_budget_no_reset ON service_improvement_budget;
CREATE TRIGGER improvement_budget_no_reset BEFORE UPDATE OR DELETE ON service_improvement_budget
    FOR EACH ROW EXECUTE FUNCTION keep_improvement_budget();

CREATE TABLE IF NOT EXISTS service_improvement_batches (
    batch_id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    terms_version text NOT NULL,
    payload jsonb NOT NULL,
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'approved')),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    review_due_at timestamptz,
    review jsonb,
    CHECK (expires_at > created_at),
    CHECK (state <> 'approved' OR (review IS NOT NULL AND review_due_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS improvement_batches_tenant ON service_improvement_batches (tenant_id, expires_at);
