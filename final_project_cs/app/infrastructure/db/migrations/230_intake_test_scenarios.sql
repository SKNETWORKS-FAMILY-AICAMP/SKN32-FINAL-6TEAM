-- 명시적으로 선택한 시험 접수의 출처. 일반 접수·검사값을 시험값으로 대체하지 않는다.
CREATE TABLE IF NOT EXISTS intake_test_scenarios (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id),
    intake_id uuid NOT NULL REFERENCES trip_intakes(intake_id) ON DELETE CASCADE,
    customer_id uuid NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, intake_id)
);
