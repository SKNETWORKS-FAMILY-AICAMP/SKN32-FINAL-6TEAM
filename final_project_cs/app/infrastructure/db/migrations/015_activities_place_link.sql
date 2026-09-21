-- 015 — activities ↔ places 관계 (2026-09-20)
--
-- ★왜. `places`(013)는 이미 TourAPI 신원 해소 결과를 들고 있다
--   (`source_name`·`source_content_id`·`source_content_type_id`). 013 의 요지가
--   "해소는 한 번만 하면 된다, 그 다음부터는 id 로 본다"였다. `activities` 에
--   `tour_api_content_id` 로 또 다른 TourAPI 식별자 칸을 두면 같은 신원을 두
--   곳에서 따로 해소하게 되고, 둘이 어긋날 수 있다 — 013 이 막으려던 문제를
--   그대로 재현한다.
--
-- ★역할을 가른다. `activities` = 「언제·무엇을」(일정 사실).
--   `places` = 「어디·그곳이 지금 어떤 상태인가」(장소 사실, weather_sensitive·
--   hours_confirmed_at·open_at_slot 등 판정에 쓰는 값이 이미 여기 있다).
--   장소 사실을 다시 두지 않고 `place_id` 로 참조한다.
--
-- ★NULL 을 허용한다 — 무예약 활동은 아직 `places` 행으로 해소되지 않았을 수
--   있다(v11 §5-D). NULL = 「아직 해소 안 됨」이지 「장소가 없다」가 아니다.
--
-- `disaster_api_content_id` 는 이번 결정 범위 밖이다 — 건드리지 않는다.

ALTER TABLE activities ADD COLUMN IF NOT EXISTS place_id uuid REFERENCES places (place_id);

CREATE INDEX IF NOT EXISTS activities_place_idx ON activities (place_id);

-- 013 과 같은 이유로 중복 해소를 만들던 칸을 뺀다.
ALTER TABLE activities DROP COLUMN IF EXISTS tour_api_content_id;
