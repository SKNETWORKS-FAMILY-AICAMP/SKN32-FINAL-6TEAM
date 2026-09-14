-- Human resolution evidence for provider outcomes that remained unknown.
-- Resolution is append-only metadata; it does not change outbox.status.
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolved_at timestamptz;
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolved_by text;
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolution_note text;
ALTER TABLE outbox ADD COLUMN IF NOT EXISTS resolution text;
