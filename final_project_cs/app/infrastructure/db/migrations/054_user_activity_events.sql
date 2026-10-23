-- 054 — 사용자 활동 기록(운영 · 개선용). `[2026-10-06 사용자 지시]` 「사용자가 활동한 모든 데이터는 운영을 위해 기록해야 해」
--
-- ★이 표는 **사용자가 무엇을 골랐나 · 눌렀나**를 한 줄씩 쌓는다(append-only — 고치지 않는다). 처음 쓰는 곳: 재난 뒤 다시 시작할 때의 선택
--   (`safety_recovery_choice`). 값을 모를 때 기본값을 정하려면 **실제 선택이 쌓여야** 한다(조사 근거가 다른 나라 · 집계뿐이다).
-- ★자유 문장은 여기에 넣지 않는다 — 채팅은 `trip_chat_turns`(가린 뒤 저장)가 정본이다. 여기에는 선택 값 · 식별자 · 때만 둔다.
-- ★여행을 지우면 같이 지운다(`trip_delete._PURGE`) — 채팅 기록과 같은 기본값이다. 지운 뒤에도 비식별로 남길지는 사용자 결정 대기.
-- ★다시 돌려도 안전하다(IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS user_activity_events (
    event_id     bigserial   PRIMARY KEY,
    tenant_id    text        NOT NULL,
    trip_id      uuid,
    customer_id  uuid,
    kind         text        NOT NULL,
    payload_json jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS user_activity_events_trip_idx ON user_activity_events (tenant_id, trip_id, created_at);
CREATE INDEX IF NOT EXISTS user_activity_events_kind_idx ON user_activity_events (tenant_id, kind, created_at);
