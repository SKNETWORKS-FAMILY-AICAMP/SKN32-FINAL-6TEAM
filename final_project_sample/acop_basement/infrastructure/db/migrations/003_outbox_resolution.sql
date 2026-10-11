ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolved_at timestamptz;
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolved_by text;
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolution_note text;
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolution text;
