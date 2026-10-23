-- 036 — 관광공사 장소 목록의 운영시간을 **새벽에 읽어 두는** 표. `[2026-09-29 사용자 지시]`
--
-- ★왜. 활동 「다른 데로 바꿔」가 후보마다 관광공사 운영정보(detailIntro2)를 **요청 자리에서** 불렀다 — 요청마다 최대 10건,
--   몰림 30건 뒤로는 89초에 1건이라 연달아 요청하면 한도에 걸렸고, 모델로 읽는 곳은 몇 초씩 걸렸다. 사용자 설계는
--   「장소 갱신은 새벽 3시에 한 번, 요청은 DB 만 본다」다.
-- ★하는 일: 새벽 작업(`scripts.run_sweepers --only catalog_hours`)이 목록(`place_catalog`)의 활동을 읽어 여기 적는다.
--   **처음 보는 곳 · 목록의 수정 시각(`source_modified_at`)이 읽을 때와 달라진 곳**만 다시 읽는다(바뀐 것만).
--   요청 경로(`catalog_pool`)는 이 표만 읽는다.
-- ★적는 것은 사실 정보다 — 운영시간을 옮긴 값 · 원문(이용시간 · 쉬는 날) · 문의 전화. 사진 · 소개글은 적지 않는다
--   (관광공사 값 DB 저장은 허용 — 2026-09-28 사용자 결정, 루트 CLAUDE.md 「외부 공공데이터 저장」).
-- ★다시 돌려도 안전하다.

CREATE TABLE IF NOT EXISTS catalog_hours (
    tenant_id           text        NOT NULL,
    source              text        NOT NULL,
    content_id          text        NOT NULL,
    content_type_id     text        NULL,
    hours_week          jsonb       NULL,       -- 요일별 운영시간(`place_hours` 모양) — 못 옮겼으면 NULL
    hours_read          jsonb       NOT NULL,   -- 읽은 방법 · 인용 · 조건 · 시각 · 못 읽은 이유
    hours_origin        jsonb       NULL,       -- 관광공사 원문 {usetime, restdate}
    phone               text        NULL,
    source_modified_at  text        NULL,       -- 읽을 때의 목록 수정 시각 — 목록 값과 다르면 다시 읽는다
    read_at             timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, source, content_id)
);
CREATE INDEX IF NOT EXISTS catalog_hours_read_idx ON catalog_hours (tenant_id, read_at DESC);
