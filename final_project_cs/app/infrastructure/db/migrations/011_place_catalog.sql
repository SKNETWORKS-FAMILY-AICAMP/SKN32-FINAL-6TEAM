-- 011 — 장소 카탈로그와 동기화 상태 (여행, 2026-09-10)
--
-- ★왜 캐시를 두는가. TourAPI 장소 기본정보는 **거의 안 바뀐다** —
--   2026-09-10 실측으로 서울 전체에서 가장 최근 수정이 2025-11-21 이었다
--   (10개월 전). 사용자 계획서를 순회하며 매번 API 를 부르면 콜 수가
--   **사용자 수에 비례**해 늘고 하루 한도를 바로 태운다.
--   지역 단위로 한 번 받아 여기 두고, 계획서는 이 표를 읽는다.
--
-- ★`places` 와 다른 표인 이유. `places` 는 **우리 예약이 가리키는 장소**이고
--   여기는 **공급자가 아는 장소 전부**다. 둘을 한 표에 두면 「우리가 만든
--   행」과 「받아 온 행」이 섞여, 다시 받을 때 무엇을 지워도 되는지 모른다.

CREATE TABLE IF NOT EXISTS place_catalog (
    catalog_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    source        text NOT NULL,          -- tour_api 등. 출처를 섞지 않는다
    content_id    text NOT NULL,          -- 공급자의 식별자
    content_type_id text,                 -- 12 관광지 / 39 음식점 …
    area_code     text,
    title         text NOT NULL,
    address       text,
    latitude      double precision,
    longitude     double precision,
    -- ★공급자가 말한 수정 시각. **우리가 받은 시각이 아니다.**
    --   델타 동기화의 기준이 이 값이라 둘을 섞으면 안 된다.
    source_modified_at text,
    -- ★우리가 받은 시각. v10 §4-D 「확인 시각·출처를 같이 저장한다」.
    fetched_at    timestamptz NOT NULL DEFAULT now(),
    raw_json      jsonb,
    UNIQUE (tenant_id, source, content_id)
);

CREATE INDEX IF NOT EXISTS place_catalog_lookup_idx
    ON place_catalog (tenant_id, source, title);

-- ★동기화가 어디까지 갔는지. **재개 가능해야 한다** — 속도 제한이 걸려 있어서
--   서울 2,063건을 한 번에 못 받는다(하루 한도를 하루에 걸쳐 쓰므로).
--   중간에 끊겨도 다음 실행이 이어받는다.
CREATE TABLE IF NOT EXISTS source_sync_state (
    sync_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    source        text NOT NULL,
    scope         text NOT NULL,          -- 지역코드 등. 무엇을 받는 중인지
    -- 부트스트랩(전체 받기) 진행 상태
    bootstrap_done boolean NOT NULL DEFAULT false,
    next_page     int NOT NULL DEFAULT 1,
    total_expected int,
    rows_seen     int NOT NULL DEFAULT 0,
    -- 델타(변경분만) 진행 상태
    last_delta_at timestamptz,
    high_water    text,                   -- 지금까지 본 가장 큰 source_modified_at
    -- ★★델타를 **믿을 수 있는가.** 0건이 「안 바뀜」인지 「델타가 고장」인지
    --   우리가 구분 못 하면 그건 조용한 폴백이다(RULE.md §3.2).
    --   전체 재수집과 대조해서 어긋나면 false 로 내리고 그 사실을 남긴다.
    delta_trusted boolean NOT NULL DEFAULT false,
    delta_note    text,
    last_error    text,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source, scope)
);
