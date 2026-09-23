-- 선언 이력 — 적용된 revision 을 순서대로 남겨 되돌릴 수 있게 한다 (D-011, 2026-09-06).
--
-- ★왜: project_configs 는 대상당 현재 행 하나뿐이라 되돌릴 수가 없었고,
--   그 빈자리를 "아무 설정이나 통째로 던져 넣는" /composer/apply 가 메우고
--   있었다. 이력이 있으면 되돌리기는 "이력에서 골라 새 revision 으로 다시
--   적용" 이 되고, 통째 교체는 관리자 전용(설치·복원)으로 내려간다.
--
-- ★revision 은 내용 해시라 같은 내용으로 되돌리면 같은 값이 다시 나온다.
--   그래서 (deployment_id, revision) 은 고유 제약이 아니다. 순서는 revision_id.
--
-- ★append-only 다. 이 테이블을 UPDATE 또는 DELETE 하는 제품 코드는 없다.
--   되돌린 것도 앞으로 한 줄 더 쌓인다 — 이력을 되감지 않는다.
--
-- ★재실행 안전하다.

CREATE TABLE IF NOT EXISTS project_config_revisions (
    revision_id        BIGSERIAL   PRIMARY KEY,
    deployment_id      TEXT        NOT NULL,
    revision           TEXT        NOT NULL,
    previous_revision  TEXT,
    declaration        JSONB       NOT NULL,
    actor              TEXT        NOT NULL,
    reason             TEXT        NOT NULL,
    -- apply · change · toggle · restore · baseline(첫 기록 직전 상태)
    event              TEXT        NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_config_revisions_deployment_order_idx
    ON project_config_revisions (deployment_id, revision_id DESC);

CREATE INDEX IF NOT EXISTS project_config_revisions_deployment_revision_idx
    ON project_config_revisions (deployment_id, revision);
