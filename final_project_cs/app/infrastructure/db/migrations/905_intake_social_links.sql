-- SNS 출처는 장소 제공자와 별개다. 고객 소유 접수에 희망 목록과 명시적 적용안을 보관한다.
-- 일정 revision과 후보 변경은 독립적이며, 후보 변경 시 proposal을 비운다.
CREATE TABLE IF NOT EXISTS intake_dining_links (
    intake_id uuid PRIMARY KEY REFERENCES trip_intakes(intake_id) ON DELETE CASCADE,
    tenant_id text NOT NULL,
    links jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(links) = 'array'),
    proposal jsonb,
    applied jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(applied) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS intake_dining_links_tenant_idx ON intake_dining_links(tenant_id, intake_id);
