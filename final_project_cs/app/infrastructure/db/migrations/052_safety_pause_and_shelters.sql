-- 052 — 재난 시 **일정 정지**(`trip_safety_pauses`)와 **대피 장소**(`safety_shelters`). `[결정 2026-10-06 사용자]`
--   설계 `wiki/records/plans/2026-10-06_재난_일정정지와_피난안내_설계.md`.
--
-- ★일정 정지 = 일정 항목을 고치거나 지우지 않고, **그 여행(또는 그날)을 감시·안내 대상에서 멈추는 표시**다. 되돌리기는 이 줄을 닫는 것(`resumed_at`)이다 — 일정 판(`itinerary_versions`)은 안 바뀐다.
--   · `level = 'day'`  재난이 난 시각에 그 지역에 여행객이 있었다 → **그날(KST)** 남은 일정 정지. `until_at` = 그날 자정(KST) — 자정이 지나면 저절로 풀린다.
--   · `level = 'trip'` 전쟁 · 활화산 폭발 같은 **아주 심각한** 사건 → 여행 **전체** 정지. `until_at` 은 NULL — 사용자가 다시 시작할 때까지(또는 해제 알림 뒤 재개).
-- ★같은 사건으로 두 번 열지 않는다 — `(tenant, trip, level, event_key)` 가 유일하다. 사용자가 재개한 뒤에도 같은 사건(재난문자 조회 창에 남아 있다)이 다시 정지시키지 않는다.
-- ★`event_json` 은 정지의 **근거**(재난 종류 · 단계 · 시각 · 원문 일부)이고 `guidance_json` 은 알림에 실은 안내(대피 장소 포함) — 감사용이다. 지어낸 값이 없다.
-- ★여행을 지우면 같이 지워진다(`ON DELETE CASCADE`).
--
-- ★`safety_shelters` — 공공 대피 장소 자료. 두 종류: `civil_defense`(민방위 대피시설 — 전쟁 · 공습 · 폭발 · 테러 때) · `quake_outdoor`(지진 옥외 대피장소 — 지진 때).
--   적재는 `scripts/load_safety_shelters.py` 가 받아 둔 파일에서 한다(출처 · 불러온 시각을 행마다 남긴다). 표가 비어 있으면 안내는 **지어내지 않고** 「대피 장소 자료를 아직 못 불러왔어요 + 공식 안내」로 나간다.
--   좌표는 WGS84. 가까운 곳 찾기는 상자(위도·경도 범위) + 거리 계산이라 확장이 필요 없다.
-- ☆재실행해도 안전하다 — IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS trip_safety_pauses (
    pause_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    seq              bigserial   NOT NULL,
    tenant_id        text        NOT NULL,
    trip_id          uuid        NOT NULL REFERENCES trips (trip_id) ON DELETE CASCADE,
    level            text        NOT NULL CHECK (level IN ('day', 'trip')),
    -- 사건의 지문 — 같은 사건으로 다시 열지 않는다
    event_key        text        NOT NULL,
    event_json       jsonb       NOT NULL,
    -- level = 'day' 일 때 그날(KST)
    day              date,
    from_at          timestamptz NOT NULL,
    -- day: 그날 자정(KST) · trip: NULL(다시 시작할 때까지)
    until_at         timestamptz,
    guidance_json    jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    -- 공식 「해제」를 알린 시각(알림은 한 번만)
    release_notified_at timestamptz,
    resumed_at       timestamptz,
    -- web(사용자가 눌렀다) · release(해제 뒤 사용자가 다시 시작했다) · expired(그날이 끝났다 — 읽을 때 계산하므로 보통 비어 있다)
    resumed_via      text        CHECK (resumed_via IN ('web', 'agent', 'release', 'expired')),
    resumed_by       uuid,
    UNIQUE (tenant_id, trip_id, level, event_key)
);

CREATE INDEX IF NOT EXISTS idx_trip_safety_pauses_open ON trip_safety_pauses (tenant_id, trip_id) WHERE resumed_at IS NULL;

CREATE TABLE IF NOT EXISTS safety_shelters (
    shelter_id    bigserial        PRIMARY KEY,
    shelter_type  text             NOT NULL CHECK (shelter_type IN ('civil_defense', 'quake_outdoor')),
    name          text             NOT NULL,
    address       text,
    latitude      double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude     double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    -- 지하 시설인가(모르면 NULL)
    underground   boolean,
    capacity      integer,
    -- 자료 이름(예: 행정안전부 전국민방위대피시설표준데이터) · 그 자료 안의 번호 · 자료 기준일
    source        text             NOT NULL,
    source_ref    text,
    source_date   date,
    loaded_at     timestamptz      NOT NULL DEFAULT now()
);

-- 같은 자료를 다시 적재해도 줄이 늘지 않게(자료 안 번호가 있을 때) — 번호가 없는 자료는 이름 + 좌표로
CREATE UNIQUE INDEX IF NOT EXISTS uq_safety_shelters_ref ON safety_shelters (shelter_type, source, source_ref) WHERE source_ref IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_safety_shelters_place ON safety_shelters (shelter_type, source, name, latitude, longitude) WHERE source_ref IS NULL;
-- 가까운 곳 찾기(상자 검색)
CREATE INDEX IF NOT EXISTS idx_safety_shelters_box ON safety_shelters (shelter_type, latitude, longitude);
