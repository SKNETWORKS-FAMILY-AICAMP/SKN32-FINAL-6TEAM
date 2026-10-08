-- 031 — 웹 남용 방어: 사용량 · 운영이 바꾼 제한값 · 그 감사 기록 · 2026-09-28 사용자 지시
--
-- ★★왜. 웹은 로그인 없이 키를 받아 쓴다. 키를 받은 뒤 비싼 작업(사진·PDF 읽기 · 일정 짜기 · 채팅)을 몇 번이든
--   부를 수 있었고, 막는 장치는 「한 주소 한 시간 키 20개」 하나뿐이었는데 **프로세스 메모리**에서 세서 재시작하면
--   풀렸다(`web_session.py`). 여기서 모든 프로세스가 같이 센다(027 `external_call_budget` 과 같은 방식).
-- ★주소는 원문을 두지 않는다 — `HMAC(서버 비밀키, 날짜|주소)` 만. 날짜가 섞여 다른 날의 같은 주소를 잇지 못하고,
--   되잡기 작업이 48시간 뒤 지운다(`web_guard.prune_usage`).
-- ★제한 **값**은 여기 없다 — 기본값·범위는 `config/guardrails.yaml` `web_guard` 가 정본이고(RULE §3.1),
--   운영자가 바꾼 값만 `runtime_limits` 에 둔다.
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS web_usage (
    tenant_id  text NOT NULL,
    who_kind   text NOT NULL,          -- key(사용자) · ip(주소 해시) · all(서비스 전체)
    who        text NOT NULL,          -- 사용자 id · 주소 해시 · '*'
    action     text NOT NULL,          -- intake · plan · confirm · trip_create · message · session
    period     text NOT NULL,          -- 'day:2026-09-28'(KST) · 'hour:2026-09-28T21'(KST)
    used       integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, who_kind, who, action, period)
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'web_usage_who_kind_chk') THEN
        ALTER TABLE web_usage ADD CONSTRAINT web_usage_who_kind_chk CHECK (who_kind IN ('key', 'ip', 'all'));
    END IF;
END $$;

-- 오래된 줄을 지우는 자리(되잡기 작업)
CREATE INDEX IF NOT EXISTS web_usage_age_idx ON web_usage (tenant_id, who_kind, updated_at);

-- 운영자가 바꾼 값. 없으면 가드레일 기본값을 쓴다
CREATE TABLE IF NOT EXISTS runtime_limits (
    tenant_id  text NOT NULL,
    name       text NOT NULL,          -- 예: web.intake.per_key_day
    value      jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL,
    PRIMARY KEY (tenant_id, name)
);

-- 바꿀 때마다 +1 — 두 운영자가 같은 판을 보고 동시에 바꾸면 뒤엣것이 409 를 받는다
CREATE TABLE IF NOT EXISTS runtime_limit_state (
    tenant_id  text PRIMARY KEY,
    revision   bigint NOT NULL DEFAULT 0 CHECK (revision >= 0)
);

-- ★감사 — **덧붙이기만** 한다(021 `delegation_events` 와 같은 모양). 누가 · 언제 · 무엇을 · 이전 → 새 값 · 왜
CREATE TABLE IF NOT EXISTS runtime_limit_events (
    event_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seq        bigserial NOT NULL,
    tenant_id  text NOT NULL,
    revision   bigint NOT NULL,
    name       text NOT NULL,
    old_value  jsonb,                  -- null = 기본값이었다
    new_value  jsonb,                  -- null = 기본값으로 돌렸다
    actor      text NOT NULL,          -- 콘솔이 실어 보낸 운영자 id(API 는 그 값을 믿는다 — 한계)
    key_id     text NOT NULL,          -- 부른 scope 키
    reason     text NOT NULL,
    at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS runtime_limit_events_lookup_idx ON runtime_limit_events (tenant_id, seq DESC);

-- ★고치지도 지우지도 못하게 막는다. 감사 기록이 나중에 바뀌면 기록이 아니다
CREATE OR REPLACE FUNCTION runtime_limit_events_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'runtime_limit_events is append-only (%)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'runtime_limit_events_no_change') THEN
        CREATE TRIGGER runtime_limit_events_no_change BEFORE UPDATE OR DELETE ON runtime_limit_events
            FOR EACH ROW EXECUTE FUNCTION runtime_limit_events_append_only();
    END IF;
END $$;
