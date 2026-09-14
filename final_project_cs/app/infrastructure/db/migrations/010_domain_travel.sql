-- 010 — 도메인 테이블 (여행 CS, v10 §5)
--
-- ★basement 가 아니다. 001_schema.sql(core)은 손대지 않는다.
--   002_domain_commerce.sql 도 **지우지 않는다** — 쇼핑몰 시절 기록이고,
--   `app/modules/customer_ops/` 가 아직 그 테이블을 읽는다.
--
-- 커머스 → 여행 대응:
--   orders      → bookings          (예약 한 건. 금액·시각·인원의 출처)
--   products    → places            (장소. 좌표·운영시간·조건)
--   shipments   → supplier_bookings (공급자 원장. **우리 기록과 대조할 상대**)
--
-- ★`supplier_bookings` 가 따로 있는 이유. Booking Handoff 의 `booking.verify`
--   는 "우리가 아는 것" 과 "공급자가 아는 것" 을 **대조**한다. 한 테이블에
--   두면 대조할 상대가 사라져 그 capability 자체가 무의미해진다.

CREATE TABLE IF NOT EXISTS places (
    place_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         text NOT NULL,
    name              text NOT NULL,
    kind              text NOT NULL,           -- activity / dining / lodging / flight
    latitude          double precision,
    longitude         double precision,
    -- ★NULL 은 「모름」이다. Team 은 모르면 기상을 **보지 않는다** —
    --   실내 활동에 기상 판정을 걸면 틀린 이유로 판정이 흔들리기 때문이다.
    --   모름과 실내를 같게 다루는 것은 의도한 선택이고 Team 주석에 적혀 있다.
    weather_sensitive boolean,
    -- ★영업 정보를 **언제 확인했는지**. NULL 이면 Team 이 "확인했다" 고
    --   말하지 않는다(v10 §4-D). 조회 시각을 현장 확인 시각처럼 쓰지 않는다.
    hours_confirmed_at timestamptz,
    open_at_slot      boolean,                 -- 그 일정 시각에 여는가. NULL = 모름
    dietary           text[] NOT NULL DEFAULT '{}',   -- 확인된 「있음」
    dietary_absent    text[] NOT NULL DEFAULT '{}',   -- 확인된 「없음」
    -- ★둘 다에 없는 조건은 **모름**이다. 빈 배열을 「없음」으로 읽으면
    --   결함이 자리만 옮긴다.
    UNIQUE (tenant_id, name, kind)
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    customer_id   uuid NOT NULL REFERENCES customers,
    place_id      uuid REFERENCES places,
    booking_no    text NOT NULL,
    kind          text NOT NULL,               -- activity / dining / mobility / lodging / flight
    status        text NOT NULL,               -- requested / confirmed / changed / cancelled
    starts_at     timestamptz NOT NULL,
    party_size    int,
    capacity      int,
    amount_cents  int,
    -- ★잠긴 예약(Lodging/Flight)은 조정 대상이 아니다. 그 사실을 데이터가 든다.
    locked        boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, booking_no)
);

CREATE INDEX IF NOT EXISTS bookings_tenant_customer_idx
    ON bookings (tenant_id, customer_id, starts_at DESC);

CREATE TABLE IF NOT EXISTS supplier_bookings (
    supplier_booking_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    booking_id    uuid NOT NULL REFERENCES bookings,
    supplier      text NOT NULL,
    supplier_ref  text NOT NULL,
    -- ★우리 `bookings.status` 와 **일부러 따로 둔다.** 어긋나는 것이 정상이고,
    --   어긋남을 찾는 것이 `booking.verify` 의 일이다.
    status        text NOT NULL,
    confirmed_at  timestamptz,
    UNIQUE (tenant_id, supplier, supplier_ref)
);
