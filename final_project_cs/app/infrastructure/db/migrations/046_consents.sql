-- 046 — 약관 동의 기록. `[2026-10-05 사용자 지시 — ui 세션 요청서 「동의 기록 · 위치 수집」]`
--
-- ★왜. 「누가 어떤 약관 버전의 어떤 항목에 언제 동의(또는 철회)했나」는 분쟁 때 우리가 가진 증빙이다. 그래서 **추가만 하는** 사건 표(`consent_events`)로 남기고
--   지우지도 고치지도 않는다 — 철회도 새 줄이다. 「지금 동의 상태」는 가장 최근 줄(`consent_current` 뷰)이다.
-- ★사용자(`user_id`)에는 **외래키를 걸지 않는다** — 게스트가 정리돼 사용자 행이 지워져도 증빙은 보관 기간(`consent.evidence_retention_days`) 동안 남는다.
--   주소는 원문이 아니라 서버 비밀로 만든 해시(`ip_hash`)만 둔다(증빙은 되고 주소 자체는 안 남긴다).
-- ★추가만 하는 것을 **DB 가 지킨다** — UPDATE 는 늘 거절, DELETE 는 보관 기간 정리 작업이 `SET LOCAL app.consent_purge = 'on'` 을 켠 트랜잭션에서만 된다.

CREATE TABLE IF NOT EXISTS consent_events (
    event_id      bigserial PRIMARY KEY,
    tenant_id     text NOT NULL,
    user_id       uuid NOT NULL,
    session_kind  text NOT NULL CHECK (session_kind IN ('guest', 'member', 'key')),
    code          text NOT NULL,
    agreed        boolean NOT NULL,
    terms_version text NOT NULL,
    text_sha256   text NOT NULL,               -- 동의할 때 화면에 보여 준 약관 전문의 sha256(웹이 보낸 값 — 정본 텍스트는 저장소의 그 버전 파일)
    at            timestamptz NOT NULL DEFAULT now(),
    ip_hash       text,
    user_agent    text
);

CREATE INDEX IF NOT EXISTS idx_consent_events_user ON consent_events (tenant_id, user_id, code, at DESC, event_id DESC);
CREATE INDEX IF NOT EXISTS idx_consent_events_at ON consent_events (at);

CREATE OR REPLACE VIEW consent_current AS
    SELECT DISTINCT ON (tenant_id, user_id, code)
           tenant_id, user_id, code, agreed, terms_version, text_sha256, at
      FROM consent_events
     ORDER BY tenant_id, user_id, code, at DESC, event_id DESC;

CREATE OR REPLACE FUNCTION consent_events_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_setting('app.consent_purge', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'consent_events 는 추가만 한다 (% 불가)', TG_OP;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS consent_events_no_change ON consent_events;
CREATE TRIGGER consent_events_no_change BEFORE UPDATE OR DELETE ON consent_events
    FOR EACH ROW EXECUTE FUNCTION consent_events_append_only();
