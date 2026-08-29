-- Ensure that a case has at most one active agent run, including when two
-- first-run requests race before either transaction has inserted a row.
CREATE UNIQUE INDEX IF NOT EXISTS agent_runs_one_active_per_case
    ON agent_runs (tenant_id, case_id)
    WHERE status IN ('active', 'running', 'resuming');
