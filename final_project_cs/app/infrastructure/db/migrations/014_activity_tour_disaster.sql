-- 014 — Activity 전용: activities · tour · disaster (제안 스키마 반영, 2026-09-20)
--
-- 근거: wiki/teams/Activity_모듈_스펙.md, wiki/teams/데이터베이스_저장소_설계_v2.md
-- 결정: wiki/teams/activity.md 「제안 테이블 — Activity 전용」 — 이 세 테이블은
--   Activity Team 전용이다. Dining·Mobility 는 쓰지 않는다(공유는 `places`가 한다).
--
-- ★`places`(010)를 대체하지 않는다. `places`는 예약이 가리키는 장소 하나를
--   Team 무관하게 저장하는 범용 테이블이고, 여기는 그 위에 **Activity 판정에만
--   쓰는 부가 정보**(TourAPI·재난문자API 원본 대조)를 얹는 자리다.
--   `activities.tour_api_content_id` 와 `places.source_content_id` 의 관계(같은
--   해소 결과를 가리키는지, FK로 묶을지)는 아직 정해지지 않았다 — 이 마이그레이션은
--   그 결정을 선점하지 않는다. `[미확보 2026-09-20]`
--
-- ★설계 원본에 없던 컬럼을 하나 추가했다 — `tenant_id`. 이 저장소의 도메인
--   테이블은 전부 tenant_id 로 격리된다(001_schema.sql, RULE.md §1 "조회는 항상
--   tenant_id + customer_id 로 좁힌다"). tenant_id 가 없는 도메인 테이블은
--   격리 테스트(tests/security)를 못 통과한다. FK는 걸지 않는다 — `places`·
--   `place_catalog`와 같은 패턴이다(정본 FK는 customers/bookings 쪽에만 건다).

CREATE TABLE IF NOT EXISTS tour (
    contentid       text PRIMARY KEY,       -- TourAPI 원본 식별자. 우리가 만들지 않는다
    contenttypeid   text NOT NULL,          -- 12 관광지 / 14 문화시설 / 28 레포츠 / 38 쇼핑 …
    title           text NOT NULL,
    addr1           text,
    mapx            text,                   -- GPS X좌표(WGS84 경도). TourAPI 응답 그대로 text
    mapy            text,                   -- GPS Y좌표(WGS84 위도). TourAPI 응답 그대로 text
    -- ★신분류체계 대분류·중분류·소분류. wiki/teams/activity.md 「신분류체계 — 지금
    --   근거」와 같은 축이다(같은 스프레드시트에서 나왔다).
    "lclsSystm1"    text,
    "lclsSystm2"    text,
    "lclsSystm3"    text,
    tenant_id       text NOT NULL,
    fetched_at      timestamptz NOT NULL DEFAULT now()   -- 우리가 받은 시각. v10 §4-D
);

CREATE INDEX IF NOT EXISTS tour_tenant_idx ON tour (tenant_id);

CREATE TABLE IF NOT EXISTS disaster (
    "SN"            text PRIMARY KEY,       -- 재난문자 일련번호. 원본 그대로
    "CRT_DT"        text NOT NULL,          -- 생성일시. ★원본 포맷 그대로 text 로 둔다
                                             --   (설계서 확정값) — timestamptz 변환은
                                             --   실제 응답 포맷 확인 후에 한다
    "MSG_CN"        text NOT NULL,          -- 메시지내용
    "RCPTN_RGN_NM"  text NOT NULL,          -- 수신지역
    -- ★값 목록(재해구분명 34종·긴급단계명 3종)은 wiki/teams/activity.md 에
    --   적어 뒀다. CHECK 제약으로 강제하지 않는다 — 공급자가 값을 늘리면
    --   깨지는 제약을 만들지 않는다(source_sync_state 의 delta_trusted 와 같은 태도).
    "DST_SE_NM"     text NOT NULL,          -- 재해구분명
    "EMRG_STEP_NM"  text NOT NULL,          -- 긴급단계명
    tenant_id       text NOT NULL,
    fetched_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS disaster_tenant_region_idx
    ON disaster (tenant_id, "RCPTN_RGN_NM", "CRT_DT" DESC);

CREATE TABLE IF NOT EXISTS activities (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                text NOT NULL,
    name                     text NOT NULL,
    lat                      numeric,
    lng                      numeric,
    activity_time            timestamptz NOT NULL,
    address                  text,
    -- ★NULL 이 「이 항목은 TourAPI/재난문자로 아직 해소되지 않았다」다.
    --   `places.source_content_id`(013)와 같은 이유로 NULL 을 허용한다.
    tour_api_content_id      text REFERENCES tour (contentid),
    disaster_api_content_id  text REFERENCES disaster ("SN")
);

CREATE INDEX IF NOT EXISTS activities_tenant_time_idx
    ON activities (tenant_id, activity_time);

-- ★D-1 배치·당일 개별 체크(wiki/teams/activity.md 「조회 시점·재검토 주기」)가
--   이 인덱스로 "지금부터 N시간 안의 활동"을 조회한다.
