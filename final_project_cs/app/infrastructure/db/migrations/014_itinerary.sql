-- 014 — 여행(trips) · 일정 버전 · 일정 항목 (v11 §7-B)
--
-- ★Case 는 여러 번 생기고 끝나지만 **Trip 은 여행 끝까지 산다**(§4-B). 그래서 따로 둔다.
-- ★일정은 **버전으로 쌓는다(append-only)**. 되돌림·감사 추적을 새로 만들지 않고 얻는다
--   (§7-B). 최신 버전 포인터는 `trips.latest_version` 이고, 바꿀 때는 **기준 버전
--   조건**으로만 올린다 — 낡은 쓰기를 거부하는 자리다(§6-C-7).
-- ★대체 항목은 원래 항목을 가리킨다(`replaces_item_id`). 안 그러면 지우고 새로 만들어
--   「바뀐 항목 수 0」을 만드는 편법이 통한다(§6-C-2).
--
-- 2026-09-14 확정 시나리오(대만인 친구 2명의 서울 하루) 구현으로 만들었다.

CREATE TABLE IF NOT EXISTS trips (
    trip_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      text NOT NULL,
    customer_id    uuid NOT NULL REFERENCES customers,
    title          text NOT NULL,
    -- 고객 언어. ★알림은 **보낼 때 이 언어로 생성**한다(결정 14). 목록을 미리 정하지 않는다.
    locale         text,
    party_size     int,
    latest_version int NOT NULL DEFAULT 0,
    status         text NOT NULL DEFAULT 'active',
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS itinerary_versions (
    trip_id     uuid NOT NULL REFERENCES trips ON DELETE CASCADE,
    version     int NOT NULL,
    tenant_id   text NOT NULL,
    reason      text NOT NULL,              -- created / auto_adjusted / customer_request …
    cause_json  jsonb NOT NULL DEFAULT '[]', -- 원인별 요약 — 통지에 그대로 들어간다(§6-C-1)
    case_id     uuid,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (trip_id, version)
);

CREATE TABLE IF NOT EXISTS itinerary_items (
    item_id          uuid NOT NULL,
    trip_id          uuid NOT NULL,
    version          int NOT NULL,
    tenant_id        text NOT NULL,
    seq              int NOT NULL,
    kind             text NOT NULL,          -- activity / dining / mobility / lodging
    title            text NOT NULL,
    place_id         uuid REFERENCES places,
    starts_at        timestamptz NOT NULL,
    ends_at          timestamptz,
    locked           boolean NOT NULL DEFAULT false,
    booking_id       uuid REFERENCES bookings,
    replaces_item_id uuid,
    detail           jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (trip_id, version, item_id),
    FOREIGN KEY (trip_id, version) REFERENCES itinerary_versions ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS itinerary_items_start_idx
    ON itinerary_items (tenant_id, starts_at);

-- 장소의 판정용 속성(구·건물·층·실내 여부·영업시간·브레이크타임·결제수단·가격…).
-- ★칸을 계속 늘리지 않고 한 칸에 둔다 — 공급자마다 주는 속성이 다르다.
ALTER TABLE places ADD COLUMN IF NOT EXISTS attributes jsonb NOT NULL DEFAULT '{}';

-- Trip 수준 조건(결제수단·식단 …). ★항목 수준 조건은 항목 detail 에 둔다(§7-B scope).
ALTER TABLE trips ADD COLUMN IF NOT EXISTS constraints jsonb NOT NULL DEFAULT '{}';
