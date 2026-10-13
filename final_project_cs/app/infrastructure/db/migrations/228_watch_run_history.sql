-- 감시 회차와 항목별 결과. 운영 앱에서 테넌트 한정 조회한다.
CREATE TABLE IF NOT EXISTS travel_watch_runs (
 tenant_id text NOT NULL REFERENCES tenants, run_id uuid NOT NULL,
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(), finished_at timestamptz,
 forced boolean NOT NULL, interval_seconds double precision NOT NULL CHECK(interval_seconds>0),
 status text NOT NULL CHECK(status IN ('running','completed','attention','failed')),
 counts jsonb NOT NULL DEFAULT '{}'::jsonb, error_type text,
 PRIMARY KEY(tenant_id,run_id)
);
CREATE INDEX IF NOT EXISTS travel_watch_runs_time_idx ON travel_watch_runs(tenant_id,started_at DESC,run_id DESC);
CREATE TABLE IF NOT EXISTS travel_watch_checks (
 check_id bigserial PRIMARY KEY, tenant_id text NOT NULL, run_id uuid NOT NULL,
 at timestamptz NOT NULL DEFAULT clock_timestamp(), stage text NOT NULL,
 trip_id uuid REFERENCES trips(trip_id) ON DELETE CASCADE, item_id uuid,
 target_title text, report jsonb NOT NULL,
 FOREIGN KEY(tenant_id,run_id) REFERENCES travel_watch_runs(tenant_id,run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS travel_watch_checks_run_idx ON travel_watch_checks(tenant_id,run_id,check_id);
CREATE INDEX IF NOT EXISTS travel_watch_checks_trip_idx ON travel_watch_checks(tenant_id,trip_id,run_id);
