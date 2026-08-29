-- Scope outbox deduplication to a tenant.
ALTER TABLE outbox DROP CONSTRAINT IF EXISTS outbox_topic_dedupe_key_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'outbox'::regclass
          AND conname = 'outbox_tenant_topic_dedupe_key_key'
    ) THEN
        ALTER TABLE outbox
            ADD CONSTRAINT outbox_tenant_topic_dedupe_key_key
            UNIQUE (tenant_id, topic, dedupe_key);
    END IF;
END $$;
