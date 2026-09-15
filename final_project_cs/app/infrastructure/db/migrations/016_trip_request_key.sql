-- 016 — 여행 등록의 멱등 키 (v11 §6 승계 규칙 · §4-E)
--
-- ★같은 등록 요청을 두 번 받으면 여행이 둘 생기고, 감시 루프가 둘을 따로 지켜보며
--   통지도 두 번 나간다. 등록 요청의 `request_id` 로 서버가 키를 만들어 여기에 둔다.
-- ★부분 UNIQUE — 키 없이 만든 여행(재생 시험·시드)은 막지 않는다.
-- ☆번호 015 는 `pending/015_drop_commerce_domain.sql`(적용 보류) 몫이라 건너뛴다.

ALTER TABLE trips ADD COLUMN IF NOT EXISTS request_key text;
-- ★같은 키에 **다른 몸통**이 오면 조용히 옛 여행을 돌려주지 않고 409 로 알린다.
ALTER TABLE trips ADD COLUMN IF NOT EXISTS request_sha256 text;

CREATE UNIQUE INDEX IF NOT EXISTS trips_request_key_uq
    ON trips (tenant_id, request_key) WHERE request_key IS NOT NULL;
