-- 056 — 약관의 보관 기간: 운영자가 바꾼 값 · 그 변경 이력 · 정리 작업의 실행 기록. `[2026-10-07 사용자 결정 — uiux 전달]`
--
-- ★왜. 약관 화면이 「마지막 이용 후 1년이 지나면 파기」 같은 **기간**을 적는다. 그 기간을 서버가 실제로 지켜야 하고(정리 작업), 운영자가 관리 화면에서 고칠 수 있어야 하며
--   (누가 · 언제 · 왜 바꿨는지 남긴다), **값이 바뀌면 약관 글이 바뀌므로 약관 버전도 따라 바뀌어 모두 다시 동의**한다(`consents.current_version` 이 `+ret{revision}` 을 붙인다).
-- ★기본값은 여기 없다 — `config/guardrails.yaml` 의 `retention` 이 정본이고(RULE §3.1), 운영자가 바꾼 값만 `legal_retention.overrides` 에 둔다(빈 객체 = 전부 기본값).
-- ★변경 이력은 **덧붙이기만** 한다(031 `runtime_limit_events` · 021 `delegation_events` 와 같은 모양) — 버전 `+ret{N}` 의 글을 나중에 다시 만들어 동의 증빙(`text_sha256`)을 맞춰 볼 수 있다.
-- ★정리 작업 기록(`retention_runs`)은 **지운 건수**만 둔다(개인 정보 없음). 처음에는 건수만 세는 모드(`dry_run`)로 돌아 사용자가 건수를 보고 승인하고서야 켠다.
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS legal_retention (
    tenant_id  text PRIMARY KEY,
    revision   integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    overrides  jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS legal_retention_history (
    event_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seq        bigserial NOT NULL,
    tenant_id  text NOT NULL,
    revision   integer NOT NULL,
    old_values jsonb NOT NULL,              -- 바꾸기 전에 **적용되던** 값(기본값 포함)
    new_values jsonb NOT NULL,              -- 바꾼 뒤 적용되는 값
    changed    jsonb NOT NULL,              -- {칸: [이전, 새]} — 이번에 바뀐 칸만
    actor      text NOT NULL,               -- 콘솔이 실어 보낸 운영자 id(API 는 그 값을 믿는다 — 한계. `key_id` 로 부른 키를 같이 남긴다)
    key_id     text NOT NULL,
    reason     text NOT NULL,
    at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS legal_retention_history_lookup_idx ON legal_retention_history (tenant_id, seq DESC);

CREATE OR REPLACE FUNCTION legal_retention_history_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'legal_retention_history is append-only (%)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'legal_retention_history_no_change') THEN
        CREATE TRIGGER legal_retention_history_no_change BEFORE UPDATE OR DELETE ON legal_retention_history
            FOR EACH ROW EXECUTE FUNCTION legal_retention_history_append_only();
    END IF;
END $$;

-- 정리 작업이 한 번 돌 때마다 한 줄 — mode: dry_run(세기만 · 아무것도 안 지움) · on(지움). 승인 전에 사용자가 보는 건수의 정본이다
CREATE TABLE IF NOT EXISTS retention_runs (
    run_id     bigserial PRIMARY KEY,
    tenant_id  text NOT NULL,
    mode       text NOT NULL CHECK (mode IN ('dry_run', 'on')),
    started_at timestamptz NOT NULL DEFAULT now(),
    counts     jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS retention_runs_lookup_idx ON retention_runs (tenant_id, run_id DESC);
