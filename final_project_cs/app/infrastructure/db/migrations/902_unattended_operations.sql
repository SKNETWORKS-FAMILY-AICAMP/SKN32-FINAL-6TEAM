-- 무인 운영: 기존 선택 동의 합성 자료와 진단 고객 연결을 분리한다.
CREATE TABLE IF NOT EXISTS ops_source_policy (
    tenant_id text PRIMARY KEY,
    revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    value jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ops_lookup_usage (
    tenant_id text NOT NULL,
    day date NOT NULL,
    trip_id uuid NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    used integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    PRIMARY KEY (tenant_id, day, trip_id)
);
CREATE TABLE IF NOT EXISTS ops_lookup_checks (
    tenant_id text NOT NULL,
    trip_id uuid NOT NULL REFERENCES trips(trip_id) ON DELETE CASCADE,
    resource_hash text NOT NULL,
    checked_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, trip_id, resource_hash)
);
CREATE TABLE IF NOT EXISTS ops_defects (
    tenant_id text NOT NULL,
    fingerprint text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('place_unmatched','processing_error','suggestion')),
    code text NOT NULL,
    deployment text NOT NULL,
    policy_version text NOT NULL,
    conditions jsonb NOT NULL,
    occurrences bigint NOT NULL DEFAULT 0,
    first_at timestamptz NOT NULL,
    last_at timestamptz NOT NULL,
    resolved_version text,
    PRIMARY KEY (tenant_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS ops_diagnostic_events (
    tenant_id text NOT NULL,
    event_id uuid NOT NULL,
    fingerprint text NOT NULL,
    customer_id uuid REFERENCES customers(customer_id) ON DELETE SET NULL,
    trip_id uuid REFERENCES trips(trip_id) ON DELETE SET NULL,
    case_id uuid,
    request_id uuid,
    occurred_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, event_id)
);
CREATE TABLE IF NOT EXISTS ops_defect_customers (
    tenant_id text NOT NULL,
    fingerprint text NOT NULL,
    customer_id uuid NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    last_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, fingerprint, customer_id)
);
CREATE INDEX IF NOT EXISTS ops_defects_page ON ops_defects (tenant_id, last_at DESC, fingerprint DESC);
CREATE INDEX IF NOT EXISTS ops_diagnostic_expiry ON ops_diagnostic_events (expires_at);
CREATE INDEX IF NOT EXISTS ops_diagnostic_events_page ON ops_diagnostic_events (tenant_id, fingerprint, event_id);
CREATE INDEX IF NOT EXISTS ops_defect_customer_expiry ON ops_defect_customers (expires_at);
CREATE INDEX IF NOT EXISTS ops_lookup_usage_day ON ops_lookup_usage (tenant_id, day);
CREATE INDEX IF NOT EXISTS admin_inquiries_customer_page ON admin_records (tenant_id, customer_id, updated_at DESC, id DESC) WHERE kind='inquiry';
