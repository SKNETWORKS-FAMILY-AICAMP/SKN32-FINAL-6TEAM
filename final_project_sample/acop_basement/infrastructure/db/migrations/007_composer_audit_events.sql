-- 중앙 감사 저장소 — 여러 대상의 Composer 이벤트를 한 곳에 둔다.
--
-- ★payload 는 감사 이벤트 전문을 계약 shape 그대로 보존한다. 조회용 필드만
--   별도 컬럼에 중복해 두며 payload 를 재구성하거나 바꾸지 않는다.
--
-- ★append-only 다. 이 테이블을 UPDATE 또는 DELETE 하는 제품 코드는 없다.
--
-- ★재실행 안전하다.

CREATE TABLE IF NOT EXISTS composer_audit_events (
    event_id         BIGSERIAL   PRIMARY KEY,
    deployment_id    TEXT        NOT NULL,
    event            TEXT        NOT NULL,
    actor            TEXT        NOT NULL,
    payload          JSONB       NOT NULL,
    idempotency_key  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS composer_audit_events_deployment_created_at_idx
    ON composer_audit_events (deployment_id, created_at DESC);

-- 고유 인덱스가 아니다. 같은 key 의 재요청도 감사 기록은 모두 남긴다.
CREATE INDEX IF NOT EXISTS composer_audit_events_deployment_idempotency_key_idx
    ON composer_audit_events (deployment_id, idempotency_key);
