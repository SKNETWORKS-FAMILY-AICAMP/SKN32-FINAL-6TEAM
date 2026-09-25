-- 026 — 새벽 3시 식당 영업 확인 (D-020 · 2026-09-25)
--
-- ★★왜. 식당 당일 휴무는 3분 감시가 못 본다(무료 소스에 없다). 팀 결정(2026-09-24): **새벽 3시에만**
--   구글 장소로 그날 식사 일정이 그 시각에 여는지 확인하고, 문제가 있으면 하루 시작 알림 전에 고친다.
--   첫 심야버스(03:30) 기준이라 3시다. 그 뒤로는 식당을 따로 부르지 않는다 — 당일 문제는 고객 신고로 받는다.
--
-- ★★구글 약관 — `place_id` 만 **무기한 저장**이 허락된다. 이름·주소·**영업시간 원문**은 미리 받기·저장 금지
--   (`wiki/research/place-api-quota-and-terms.md`). 그래서 여기에는
--     ① 우리 장소 ↔ 구글 `place_id` 연결
--     ② 「그날 그 시각에 여는가」 **판정**과 확인 시각
--   만 남긴다. 영업시간 원문은 어디에도 쓰지 않는다.
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS place_provider_ids (
    tenant_id         text NOT NULL,
    place_id          uuid NOT NULL,
    provider          text NOT NULL CHECK (provider IN ('google_places')),
    provider_place_id text NOT NULL,
    -- 어떻게 맞췄나 — 이름 검색 결과가 우리 좌표에서 몇 m 떨어졌나. 먼 것을 같은 곳이라 하지 않는다
    match_distance_m  double precision NOT NULL CHECK (match_distance_m >= 0),
    matched_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, place_id, provider)
);

CREATE TABLE IF NOT EXISTS place_open_checks (
    check_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   text NOT NULL,
    trip_id     uuid NOT NULL,
    item_id     uuid NOT NULL,
    day         date NOT NULL,
    place_id    uuid NOT NULL,
    -- open 계획한 시각에 연다 · closed 그 시각에 안 연다(임시·영구 휴업 포함) · unknown 영업시간이 비어 있다 ·
    -- unmatched 구글 장소를 못 찾았다(이름·좌표가 안 맞는다)
    verdict     text NOT NULL CHECK (verdict IN ('open', 'closed', 'unknown', 'unmatched')),
    detail      text,          -- 판정 이유 한 줄(예: 「영구 휴업」). 영업시간 원문은 넣지 않는다
    source      text NOT NULL,
    checked_at  timestamptz NOT NULL DEFAULT now(),
    -- ★같은 항목·같은 날은 한 번만 — 새벽 작업이 1분마다 돌아도 구글을 한 번만 부른다
    UNIQUE (tenant_id, item_id, day)
);

CREATE INDEX IF NOT EXISTS place_open_checks_trip_idx ON place_open_checks (tenant_id, trip_id, day);
