-- 021 — 위임을 **누가 언제 주고 거뒀나**의 이력 (감사, append-only)
--
-- ★★왜 019 로 충분하지 않은가. 019 의 `delegations` 는 **지금 상태**만 든다 —
--   `granted_at`·`granted_by`·`revoked_at`·`revoked_by`·`note` 가 한 행에 한 벌씩 있다.
--   그런데 다시 주는 것이 `ON CONFLICT … DO UPDATE SET granted_at=now(), revoked_at=NULL,
--   revoked_by=NULL` 이다(`delegation.grant()`). 즉 **주기 → 거두기 → 다시 주기** 를 하면
--   누가 언제 거뒀는지가 **덮여서 사라진다.**
--
--   019 자신이 그렇게 하지 말라고 적어 두었다 — "철회는 지우는 것이 아니라 `revoked_at` 을
--   적는 것이다 … 「그때는 위임 안에 있었다」를 나중에 확인할 수 있어야 한다(감사)".
--   한 번만 주고 거두는 동안은 지켜졌지만, 다시 주는 순간 깨진다. 여기서 막는다.
--
-- ★`case_events` 와 같은 모양이다 — **덧붙이기만 한다**(append-only). 고치지도 지우지도
--   않는다. 지금 상태는 `delegations` 가 답하고, "어떻게 여기까지 왔나" 는 이 표가 답한다.
--
-- ★상한 값은 여기 없다 — `config/guardrails.yaml` `travel.delegation` 이 정본이다
--   (RULE.md §3.1). 이 표에 있는 것은 「누가·언제·왜 상태를 바꿨나」뿐이다.
--
-- ☆재실행해도 안전하다 — CREATE TABLE IF NOT EXISTS · CREATE INDEX IF NOT EXISTS ·
--   제약은 pg_constraint 를 먼저 보고 만든다(019 와 같은 모양).

CREATE TABLE IF NOT EXISTS delegation_events (
    event_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- ★쌓인 **순서**. 시각(`at`)만으로 줄을 세우면 같은 순간에 들어온 둘의 앞뒤가
    --   정해지지 않는다 — 「주기 → 거두기」가 뒤집혀 보이면 이력이 거짓말을 한다.
    seq         bigserial NOT NULL,
    tenant_id   text NOT NULL,
    customer_id uuid NOT NULL REFERENCES customers,
    -- 'granted' | 'revoked'. ★상태가 아니라 **행위**다 — 같은 고객에 여러 번 쌓인다
    action      text NOT NULL,
    -- 누가. ★비워 둘 수 있게 두지만 API·화면은 빈 값을 받지 않는다
    --   (근거 없이 위임 상태를 바꾸지 않는다 — 019 의 `granted_by` 주석과 같은 이유)
    actor_id    text,
    -- 왜. 사람이 적은 문장을 그대로 싣는다(생성하지 않는다)
    note        text,
    at          timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'delegation_events_action_chk') THEN
        -- ★값을 둘로 묶는다. 오타가 들어오면 이력을 세는 쪽이 조용히 틀린 수를 낸다
        --   (017 의 `tier` CHECK 와 같은 이유).
        ALTER TABLE delegation_events
            ADD CONSTRAINT delegation_events_action_chk
            CHECK (action IN ('granted', 'revoked'));
    END IF;
END $$;

-- 한 고객의 이력을 최신부터 읽는 자리(화면·API). 정렬 기준은 `seq` 다
CREATE INDEX IF NOT EXISTS delegation_events_lookup_idx
    ON delegation_events (tenant_id, customer_id, seq DESC);
