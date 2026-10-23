-- 048 — 텔레그램으로 알림 받기 + 알림 받는 곳(notice_channel). `[2026-10-05 사용자 지시 「텔레그램만 붙여 · 알림만」 — ui 세션 요청서]`
--
-- ★저장하는 것은 **대화 번호(chat.id)·연결 시각·상태**뿐이다 — 텔레그램 이름 · 사용자명 · 전화 · 사진은 받아도 저장하지 않는다.
--   대화 번호는 웹훅 주소와 같은 방식으로 **암호화**(`telegram_chat_enc`)해 두고, 같은 대화가 다른 사용자에게 묶이는 것을 막으려고 **서버 비밀 HMAC**(`telegram_chat_hash`)만 따로 둔다(유일 색인).
-- ★알림 받는 곳은 **한 번에 한 곳**(`notice_channel` = discord | telegram | NULL) — 마지막에 연결한 곳이 활성이다.
-- ★일회용 코드(`telegram_link_codes`)는 **해시만** 저장 · 10분 · 한 번만. 텔레그램이 같은 업데이트를 다시 보낼 때를 위해 처리한 `update_id` 를 이틀 동안 기억한다.
-- ★사용자 행이 지워지면(`customers`) 코드도 같이 지워진다(CASCADE) — 게스트 정리를 막지 않는다. 재실행 안전.

ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS telegram_chat_enc      text;
ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS telegram_chat_hash     text;
ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS telegram_status        text CHECK (telegram_status IN ('untested', 'ok', 'blocked'));
ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS telegram_connected_at  timestamptz;
ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS telegram_checked_at    timestamptz;
ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS telegram_tested_at     timestamptz;
ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS notice_channel         text CHECK (notice_channel IN ('discord', 'telegram'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_profiles_telegram_chat
    ON customer_profiles (tenant_id, telegram_chat_hash) WHERE telegram_chat_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS telegram_link_codes (
    code_hash   text PRIMARY KEY,
    tenant_id   text NOT NULL,
    customer_id uuid NOT NULL REFERENCES customers (customer_id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    used_at     timestamptz
);

CREATE INDEX IF NOT EXISTS idx_telegram_link_codes_created ON telegram_link_codes (created_at);

CREATE TABLE IF NOT EXISTS telegram_seen_updates (
    update_id bigint PRIMARY KEY,
    seen_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telegram_seen_updates_at ON telegram_seen_updates (seen_at);
