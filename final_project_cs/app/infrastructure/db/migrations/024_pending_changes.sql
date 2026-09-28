-- 024 — 보류 제안: 바꾸지 않고 「어떻게 할까요」를 묻는 동안 안(1·2·3)을 들고 있는다 (D-020)
--
-- ★★왜. 지금까지 일정이 꼬이면 최고 안을 **바로 적용**했다(결정 15). 2026-09-24 회의에서 셋이 갈렸다 —
--   ① 설문 15번 「먼저 물어봐줘」(`ask_first`)인 여행은 바꾸지 않고 **선택을 기다린다**
--   ② 「변경 안 할 일정」(고객 고정 · 잠긴 예약)은 **15번 답과 상관없이** 바꾸지 않고 묻는다 — 돈이 걸렸는지는 따지지 않는다
--   ③ 「먼저 물어봐줘」인 여행의 안전 사건(지진 · 재난문자 · 기상 경보)은 **알림만** 명확하게 — 바꾸지 않는다
--   그 동안 안을 **어디엔가 들고 있어야** 고객이 고를 수 있다. 계산을 다시 하면 고객이 본 안과
--   다른 것이 들어간다 — 그래서 적용에 필요한 값을 그대로 적어 둔다(`alternate_record` 와 같은 모양).
--
-- ★무응답이면 그 일정이 **끝날 때까지** 기다렸다가 `expired` 로 닫는다 — **바꾸지 않는다.**
--   그 뒤로는 다음 일정으로 그대로 진행한다(알림은 일정 순서대로).
-- ★일행이 링크를 같이 쓴다 — **먼저 고른 쪽**이 이긴다. 한 건은 한 번만 닫힌다(`status` 전이는 open → 하나).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS pending_changes (
    proposal_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      text NOT NULL,
    trip_id        uuid NOT NULL REFERENCES trips ON DELETE CASCADE,
    -- 이 제안을 만든 **기준 버전의** 항목. 그 사이 일정이 바뀌면 고를 수 없다(stale)
    item_id        uuid NOT NULL,
    base_version   int NOT NULL,
    -- ask_first(설문 15번) · protected(변경 안 할 일정) · safety_alert(먼저 물어봐줘 + 안전 사건)
    reason         text NOT NULL,
    -- protected 일 때 무엇 때문에: customer_pinned(변경 안 할 일정) · locked(잠긴 예약)
    protected_by   text,
    safety         boolean NOT NULL DEFAULT false,
    cause_json     jsonb NOT NULL DEFAULT '[]',
    -- [{key, name, place_id, option, option_label, starts_at, ends_at, walk_min, rank}] — 1위가 앞
    options_json   jsonb NOT NULL DEFAULT '[]',
    status         text NOT NULL DEFAULT 'open',
    -- 그 일정이 끝나는 시각. 지나도 답이 없으면 expired(바꾸지 않음)
    expires_at     timestamptz,
    chosen_key     text,
    -- 누가 골랐나(웹 토큰이면 'plan_link', 에이전트면 API 주체) · 그때 쓴 새 버전
    chosen_by      text,
    chosen_version int,
    decided_at     timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    -- ★같은 버전의 같은 항목에는 제안이 하나 — 3분마다 도는 감시가 같은 것을 거듭 만들지 않게
    UNIQUE (tenant_id, trip_id, item_id, base_version)
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_status_check') THEN
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_status_check
            CHECK (status IN ('open', 'chosen', 'kept', 'expired', 'superseded'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pending_changes_reason_check') THEN
        ALTER TABLE pending_changes ADD CONSTRAINT pending_changes_reason_check
            CHECK (reason IN ('ask_first', 'protected', 'safety_alert'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS pending_changes_open_idx
    ON pending_changes (tenant_id, trip_id) WHERE status = 'open';
