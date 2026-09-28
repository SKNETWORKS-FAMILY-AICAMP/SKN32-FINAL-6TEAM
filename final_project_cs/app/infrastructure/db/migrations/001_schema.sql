CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

DO $$ BEGIN
    CREATE TYPE case_status AS ENUM ('new','classifying','routing','running','waiting_input','waiting_approval','waiting_external','resuming','resolved','escalated','failed','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE TYPE action_status AS ENUM ('proposed','pending_approval','approved','rejected','executing','succeeded','failed','unknown','cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS tenants (tenant_id text PRIMARY KEY, name text NOT NULL);
CREATE TABLE IF NOT EXISTS customers (customer_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL REFERENCES tenants, external_id text NOT NULL, email_hash text, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id, external_id));
CREATE TABLE IF NOT EXISTS customer_cases (case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, customer_id uuid NOT NULL REFERENCES customers, status case_status NOT NULL, subject text NOT NULL, state_json jsonb NOT NULL DEFAULT '{}', intent text, issue_code text, sentiment text, owner_team_id text, version int NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS case_events (event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, case_id uuid NOT NULL REFERENCES customer_cases, aggregate_version int NOT NULL, event_type text NOT NULL, payload_json jsonb NOT NULL, actor_type text NOT NULL, actor_id text, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(case_id, aggregate_version));
CREATE TABLE IF NOT EXISTS agent_runs (run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, case_id uuid NOT NULL REFERENCES customer_cases, graph_revision text NOT NULL, status text NOT NULL, attempt int NOT NULL DEFAULT 0, started_at timestamptz, finished_at timestamptz);
CREATE TABLE IF NOT EXISTS team_tasks (task_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL REFERENCES agent_runs, team_id text NOT NULL, contract_version text NOT NULL, payload_json jsonb NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS action_requests (action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, case_id uuid NOT NULL REFERENCES customer_cases, action_type text NOT NULL, arguments_json jsonb NOT NULL, idempotency_key text NOT NULL, status action_status NOT NULL, provider_ref text, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id, idempotency_key));
CREATE TABLE IF NOT EXISTS action_approvals (approval_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), action_id uuid NOT NULL REFERENCES action_requests, approver_id text, decision text NOT NULL, decided_at timestamptz);
CREATE TABLE IF NOT EXISTS outbox (message_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, topic text NOT NULL, dedupe_key text NOT NULL, payload_json jsonb NOT NULL, status text NOT NULL DEFAULT 'pending', attempts int NOT NULL DEFAULT 0, available_at timestamptz NOT NULL DEFAULT now(), locked_at timestamptz, last_error text, UNIQUE(topic, dedupe_key));
CREATE TABLE IF NOT EXISTS prompts (prompt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), prompt_key text NOT NULL, version text NOT NULL, template text NOT NULL, sha256 text NOT NULL, model_family text NOT NULL, active boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(prompt_key, version), UNIQUE(prompt_key, sha256));
CREATE TABLE IF NOT EXISTS llm_calls (call_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid REFERENCES agent_runs, prompt_id uuid NOT NULL REFERENCES prompts, provider text NOT NULL, model text NOT NULL, input_tokens int, output_tokens int, latency_ms int, cost_microusd bigint, response_json jsonb, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS knowledge_documents (document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, title text NOT NULL, source_uri text NOT NULL, scope text NOT NULL, version text NOT NULL, pii_class text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS knowledge_chunks (chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), document_id uuid NOT NULL REFERENCES knowledge_documents, chunk_no int NOT NULL, content text NOT NULL, metadata_json jsonb NOT NULL, embedding vector(1536) NOT NULL, UNIQUE(document_id, chunk_no));
CREATE TABLE IF NOT EXISTS feedback_analytics_reports (report_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id text NOT NULL, period_start date NOT NULL, period_end date NOT NULL, metrics_json jsonb NOT NULL, alerts_json jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id, period_start, period_end));


CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS cases_tenant_customer_idx ON customer_cases(tenant_id, customer_id);
CREATE INDEX IF NOT EXISTS events_case_version_idx ON case_events(case_id, aggregate_version);
