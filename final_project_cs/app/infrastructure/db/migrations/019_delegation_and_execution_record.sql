-- 019 — 위임(delegation)과 자동 실행 기록 (v11 §12 DoD-18·19·20·21 · wiki `teams/booking-handoff.md` 「위임 범위」)
--
-- ★★왜. 018 까지 자동 실행 분기(승인 뒤 공급자 원장을 사람 손 없이 바꾸는 자리)를 막는 문은
--   **공급자 등급 하나**(017 `supplier_bookings.tier`)뿐이었다. 등급은 「누구의 원장인가」만
--   답한다 — 「얼마까지·무엇에·몇 번까지 맡겼나」는 아무 데도 없었다. 그래서 등급이
--   `simulated` 이면 금액이 얼마든 몇 번이든 원장이 바뀌었다.
--
-- ★두 개를 만든다.
--   (1) `delegations`      — 위임이 **살아 있는가**. 데이터에 둔다(철회 자리, DoD-19)
--   (2) `action_requests`  — 자동 실행에 **무엇을·왜·얼마에·되돌림 기한**을 적는 칸(DoD-20)
--
-- ★상한 값(전체 N원·건당 M원·횟수 K)은 여기 두지 않는다 — `config/guardrails.yaml`
--   `travel.delegation` 이 정본이다(RULE.md §3.1 가드레일 단일 출처). 여기 있는 것은
--   「누가 맡겼나」와 「무엇이 실행됐나」뿐이다.
--
-- ☆재실행해도 안전하다 — 테이블은 IF NOT EXISTS, 칼럼은 ADD COLUMN IF NOT EXISTS.

-- ── (1) 위임 ────────────────────────────────────────────────────────────────
-- ★★**행이 없으면 위임이 없다.** 017 의 `tier DEFAULT 'real'` 과 같은 방향으로 기운다 —
--   위임을 적는 것을 잊은 고객은 자동 실행 대상이 아니고 사람에게 간다. 반대로
--   「행이 없으면 위임된 것으로 본다」로 두면 **잊음의 대가가 돈**이 된다.
-- ★철회는 지우는 것이 아니라 `revoked_at` 을 적는 것이다 — 언제 누가 철회했는지가 남아야
--   「그때는 위임 안에 있었다」를 나중에 확인할 수 있다(감사).
CREATE TABLE IF NOT EXISTS delegations (
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers,
    granted_at   timestamptz NOT NULL DEFAULT now(),
    -- NULL 이면 살아 있다. 값이 있으면 그 시각 **이후로** 자동 실행이 막힌다
    revoked_at   timestamptz,
    -- 누가 주고 누가 거뒀나 · 왜. 근거 없이 위임 상태를 바꾸지 않는다
    granted_by   text,
    revoked_by   text,
    note         text,
    PRIMARY KEY (tenant_id, customer_id)
);

-- ── (2) 자동 실행 기록 ──────────────────────────────────────────────────────
-- ★「무엇을」은 이미 있다 — `action_type`(작업 종류) + `arguments_json`(대상 id).
--   없던 넷을 더한다.
ALTER TABLE action_requests
    -- 얼마에. ★★NULL 은 0 이 아니라 **「확인되지 않았다」**다. 금액을 모르면
    --   지어내지 않고 비운다(CLAUDE.md §1 「지어내지 않는다」). 자동 실행 분기는
    --   금액을 모르면 아예 열리지 않으므로(`delegation.py` `amount_unknown`),
    --   여기 NULL 인 행은 인계처럼 **금액이 성립하지 않는** 작업이다.
    ADD COLUMN IF NOT EXISTS amount_cents    bigint,
    -- 그 금액을 **어디서 읽었나**(예: `bookings.amount_cents`). 금액만 있고 출처가
    -- 없으면 근거 없는 수다 — 둘은 같이 채우거나 같이 비운다.
    ADD COLUMN IF NOT EXISTS amount_source   text,
    -- 왜. 고객 문장·사건 사유를 그대로 싣는다(생성하지 않는다)
    ADD COLUMN IF NOT EXISTS reason          text,
    -- 되돌림 기한. NULL 은 **되돌릴 수 있는 종류가 아니다**(인계·조회 등)
    ADD COLUMN IF NOT EXISTS revert_deadline timestamptz,
    -- 위임 범위 판정의 근거 — 무엇을 무엇과 비교했나. DoD-18 이 이것을 센다.
    -- ★판정 결과만 남기면 「범위 안이었다」를 나중에 검증할 수 없다.
    ADD COLUMN IF NOT EXISTS delegation_json jsonb,
    -- ★★되돌리려면 **무엇으로** 돌아가야 하나(DoD-21). 실행 전 상태를 여기 적는다.
    --   이것이 없으면 되돌림이 상태를 **지어내야** 한다 — 취소 전 예약이 `confirmed` 였는지
    --   `requested` 였는지 `changed` 였는지 알 길이 없는데 하나를 골라 쓰게 된다
    --   (CLAUDE.md §1 「지어내지 않는다」). 비어 있으면 되돌리지 않고 사람에게 넘긴다.
    ADD COLUMN IF NOT EXISTS prior_state_json jsonb;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'action_requests_amount_source_chk') THEN
        -- ★금액과 출처는 **같이** 채우거나 같이 비운다. 출처 없는 금액이 들어오면
        --   그 수를 근거로 쓸 수 없는데 표에는 보인다 — DB 가 막는다.
        ALTER TABLE action_requests
            ADD CONSTRAINT action_requests_amount_source_chk
            CHECK ((amount_cents IS NULL) = (amount_source IS NULL));
    END IF;
END $$;

-- 되돌림 기한이 지난 자동 실행을 찾는 자리(되돌림 시도·보고서)
CREATE INDEX IF NOT EXISTS action_requests_revert_deadline_idx
    ON action_requests (tenant_id, revert_deadline)
    WHERE revert_deadline IS NOT NULL;
