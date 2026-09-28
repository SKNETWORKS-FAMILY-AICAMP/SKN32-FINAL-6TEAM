-- 013 — 장소의 공급자 신원 (2026-09-10)
--
-- ★★왜. 감시가 장소를 **이름으로** 찾고 있었는데, 「경복궁」이 서울 궁궐(12)과
--   울산 음식점(39) 둘로 나와 매번 ambiguous 로 「모름」이 됐다. 즉 그 장소는
--   **영영 감시되지 않는다.** 안전 가드가 감시 자체를 막고 있던 셈이다.
--
--   신원은 한 번만 해소하면 된다. 해소한 결과를 여기 저장하고, 그 다음부터는
--   **id 로** 본다 — 애매함도 없고 콜도 줄어든다.
ALTER TABLE places ADD COLUMN IF NOT EXISTS source_name text;
ALTER TABLE places ADD COLUMN IF NOT EXISTS source_content_id text;
ALTER TABLE places ADD COLUMN IF NOT EXISTS source_content_type_id text;
-- ★언제 해소했는지. 오래되면 다시 확인해야 한다(공급자가 id 를 바꿀 수 있다).
ALTER TABLE places ADD COLUMN IF NOT EXISTS source_resolved_at timestamptz;

CREATE INDEX IF NOT EXISTS places_source_identity_idx
    ON places (tenant_id, source_name, source_content_id);
