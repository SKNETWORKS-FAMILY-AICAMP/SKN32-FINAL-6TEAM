-- 예보 주의와 확정 사건의 제안을 분리한다. 예보 유지 응답이 이후 안전 제안을 막지 않게 한다.
-- 기존 행은 모두 change 범위로 보존한다. 반복 적용해도 기존 데이터를 수정하지 않는다.
ALTER TABLE pending_changes ADD COLUMN IF NOT EXISTS proposal_scope text NOT NULL DEFAULT 'change';
ALTER TABLE pending_changes DROP CONSTRAINT IF EXISTS pending_changes_tenant_id_trip_id_item_id_base_version_key;
CREATE UNIQUE INDEX IF NOT EXISTS pending_changes_scope_key
    ON pending_changes (tenant_id, trip_id, item_id, base_version, proposal_scope);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='pending_changes_scope_check') THEN
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_scope_check
            CHECK (proposal_scope IN ('change', 'forecast'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='pending_changes_reason_check'
                   AND pg_get_constraintdef(oid) LIKE '%''forecast_advisory_options''%') THEN
        ALTER TABLE pending_changes DROP CONSTRAINT IF EXISTS pending_changes_reason_check;
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
            CHECK (reason IN ('ask_first', 'protected', 'safety_alert', 'indoor_unknown',
                              'indoor_unknown_options', 'relaxed', 'requested_options', 'other_options',
                              'forecast_advisory', 'forecast_advisory_options'));
    END IF;
END $$;
